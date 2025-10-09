#!/usr/bin/env python3
"""
Simple Standalone MQTT Service
Creates a new MQTT client for each message to avoid connection issues
"""

import os
import sys
import time
import json
import logging
import threading
import redis
import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleStandaloneMQTTService:
    """Simple standalone MQTT service - creates new client for each message"""
    
    def __init__(self):
        self.redis_client = None
        self.running = False
        self.thread = None
        
        # MQTT Configuration
        self.config = {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'username': None,
            'password': None,
            'use_tls': False,
            'keepalive': 60
        }
        
        # Note: Signal handlers removed - not needed when running in background thread
    
    
    def _initialize_redis_client(self):
        """Initialize Redis client"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)  # Use database 1 for plugin isolation
            self.redis_client.ping()
            print("✅ Connected to Redis")
            logger.info("Connected to Redis")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _publish_message(self, topic, payload, qos=1, retain=False):
        """Publish a single message using a new MQTT client"""
        import uuid
        publish_id = str(uuid.uuid4())[:8]
        
        print(f"\n🚀 [SIMPLE-{publish_id}] Publishing message to MQTT")
        print(f"   Topic: {topic}")
        print(f"   Payload: {payload[:100]}{'...' if len(payload) > 100 else ''}")
        
        try:
            # Create a new MQTT client for this message
            client_id = f"simple_mqtt_{publish_id}"
            client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            
            # Set authentication if configured
            if self.config['username'] and self.config['password']:
                client.username_pw_set(self.config['username'], self.config['password'])
            
            # Connect to broker and wait for connection
            client.connect(self.config['broker_host'], self.config['broker_port'], self.config['keepalive'])
            client.loop_start()  # Start the network loop
            
            # Wait for connection to be established
            import time
            for i in range(10):  # Wait up to 1 second
                if client.is_connected():
                    break
                time.sleep(0.1)
            
            if not client.is_connected():
                print(f"❌ [SIMPLE-{publish_id}] Failed to connect to MQTT broker")
                logger.error(f"Failed to connect to MQTT broker")
                client.loop_stop()
                return
            
            # Publish message
            result = client.publish(topic, payload, qos=qos, retain=retain)
            
            # Wait for publish to complete
            result.wait_for_publish(timeout=5)
            
            print(f"   Publish result: {result.rc}")
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ [SIMPLE-{publish_id}] Message published successfully")
                logger.info(f"Message published successfully: {topic}")
            else:
                print(f"❌ [SIMPLE-{publish_id}] Publish failed: {result.rc}")
                logger.error(f"Publish failed: {result.rc}")
            
            # Disconnect
            client.disconnect()
            client.loop_stop()
            
        except Exception as e:
            print(f"❌ [SIMPLE-{publish_id}] Error publishing message: {e}")
            logger.error(f"Error publishing message: {e}")
    
    def _process_event(self, event_data):
        """Process a single event from Redis"""
        import uuid
        event_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [SIMPLE-{event_id}] Processing event from Redis")
        
        try:
            event = json.loads(event_data)
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 1)
            retain = event.get('retain', False)
            
            if topic and payload is not None:
                self._publish_message(topic, payload, qos, retain)
            else:
                print(f"❌ [SIMPLE-{event_id}] Invalid event data")
                logger.warning(f"Invalid event data: {event}")
                
        except json.JSONDecodeError as e:
            print(f"❌ [SIMPLE-{event_id}] JSON parse error: {e}")
            logger.error(f"Failed to parse event data: {e}")
        except Exception as e:
            print(f"❌ [SIMPLE-{event_id}] Processing error: {e}")
            logger.error(f"Failed to process event: {e}")
    
    def _run(self):
        """Main service loop - consumes events from Redis and publishes to MQTT"""
        print("🔍 Starting simple Redis consumption loop...")
        logger.info("Starting simple event consumption loop...")
        
        while self.running:
            try:
                # Consume events from Redis using BLPOP
                result = self.redis_client.blpop('NEMO_mqtt_events', timeout=1)
                
                if result:
                    channel, event_data = result
                    print(f"📨 Received message from Redis: {channel}")
                    self._process_event(event_data)
                else:
                    # Only print every 10 seconds to avoid spam
                    if int(time.time()) % 10 == 0:
                        list_length = self.redis_client.llen('NEMO_mqtt_events')
                        print(f"🔍 No messages in Redis, waiting... (list length: {list_length})")
                
            except Exception as e:
                print(f"❌ Error in service loop: {e}")
                logger.error(f"Error in service loop: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the MQTT service"""
        print("🚀 Starting Simple MQTT service...")
        logger.info("Starting Simple MQTT service...")
        
        try:
            # Initialize Redis
            self._initialize_redis_client()
            
            # Start the service
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            print("✅ Simple MQTT service started successfully")
            logger.info("Simple MQTT service started successfully")
            print("🔍 Simple MQTT service is running. Press Ctrl+C to stop.")
            logger.info("Simple MQTT service is running. Press Ctrl+C to stop.")
            
        except Exception as e:
            print(f"❌ Failed to start Simple MQTT service: {e}")
            logger.error(f"Failed to start Simple MQTT service: {e}")
            raise
    
    def stop(self):
        """Stop the MQTT service"""
        print("🛑 Stopping Simple MQTT service...")
        logger.info("Stopping Simple MQTT service...")
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("✅ Simple MQTT service stopped")
        logger.info("Simple MQTT service stopped")

def main():
    """Main function"""
    service = SimpleStandaloneMQTTService()
    
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
