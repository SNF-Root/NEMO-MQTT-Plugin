#!/usr/bin/env python3
"""
Redis-MQTT Bridge Service for NEMO Plugin
Unified service that bridges Redis events to MQTT broker with robust connection management.

Modes:
  - AUTO: Automatically starts Redis and Mosquitto for development/testing
  - EXTERNAL: Connects to existing Redis and MQTT broker for production
"""

import os
import sys
import time
import json
import logging
import signal
import threading
import subprocess
import fcntl
import tempfile
import ssl
import ipaddress
from typing import Optional, Dict, Any

# Django setup - only when running standalone
if __name__ == "__main__":
    # Add Django project to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')
    
    import django
    django.setup()

import redis
import paho.mqtt.client as mqtt

# Import Django models - Django is already set up by this point
try:
    from nemo_mqtt.models import MQTTConfiguration
    from nemo_mqtt.utils import get_mqtt_config
except ImportError:
    from NEMO.plugins.nemo_mqtt.models import MQTTConfiguration
    from NEMO.plugins.nemo_mqtt.utils import get_mqtt_config

# Import the ConnectionManager and Redis list key
try:
    from nemo_mqtt.connection_manager import ConnectionManager
    from nemo_mqtt.redis_publisher import EVENTS_LIST_KEY
