#!/usr/bin/env python3
"""
Simple test to verify Redis connection and message publishing
"""

import redis
import json
import time

def test_redis_and_mqtt():
    print("🧪 Testing Redis and MQTT Message Flow")
    print("=" * 50)
    
    # Test Redis connection
    print("1. Testing Redis connection...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("   ✅ Redis is available")
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        return
    
    # Check current messages
    print("2. Checking current messages in Redis...")
    messages = r.lrange('nemo_mqtt_events', 0, -1)
    print(f"   Current messages in queue: {len(messages)}")
    
    # Publish a test message
    print("3. Publishing test message...")
    test_event = {
        'topic': 'nemo/test/monitor',
        'payload': json.dumps({
            'test': 'message',
            'timestamp': time.time(),
            'source': 'test_script'
        }),
        'qos': 0,
        'retain': False,
        'timestamp': time.time()
    }
    
    try:
        r.lpush('nemo_mqtt_events', json.dumps(test_event))
        print("   ✅ Test message published to Redis")
    except Exception as e:
        print(f"   ❌ Failed to publish message: {e}")
        return
    
    # Check messages again
    print("4. Checking messages after publish...")
    messages = r.lrange('nemo_mqtt_events', 0, -1)
    print(f"   Messages in queue: {len(messages)}")
    
    if messages:
        print("   Recent messages:")
        for i, msg in enumerate(messages[:3], 1):
            try:
                data = json.loads(msg)
                print(f"     {i}. {data.get('topic', 'unknown')} - {data.get('payload', 'unknown')[:50]}...")
            except:
                print(f"     {i}. Raw: {msg[:50]}...")
    
    # Test consuming a message
    print("5. Testing message consumption...")
    try:
        consumed = r.rpop('nemo_mqtt_events')
        if consumed:
            data = json.loads(consumed)
            print(f"   ✅ Consumed message: {data.get('topic', 'unknown')}")
        else:
            print("   ⚠️  No messages to consume")
    except Exception as e:
        print(f"   ❌ Failed to consume message: {e}")
    
    print("\n✅ Test completed!")
    print("\nNext steps:")
    print("1. Make sure the external MQTT service is running")
    print("2. Check the web monitor page")
    print("3. Enable/disable a tool in NEMO to generate real messages")

if __name__ == "__main__":
    test_redis_and_mqtt()

