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
        if not self.redis_client:
            logger.error("Redis client not available")
            return False
        
        try:
            event = {
                'topic': topic,
                'payload': payload,
                'qos': qos,
                'retain': retain,
                'timestamp': time.time()
            }
            
            # Publish to Redis list
            self.redis_client.lpush('nemo_mqtt_events', json.dumps(event))
            print(f"📤 Redis lpush successful: {topic}")
            logger.debug(f"Published event to Redis: {topic}")
            return True
            
        except Exception as e:
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
