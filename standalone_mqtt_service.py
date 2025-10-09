#!/usr/bin/env python3
"""
Standalone MQTT Service for Development
This service works without Django/NEMO for development and testing.
Uses hardcoded configuration that can be easily modified.
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StandaloneMQTTService:
    """Standalone MQTT service for development - no Django dependencies"""
    
    def __init__(self):
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        self.thread = None
        
        # MQTT Configuration (modify these for your setup)
        self.config = {
            'broker_host': 'localhost',
            'broker_port': 1883,
            'username': None,  # Set if your broker requires auth
            'password': None,  # Set if your broker requires auth
            'use_tls': False,
            'keepalive': 60,
            'client_id': 'nemo_dev_client'
        }
        
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
            print("🚀 Starting Standalone MQTT Service (Development Mode)")
            print("=" * 60)
            print("📋 Configuration:")
            print(f"   Broker: {self.config['broker_host']}:{self.config['broker_port']}")
            print(f"   Auth: {'Yes' if self.config['username'] else 'No'}")
            print(f"   TLS: {'Yes' if self.config['use_tls'] else 'No'}")
            print("=" * 60)
            
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
            
            print("✅ Standalone MQTT service started successfully")
            print("📋 Consuming from Redis → Publishing to MQTT")
            print("=" * 60)
            logger.info("Standalone MQTT service started successfully")
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
            client_id = f"{self.config['client_id']}_{socket.gethostname()}_{os.getpid()}"
            print(f"   Client ID: {client_id}")
            
            # Create MQTT client with protocol version
            self.mqtt_client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            
            # Set authentication if configured
            if self.config['username'] and self.config['password']:
                print(f"   Authentication: {self.config['username']}")
                self.mqtt_client.username_pw_set(self.config['username'], self.config['password'])
            else:
                print("   Authentication: None")
            
            # Set TLS if configured
            if self.config['use_tls']:
                print("   TLS: Enabled")
                import ssl
                context = ssl.create_default_context()
                self.mqtt_client.tls_set_context(context)
            else:
                print("   TLS: Disabled")
            
            # Connect to broker
            broker_host = self.config['broker_host']
            broker_port = self.config['broker_port']
            keepalive = self.config['keepalive']
            
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
        print(f"🔍 [MQTT-CONNECT] Connection callback triggered")
        print(f"   Return code: {rc}")
        print(f"   Client connected: {client.is_connected()}")
        print(f"   Flags: {flags}")
        
        if rc == 0:
            print("✅ MQTT broker connection established")
            logger.info("Connected to MQTT broker")
        else:
            print(f"❌ MQTT broker connection failed: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        print(f"🔍 [MQTT-DISCONNECT] Disconnection callback triggered")
        print(f"   Return code: {rc}")
        print(f"   Client connected: {client.is_connected()}")
        
        if rc != 0:
            print(f"⚠️  MQTT broker disconnected: {rc}")
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
        else:
            print("✅ MQTT broker disconnected normally")
            logger.info("MQTT broker disconnected normally")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published with mid: {mid}")
    
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
    
    def _reconnect(self):
        """Attempt to reconnect to MQTT broker"""
        try:
            if self.mqtt_client and not self.mqtt_client.is_connected():
                print("🔍 Attempting to reconnect to MQTT broker...")
                self.mqtt_client.reconnect()
                # Wait for connection to be established
                time.sleep(0.5)
                if self.mqtt_client.is_connected():
                    print("✅ Reconnected to MQTT broker")
                    logger.info("Reconnected to MQTT broker")
                else:
                    print("❌ Reconnection failed - client still not connected")
                    logger.error("Reconnection failed - client still not connected")
            else:
                print("🔍 MQTT client already connected or not initialized")
        except Exception as e:
            print(f"❌ Failed to reconnect to MQTT broker: {e}")
            logger.error(f"Failed to reconnect to MQTT broker: {e}")
    
    def _process_event(self, event_data: str):
        """Process a single event from Redis"""
        import uuid
        mqtt_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [STANDALONE-{mqtt_id}] Processing event from Redis")
        print(f"   Raw event data: {event_data}")
        
        print(f"\n" + "="*80)
        print(f"🔍 [MQTT-{mqtt_id}] PROCESSING EVENT FROM REDIS")
        print(f"="*80)
        print(f"📥 Raw Redis data: {event_data}")
        print(f"📏 Data length: {len(event_data)} characters")
        
        # Check if this is a START or END event
        if '"event": "tool_usage_start"' in event_data:
            print(f"🔍 [MQTT-{mqtt_id}] DETECTED: START EVENT")
        elif '"event": "tool_usage_end"' in event_data:
            print(f"🔍 [MQTT-{mqtt_id}] DETECTED: END EVENT")
        else:
            print(f"🔍 [MQTT-{mqtt_id}] DETECTED: OTHER EVENT")
        
        try:
            event = json.loads(event_data)
            print(f"✅ [MQTT-{mqtt_id}] JSON parsing successful")
            print(f"📋 Parsed event: {json.dumps(event, indent=2)}")
            
            topic = event.get('topic')
            payload = event.get('payload')
            qos = event.get('qos', 0)
            retain = event.get('retain', False)
            event_id = event.get('id', 'unknown')
            
            print(f"\n🔍 [MQTT-{mqtt_id}] EXTRACTED VALUES:")
            print(f"   📍 Topic: '{topic}'")
            print(f"   📦 Payload: '{payload}'")
            print(f"   🎯 QoS: {qos}")
            print(f"   🔒 Retain: {retain}")
            print(f"   🆔 Event ID: {event_id}")
            print(f"   📏 Payload length: {len(str(payload))} characters")
            
            if topic and payload is not None:
                print(f"\n🚀 [MQTT-{mqtt_id}] PUBLISHING TO MQTT BROKER...")
                print(f"   📍 Publishing to topic: '{topic}'")
                print(f"   📦 Payload: {str(payload)[:100]}{'...' if len(str(payload)) > 100 else ''}")
                
                self._publish_to_mqtt(topic, payload, qos, retain)
                print(f"✅ [MQTT-{mqtt_id}] SUCCESSFULLY PUBLISHED TO MQTT")
                print(f"   📍 Topic: {topic}")
                logger.info(f"Published event to MQTT: {topic}")
            else:
                print(f"❌ [MQTT-{mqtt_id}] INVALID EVENT DATA")
                print(f"   Topic valid: {bool(topic)}")
                print(f"   Payload valid: {payload is not None}")
                logger.warning(f"Invalid event data: {event}")
                
        except json.JSONDecodeError as e:
            print(f"❌ [MQTT-{mqtt_id}] JSON PARSE ERROR")
            print(f"   Error: {e}")
            print(f"   Raw data: {event_data}")
            logger.error(f"Failed to parse event data: {e}")
        except Exception as e:
            print(f"❌ [MQTT-{mqtt_id}] PROCESSING ERROR")
            print(f"   Error: {e}")
            print(f"   Event data: {event_data}")
            logger.error(f"Failed to process event: {e}")
        
        print(f"="*80)
    
    def _publish_to_mqtt(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish message to MQTT broker"""
        import uuid
        publish_id = str(uuid.uuid4())[:8]
        
        print(f"\n" + "="*80)
        print(f"🚀 [PUBLISH-{publish_id}] PUBLISHING TO MQTT BROKER")
        print(f"="*80)
        print(f"📍 Topic: '{topic}'")
        print(f"🎯 QoS: {qos}")
        print(f"🔒 Retain: {retain}")
        print(f"📦 Payload: {payload}")
        print(f"📏 Payload length: {len(payload)} characters")
        
        # Check MQTT client status
        print(f"\n🔍 [PUBLISH-{publish_id}] MQTT CLIENT STATUS:")
        print(f"   Client exists: {self.mqtt_client is not None}")
        if self.mqtt_client:
            print(f"   Client connected: {self.mqtt_client.is_connected()}")
            print(f"   Client ID: {getattr(self.mqtt_client, '_client_id', 'unknown')}")
        
        # Try to publish with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check connection before each attempt
                if not self.mqtt_client or not self.mqtt_client.is_connected():
                    print(f"🔍 [PUBLISH-{publish_id}] Attempt {attempt + 1}: MQTT client not connected, attempting reconnect...")
                    self._reconnect()
                    time.sleep(0.5)  # Wait for reconnection
                    
                    if not self.mqtt_client or not self.mqtt_client.is_connected():
                        print(f"❌ [PUBLISH-{publish_id}] Attempt {attempt + 1}: Still not connected after reconnect")
                        if attempt < max_retries - 1:
                            time.sleep(1)  # Wait before retry
                            continue
                        else:
                            print(f"❌ [PUBLISH-{publish_id}] ERROR - MQTT CLIENT NOT CONNECTED after {max_retries} attempts")
                            logger.warning("MQTT client not connected, cannot publish message")
                            return
                
                print(f"\n🚀 [PUBLISH-{publish_id}] Attempt {attempt + 1}: ATTEMPTING TO PUBLISH...")
                result = self.mqtt_client.publish(topic, payload, qos=qos, retain=retain)
                
                print(f"\n📊 [PUBLISH-{publish_id}] PUBLISH RESULT:")
                print(f"   Result object: {result}")
                print(f"   Message ID: {result.mid}")
                print(f"   Return code: {result.rc}")
                print(f"   Is published: {result.is_published()}")
                
                # Check return codes
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"✅ [PUBLISH-{publish_id}] SUCCESS - Message queued for publishing")
                    logger.info(f"Message queued for publishing: {topic}")
                    return  # Success, exit retry loop
                elif result.rc == mqtt.MQTT_ERR_NO_CONN:
                    print(f"❌ [PUBLISH-{publish_id}] Attempt {attempt + 1}: No connection to broker")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        logger.error("No connection to MQTT broker")
                        return
                elif result.rc == mqtt.MQTT_ERR_QUEUE_SIZE:
                    print(f"❌ [PUBLISH-{publish_id}] Attempt {attempt + 1}: Message queue is full")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        logger.error("MQTT message queue is full")
                        return
                else:
                    print(f"❌ [PUBLISH-{publish_id}] Attempt {attempt + 1}: Unknown error code: {result.rc}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        logger.error(f"Unknown MQTT error: {result.rc}")
                        return
                        
            except Exception as e:
                print(f"❌ [PUBLISH-{publish_id}] Attempt {attempt + 1}: Exception during publish: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                    continue
                else:
                    logger.error(f"Failed to publish to MQTT after {max_retries} attempts: {e}")
                    return
        
        print(f"="*80)
    
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
    service = StandaloneMQTTService()
    
    try:
        if service.start():
            print("🚀 Standalone MQTT service is running. Press Ctrl+C to stop.")
            logger.info("Standalone MQTT service is running. Press Ctrl+C to stop.")
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
