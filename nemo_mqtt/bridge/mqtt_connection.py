"""
MQTT client connection setup with TLS support.
"""
import logging
import os
import ssl
import socket
import tempfile
import time
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


def create_ssl_context(config) -> ssl.SSLContext:
    """Create SSL context from config."""
    context = ssl.create_default_context()
    tls_map = {
        'tlsv1': ssl.TLSVersion.TLSv1,
        'tlsv1.1': ssl.TLSVersion.TLSv1_1,
        'tlsv1.2': ssl.TLSVersion.TLSv1_2,
        'tlsv1.3': ssl.TLSVersion.TLSv1_3,
    }
    ver = tls_map.get(config.tls_version, ssl.TLSVersion.TLSv1_2)
    context.minimum_version = ver
    context.maximum_version = ver

    if config.ca_cert_content:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
            f.write(config.ca_cert_content)
            path = f.name
        try:
            context.load_verify_locations(path)
        finally:
            os.unlink(path)
    elif config.ca_cert_path and os.path.exists(config.ca_cert_path):
        context.load_verify_locations(config.ca_cert_path)

    if config.client_cert_content and config.client_key_content:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as cf:
            cf.write(config.client_cert_content)
            cert_path = cf.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as kf:
            kf.write(config.client_key_content)
            key_path = kf.name
        try:
            context.load_cert_chain(cert_path, key_path)
        finally:
            os.unlink(cert_path)
            os.unlink(key_path)
    elif config.client_cert_path and config.client_key_path:
        if os.path.exists(config.client_cert_path) and os.path.exists(config.client_key_path):
            context.load_cert_chain(config.client_cert_path, config.client_key_path)

    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
    return context


def connect_mqtt(
    config,
    on_connect: Callable,
    on_disconnect: Callable,
    on_publish: Callable,
) -> mqtt.Client:
    """Create and connect MQTT client."""
    client_id = f"nemo_bridge_{socket.gethostname()}_{os.getpid()}"
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish

    if config.username and config.password:
        client.username_pw_set(config.username, config.password)

    if config.use_tls:
        ctx = create_ssl_context(config)
        client.tls_set_context(ctx)

    broker_host = config.broker_host or 'localhost'
    broker_port = config.broker_port or 1883
    keepalive = config.keepalive or 60

    client.connect(broker_host, broker_port, keepalive)
    client.loop_start()

    timeout = 15
    for _ in range(int(timeout / 0.5)):
        if client.is_connected():
            return client
        time.sleep(0.5)

    raise RuntimeError(f"Connection timeout to {broker_host}:{broker_port} after {timeout}s")
