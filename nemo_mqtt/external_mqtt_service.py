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
            print("🚀 Starting External MQTT Service")
            print("=" * 50)
            
            # Get MQTT configuration from Django
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
            
            # Initialize Redis client
            print("🔍 Connecting to Redis...")
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            
            # Test Redis connection
            self.redis_client.ping()
            print("✅ Connected to Redis")
            logger.info("Connected to Redis")
            
            # Initialize MQTT client
            print("🔍 Connecting to MQTT broker...")
            self._initialize_mqtt_client()
            
            # Start the service
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            print("✅ External MQTT service started successfully")
            print("📋 Consuming from Redis → Publishing to MQTT")
            print("=" * 50)
            logger.info("External MQTT service started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start MQTT service: {e}")
            logger.error(f"Failed to start MQTT service: {e}")
            return False
    
    def _initialize_mqtt_client(self):
        """Initialize MQTT client with configuration"""
        try:
            # Create unique client ID
            import socket
            client_id = f"nemo_external_{socket.gethostname()}_{os.getpid()}"
            print(f"   Client ID: {client_id}")
            
            # Create MQTT client
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            
            # Set authentication if configured
            if self.config.username and self.config.password:
                print(f"   Authentication: {self.config.username}")
                self.mqtt_client.username_pw_set(self.config.username, self.config.password)
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
                self.mqtt_client.tls_set_context(context)
            else:
                print("   TLS: Disabled")
            
            # Connect to broker
            broker_host = self.config.broker_host or 'localhost'
            broker_port = self.config.broker_port or 1883
            keepalive = self.config.keepalive or 60
            
            print(f"   Connecting to: {broker_host}:{broker_port}")
            self.mqtt_client.connect(broker_host, broker_port, keepalive)
            self.mqtt_client.loop_start()
            
            print(f"✅ Connected to MQTT broker ({broker_host}:{broker_port})")
            logger.info(f"MQTT client initialized - Broker: {broker_host}:{broker_port}")
            
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            logger.error(f"Failed to initialize MQTT client: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print("✅ MQTT broker connection established")
            logger.info("Connected to MQTT broker")
        else:
            print(f"❌ MQTT broker connection failed: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            print(f"⚠️  MQTT broker disconnected: {rc}")
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
                print("🔍 Attempting to reconnect to MQTT broker...")
                self.mqtt_client.reconnect()
                print("✅ Reconnected to MQTT broker")
                logger.info("Reconnected to MQTT broker")
        except Exception as e:
            print(f"❌ Failed to reconnect to MQTT broker: {e}")
            logger.error(f"Failed to reconnect to MQTT broker: {e}")
    
    def _run(self):
        """Main service loop - consumes events from Redis and publishes to MQTT"""
        print("🔍 Starting Redis consumption loop...")
        logger.info("Starting event consumption loop...")
        
        while self.running:
            try:
                # Check MQTT connection
                if not self.mqtt_client or not self.mqtt_client.is_connected():
                    print("🔍 MQTT client not connected, attempting reconnect...")
                    self._reconnect()
                    time.sleep(1)
                    continue
                
                # Check Redis list length before consuming
                list_length = self.redis_client.llen('NEMO_mqtt_events')
                if list_length > 0:
                    print(f"🔍 Found {list_length} messages in Redis, consuming...")
                
                # Consume events from Redis using BLPOP
                result = self.redis_client.blpop('NEMO_mqtt_events', timeout=1)
                
                if result:
                    channel, event_data = result
                    print(f"📨 Received message from Redis: {channel}")
                    self._process_event(event_data)
                else:
                    # Only print every 10 seconds to avoid spam
                    if int(time.time()) % 10 == 0:
                        print(f"🔍 No messages in Redis, waiting... (list length: {self.redis_client.llen('NEMO_mqtt_events')})")
                
            except Exception as e:
                print(f"❌ Error in service loop: {e}")
                logger.error(f"Error in service loop: {e}")
                time.sleep(1)
    
    def _process_event(self, event_data: str):
        """Process a single event from Redis"""
        import uuid
        mqtt_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [MQTT-{mqtt_id}] Processing event from Redis")
        print(f"   Raw data: {event_data[:200]}{'...' if len(event_data) > 200 else ''}")
        
        try:
            event = json.loads(event_data)
            print(f"🔍 [MQTT-{mqtt_id}] Event parsed successfully")
            print(f"   Event: {json.dumps(event, indent=2)}")
            
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 0)
            retain = event.get('retain', False)
            
            print(f"🔍 [MQTT-{mqtt_id}] Extracted values:")
            print(f"   Topic: {topic}")
            print(f"   QoS: {qos}")
            print(f"   Retain: {retain}")
            print(f"   Payload: {payload[:200]}{'...' if len(str(payload)) > 200 else ''}")
            
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
        print(f"   Payload: {payload[:200]}{'...' if len(payload) > 200 else ''}")
        
        try:
            if self.mqtt_client and self.mqtt_client.is_connected():
                print(f"🔍 [PUBLISH-{publish_id}] MQTT client is connected, publishing...")
                result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
                print(f"🔍 [PUBLISH-{publish_id}] Publish result: {result}")
                print(f"   Message ID: {result.mid}")
                print(f"   Return code: {result.rc}")
                
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"❌ [PUBLISH-{publish_id}] Failed to publish message: {result.rc}")
                    logger.error(f"Failed to publish message: {result.rc}")
                else:
                    print(f"✅ [PUBLISH-{publish_id}] Message published successfully to MQTT broker")
            else:
                print(f"❌ [PUBLISH-{publish_id}] MQTT client not connected, cannot publish message")
                print(f"   Client exists: {self.mqtt_client is not None}")
                if self.mqtt_client:
                    print(f"   Client connected: {self.mqtt_client.is_connected()}")
                logger.warning("MQTT client not connected, cannot publish message")
        except Exception as e:
            print(f"❌ [PUBLISH-{publish_id}] Failed to publish to MQTT: {e}")
            logger.error(f"Failed to publish to MQTT: {e}")
    
    def stop(self):
        """Stop the MQTT service"""
        print("🛑 Stopping MQTT service...")
        logger.info("Stopping MQTT service...")
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
        
        print("✅ MQTT service stopped")
        logger.info("MQTT service stopped")

def main():
    """Main entry point"""
    service = ExternalMQTTService()
    
    try:
        if service.start():
            print("🚀 External MQTT service is running. Press Ctrl+C to stop.")
            logger.info("External MQTT service is running. Press Ctrl+C to stop.")
            # Keep the main thread alive
            while service.running:
                time.sleep(1)
        else:
            print("❌ Failed to start MQTT service")
            logger.error("Failed to start MQTT service")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Received keyboard interrupt")
        logger.info("Received keyboard interrupt")
    finally:
        service.stop()

if __name__ == "__main__":
    main()
