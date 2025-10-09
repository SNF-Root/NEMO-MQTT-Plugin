#!/usr/bin/env python3
"""
Direct MQTT Publisher
Publishes messages directly to MQTT broker to test the monitor
"""

import paho.mqtt.client as mqtt
import json
import time

def publish_test_message():
    print("📤 Publishing test message directly to MQTT...")
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    
    try:
        client.connect("localhost", 1883, 60)
        
        # Test message
        message = {
            "event": "tool_usage_start",
            "usage_id": 888,
            "user_id": 1,
            "user_name": "Direct Test User",
            "tool_id": 1,
            "tool_name": "direct_test_tool",
            "start_time": "2025-10-08T22:20:00.000000+00:00",
            "end_time": None,
            "timestamp": False
        }
        
        topic = "nemo/tools/direct_test_tool/start"
        payload = json.dumps(message)
        
        print(f"   Topic: {topic}")
        print(f"   Payload: {payload}")
        
        result = client.publish(topic, payload)
        print(f"✅ Published with result: {result}")
        
        client.disconnect()
        print("📡 Message published! Check your monitor.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    publish_test_message()
