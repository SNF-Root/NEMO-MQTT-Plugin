#!/usr/bin/env python3
"""
Redis-MQTT Bridge Service for NEMO Plugin.

Modes:
  - AUTO: Starts Redis and Mosquitto for development
  - EXTERNAL: Connects to existing services (production)
"""
import json
import logging
import os
import signal
import sys
import threading
import time

import paho.mqtt.client as mqtt
import redis

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')
    import django
    django.setup()

try:
    from nemo_mqtt.models import MQTTConfiguration
    from nemo_mqtt.utils import get_mqtt_config
except ImportError:
    from NEMO.plugins.nemo_mqtt.models import MQTTConfiguration
    from NEMO.plugins.nemo_mqtt.utils import get_mqtt_config

try:
    from nemo_mqtt.connection_manager import ConnectionManager
    from nemo_mqtt.redis_publisher import EVENTS_LIST_KEY
    from nemo_mqtt.bridge.process_lock import acquire_lock, release_lock
    from nemo_mqtt.bridge.auto_services import (
        cleanup_existing_services,
        start_redis,
        start_mosquitto,
    )
    from nemo_mqtt.bridge.mqtt_connection import connect_mqtt
except ImportError:
    from NEMO.plugins.nemo_mqtt.connection_manager import ConnectionManager
    from NEMO.plugins.nemo_mqtt.redis_publisher import EVENTS_LIST_KEY
    from NEMO.plugins.nemo_mqtt.bridge.process_lock import acquire_lock, release_lock
    from NEMO.plugins.nemo_mqtt.bridge.auto_services import (
        cleanup_existing_services,
        start_redis,
        start_mosquitto,
    )
    from NEMO.plugins.nemo_mqtt.bridge.mqtt_connection import connect_mqtt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RedisMQTTBridge:
    """Bridges Redis events to MQTT broker."""

    def __init__(self, auto_start: bool = False):
        self.auto_start = auto_start
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        self.config = None
        self.thread = None
        self.lock_file = None
        self.redis_process = None
        self.mosquitto_process = None
        self.broker_host = None
        self.broker_port = None
        self.connection_count = 0
        self.last_connect_time = None
        self.last_disconnect_time = None
        # Debounce disconnect logging (paho can fire on_disconnect many times)
        self._last_disconnect_log_time = 0
        self._last_disconnect_rc = None
        self._disconnect_log_interval = 5
        # Throttle reconnection failure logs when circuit breaker is open
        self._last_reconnect_fail_log_time = 0
        self._last_reconnect_fail_msg = None
        self._reconnect_fail_log_interval = 30
        self._last_reconnecting_log_time = 0
        self._reconnecting_log_interval = 15
        self._mqtt_has_connected_before = False

        self.mqtt_connection_mgr = ConnectionManager(
            max_retries=None, base_delay=1, max_delay=60,
            failure_threshold=5, success_threshold=3, timeout=60,
        )
        self.redis_connection_mgr = ConnectionManager(
            max_retries=None, base_delay=1, max_delay=30,
            failure_threshold=5, success_threshold=3, timeout=60,
        )

        self.lock_file = acquire_lock()
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        self.stop()
        sys.exit(0)

    def start(self):
        """Start the bridge service."""
        try:
            mode = "AUTO" if self.auto_start else "EXTERNAL"
            logger.info("Starting Redis-MQTT Bridge (%s mode)", mode)

            self.config = get_mqtt_config()
            if not self.config or not self.config.enabled:
                logger.error("No enabled MQTT configuration found")
                return False

            if self.auto_start:
                cleanup_existing_services(self.redis_process)
                self.redis_process = start_redis()
                self.mosquitto_process = start_mosquitto(self.config)

            self._initialize_redis()
            self._initialize_mqtt()

            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

            logger.info("Redis-MQTT Bridge started successfully")
            return True
        except Exception as e:
            logger.error("Failed to start bridge: %s", e)
            return False

    def _initialize_redis(self):
        def connect():
            c = redis.Redis(
                host='localhost', port=6379, db=1,
                decode_responses=True, socket_connect_timeout=5, socket_timeout=5,
            )
            c.ping()
            return c
        self.redis_client = self.redis_connection_mgr.connect_with_retry(connect)
        logger.info("Connected to Redis")

    def _initialize_mqtt(self):
        # Stop existing client so broker can release the session and we don't accumulate clients
        reconnecting = self.mqtt_client is not None
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.debug("Cleanup of previous MQTT client: %s", e)
            self.mqtt_client = None

        # When reconnecting, reset connection manager so we get full retries/backoff
        if reconnecting:
            self.mqtt_connection_mgr.reset()

        self.config = get_mqtt_config()

        def connect():
            self.config = get_mqtt_config()
            if not self.config or not self.config.enabled:
                raise RuntimeError("No enabled MQTT configuration")
            self.broker_host = self.config.broker_host or 'localhost'
            self.broker_port = self.config.broker_port or 1883
            return connect_mqtt(
                self.config,
                self._on_connect,
                self._on_disconnect,
                self._on_publish,
            )
        self.mqtt_client = self.mqtt_connection_mgr.connect_with_retry(connect)
        self.connection_count += 1
        self.last_connect_time = time.time()
        self._last_reconnect_fail_msg = None  # Reset so next failure is logged
        logger.info("Connected to MQTT broker at %s:%s", self.broker_host, self.broker_port)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self._mqtt_has_connected_before:
                logger.info("Successfully reconnected to MQTT broker at %s:%s", self.broker_host, self.broker_port)
            else:
                logger.info("Connected to MQTT broker at %s:%s", self.broker_host, self.broker_port)
                self._mqtt_has_connected_before = True
        else:
            errors = {1: "protocol", 2: "client id", 3: "unavailable", 4: "bad auth", 5: "unauthorized"}
            logger.error("MQTT connection failed: %s (rc=%s)", errors.get(rc, rc), rc)

    def _on_disconnect(self, client, userdata, rc):
        self.last_disconnect_time = time.time()
        if rc != 0:
            now = time.time()
            rc_changed = self._last_disconnect_rc != rc
            interval_elapsed = (now - self._last_disconnect_log_time) >= self._disconnect_log_interval
            if rc_changed or interval_elapsed or self._last_disconnect_log_time == 0:
                logger.warning("MQTT disconnected (rc=%s)", rc)
                self._last_disconnect_log_time = now
                self._last_disconnect_rc = rc

    def _on_publish(self, client, userdata, mid):
        logger.debug("Published mid=%s", mid)

    def _ensure_mqtt_connected(self):
        if self.mqtt_client and self.mqtt_client.is_connected():
            return True
        now = time.time()
        if (now - self._last_reconnecting_log_time) >= self._reconnecting_log_interval:
            logger.warning("MQTT disconnected, reconnecting...")
            self._last_reconnecting_log_time = now
        try:
            self._initialize_mqtt()
            return True
        except Exception as e:
            msg = str(e)
            should_log = (
                (now - self._last_reconnect_fail_log_time) >= self._reconnect_fail_log_interval
                or msg != self._last_reconnect_fail_msg
            )
            if should_log:
                logger.error("Reconnection failed: %s", e)
                self._last_reconnect_fail_log_time = now
                self._last_reconnect_fail_msg = msg
            return False

    def _run(self):
        """Main loop: consume Redis, publish to MQTT."""
        logger.info("Starting consumption loop")
        while self.running:
            try:
                if not self._ensure_mqtt_connected():
                    time.sleep(5)
                    continue
                try:
                    self.redis_client.ping()
                except Exception as e:
                    logger.warning("Redis disconnected: %s", e)
                    self._initialize_redis()
                result = self.redis_client.blpop(EVENTS_LIST_KEY, timeout=1)
                if result:
                    channel, event_data = result
                    self._process_event(event_data)
            except Exception as e:
                logger.error("Service loop error: %s", e)
                time.sleep(1)
        logger.info("Consumption loop stopped")

    def _process_event(self, event_data: str):
        try:
            event = json.loads(event_data)
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 0)
            retain = event.get('retain', False)
            if topic and payload is not None:
                self._publish_to_mqtt(topic, payload, qos, retain)
                logger.debug("Published to MQTT: %s", topic)
            else:
                logger.warning("Invalid event: missing topic or payload")
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON: %s", e)
        except Exception as e:
            logger.error("Process event failed: %s", e)

    def _publish_to_mqtt(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        if not self.mqtt_client or not self.mqtt_client.is_connected():
            logger.warning("MQTT not connected, cannot publish")
            return
        try:
            out_payload = payload
            if self.config and getattr(self.config, "use_hmac", False) and getattr(self.config, "hmac_secret_key", None):
                try:
                    from nemo_mqtt.utils import sign_payload_hmac
                except ImportError:
                    from NEMO.plugins.nemo_mqtt.utils import sign_payload_hmac
                try:
                    out_payload = sign_payload_hmac(
                        payload,
                        self.config.hmac_secret_key,
                        getattr(self.config, "hmac_algorithm", "sha256") or "sha256",
                    )
                except Exception as e:
                    logger.warning("HMAC signing failed, publishing unsigned: %s", e)
            result = self.mqtt_client.publish(topic, out_payload, qos=qos, retain=retain)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error("Publish failed: rc=%s", result.rc)
        except Exception as e:
            logger.error("Publish failed: %s", e)

    def stop(self):
        """Stop the bridge service."""
        logger.info("Stopping Redis-MQTT Bridge")
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        if self.redis_client:
            self.redis_client.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        if self.auto_start:
            cleanup_existing_services(self.redis_process)
        release_lock(self.lock_file)
        logger.info("Bridge stopped")


_mqtt_bridge_instance = None
_mqtt_bridge_lock = threading.Lock()


def get_mqtt_bridge():
    """Get or create the global bridge instance."""
    global _mqtt_bridge_instance
    with _mqtt_bridge_lock:
        if _mqtt_bridge_instance is None:
            _mqtt_bridge_instance = RedisMQTTBridge(auto_start=True)
        return _mqtt_bridge_instance


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Redis-MQTT Bridge Service')
    parser.add_argument('--auto', action='store_true', help='AUTO mode: start Redis and Mosquitto')
    args = parser.parse_args()

    service = RedisMQTTBridge(auto_start=args.auto)
    try:
        if service.start():
            mode = "AUTO" if args.auto else "EXTERNAL"
            logger.info("Bridge running in %s mode. Ctrl+C to stop.", mode)
            while service.running:
                time.sleep(1)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
