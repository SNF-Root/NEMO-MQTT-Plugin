#!/usr/bin/env python3
"""
Test the complete MQTT flow
Django signals → Redis → MQTT Publisher → MQTT Broker → Monitor
"""

import redis
import json
import time

def test_complete_flow():
    print("🧪 Testing Complete MQTT Flow")
    print("=" * 50)
    
    # Connect to Redis
    try:
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        redis_client.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    # Create a test message (simulating what Django signals do)
    test_message = {
        "topic": "nemo/tools/test_tool/start",
        "payload": json.dumps({
            "event": "tool_usage_start",
            "usage_id": 999,
            "user_id": 1,
            "user_name": "Test User",
            "tool_id": 1,
            "tool_name": "test_tool",
            "start_time": "2025-10-08T22:15:00.000000+00:00",
            "end_time": None,
            "timestamp": False
        }),
        "qos": 0,
        "retain": False,
        "timestamp": time.time()
    }
    
    print(f"📤 Publishing test message to Redis...")
    print(f"   Topic: {test_message['topic']}")
    print(f"   Payload: {test_message['payload']}")
    
    # Publish to Redis (this is what Django signals do)
    result = redis_client.lpush('NEMO_mqtt_events', json.dumps(test_message))
    print(f"✅ Published to Redis (list length: {result})")
    
    # Wait a moment for the standalone service to process it
    print("⏳ Waiting for standalone service to process...")
    time.sleep(2)
    
    # Check if Redis list is empty (meaning it was consumed)
    list_length = redis_client.llen('NEMO_mqtt_events')
    print(f"📊 Redis list length after processing: {list_length}")
    
    if list_length == 0:
        print("✅ Message was consumed by standalone service")
        print("📡 Check your MQTT monitor to see if the message was published to MQTT")
    else:
        print("❌ Message was not consumed by standalone service")
    
    print("=" * 50)

if __name__ == "__main__":
    test_complete_flow()
