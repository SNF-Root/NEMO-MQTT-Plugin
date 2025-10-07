#!/usr/bin/env python3
"""
External MQTT Service for NEMO
This service runs independently of Django and maintains a persistent MQTT connection.
It consumes events from Redis and publishes them to the MQTT broker.
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from typing import Optional, Dict, Any

# Add Django project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')

import django
django.setup()

import redis
import paho.mqtt.client as mqtt
from NEMO.plugins.mqtt.models import MQTTConfiguration
from NEMO.plugins.mqtt.utils import get_mqtt_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExternalMQTTService:
    """Standalone MQTT service that maintains persistent connection"""
    
    def __init__(self):
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        self.config = None
        self.thread = None
        self.lock = threading.Lock()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the MQTT service"""
        try:
            # Get MQTT configuration from Django
            self.config = get_mqtt_config()
            if not self.config or not self.config.enabled:
                logger.error("No enabled MQTT configuration found")
                return False
            
            # Initialize Redis client
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            
            # Test Redis connection
            self.redis_client.ping()
            logger.info("Connected to Redis")
            
            # Initialize MQTT client
            self._initialize_mqtt_client()
            
            # Start the service
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logger.info("External MQTT service started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT service: {e}")
            return False
    
    def _initialize_mqtt_client(self):
        """Initialize MQTT client with configuration"""
        try:
            # Create unique client ID
            import socket
            client_id = f"nemo_external_{socket.gethostname()}_{os.getpid()}"
            
            # Create MQTT client
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            
            # Set authentication if configured
            if self.config.username and self.config.password:
                self.mqtt_client.username_pw_set(self.config.username, self.config.password)
            
            # Set TLS if configured
            if self.config.use_tls:
                import ssl
                context = ssl.create_default_context()
                if not self.config.verify_tls:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                self.mqtt_client.tls_set_context(context)
            
            # Connect to broker
            broker_host = self.config.broker_host or 'localhost'
            broker_port = self.config.broker_port or 1883
            keepalive = self.config.keepalive or 60
            
            self.mqtt_client.connect(broker_host, broker_port, keepalive)
            self.mqtt_client.loop_start()
            
            logger.info(f"MQTT client initialized - Broker: {broker_host}:{broker_port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
            # Attempt to reconnect
            self._reconnect()
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published with mid: {mid}")
    
    def _reconnect(self):
        """Attempt to reconnect to MQTT broker"""
        try:
            if self.mqtt_client and not self.mqtt_client.is_connected():
                self.mqtt_client.reconnect()
                logger.info("Reconnected to MQTT broker")
        except Exception as e:
            logger.error(f"Failed to reconnect to MQTT broker: {e}")
    
    def _run(self):
        """Main service loop - consumes events from Redis and publishes to MQTT"""
        logger.info("Starting event consumption loop...")
        
        while self.running:
            try:
                # Check MQTT connection
                if not self.mqtt_client or not self.mqtt_client.is_connected():
                    self._reconnect()
                    time.sleep(1)
                    continue
                
                # Consume events from Redis
                # Using BLPOP with timeout to avoid busy waiting
                result = self.redis_client.blpop('NEMO_mqtt_events', timeout=1)
                
                if result:
                    channel, event_data = result
                    self._process_event(event_data)
                
            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                time.sleep(1)
    
    def _process_event(self, event_data: str):
        """Process a single event from Redis"""
        try:
            event = json.loads(event_data)
            
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 0)
            retain = event.get('retain', False)
            
            if topic and payload is not None:
                self._publish_to_mqtt(topic, payload, qos, retain)
                logger.info(f"Published event to MQTT: {topic}")
            else:
                logger.warning(f"Invalid event data: {event}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event data: {e}")
        except Exception as e:
            logger.error(f"Failed to process event: {e}")
    
    def _publish_to_mqtt(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish message to MQTT broker"""
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logger.error(f"Failed to publish message: {result.rc}")
            else:
                logger.warning("MQTT client not connected, cannot publish message")
        except Exception as e:
            logger.error(f"Failed to publish to MQTT: {e}")
    
    def stop(self):
        """Stop the MQTT service"""
        logger.info("Stopping MQTT service...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")
        
        if self.redis_client:
            self.redis_client.close()
            logger.info("Redis client closed")
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info("MQTT service stopped")

def main():
    """Main entry point"""
    service = ExternalMQTTService()
    
    try:
        if service.start():
            logger.info("External MQTT service is running. Press Ctrl+C to stop.")
            # Keep the main thread alive
            while service.running:
                time.sleep(1)
        else:
            logger.error("Failed to start MQTT service")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        service.stop()

if __name__ == "__main__":
    main()
