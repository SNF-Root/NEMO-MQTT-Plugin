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
        """Initialize Redis client"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for MQTT event publishing")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
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
        print(f"   Payload: {payload[:200]}{'...' if len(payload) > 200 else ''}")
        
        if not self.redis_client:
            print(f"❌ [REDIS-{redis_id}] Redis client not available")
            logger.error("Redis client not available")
            return False
        
        try:
            # Test Redis connection first
            self.redis_client.ping()
            print(f"🔍 [REDIS-{redis_id}] Redis connection test successful")
            
            event = {
                'id': redis_id,
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'retain': retain,
                'timestamp': time.time()
            }
            
            print(f"🔍 [REDIS-{redis_id}] Event object created, pushing to Redis list...")
            
            # Publish to Redis list
            result = self.redis_client.lpush('NEMO_mqtt_events', json.dumps(event))
            print(f"📤 [REDIS-{redis_id}] Redis lpush successful: {topic} (list length: {result})")
            logger.debug(f"Published event to Redis: {topic}")
            
            # Verify the message was added
            list_length = self.redis_client.llen('NEMO_mqtt_events')
            print(f"🔍 [REDIS-{redis_id}] Redis list 'NEMO_mqtt_events' now has {list_length} messages")
            
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