except ImportError:
    from NEMO.plugins.nemo_mqtt.connection_manager import ConnectionManager
    from NEMO.plugins.nemo_mqtt.redis_publisher import EVENTS_LIST_KEY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RedisMQTTBridge:
    """
    Unified service that bridges Redis events to MQTT broker.
    
    This service can operate in two modes:
    1. AUTO mode: Starts and manages Redis + Mosquitto (development/testing)
    2. EXTERNAL mode: Connects to existing services (production)
    """
    
    def __init__(self, auto_start: bool = False):
        """
        Initialize the Redis-MQTT bridge.
        
        Args:
            auto_start: If True, automatically start Redis and Mosquitto (dev mode)
                       If False, connect to existing services (production mode)
        """
        self.auto_start = auto_start
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        self.config = None
        self.thread = None
        self.lock = threading.Lock()
        
        # Process lock to prevent multiple instances
        self.lock_file = None
        self._acquire_lock()
        
        # Process handles for auto-started services
        self.redis_process = None
        self.mosquitto_process = None
        
        # Connection details for debugging
        self.broker_host = None
        self.broker_port = None
        self.connection_count = 0
        self.last_connect_time = None
        self.last_disconnect_time = None
        
        # Connection managers for robust retry logic
        self.mqtt_connection_mgr = ConnectionManager(
            max_retries=None,  # Infinite retries
            base_delay=1,
            max_delay=60,
            failure_threshold=5,
            success_threshold=3,
            timeout=60
        )
        
        self.redis_connection_mgr = ConnectionManager(
            max_retries=None,
            base_delay=1,
            max_delay=30,
            failure_threshold=5,
            success_threshold=3,
            timeout=60
        )
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _acquire_lock(self):
        """Acquire lock file to prevent multiple instances - with automatic cleanup"""
        lock_dir = tempfile.gettempdir()
        lock_path = os.path.join(lock_dir, 'nemo_mqtt_bridge.lock')
        
        try:
            self.lock_file = open(lock_path, 'w')
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            os.fsync(self.lock_file.fileno())  # Force write to disk
            print(f"🔒 Acquired lock: {lock_path} (PID: {os.getpid()})")
        except IOError:
            # Lock file exists - check if process is still running
            print(f"⚠️  Lock file exists: {lock_path}")
            
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, 'r') as f:
                        pid_str = f.read().strip()
                    
                    # Handle empty or invalid PID
                    if not pid_str:
                        print(f"   Lock file is empty (race condition), cleaning up...")
                        time.sleep(0.5)  # Wait a moment for other process to write
                        # Try reading again
                        with open(lock_path, 'r') as f:
                            pid_str = f.read().strip()
                        
                        if not pid_str:
                            print(f"   Still empty, assuming stale lock")
                            os.remove(lock_path)
                            # Retry lock acquisition
                            self._acquire_lock()
                            return
                    
                    old_pid = int(pid_str)
                    
                    # Check if process is still running
                    try:
                        os.kill(old_pid, 0)  # Signal 0 just checks if process exists
                        print(f"❌ Another instance is already running (PID: {old_pid})")
                        print(f"   Killing stale instance and retrying...")
                        
                        # Kill the old process
                        try:
                            os.kill(old_pid, signal.SIGTERM)
                            time.sleep(1)
                            # Check if it's still running
                            try:
                                os.kill(old_pid, 0)
                                # Still running, force kill
                                os.kill(old_pid, signal.SIGKILL)
                                time.sleep(0.5)
                            except OSError:
                                pass  # Process is dead
                        except OSError:
                            pass  # Process already dead
                        
                    except OSError:
                        # Process doesn't exist - stale lock file
                        print(f"   Old process (PID: {old_pid}) is dead - cleaning up stale lock")
                    
                    # Remove stale lock file
                    os.remove(lock_path)
                    print(f"🧹 Cleaned up stale lock file")
                    
                    # Try again
                    self.lock_file = open(lock_path, 'w')
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.lock_file.write(str(os.getpid()))
                    self.lock_file.flush()
                    os.fsync(self.lock_file.fileno())
                    print(f"🔒 Acquired lock: {lock_path} (PID: {os.getpid()})")
                    
                except ValueError as e:
                    print(f"❌ Invalid PID in lock file: {e}")
                    print(f"   Removing corrupt lock file and retrying...")
                    os.remove(lock_path)
                    self._acquire_lock()
                    return
                except Exception as e:
                    print(f"❌ Failed to clean up lock file: {e}")
                    import traceback
                    traceback.print_exc()
                    sys.exit(1)
            else:
                print(f"❌ Failed to acquire lock for unknown reason")
                sys.exit(1)
    
    def _release_lock(self):
        """Release the lock file"""
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                lock_path = os.path.join(tempfile.gettempdir(), 'nemo_mqtt_bridge.lock')
                if os.path.exists(lock_path):
                    os.remove(lock_path)
                print(f"🔓 Released lock (PID: {os.getpid()})")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the Redis-MQTT bridge service"""
        try:
            mode = "AUTO" if self.auto_start else "EXTERNAL"
            print(f"🚀 Starting Redis-MQTT Bridge Service ({mode} mode)")
            print("=" * 50)
            
            # Get MQTT configuration from Django first (needed for port info)
            print("🔍 Loading MQTT configuration from Django...")
            self.config = get_mqtt_config()
            if not self.config or not self.config.enabled:
                print("❌ No enabled MQTT configuration found")
                logger.error("No enabled MQTT configuration found")
                return False
            
            print(f"✅ MQTT configuration loaded: {self.config.name}")
            print(f"   Broker: {self.config.broker_host}:{self.config.broker_port}")
            print(f"   TLS: {'Yes' if self.config.use_tls else 'No'}")
            print(f"   Auth: {'Yes' if self.config.username else 'No'}")
            
            # Auto-start Redis and Mosquitto if in AUTO mode (after config loaded)
            if self.auto_start:
                print("🔧 AUTO mode: Starting Redis and Mosquitto...")
                self._cleanup_existing_services()
                self._start_redis()
                self._start_mosquitto()  # Now has access to self.config.broker_port
            
            # Initialize Redis client with connection manager
            print("🔍 Connecting to Redis with robust retry logic...")
            self._initialize_redis_robust()
            
            # Initialize MQTT client with connection manager
            print("🔍 Connecting to MQTT broker with robust retry logic...")
            self._initialize_mqtt_robust()
            
            # Start the bridge service
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            print("✅ Redis-MQTT Bridge started successfully")
            print("📋 Consuming from Redis → Publishing to MQTT")
            print("=" * 50)
            logger.info(f"Redis-MQTT Bridge started successfully in {mode} mode")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Redis-MQTT Bridge: {e}")
            logger.error(f"Failed to start Redis-MQTT Bridge: {e}")
            return False
    
    def _cleanup_existing_services(self):
        """Clean up any existing Redis, MQTT broker, and MQTT service instances"""
        try:
            logger.info("🧹 Cleaning up existing services...")
            
            # Only kill Redis if we started it (not system Redis)
            if self.redis_process:
                logger.info("   Stopping Redis instance started by plugin...")
                try:
                    self.redis_process.terminate()
                    self.redis_process.wait(timeout=5)
                except:
                    self.redis_process.kill()
                self.redis_process = None
            
            # Kill all Mosquitto processes
            logger.info("   Stopping existing MQTT broker instances...")
            subprocess.run(['pkill', '-f', 'mosquitto'], capture_output=True)
            subprocess.run(['pkill', '-9', 'mosquitto'], capture_output=True)
            
            # Kill all old MQTT service processes
            logger.info("   Stopping existing MQTT service instances...")
            subprocess.run(['pkill', '-f', 'external_mqtt_service'], capture_output=True)
            subprocess.run(['pkill', '-f', 'simple_standalone_mqtt'], capture_output=True)
            subprocess.run(['pkill', '-f', 'redis_mqtt_bridge'], capture_output=True)
            
            # Wait for processes to die
            time.sleep(2)
            
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning: {e}")
    
    def _start_redis(self):
        """Start Redis server or connect to existing one"""
        try:
            # First, check if Redis is already running
            logger.info("🔍 Checking for existing Redis server...")
            try:
                test_client = redis.Redis(host='localhost', port=6379, db=0)
                test_client.ping()
                logger.info("✅ Redis server already running, connecting to existing instance")
                return
            except redis.ConnectionError:
                logger.info("🔍 No existing Redis server found, starting new one...")
            
            # Start Redis server
            self.redis_process = subprocess.Popen(
                ['redis-server', '--daemonize', 'yes'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for Redis to start
            for i in range(10):
                try:
                    test_client = redis.Redis(host='localhost', port=6379, db=0)
                    test_client.ping()
                    logger.info("✅ Redis server started successfully")
                    return
                except redis.ConnectionError:
                    time.sleep(1)
            
            raise Exception("Redis failed to start within 10 seconds")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Redis: {e}")
            raise
    
    def _start_mosquitto(self):
        """
        Start Mosquitto MQTT broker.
        
        Note: This is intended for development/testing only.
        In production, use an external MQTT broker configured via the NEMO admin interface.
        """
        try:
            # Check if Mosquitto is already running on the configured port
            broker_port = self.config.broker_port if self.config else 1883
            
            print(f"🔍 Checking if Mosquitto is already running on port {broker_port}...")
            try:
                test_client = mqtt.Client(client_id="mosquitto_check")
                test_client.connect('localhost', broker_port, 5)
                test_client.disconnect()
                print(f"✅ Mosquitto is already running on port {broker_port}")
                logger.info(f"Mosquitto is already running on port {broker_port}")
                return
            except Exception:
                print(f"   Mosquitto not running on port {broker_port}, starting it...")
            
            logger.info("🔍 Starting MQTT broker...")
            logger.info("   ⚠️  Using auto-started Mosquitto for development")
            logger.info("   ⚠️  For production, use external MQTT broker configured in NEMO admin")
            
            # Check if TLS is enabled and create configuration
            if self.config and self.config.use_tls:
                print(f"🔐 TLS enabled - creating Mosquitto TLS configuration...")
                mosquitto_config = self._create_mosquitto_tls_config()
                print(f"🔐 Mosquitto config file: {mosquitto_config}")
                
                # Start Mosquitto with TLS configuration
                print(f"🚀 Starting Mosquitto with TLS on port {broker_port}...")
                self.mosquitto_process = subprocess.Popen(
                    ['mosquitto', '-c', mosquitto_config],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # Start Mosquitto broker on configured port without TLS
                print(f"🚀 Starting Mosquitto on port {broker_port}...")
                self.mosquitto_process = subprocess.Popen(
                    ['mosquitto', '-p', str(broker_port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Wait for Mosquitto to ACTUALLY be ready (more robust check)
            print(f"⏳ Waiting for Mosquitto to be fully ready...")
            max_retries = 20  # 20 seconds max
            retry_delay = 1.0
            
            for i in range(max_retries):
                try:
                    test_client = mqtt.Client(client_id=f"mosquitto_startup_check_{i}")
                    test_client.connect('localhost', broker_port, 5)
                    test_client.loop_start()
                    time.sleep(0.5)  # Let it actually connect
                    
                    if test_client.is_connected():
                        test_client.loop_stop()
                        test_client.disconnect()
                        print(f"✅ MQTT broker started successfully on port {broker_port} (took {i+1}s)")
                        logger.info(f"✅ MQTT broker started successfully on port {broker_port}")
                        return
                    
                    test_client.loop_stop()
                    test_client.disconnect()
                except Exception as e:
                    if i < max_retries - 1:
                        print(f"   Attempt {i+1}/{max_retries}: Not ready yet, waiting...")
                        time.sleep(retry_delay)
                    else:
                        # Last attempt failed
                        raise Exception(f"Mosquitto failed to start within {max_retries} seconds: {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MQTT broker: {e}")
            print(f"❌ Failed to start MQTT broker: {e}")
            raise
    
    def _create_mosquitto_tls_config(self):
        """
        Create a Mosquitto configuration file with TLS support.
        
        Returns:
            Path to the created configuration file
        """
        try:
            # Create a temporary configuration file
            config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
            
            # Write basic Mosquitto configuration
            config_file.write("# Mosquitto TLS Configuration for NEMO MQTT Plugin\n")
            config_file.write("# This is a temporary configuration for development/testing\n\n")
            
            # Port configuration
            broker_port = self.config.broker_port if self.config else 8883
            config_file.write(f"port {broker_port}\n")
            config_file.write(f"listener {broker_port}\n")
            config_file.write(f"protocol mqtt\n")
            
            # For development broker, always generate self-signed certificates
            # The client will use your CA certificate for verification
            print("   🔐 Generating self-signed certificates for development broker...")
            if self.config.ca_cert_content:
                print("   ℹ️  Your CA certificate will be used for client verification")
            else:
                print("   ℹ️  No CA certificate provided - using generated CA for both broker and client")
            
            cert_files = self._generate_self_signed_certificates()
            config_file.write(f"cafile {cert_files['ca_cert']}\n")
            config_file.write(f"certfile {cert_files['server_cert']}\n")
            config_file.write(f"keyfile {cert_files['server_key']}\n")
            
            # Allow anonymous connections for development
            config_file.write(f"allow_anonymous true\n")
            
            # Logging
            config_file.write(f"log_dest stdout\n")
            config_file.write(f"log_type all\n")
            
            # Close the file
            config_file.close()
            
            print(f"🔐 Created Mosquitto TLS config: {config_file.name}")
            print(f"🔐   Port: {broker_port}")
            print(f"🔐   CA File: {cert_files['ca_cert']}")
            print(f"🔐   Cert File: {cert_files['server_cert']}")
            print(f"🔐   Key File: {cert_files['server_key']}")
            print(f"🔐   Anonymous: true (development mode)")
            
            return config_file.name
            
        except Exception as e:
            logger.error(f"❌ Failed to create Mosquitto TLS config: {e}")
            print(f"❌ Failed to create Mosquitto TLS config: {e}")
            raise
    
    def _generate_self_signed_certificates(self):
        """
        Generate self-signed certificates for development TLS.
        
        Returns:
            Dictionary with paths to generated certificate files
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from datetime import datetime, timedelta
            
            print("🔐 Generating self-signed certificates for development...")
            
            # Create temporary directory for certificates
            cert_dir = tempfile.mkdtemp(prefix='nemo_mqtt_certs_')
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Create CA certificate
            ca_subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "NEMO"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEMO MQTT Plugin"),
                x509.NameAttribute(NameOID.COMMON_NAME, "NEMO MQTT CA"),
            ])
            
            ca_cert = x509.CertificateBuilder().subject_name(
                ca_subject
            ).issuer_name(
                ca_subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            ).sign(private_key, hashes.SHA256())
            
            # Create server certificate
            server_subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "NEMO"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEMO MQTT Plugin"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ])
            
            server_cert = x509.CertificateBuilder().subject_name(
                server_subject
            ).issuer_name(
                ca_subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            ).sign(private_key, hashes.SHA256())
            
            # Write certificates to files
            ca_cert_path = os.path.join(cert_dir, 'ca.crt')
            server_cert_path = os.path.join(cert_dir, 'server.crt')
            server_key_path = os.path.join(cert_dir, 'server.key')
            
            with open(ca_cert_path, 'wb') as f:
                f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
            
            with open(server_cert_path, 'wb') as f:
                f.write(server_cert.public_bytes(serialization.Encoding.PEM))
            
            with open(server_key_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            print(f"🔐 Generated certificates in: {cert_dir}")
            print(f"🔐   CA Certificate: {ca_cert_path}")
            print(f"🔐   Server Certificate: {server_cert_path}")
            print(f"🔐   Server Key: {server_key_path}")
            
            return {
                'ca_cert': ca_cert_path,
                'server_cert': server_cert_path,
                'server_key': server_key_path,
                'cert_dir': cert_dir
            }
            
        except ImportError:
            print("⚠️  cryptography library not available, using simple certificate generation...")
            return self._generate_simple_certificates()
        except Exception as e:
            print(f"⚠️  Failed to generate certificates with cryptography: {e}")
            return self._generate_simple_certificates()
    
    def _generate_simple_certificates(self):
        """
        Generate simple self-signed certificates using OpenSSL command line.
        
        Returns:
            Dictionary with paths to generated certificate files
        """
        try:
            import subprocess
            
            print("🔐 Generating simple self-signed certificates using OpenSSL...")
            
            # Create temporary directory for certificates
            cert_dir = tempfile.mkdtemp(prefix='nemo_mqtt_certs_')
            
            ca_cert_path = os.path.join(cert_dir, 'ca.crt')
            server_cert_path = os.path.join(cert_dir, 'server.crt')
            server_key_path = os.path.join(cert_dir, 'server.key')
            
            # Generate CA private key
            subprocess.run([
                'openssl', 'genrsa', '-out', os.path.join(cert_dir, 'ca.key'), '2048'
            ], check=True, capture_output=True)
            
            # Generate CA certificate
            subprocess.run([
                'openssl', 'req', '-new', '-x509', '-days', '365',
                '-key', os.path.join(cert_dir, 'ca.key'),
                '-out', ca_cert_path,
                '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=NEMO MQTT CA'
            ], check=True, capture_output=True)
            
            # Generate server private key
            subprocess.run([
                'openssl', 'genrsa', '-out', server_key_path, '2048'
            ], check=True, capture_output=True)
            
            # Generate server certificate request
            subprocess.run([
                'openssl', 'req', '-new', '-key', server_key_path,
                '-out', os.path.join(cert_dir, 'server.csr'),
                '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=localhost'
            ], check=True, capture_output=True)
            
            # Generate server certificate
            subprocess.run([
                'openssl', 'x509', '-req', '-days', '365',
                '-in', os.path.join(cert_dir, 'server.csr'),
                '-CA', ca_cert_path,
                '-CAkey', os.path.join(cert_dir, 'ca.key'),
                '-CAcreateserial',
                '-out', server_cert_path
            ], check=True, capture_output=True)
            
            print(f"🔐 Generated certificates in: {cert_dir}")
            print(f"🔐   CA Certificate: {ca_cert_path}")
            print(f"🔐   Server Certificate: {server_cert_path}")
            print(f"🔐   Server Key: {server_key_path}")
            
            return {
                'ca_cert': ca_cert_path,
                'server_cert': server_cert_path,
                'server_key': server_key_path,
                'cert_dir': cert_dir
            }
            
        except Exception as e:
            print(f"❌ Failed to generate certificates: {e}")
            # Fallback: create a simple configuration without TLS
            print("⚠️  Falling back to non-TLS configuration...")
            return None
    
    def _get_generated_ca_certificate(self):
        """
        Get the generated CA certificate content for the client to use.
        
        Returns:
            CA certificate content as string
        """
        try:
            # Find the most recent certificate directory
            import glob
            cert_dirs = glob.glob('/tmp/nemo_mqtt_certs_*')
            if not cert_dirs:
                return None
            
            # Get the most recent one
            latest_cert_dir = max(cert_dirs, key=os.path.getctime)
            ca_cert_path = os.path.join(latest_cert_dir, 'ca.crt')
            
            if os.path.exists(ca_cert_path):
                with open(ca_cert_path, 'r') as f:
                    return f.read()
            
            return None
        except Exception as e:
            print(f"⚠️  Could not get generated CA certificate: {e}")
            return None
    
    def _generate_server_certificate_with_ca(self, ca_cert_path):
        """
        Generate a server certificate using the provided CA certificate.
        
        Args:
            ca_cert_path: Path to the CA certificate file
            
        Returns:
            Dictionary with paths to generated certificate files
        """
        try:
            import subprocess
            
            print("🔐 Generating server certificate using provided CA...")
            
            # Create temporary directory for certificates
            cert_dir = tempfile.mkdtemp(prefix='nemo_mqtt_server_certs_')
            
            server_cert_path = os.path.join(cert_dir, 'server.crt')
            server_key_path = os.path.join(cert_dir, 'server.key')
            
            # Generate server private key
            print("🔑 Generating server private key...")
            subprocess.run([
                'openssl', 'genrsa', '-out', server_key_path, '2048'
            ], check=True, capture_output=True)
            
            # Generate server certificate request
            print("📝 Generating server certificate request...")
            subprocess.run([
                'openssl', 'req', '-new', '-key', server_key_path,
                '-out', os.path.join(cert_dir, 'server.csr'),
                '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=localhost'
            ], check=True, capture_output=True)
            
            # Generate server certificate using the provided CA
            print("📜 Generating server certificate with provided CA...")
            subprocess.run([
                'openssl', 'x509', '-req', '-days', '365',
                '-in', os.path.join(cert_dir, 'server.csr'),
                '-CA', ca_cert_path,
                '-CAkey', ca_cert_path.replace('.pem', '.key'),  # Assume CA key has same name
                '-CAcreateserial',
                '-out', server_cert_path
            ], check=True, capture_output=True)
            
            print(f"🔐 Generated server certificate: {server_cert_path}")
            print(f"🔐 Generated server key: {server_key_path}")
            
            return {
                'server_cert': server_cert_path,
                'server_key': server_key_path,
                'cert_dir': cert_dir
            }
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate server certificate: {e}")
            print(f"   stdout: {e.stdout}")
            print(f"   stderr: {e.stderr}")
            # Fallback to self-signed
            return self._generate_self_signed_certificates()
        except Exception as e:
            print(f"❌ Failed to generate server certificate: {e}")
            # Fallback to self-signed
            return self._generate_self_signed_certificates()
    
    def _initialize_redis_robust(self):
        """Initialize Redis with ConnectionManager for robust retry"""
        def connect_redis():
            """Connection function for ConnectionManager"""
            client = redis.Redis(
                host='localhost',
                port=6379,
                db=1,  # Use database 1 for plugin isolation (must match redis_publisher.py)
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            client.ping()
            return client
        
        # Use connection manager to connect with retry logic
        self.redis_client = self.redis_connection_mgr.connect_with_retry(connect_redis)
        print("✅ Connected to Redis with robust connection manager")
        logger.info("Connected to Redis")
    
    def _initialize_mqtt_robust(self):
        """Initialize MQTT client with ConnectionManager for robust retry"""
        def connect_mqtt():
            """Connection function for ConnectionManager"""
            # Reload configuration to pick up any changes
            print("🔄 Reloading MQTT configuration from Django...")
            self.config = get_mqtt_config()
            if not self.config or not self.config.enabled:
                raise Exception("No enabled MQTT configuration found")
            print(f"✅ Config reloaded: {self.config.name}")
            print(f"   📍 Broker: {self.config.broker_host}:{self.config.broker_port}")
            
            # Create unique client ID
            import socket
            client_id = f"nemo_bridge_{socket.gethostname()}_{os.getpid()}"
            print(f"   Client ID: {client_id}")
            
            # Create MQTT client
            client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_publish = self._on_publish
            
            # Set authentication if configured
            if self.config.username and self.config.password:
                print(f"   Authentication: {self.config.username}")
                client.username_pw_set(self.config.username, self.config.password)
            else:
                print("   Authentication: None")
            
            # Set TLS if configured
            if self.config.use_tls:
                print("   🔐 TLS: Enabled")
                print(f"   🔐 TLS Version: {self.config.tls_version}")
                print(f"   🔐 Insecure Mode: {getattr(self.config, 'insecure', False)}")
                
                
                try:
                    # Create SSL context with proper configuration
                    context = ssl.create_default_context()
                    
                    # Set TLS version using the correct method
                    print(f"   🔐 Configuring TLS version: {self.config.tls_version}")
                    
                    # Set minimum and maximum TLS versions
                    if self.config.tls_version == 'tlsv1':
                        context.minimum_version = ssl.TLSVersion.TLSv1
                        context.maximum_version = ssl.TLSVersion.TLSv1
                    elif self.config.tls_version == 'tlsv1.1':
                        context.minimum_version = ssl.TLSVersion.TLSv1_1
                        context.maximum_version = ssl.TLSVersion.TLSv1_1
                    elif self.config.tls_version == 'tlsv1.2':
                        context.minimum_version = ssl.TLSVersion.TLSv1_2
                        context.maximum_version = ssl.TLSVersion.TLSv1_2
                    elif self.config.tls_version == 'tlsv1.3':
                        context.minimum_version = ssl.TLSVersion.TLSv1_3
                        context.maximum_version = ssl.TLSVersion.TLSv1_3
                    else:
                        print(f"   ⚠️  Unknown TLS version {self.config.tls_version}, using default (TLSv1.2)")
                        context.minimum_version = ssl.TLSVersion.TLSv1_2
                        context.maximum_version = ssl.TLSVersion.TLSv1_2
                    
                    print(f"   🔐 TLS version range: {context.minimum_version} to {context.maximum_version}")
                    
                    # Handle CA certificate
                    ca_cert_loaded = False
                    
                    # Always use CA certificate from NEMO configuration (both AUTO and EXTERNAL modes)
                    if self.config.ca_cert_content:
                        print("   🔐 CA Certificate: Found in content field")
                        try:
                            # Create temporary file for CA certificate
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as ca_file:
                                ca_file.write(self.config.ca_cert_content)
                                ca_file_path = ca_file.name
                            
                            print(f"   🔐 CA Certificate: Written to temp file: {ca_file_path}")
                            context.load_verify_locations(ca_file_path)
                            ca_cert_loaded = True
                            print("   ✅ CA Certificate: Successfully loaded into SSL context")
                            
                            # Clean up temp file
                            os.unlink(ca_file_path)
                            print("   🧹 CA Certificate: Temp file cleaned up")
                            
                        except Exception as e:
                            print(f"   ❌ CA Certificate: Failed to load from content: {e}")
                            print(f"   🔍 CA Certificate Content Preview: {self.config.ca_cert_content[:100]}...")
                    elif self.config.ca_cert_path:
                        print(f"   🔐 CA Certificate: Found in path field: {self.config.ca_cert_path}")
                        try:
                            if os.path.exists(self.config.ca_cert_path):
                                context.load_verify_locations(self.config.ca_cert_path)
                                ca_cert_loaded = True
                                print("   ✅ CA Certificate: Successfully loaded from file")
                            else:
                                print(f"   ❌ CA Certificate: File not found: {self.config.ca_cert_path}")
                        except Exception as e:
                            print(f"   ❌ CA Certificate: Failed to load from file: {e}")
                    else:
                        print("   🔐 CA Certificate: Not provided, using system default")
                    
                    # Handle client certificate and key
                    client_cert_loaded = False
                    if self.config.client_cert_content and self.config.client_key_content:
                        print("   🔐 Client Certificate: Found in content fields")
                        try:
                            # Create temporary files for client certificate and key
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as cert_file:
                                cert_file.write(self.config.client_cert_content)
                                cert_file_path = cert_file.name
                            
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as key_file:
                                key_file.write(self.config.client_key_content)
                                key_file_path = key_file.name
                            
                            print(f"   🔐 Client Certificate: Written to temp files")
                            print(f"   🔐   Cert: {cert_file_path}")
                            print(f"   🔐   Key: {key_file_path}")
                            
                            context.load_cert_chain(cert_file_path, key_file_path)
                            client_cert_loaded = True
                            print("   ✅ Client Certificate: Successfully loaded into SSL context")
                            
                            # Clean up temp files
                            os.unlink(cert_file_path)
                            os.unlink(key_file_path)
                            print("   🧹 Client Certificate: Temp files cleaned up")
                            
                        except Exception as e:
                            print(f"   ❌ Client Certificate: Failed to load from content: {e}")
                            print(f"   🔍 Client Cert Content Preview: {self.config.client_cert_content[:100]}...")
                            print(f"   🔍 Client Key Content Preview: {self.config.client_key_content[:100]}...")
                    elif self.config.client_cert_path and self.config.client_key_path:
                        print(f"   🔐 Client Certificate: Found in path fields")
                        print(f"   🔐   Cert: {self.config.client_cert_path}")
                        print(f"   🔐   Key: {self.config.client_key_path}")
                        try:
                            if os.path.exists(self.config.client_cert_path) and os.path.exists(self.config.client_key_path):
                                context.load_cert_chain(self.config.client_cert_path, self.config.client_key_path)
                                client_cert_loaded = True
                                print("   ✅ Client Certificate: Successfully loaded from files")
                            else:
                                missing_files = []
                                if not os.path.exists(self.config.client_cert_path):
                                    missing_files.append(f"cert: {self.config.client_cert_path}")
                                if not os.path.exists(self.config.client_key_path):
                                    missing_files.append(f"key: {self.config.client_key_path}")
                                print(f"   ❌ Client Certificate: Files not found: {', '.join(missing_files)}")
                        except Exception as e:
                            print(f"   ❌ Client Certificate: Failed to load from files: {e}")
                    else:
                        print("   🔐 Client Certificate: Not provided")
                    
                    # Configure verification settings (always use secure mode)
                    print("   🔐 TLS Verification: ENABLED")
                    context.check_hostname = True
                    context.verify_mode = ssl.CERT_REQUIRED
                    
                    if not ca_cert_loaded:
                        print("   ⚠️  TLS Verification: No CA certificate loaded, using system defaults")
                    
                    # Set additional SSL context options
                    context.options |= ssl.OP_NO_SSLv2
                    context.options |= ssl.OP_NO_SSLv3
                    print("   🔐 SSL Options: Disabled SSLv2 and SSLv3")
                    
                    # Log final SSL context configuration
                    print(f"   🔐 Final SSL Context Configuration:")
                    print(f"   🔐   Protocol: {context.protocol}")
                    print(f"   🔐   Check Hostname: {context.check_hostname}")
                    print(f"   🔐   Verify Mode: {context.verify_mode}")
                    print(f"   🔐   CA Cert Loaded: {ca_cert_loaded}")
                    print(f"   🔐   Client Cert Loaded: {client_cert_loaded}")
                    
                    # Apply SSL context to MQTT client
                    client.tls_set_context(context)
                    print("   ✅ SSL Context: Successfully applied to MQTT client")
                    
                except Exception as e:
                    print(f"   ❌ TLS Configuration: Failed to configure TLS: {e}")
                    print(f"   🔍 Error Type: {type(e).__name__}")
                    import traceback
                    print(f"   🔍 Traceback: {traceback.format_exc()}")
                    raise Exception(f"TLS configuration failed: {e}")
            else:
                print("   🔐 TLS: Disabled")
            
            # Connect to broker
            self.broker_host = self.config.broker_host or 'localhost'
            self.broker_port = self.config.broker_port or 1883
            keepalive = self.config.keepalive or 60
            
            print(f"🔌 Attempting MQTT connection...")
            print(f"   Broker: {self.broker_host}:{self.broker_port}")
            print(f"   Keepalive: {keepalive}s")
            print(f"   Client ID: {client_id}")
            print(f"   TLS Enabled: {self.config.use_tls}")
            if self.config.use_tls:
                print(f"   TLS Port: {self.broker_port} (should be 8883 for TLS)")
                print(f"   TLS Version: {self.config.tls_version}")
            
            try:
                print("   🔌 Calling client.connect()...")
                client.connect(self.broker_host, self.broker_port, keepalive)
                print("   ✅ client.connect() completed successfully")
                
                print("   🔄 Starting MQTT loop...")
                client.loop_start()
                print("   ✅ MQTT loop started")
                
                # Wait for connection to be established with detailed status
                timeout = 15  # Increased timeout for TLS connections
                elapsed = 0
                print(f"   ⏳ Waiting for connection (timeout: {timeout}s)...")
                
                while elapsed < timeout:
                    connected = client.is_connected()
                    print(f"   🔍 Connection check {elapsed:.1f}s: {'✅ Connected' if connected else '⏳ Pending'}")
                    
                    if connected:
                        self.connection_count += 1
                        self.last_connect_time = time.time()
                        print(f"✅ MQTT CONNECTION ESTABLISHED!")
                        print(f"   Broker: {self.broker_host}:{self.broker_port}")
                        print(f"   Connection #: {self.connection_count}")
                        print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"   TLS: {'Enabled' if self.config.use_tls else 'Disabled'}")
                        if self.config.use_tls:
                            print(f"   TLS Version: {self.config.tls_version}")
                        return client
                    
                    time.sleep(0.5)
                    elapsed += 0.5
                
                # If not connected, get more details about the failure
                print(f"   ❌ Connection timeout after {timeout}s")
                print(f"   🔍 Final connection status: {client.is_connected()}")
                
                # Try to get more information about the connection state
                try:
                    # Check if there are any pending connection errors
                    print("   🔍 Checking for connection errors...")
                    # Note: paho-mqtt doesn't expose detailed error info easily
                    print("   🔍 Connection may have failed due to:")
                    print("   🔍   - Network connectivity issues")
                    print("   🔍   - TLS/SSL handshake failure")
                    print("   🔍   - Authentication failure")
                    print("   🔍   - Broker not accepting connections")
                    if self.config.use_tls:
                        print("   🔍   - TLS certificate validation failure")
                        print("   🔍   - Wrong TLS port (should be 8883)")
                        print("   🔍   - CA certificate not trusted by broker")
                except Exception as e:
                    print(f"   🔍 Error getting connection details: {e}")
                
                raise Exception(f"Connection timeout - {self.broker_host}:{self.broker_port} didn't respond after {timeout}s")
                
            except Exception as e:
                print(f"   ❌ MQTT connection failed: {e}")
                print(f"   🔍 Error Type: {type(e).__name__}")
                print(f"   🔍 Broker: {self.broker_host}:{self.broker_port}")
                print(f"   🔍 TLS Enabled: {self.config.use_tls}")
                if self.config.use_tls:
                    print(f"   🔍 TLS Version: {self.config.tls_version}")
                    print(f"   🔍 CA Cert Provided: {bool(self.config.ca_cert_content or self.config.ca_cert_path)}")
                    print(f"   🔍 Client Cert Provided: {bool(self.config.client_cert_content or self.config.client_cert_path)}")
                    print(f"   🔍 Insecure Mode: {getattr(self.config, 'insecure', False)}")
                
                # Add specific TLS debugging
                if self.config.use_tls and "SSL" in str(e):
                    print(f"   🔐 TLS/SSL Error Details:")
                    print(f"   🔐   This is likely a TLS handshake or certificate issue")
                    print(f"   🔐   Check that:")
                    print(f"   🔐   - Broker is running on TLS port (usually 8883)")
                    print(f"   🔐   - CA certificate is valid and trusted")
                    print(f"   🔐   - Client certificate is valid (if using client auth)")
                    print(f"   🔐   - TLS version is supported by broker")
                    print(f"   🔐   - Broker hostname matches certificate")
                
                import traceback
                print(f"   🔍 Full traceback: {traceback.format_exc()}")
                raise
        
        # Use connection manager to connect with retry logic
        self.mqtt_client = self.mqtt_connection_mgr.connect_with_retry(connect_mqtt)
        logger.info("MQTT client connected with robust connection manager")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        print(f"🔔 MQTT Connection Callback Triggered:")
        print(f"   🔍 Return Code: {rc}")
        print(f"   🔍 Flags: {flags}")
        print(f"   🔍 Userdata: {userdata}")
        print(f"   🔍 Client ID: {client._client_id}")
        print(f"   🔍 Broker: {self.broker_host}:{self.broker_port}")
        print(f"   🔍 TLS Enabled: {self.config.use_tls if hasattr(self, 'config') else 'Unknown'}")
        
        if rc == 0:
            print("=" * 60)
            print("✅ MQTT BROKER CONNECTED!")
            print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
            print(f"   🔢 Connection attempt: #{self.connection_count}")
            print(f"   🕐 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   🔐 TLS: {'Enabled' if hasattr(self, 'config') and self.config.use_tls else 'Disabled'}")
            if hasattr(self, 'config') and self.config.use_tls:
                print(f"   🔐 TLS Version: {self.config.tls_version}")
                print(f"   🔐 CA Cert: {'Provided' if (self.config.ca_cert_content or self.config.ca_cert_path) else 'Not provided'}")
                print(f"   🔐 Client Cert: {'Provided' if (self.config.client_cert_content or self.config.client_cert_path) else 'Not provided'}")
                print(f"   🔐 Insecure Mode: {getattr(self.config, 'insecure', False)}")
            if self.last_disconnect_time:
                downtime = time.time() - self.last_disconnect_time
                print(f"   ⏱️  Downtime: {downtime:.1f} seconds")
            print("=" * 60)
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
        else:
            error_messages = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorized"
            }
            error_msg = error_messages.get(rc, f"unknown error code {rc}")
            print("=" * 60)
            print(f"❌ MQTT BROKER CONNECTION FAILED!")
            print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
            print(f"   ⚠️  Error: {error_msg}")
            print(f"   🔢 Return code: {rc}")
            print(f"   🔐 TLS: {'Enabled' if hasattr(self, 'config') and self.config.use_tls else 'Disabled'}")
            
            if hasattr(self, 'config') and self.config.use_tls:
                print(f"   🔐 TLS Debug Info:")
                print(f"   🔐   TLS Version: {self.config.tls_version}")
                print(f"   🔐   CA Cert: {'Provided' if (self.config.ca_cert_content or self.config.ca_cert_path) else 'Not provided'}")
                print(f"   🔐   Client Cert: {'Provided' if (self.config.client_cert_content or self.config.client_cert_path) else 'Not provided'}")
                print(f"   🔐   Insecure Mode: {getattr(self.config, 'insecure', False)}")
                print(f"   🔐   Port: {self.broker_port} (should be 8883 for TLS)")
                
                # Add TLS-specific error analysis
                if rc == 3:  # Server unavailable
                    print(f"   🔐   TLS Analysis: Server unavailable could mean:")
                    print(f"   🔐     - Broker not running on TLS port {self.broker_port}")
                    print(f"   🔐     - TLS handshake failed")
                    print(f"   🔐     - Certificate validation failed")
                elif rc == 4:  # Bad username/password
                    print(f"   🔐   TLS Analysis: Auth failure could mean:")
                    print(f"   🔐     - Client certificate not accepted by broker")
                    print(f"   🔐     - Username/password not valid for TLS connection")
                elif rc == 5:  # Not authorized
                    print(f"   🔐   TLS Analysis: Not authorized could mean:")
                    print(f"   🔐     - Client certificate not trusted by broker")
                    print(f"   🔐     - CA certificate mismatch")
                    print(f"   🔐     - Certificate chain validation failed")
            
            print("=" * 60)
            logger.error(f"Failed to connect to MQTT broker at {self.broker_host}:{self.broker_port}: {error_msg} (rc={rc})")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.last_disconnect_time = time.time()
        
        if rc != 0:
            disconnect_reasons = {
                1: "client disconnected",
                2: "protocol error",
                3: "message queue full",
                4: "connection lost",
                5: "protocol violation",
                7: "keepalive timeout"
            }
            reason = disconnect_reasons.get(rc, f"unknown reason (code {rc})")
            
            print("=" * 60)
            print("⚠️  MQTT BROKER DISCONNECTED!")
            print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
            print(f"   ⚠️  Reason: {reason}")
            print(f"   🔢 Return code: {rc}")
            print(f"   🕐 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   🔄 Reconnection will be handled automatically...")
            print("=" * 60)
            logger.warning(f"Unexpected disconnection from MQTT broker at {self.broker_host}:{self.broker_port}. Reason: {reason} (rc={rc})")
            # The main loop will detect this and reconnect using ConnectionManager
        else:
            print(f"ℹ️  MQTT broker disconnected gracefully from {self.broker_host}:{self.broker_port}")
            logger.info(f"Gracefully disconnected from MQTT broker at {self.broker_host}:{self.broker_port}")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published with mid: {mid}")
    
    def _ensure_mqtt_connected(self):
        """
        Ensure MQTT client is connected, reconnect if needed.
        Uses ConnectionManager for sophisticated retry logic with exponential backoff.
        """
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logger.warning("MQTT client not connected, reconnecting with backoff...")
            print("=" * 60)
            print("🔄 MQTT RECONNECTION NEEDED")
            print(f"   📍 Target: {self.broker_host}:{self.broker_port}")
            
            # Show current connection manager state
            state = self.mqtt_connection_mgr.get_state()
            print(f"   🔧 Circuit breaker: {state['circuit_state']}")
            print(f"   ❌ Failed attempts: {state['failure_count']}")
            print(f"   ⏱️  Retry delay: {state.get('next_delay', 'N/A')}s")
            print("=" * 60)
            
            try:
                self._initialize_mqtt_robust()
                print("=" * 60)
                print("✅ RECONNECTION SUCCESSFUL!")
                print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
                print(f"   ✨ Connection restored via ConnectionManager")
                print("=" * 60)
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                print(f"❌ Reconnection failed: {e}")
                return False
        
        return True
    
    def _run(self):
        """
        Main service loop - consumes events from Redis and publishes to MQTT.
        Implements robust connection sensing and automatic reconnection.
        """
        print("🔍 Starting Redis consumption loop...")
        logger.info("Starting event consumption loop...")
        
        while self.running:
            try:
                # 1. Check MQTT connection (connection sensing)
                if not self._ensure_mqtt_connected():
                    # ConnectionManager is handling retries with backoff
                    time.sleep(5)
                    continue
                
                # 2. Check Redis connection
                try:
                    self.redis_client.ping()
                except Exception as e:
                    logger.warning(f"Redis connection lost: {e}")
                    print("🔍 Redis disconnected, reconnecting with ConnectionManager...")
                    self._initialize_redis_robust()
                
                # 3. Check Redis list length before consuming
                list_length = self.redis_client.llen(EVENTS_LIST_KEY)
                if list_length > 0:
                    print(f"🔍 [CONSUME] Processing {list_length} queued messages...")
                    logger.info(f"Found {list_length} messages in Redis queue")
                
                # 4. Consume events from Redis using BLPOP
                result = self.redis_client.blpop(EVENTS_LIST_KEY, timeout=1)
                
                if result:
                    channel, event_data = result
                    print(f"📨 Received message from Redis: {channel}")
                    self._process_event(event_data)
                
            except Exception as e:
                print(f"❌ [CONSUME] Error in service loop: {e}")
                logger.error(f"Error in service loop: {e}")
                time.sleep(1)
        
        print(f"🛑 Consumption loop stopped")
    
    def _process_event(self, event_data: str):
        """Process a single event from Redis"""
        import uuid
        mqtt_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [MQTT-{mqtt_id}] Processing event from Redis")
        print(f"   Raw data: {event_data[:200]}{'...' if len(event_data) > 200 else ''}")
        
        try:
            event = json.loads(event_data)
            print(f"🔍 [MQTT-{mqtt_id}] Event parsed successfully")
            
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 0)
            retain = event.get('retain', False)
            
            print(f"🔍 [MQTT-{mqtt_id}] Extracted values:")
            print(f"   Topic: {topic}")
            print(f"   QoS: {qos}")
            print(f"   Retain: {retain}")
            
            if topic and payload is not None:
                print(f"🔍 [MQTT-{mqtt_id}] Valid event data, publishing to MQTT...")
                self._publish_to_mqtt(topic, payload, qos, retain)
                print(f"✅ [MQTT-{mqtt_id}] Published event to MQTT: {topic}")
                logger.info(f"Published event to MQTT: {topic}")
            else:
                print(f"❌ [MQTT-{mqtt_id}] Invalid event data - missing topic or payload")
                logger.warning(f"Invalid event data: {event}")
                
        except json.JSONDecodeError as e:
            print(f"❌ [MQTT-{mqtt_id}] Failed to parse event data: {e}")
            logger.error(f"Failed to parse event data: {e}")
        except Exception as e:
            print(f"❌ [MQTT-{mqtt_id}] Failed to process event: {e}")
            logger.error(f"Failed to process event: {e}")
    
    def _publish_to_mqtt(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish message to MQTT broker"""
        import uuid
        publish_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [PUBLISH-{publish_id}] Attempting to publish to MQTT broker")
        print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
        print(f"   Topic: {topic}")
        print(f"   QoS: {qos}")
        print(f"   Retain: {retain}")
        
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                print(f"🔍 [PUBLISH-{publish_id}] MQTT client is connected, publishing...")
                result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
                
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"❌ [PUBLISH-{publish_id}] Failed to publish message: {result.rc}")
                    logger.error(f"Failed to publish message: {result.rc}")
                else:
                    print(f"✅ [PUBLISH-{publish_id}] Message published successfully to MQTT broker")
                    print(f"   📍 Published to: {self.broker_host}:{self.broker_port}")
            else:
                print(f"❌ [PUBLISH-{publish_id}] MQTT client not connected, cannot publish message")
                logger.warning("MQTT client not connected, cannot publish message")
                # The main loop will detect this and reconnect
        except Exception as e:
            print(f"❌ [PUBLISH-{publish_id}] Failed to publish to MQTT: {e}")
            logger.error(f"Failed to publish to MQTT: {e}")
    
    def stop(self):
        """Stop the Redis-MQTT Bridge service"""
        print("🛑 Stopping Redis-MQTT Bridge...")
        logger.info("Stopping Redis-MQTT Bridge...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ MQTT client disconnected")
            logger.info("MQTT client disconnected")
        
        if self.redis_client:
            self.redis_client.close()
            print("✅ Redis client closed")
            logger.info("Redis client closed")
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        # Clean up auto-started services
        if self.auto_start:
            self._cleanup_existing_services()
        
        # Release lock file
        self._release_lock()
        
        print("✅ Redis-MQTT Bridge stopped")
        logger.info("Redis-MQTT Bridge stopped")


# Global instance for Django integration (AUTO mode for development)
# Use lazy initialization to prevent multiple instances
_mqtt_bridge_instance = None
_mqtt_bridge_lock = threading.Lock()


def get_mqtt_bridge():
    """
    Get or create the global MQTT bridge instance (singleton pattern).
    This ensures only one instance exists across all imports.
    """
    global _mqtt_bridge_instance
    
    with _mqtt_bridge_lock:
        if _mqtt_bridge_instance is None:
            _mqtt_bridge_instance = RedisMQTTBridge(auto_start=True)
        return _mqtt_bridge_instance


# For backward compatibility
mqtt_bridge = None  # Will be initialized on first access


def main():
    """
    Main entry point for running as standalone service.
    Default: EXTERNAL mode (connects to existing services)
    Use --auto flag for AUTO mode (starts Redis and Mosquitto)
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Redis-MQTT Bridge Service')
    parser.add_argument('--auto', action='store_true', 
                       help='AUTO mode: Start Redis and Mosquitto automatically (dev/test)')
    args = parser.parse_args()
    
    service = RedisMQTTBridge(auto_start=args.auto)
    
    try:
        if service.start():
            mode = "AUTO" if args.auto else "EXTERNAL"
            print(f"🚀 Redis-MQTT Bridge is running in {mode} mode. Press Ctrl+C to stop.")
            logger.info(f"Redis-MQTT Bridge is running in {mode} mode. Press Ctrl+C to stop.")
            # Keep the main thread alive
            while service.running:
                time.sleep(1)
        else:
            print("❌ Failed to start Redis-MQTT Bridge")
            logger.error("Failed to start Redis-MQTT Bridge")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Received keyboard interrupt")
        logger.info("Received keyboard interrupt")
    finally:
        service.stop()


if __name__ == "__main__":
    main()

