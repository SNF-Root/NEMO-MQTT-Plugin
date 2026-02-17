"""
Redis-based MQTT Event Publisher for NEMO
This module handles publishing events to Redis instead of directly to MQTT.
The external MQTT service will consume these events and publish them to the MQTT broker.
"""

import json
import logging
import redis
import time
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Redis list for monitor UI (copy of recent publishes; bridge still consumes NEMO_mqtt_events only)
MONITOR_LIST_KEY = 'NEMO_mqtt_monitor'
MONITOR_LIST_MAXLEN = 100

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
            
            # Publish to Redis list (consumed by bridge)
            result = self.redis_client.lpush('NEMO_mqtt_events', json.dumps(event))
            print(f"📤 [REDIS-{redis_id}] Redis lpush successful: {topic} (list length: {result})")
            print(f"   📤 Message added to Redis list 'NEMO_mqtt_events'")
            print(f"   🔄 Next: Standalone service will consume this message")
            logger.debug(f"Published event to Redis: {topic}")

            # Copy to monitor list for web UI (stream of what NEMO publishes)
            self.redis_client.lpush(MONITOR_LIST_KEY, json.dumps(event))
            self.redis_client.ltrim(MONITOR_LIST_KEY, 0, MONITOR_LIST_MAXLEN - 1)

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
        except Exception:
            return False

    def get_monitor_messages(self) -> list:
        """
        Return recent events from the monitor list (what NEMO has published to Redis).
        Used by the web monitor to show a stream of plugin output without subscribing to MQTT.
        """
        if not self.redis_client:
            return []
        try:
            self.redis_client.ping()
        except Exception:
            return []
        raw = self.redis_client.lrange(MONITOR_LIST_KEY, 0, -1)
        messages = []
        for i, s in enumerate(raw):
            try:
                event = json.loads(s)
                ts = event.get('timestamp')
                if ts is not None:
                    timestamp = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
                else:
                    timestamp = None
                messages.append({
                    'id': i + 1,
                    'timestamp': timestamp,
                    'source': 'Redis',
                    'topic': event.get('topic', ''),
                    'payload': event.get('payload', ''),
                    'qos': event.get('qos', 0),
                    'retain': event.get('retain', False),
                })
            except (json.JSONDecodeError, TypeError):
                continue
        return messages

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
