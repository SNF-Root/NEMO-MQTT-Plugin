#!/usr/bin/env python3
"""
Simple MQTT Message Monitor for NEMO

This script monitors MQTT messages that are actually sent out by the NEMO MQTT plugin.
"""

import os
import sys
import time
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class MQTTMonitor:
    def __init__(self):
        self.mqtt_client = None
        self.mqtt_connected = False
        
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
            print("🔍 [MONITOR] Ready to receive MQTT messages!")
        else:
            print(f"❌ MQTT connection failed with code {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        import uuid
        monitor_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n🔔 [MONITOR-{monitor_id}] [{timestamp}] MQTT Message Received:")
        print(f"   Topic: {msg.topic}")
        print(f"   QoS: {msg.qos}")
        print(f"   Retain: {msg.retain}")
        print(f"   Message ID: {msg.mid}")
        print(f"   Raw payload length: {len(msg.payload)} bytes")
        
        try:
            payload = json.loads(msg.payload.decode())
            print(f"   Payload (JSON): {json.dumps(payload, indent=2)}")
        except json.JSONDecodeError:
            print(f"   Payload (raw): {msg.payload.decode()}")
        except Exception as e:
            print(f"   Payload (error): {e}")
            print(f"   Raw bytes: {msg.payload}")
        
        print(f"✅ [MONITOR-{monitor_id}] Message processing complete")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        self.mqtt_connected = False
        print("❌ Disconnected from MQTT broker")
        print(f"   Return code: {rc}")
    
    def run(self):
        """Run the monitor"""
        print("🚀 Starting NEMO MQTT Message Monitor")
        print("=" * 50)
        
        # Connect to MQTT
        if not self.connect_mqtt():
            print("❌ MQTT connection failed. Exiting.")
            return
        
        print("\n📋 Monitoring MQTT messages. Press Ctrl+C to stop.")
        print("💡 Try enabling/disabling a tool in NEMO to see messages!")
        print("🔍 This monitor will show detailed debugging for all MQTT messages")
        print("=" * 50)
        
        try:
            while True:
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
