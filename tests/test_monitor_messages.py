#!/usr/bin/env python3
"""
Test script to generate MQTT messages for testing the monitor
"""

import redis
import json
import time
from datetime import datetime

def test_redis_messages():
    """Generate test messages in Redis"""
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        redis_client.ping()
        print("✅ Connected to Redis")
        
        # Generate test messages
        test_messages = [
            {
                'timestamp': datetime.now().isoformat(),
                'topic': 'nemo/tool/test_tool_1',
                'payload': '{"action": "enabled", "tool_id": "test_tool_1", "user": "test_user"}',
                'qos': 0,
                'retain': False
            },
            {
                'timestamp': datetime.now().isoformat(),
                'topic': 'nemo/tool/test_tool_2',
                'payload': '{"action": "disabled", "tool_id": "test_tool_2", "user": "test_user"}',
                'qos': 0,
                'retain': False
            },
            {
                'timestamp': datetime.now().isoformat(),
                'topic': 'nemo/area/test_area',
                'payload': '{"area": "test_area", "status": "active", "users": 3}',
                'qos': 1,
                'retain': True
            }
        ]
        
        # Push messages to Redis
        for i, msg in enumerate(test_messages):
            redis_client.lpush('nemo_mqtt_events', json.dumps(msg))
            print(f"📨 Pushed message {i+1}: {msg['topic']}")
            time.sleep(0.5)
        
        print(f"✅ Generated {len(test_messages)} test messages in Redis")
        
        # Check how many messages are in Redis
        count = redis_client.llen('nemo_mqtt_events')
        print(f"📊 Total messages in Redis: {count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_redis_messages()
