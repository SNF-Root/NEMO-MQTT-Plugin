"""
Redis-based MQTT Event Publisher for NEMO
This module handles publishing events to Redis instead of directly to MQTT.
The external MQTT service will consume these events and publish them to the MQTT broker.
"""

import json
import logging
import redis
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class RedisMQTTPublisher:
    """Publishes MQTT events to Redis for consumption by external MQTT service"""
    
    def __init__(self):
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis client with retry logic"""
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                self.redis_client = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=1,  # Use database 1 for plugin isolation
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Connected to Redis for MQTT event publishing")
                return
            except Exception as e:
                logger.warning(f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to connect to Redis after {max_retries} attempts: {e}")
                    self.redis_client = None
    
    def publish_event(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """
        Publish an event to Redis for consumption by external MQTT service
        
        Args:
            topic: MQTT topic
            payload: Message payload
            qos: Quality of Service level
            retain: Whether to retain the message
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        import uuid
        redis_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [REDIS-{redis_id}] Starting Redis publish process")
        print(f"   Topic: {topic}")
        print(f"   QoS: {qos}")
        print(f"   Retain: {retain}")
        print(f"   Payload: {payload[:100]}{'...' if len(payload) > 100 else ''}")
        
        if not self.redis_client:
            print(f"❌ [REDIS-{redis_id}] Redis client not available, attempting to reconnect...")
            logger.warning("Redis client not available, attempting to reconnect...")
            self._initialize_redis()
            if not self.redis_client:
                print(f"❌ [REDIS-{redis_id}] Redis reconnection failed")
                logger.error("Redis reconnection failed")
                return False
        
        try:
            # Test Redis connection first
            self.redis_client.ping()
            print(f"✅ [REDIS-{redis_id}] Redis connection test successful")
            
            event = {
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'retain': retain,
                'timestamp': time.time()
            }
            
            print(f"🔍 [REDIS-{redis_id}] Event object created, pushing to Redis list...")
            print(f"   Event: {json.dumps(event, indent=2)}")
            
            # Publish to Redis list
            result = self.redis_client.lpush('NEMO_mqtt_events', json.dumps(event))
            print(f"📤 [REDIS-{redis_id}] Redis lpush successful: {topic} (list length: {result})")
            print(f"   📤 Message added to Redis list 'NEMO_mqtt_events'")
            print(f"   🔄 Next: Standalone service will consume this message")
            logger.debug(f"Published event to Redis: {topic}")
            
            # Verify the message was added
            list_length = self.redis_client.llen('NEMO_mqtt_events')
            print(f"🔍 [REDIS-{redis_id}] Redis list 'NEMO_mqtt_events' now has {list_length} messages")
            print(f"   ⏳ Waiting for standalone service to consume...")
            
            return True
            
        except Exception as e:
            print(f"❌ [REDIS-{redis_id}] Failed to publish event to Redis: {e}")
            logger.error(f"Failed to publish event to Redis: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except:
            return False

# Global instance
redis_publisher = RedisMQTTPublisher()

def publish_mqtt_event(topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
    """
    Convenience function to publish MQTT events via Redis
    
    Args:
        topic: MQTT topic
        payload: Message payload
        qos: Quality of Service level
        retain: Whether to retain the message
        
    Returns:
        bool: True if published successfully, False otherwise
    """
    return redis_publisher.publish_event(topic, payload, qos, retain)
