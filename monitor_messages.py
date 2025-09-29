#!/usr/bin/env python3
"""
Simple MQTT Message Monitor for NEMO

This script monitors both Redis and MQTT messages from the NEMO MQTT plugin.
"""

import os
import sys
import time
import json
import redis
import paho.mqtt.client as mqtt
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class MQTTMonitor:
    def __init__(self):
        self.redis_client = None
        self.mqtt_client = None
        self.redis_connected = False
        self.mqtt_connected = False
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis_client.ping()
            self.redis_connected = True
            print("✅ Connected to Redis")
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
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            self.mqtt_client.connect('localhost', 1883, 60)
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.mqtt_connected = True
            print("✅ Connected to MQTT broker")
            # Subscribe to all NEMO topics
            client.subscribe("nemo/#")
            print("📡 Subscribed to nemo/# topics")
        else:
            print(f"❌ MQTT connection failed with code {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n🔔 [{timestamp}] MQTT Message:")
        print(f"   Topic: {msg.topic}")
        print(f"   QoS: {msg.qos}")
        print(f"   Retain: {msg.retain}")
        try:
            payload = json.loads(msg.payload.decode())
            print(f"   Payload: {json.dumps(payload, indent=2)}")
        except:
            print(f"   Payload: {msg.payload.decode()}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        print("❌ Disconnected from MQTT broker")
    
    def check_redis_messages(self):
        """Check for new Redis messages"""
        if not self.redis_connected:
            return
        
        try:
            # Get current message count
            count = self.redis_client.llen('nemo_mqtt_events')
            if count > 0:
                # Get the latest message
                message = self.redis_client.rpop('nemo_mqtt_events')
                if message:
                    data = json.loads(message)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\n📨 [{timestamp}] Redis Message:")
                    print(f"   Topic: {data.get('topic', 'N/A')}")
                    print(f"   QoS: {data.get('qos', 'N/A')}")
                    print(f"   Retain: {data.get('retain', 'N/A')}")
                    try:
                        payload = json.loads(data.get('payload', '{}'))
                        print(f"   Payload: {json.dumps(payload, indent=2)}")
                    except:
                        print(f"   Payload: {data.get('payload', 'N/A')}")
        except Exception as e:
            print(f"❌ Redis error: {e}")
    
    def run(self):
        """Run the monitor"""
        print("🚀 Starting NEMO MQTT Message Monitor")
        print("=" * 50)
        
        # Connect to Redis
        if not self.connect_redis():
            print("⚠️  Continuing without Redis monitoring...")
        
        # Connect to MQTT
        if not self.connect_mqtt():
            print("⚠️  Continuing without MQTT monitoring...")
        
        if not self.redis_connected and not self.mqtt_connected:
            print("❌ No connections available. Exiting.")
            return
        
        print("\n📋 Monitoring started. Press Ctrl+C to stop.")
        print("💡 Try enabling/disabling a tool in NEMO to see messages!")
        print("=" * 50)
        
        try:
            while True:
                if self.redis_connected:
                    self.check_redis_messages()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping monitor...")
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            print("✅ Monitor stopped")

if __name__ == "__main__":
    monitor = MQTTMonitor()
    monitor.run()
