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
    from NEMO.plugins.NEMO_mqtt.models import MQTTConfiguration
    from NEMO.plugins.NEMO_mqtt.utils import get_mqtt_config
except ImportError:
    # Fallback for development
    from NEMO_mqtt.models import MQTTConfiguration
    from NEMO_mqtt.utils import get_mqtt_config

# Import the ConnectionManager
try:
    from NEMO.plugins.NEMO_mqtt.connection_manager import ConnectionManager
except ImportError:
    from NEMO_mqtt.connection_manager import ConnectionManager

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
            
            # Start Mosquitto broker on configured port
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
                print("   TLS: Enabled")
                import ssl
                context = ssl.create_default_context()
                if not getattr(self.config, 'verify_tls', True):
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                client.tls_set_context(context)
            else:
                print("   TLS: Disabled")
            
            # Connect to broker
            self.broker_host = self.config.broker_host or 'localhost'
            self.broker_port = self.config.broker_port or 1883
            keepalive = self.config.keepalive or 60
            
            print(f"🔌 Attempting MQTT connection...")
            print(f"   Broker: {self.broker_host}:{self.broker_port}")
            print(f"   Keepalive: {keepalive}s")
            
            client.connect(self.broker_host, self.broker_port, keepalive)
            client.loop_start()
            
            # Wait for connection to be established
            timeout = 10
            elapsed = 0
            while elapsed < timeout:
                if client.is_connected():
                    self.connection_count += 1
                    self.last_connect_time = time.time()
                    print(f"✅ MQTT CONNECTION ESTABLISHED!")
                    print(f"   Broker: {self.broker_host}:{self.broker_port}")
                    print(f"   Connection #: {self.connection_count}")
                    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    return client
                time.sleep(0.5)
                elapsed += 0.5
            
            # If not connected, raise exception to trigger retry
            raise Exception(f"Connection timeout - {self.broker_host}:{self.broker_port} didn't respond after {timeout}s")
        
        # Use connection manager to connect with retry logic
        self.mqtt_client = self.mqtt_connection_mgr.connect_with_retry(connect_mqtt)
        logger.info("MQTT client connected with robust connection manager")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print("=" * 60)
            print("✅ MQTT BROKER CONNECTED!")
            print(f"   📍 Broker: {self.broker_host}:{self.broker_port}")
            print(f"   🔢 Connection attempt: #{self.connection_count}")
            print(f"   🕐 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
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
                list_length = self.redis_client.llen('NEMO_mqtt_events')
                if list_length > 0:
                    print(f"🔍 [CONSUME] Processing {list_length} queued messages...")
                    logger.info(f"Found {list_length} messages in Redis queue")
                
                # 4. Consume events from Redis using BLPOP
                result = self.redis_client.blpop('NEMO_mqtt_events', timeout=1)
                
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

