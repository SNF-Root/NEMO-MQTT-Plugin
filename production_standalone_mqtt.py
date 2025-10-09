#!/usr/bin/env python3
"""
Production Standalone MQTT Service
Uses persistent connection with proper error handling and reconnection logic
"""

import os
import sys
import time
import json
import logging
import signal
import threading
import redis
import paho.mqtt.client as mqtt
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductionStandaloneMQTTService:
    """Production standalone MQTT service with persistent connection"""
    
    def __init__(self):
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        self.thread = None
        self.connection_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1  # seconds
        
        # MQTT Configuration
        self.config = {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'username': None,
            'password': None,
            'use_tls': False,
            'keepalive': 60,
            'client_id': 'nemo_production_client'
        }
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def _initialize_redis_client(self):
        """Initialize Redis client"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis_client.ping()
            print("✅ Connected to Redis")
            logger.info("Connected to Redis")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _initialize_mqtt_client(self):
        """Initialize MQTT client with persistent connection"""
        try:
            # Create unique client ID
            import socket
            client_id = f"{self.config['client_id']}_{socket.gethostname()}_{os.getpid()}"
            
            # Create MQTT client
            self.mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            
            # Set authentication if configured
            if self.config['username'] and self.config['password']:
                self.mqtt_client.username_pw_set(self.config['username'], self.config['password'])
            
            # Connect to broker
            self.mqtt_client.connect(self.config['broker_host'], self.config['broker_port'], self.config['keepalive'])
            self.mqtt_client.loop_start()
            
            # Wait for connection to be established
            time.sleep(0.5)
            
            if self.mqtt_client.is_connected():
                print("✅ Connected to MQTT broker")
                logger.info("Connected to MQTT broker")
                self.reconnect_attempts = 0
            else:
                raise Exception("Failed to establish MQTT connection")
                
        except Exception as e:
            print(f"❌ Failed to connect to MQTT broker: {e}")
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print("✅ MQTT broker connection established")
            logger.info("Connected to MQTT broker")
            self.reconnect_attempts = 0
        else:
            print(f"❌ MQTT broker connection failed: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            print(f"⚠️  MQTT broker disconnected: {rc}")
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
            # Trigger reconnection in the main loop
            self._schedule_reconnect()
        else:
            print("✅ MQTT broker disconnected normally")
            logger.info("MQTT broker disconnected normally")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published with mid: {mid}")
    
    def _schedule_reconnect(self):
        """Schedule a reconnection attempt"""
        self.reconnect_attempts += 1
        if self.reconnect_attempts <= self.max_reconnect_attempts:
            print(f"🔍 Scheduling reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
            logger.info(f"Scheduling reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        else:
            print(f"❌ Max reconnection attempts reached ({self.max_reconnect_attempts})")
            logger.error(f"Max reconnection attempts reached ({self.max_reconnect_attempts})")
    
    def _ensure_connection(self):
        """Ensure MQTT connection is active, reconnect if necessary"""
        with self.connection_lock:
            if not self.mqtt_client or not self.mqtt_client.is_connected():
                if self.reconnect_attempts <= self.max_reconnect_attempts:
                    try:
                        print(f"🔍 Attempting reconnection ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
                        self._initialize_mqtt_client()
                        return True
                    except Exception as e:
                        print(f"❌ Reconnection failed: {e}")
                        logger.error(f"Reconnection failed: {e}")
                        time.sleep(self.reconnect_delay)
                        return False
                else:
                    print("❌ Max reconnection attempts exceeded")
                    return False
            return True
    
    def _publish_message(self, topic, payload, qos=1, retain=False):
        """Publish a message using the persistent connection"""
        import uuid
        publish_id = str(uuid.uuid4())[:8]
        
        print(f"📤 [PROD-{publish_id}] Publishing: {topic}")
        
        # Ensure connection is active
        if not self._ensure_connection():
            print(f"❌ [PROD-{publish_id}] Cannot publish - no MQTT connection")
            return False
        
        try:
            result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ [PROD-{publish_id}] Message queued for publishing")
                logger.info(f"Message queued for publishing: {topic}")
                return True
            else:
                print(f"❌ [PROD-{publish_id}] Publish failed: {result.rc}")
                logger.error(f"Publish failed: {result.rc}")
                return False
                
        except Exception as e:
            print(f"❌ [PROD-{publish_id}] Error publishing: {e}")
            logger.error(f"Error publishing message: {e}")
            return False
    
    def _process_event(self, event_data):
        """Process a single event from Redis"""
        import uuid
        event_id = str(uuid.uuid4())[:8]
        
        print(f"🔍 [PROD-{event_id}] Processing event from Redis")
        
        try:
            event = json.loads(event_data)
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 1)
            retain = event.get('retain', False)
            
            if topic and payload is not None:
                success = self._publish_message(topic, payload, qos, retain)
                if not success:
                    # If publish failed, we could implement retry logic here
                    print(f"⚠️  [PROD-{event_id}] Message publish failed, will retry on next connection")
            else:
                print(f"❌ [PROD-{event_id}] Invalid event data")
                logger.warning(f"Invalid event data: {event}")
                
        except json.JSONDecodeError as e:
            print(f"❌ [PROD-{event_id}] JSON parse error: {e}")
            logger.error(f"Failed to parse event data: {e}")
        except Exception as e:
            print(f"❌ [PROD-{event_id}] Processing error: {e}")
            logger.error(f"Failed to process event: {e}")
    
    def _run(self):
        """Main service loop - consumes events from Redis and publishes to MQTT"""
        print("🔍 Starting production Redis consumption loop...")
        logger.info("Starting production event consumption loop...")
        
        while self.running:
            try:
                # Consume events from Redis using BLPOP
                result = self.redis_client.blpop('NEMO_mqtt_events', timeout=1)
                
                if result:
                    channel, event_data = result
                    print(f"📨 Received message from Redis: {channel}")
                    self._process_event(event_data)
                else:
                    # Only print every 30 seconds to avoid spam
                    if int(time.time()) % 30 == 0:
                        list_length = self.redis_client.llen('NEMO_mqtt_events')
                        print(f"🔍 No messages in Redis, waiting... (list length: {list_length})")
                
            except Exception as e:
                print(f"❌ Error in service loop: {e}")
                logger.error(f"Error in service loop: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the MQTT service"""
        print("🚀 Starting Production MQTT service...")
        logger.info("Starting Production MQTT service...")
        
        try:
            # Initialize Redis
            self._initialize_redis_client()
            
            # Initialize MQTT
            self._initialize_mqtt_client()
            
            # Start the service
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            print("✅ Production MQTT service started successfully")
            logger.info("Production MQTT service started successfully")
            print("🔍 Production MQTT service is running. Press Ctrl+C to stop.")
            logger.info("Production MQTT service is running. Press Ctrl+C to stop.")
            
        except Exception as e:
            print(f"❌ Failed to start Production MQTT service: {e}")
            logger.error(f"Failed to start Production MQTT service: {e}")
            raise
    
    def stop(self):
        """Stop the MQTT service"""
        print("🛑 Stopping Production MQTT service...")
        logger.info("Stopping Production MQTT service...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.thread:
            self.thread.join(timeout=5)
        
        print("✅ Production MQTT service stopped")
        logger.info("Production MQTT service stopped")

def main():
    """Main function"""
    service = ProductionStandaloneMQTTService()
    
    try:
        service.start()
        # Keep the main thread alive
        while service.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
        service.stop()
    except Exception as e:
        print(f"❌ Service error: {e}")
        logger.error(f"Service error: {e}")
        service.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
