"""
AUTO mode: start Redis and Mosquitto for development/testing.
"""
import ipaddress
import logging
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
import redis

logger = logging.getLogger(__name__)


def cleanup_existing_services(redis_process=None):
    """Clean up any existing Redis, MQTT broker, and bridge instances."""
    try:
        if redis_process:
            try:
                redis_process.terminate()
                redis_process.wait(timeout=5)
            except Exception:
                redis_process.kill()
        subprocess.run(['pkill', '-f', 'mosquitto'], capture_output=True)
        subprocess.run(['pkill', '-9', 'mosquitto'], capture_output=True)
        subprocess.run(['pkill', '-f', 'redis_mqtt_bridge'], capture_output=True)
        time.sleep(2)
        logger.info("Cleaned up existing services")
    except Exception as e:
        logger.warning("Cleanup warning: %s", e)


def start_redis():
    """Start Redis server. Returns None if already running."""
    try:
        try:
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            logger.info("Redis already running")
            return None
        except redis.ConnectionError:
            pass

        proc = subprocess.Popen(
            ['redis-server', '--daemonize', 'yes'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(10):
            try:
                r = redis.Redis(host='localhost', port=6379, db=0)
                r.ping()
                logger.info("Redis started")
                return proc
            except redis.ConnectionError:
                time.sleep(1)
        raise RuntimeError("Redis failed to start within 10 seconds")
    except Exception as e:
        logger.error("Failed to start Redis: %s", e)
        raise


def generate_self_signed_certs() -> Optional[Dict[str, str]]:
    """Generate self-signed certs for development TLS."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta

        cert_dir = tempfile.mkdtemp(prefix='nemo_mqtt_certs_')
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "NEMO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NEMO MQTT Plugin"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NEMO MQTT CA"),
        ])
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(private_key, hashes.SHA256())
        )
        server_subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        server_cert = (
            x509.CertificateBuilder()
            .subject_name(server_subject)
            .issuer_name(ca_subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )
        ca_path = os.path.join(cert_dir, 'ca.crt')
        server_cert_path = os.path.join(cert_dir, 'server.crt')
        server_key_path = os.path.join(cert_dir, 'server.key')
        with open(ca_path, 'wb') as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        with open(server_cert_path, 'wb') as f:
            f.write(server_cert.public_bytes(serialization.Encoding.PEM))
        with open(server_key_path, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        return {
            'ca_cert': ca_path,
            'server_cert': server_cert_path,
            'server_key': server_key_path,
            'cert_dir': cert_dir,
        }
    except ImportError:
        return _generate_simple_certs()
    except Exception as e:
        logger.warning("Cryptography cert generation failed: %s", e)
        return _generate_simple_certs()


def _generate_simple_certs() -> Optional[Dict[str, str]]:
    """Fallback: generate certs via OpenSSL."""
    try:
        cert_dir = tempfile.mkdtemp(prefix='nemo_mqtt_certs_')
        ca_path = os.path.join(cert_dir, 'ca.crt')
        server_cert_path = os.path.join(cert_dir, 'server.crt')
        server_key_path = os.path.join(cert_dir, 'server.key')
        ca_key = os.path.join(cert_dir, 'ca.key')
        subprocess.run(['openssl', 'genrsa', '-out', ca_key, '2048'], check=True, capture_output=True)
        subprocess.run([
            'openssl', 'req', '-new', '-x509', '-days', '365',
            '-key', ca_key, '-out', ca_path,
            '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=NEMO MQTT CA',
        ], check=True, capture_output=True)
        subprocess.run(['openssl', 'genrsa', '-out', server_key_path, '2048'], check=True, capture_output=True)
        csr = os.path.join(cert_dir, 'server.csr')
        subprocess.run([
            'openssl', 'req', '-new', '-key', server_key_path, '-out', csr,
            '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=localhost',
        ], check=True, capture_output=True)
        subprocess.run([
            'openssl', 'x509', '-req', '-days', '365',
            '-in', csr, '-CA', ca_path, '-CAkey', ca_key, '-CAcreateserial',
            '-out', server_cert_path,
        ], check=True, capture_output=True)
        return {
            'ca_cert': ca_path,
            'server_cert': server_cert_path,
            'server_key': server_key_path,
            'cert_dir': cert_dir,
        }
    except Exception as e:
        logger.error("OpenSSL cert generation failed: %s", e)
        return None


def create_mosquitto_tls_config(config, cert_files: Dict[str, str]) -> str:
    """Create Mosquitto config file for TLS."""
    cfg = tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False)
    broker_port = config.broker_port if config else 8883
    cfg.write(f"port {broker_port}\n")
    cfg.write(f"listener {broker_port}\nprotocol mqtt\n")
    cfg.write(f"cafile {cert_files['ca_cert']}\n")
    cfg.write(f"certfile {cert_files['server_cert']}\n")
    cfg.write(f"keyfile {cert_files['server_key']}\n")
    cfg.write("allow_anonymous true\nlog_dest stdout\nlog_type all\n")
    cfg.close()
    return cfg.name


def start_mosquitto(config) -> subprocess.Popen:
    """Start Mosquitto broker."""
    broker_port = config.broker_port if config else 1883
    try:
        tc = mqtt.Client(client_id="mosquitto_check")
        tc.connect('localhost', broker_port, 5)
        tc.disconnect()
        logger.info("Mosquitto already running on port %s", broker_port)
        return None
    except Exception:
        pass

    if config and config.use_tls:
        cert_files = generate_self_signed_certs()
        if cert_files:
            mosquitto_config = create_mosquitto_tls_config(config, cert_files)
            proc = subprocess.Popen(
                ['mosquitto', '-c', mosquitto_config],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            proc = subprocess.Popen(
                ['mosquitto', '-p', str(broker_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
    else:
        proc = subprocess.Popen(
            ['mosquitto', '-p', str(broker_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    for i in range(20):
        try:
            tc = mqtt.Client(client_id=f"mosquitto_check_{i}")
            tc.connect('localhost', broker_port, 5)
            tc.loop_start()
            time.sleep(0.5)
            if tc.is_connected():
                tc.loop_stop()
                tc.disconnect()
                logger.info("Mosquitto started on port %s", broker_port)
                return proc
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Mosquitto failed to start within 20 seconds")
