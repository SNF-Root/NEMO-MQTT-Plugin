#!/usr/bin/env python3
"""
Simple test script to verify the MQTT message flow
Adds a test message to Redis and checks if it gets consumed
"""

import os
import sys
import time
import json
import redis

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mqtt_flow():
    """Test the complete MQTT flow"""
    print("🧪 Testing MQTT Flow")
    print("=" * 30)
    
    # Test Redis connection
    print("🔍 Testing Redis connection...")
    try:
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # Create a test event
    test_event = {
        'topic': 'nemo/test/tool_usage_start',
        'payload': json.dumps({
            "event": "tool_usage_start",
            "usage_id": 999,
            "user_id": 1,
            "user_name": "Test User",
            "tool_id": 1,
            "tool_name": "Test Tool",
            "start_time": "2024-01-01T12:00:00Z",
            "end_time": None,
            "timestamp": time.time()
        }),
        'qos': 0,
        'retain': False,
        'timestamp': time.time()
    }
    
    print(f"📤 Adding test event to Redis: {test_event['topic']}")
    
    try:
        # Add to Redis list
        result = redis_client.lpush('nemo_mqtt_events', json.dumps(test_event))
        print(f"✅ Event added to Redis (list length: {result})")
        
        # Wait a moment for the MQTT service to process it
        print("⏳ Waiting for MQTT service to process...")
        time.sleep(2)
        
        # Check if message was consumed
        list_length = redis_client.llen('nemo_mqtt_events')
        if list_length == 0:
            print("✅ Message was consumed by MQTT service!")
            print("💡 Check your MQTT monitor to see if the message was published")
        else:
            print(f"⚠️  Message still in Redis (list length: {list_length})")
            print("   MQTT service may not be running or processing messages")
        
        return True
    except Exception as e:
        print(f"❌ Failed to add event to Redis: {e}")
        return False

if __name__ == "__main__":
    test_mqtt_flow()
