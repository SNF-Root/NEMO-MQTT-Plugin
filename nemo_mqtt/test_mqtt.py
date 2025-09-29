#!/usr/bin/env python3
"""
NEMO MQTT Test Script
Simple script to test MQTT functionality and monitor events.
"""

import os
import sys
import time
import signal
import json
import paho.mqtt.client as mqtt
import redis
import threading
from datetime import datetime

# Add Django to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

class MQTTTester:
    def __init__(self):
        self.mqtt_client = None
        self.redis_client = None
        self.running = False
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis_client.ping()
            print("✅ Redis connected")
            return True
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.connect('localhost', 1883, 60)
            self.mqtt_client.loop_start()
            time.sleep(1)
            if self.mqtt_client.is_connected():
                print("✅ MQTT connected")
                return True
            else:
                print("❌ MQTT connection failed")
                return False
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            client.subscribe('nemo/tools/+/+')
            print("🔍 Subscribed to nemo/tools/+/+")
        else:
            print(f"❌ MQTT connection failed: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            payload = json.loads(msg.payload.decode())
            print(f"\n📨 MQTT: {msg.topic}")
            print(f"   Event: {payload.get('event', 'unknown')}")
            print(f"   Tool: {payload.get('tool_name', 'unknown')}")
            print(f"   User: {payload.get('user_name', 'unknown')}")
            print(f"   Time: {time.strftime('%H:%M:%S')}")
            print("-" * 50)
        except Exception as e:
            print(f"📨 MQTT: {msg.topic} -> {msg.payload.decode()}")
            print(f"   Error: {e}")
    
    def test_redis(self):
        """Test Redis connection and show messages"""
        if not self.redis_client:
            return
        
        print("🔍 Monitoring Redis messages...")
        last_count = 0
        
        while self.running:
            try:
                count = self.redis_client.llen('nemo_mqtt_events')
                if count > last_count:
                    new_messages = count - last_count
                    print(f"\n📦 Redis: {new_messages} new message(s)")
                    
                    messages = self.redis_client.lrange('nemo_mqtt_events', -new_messages, -1)
                    for i, message in enumerate(messages):
                        try:
                            data = json.loads(message)
                            print(f"   [{i+1}] Topic: {data.get('topic', 'unknown')}")
                            payload = json.loads(data.get('payload', '{}'))
                            print(f"       Event: {payload.get('event', 'unknown')}")
                        except:
                            print(f"   [{i+1}] Raw: {message[:100]}...")
                    
                    print("-" * 50)
                    last_count = count
                
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ Redis error: {e}")
                time.sleep(1)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Shutting down...")
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        sys.exit(0)
    
    def run(self):
        """Main run method"""
        print("🧪 NEMO MQTT Tester")
        print("=" * 30)
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Connect to services
        redis_ok = self.connect_redis()
        mqtt_ok = self.connect_mqtt()
        
        if not redis_ok and not mqtt_ok:
            print("❌ Cannot connect to Redis or MQTT")
            return
        
        print(f"\n📊 Status:")
        print(f"   Redis: {'✅' if redis_ok else '❌'}")
        print(f"   MQTT:  {'✅' if mqtt_ok else '❌'}")
        print("\n💡 Try enabling/disabling tools in NEMO!")
        print("   Press Ctrl+C to stop")
        print("=" * 30)
        
        self.running = True
        
        # Start Redis monitoring in background
        if redis_ok:
            redis_thread = threading.Thread(target=self.test_redis, daemon=True)
            redis_thread.start()
        
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)

def main():
    tester = MQTTTester()
    tester.run()

if __name__ == "__main__":
    main()
