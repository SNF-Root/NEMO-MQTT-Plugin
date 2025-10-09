#!/usr/bin/env python3
"""
Simple MQTT Subscriber Test
Minimal test to see if MQTT messages are being delivered properly
"""

import paho.mqtt.client as mqtt
import json
import time
import signal
import sys
import psutil
import os

class SimpleMQTTSubscriber:
    def __init__(self):
        self.message_count = 0
        self.running = True
        self.connected = False
        self.last_message_time = None
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down...")
        print(f"📊 Total messages received: {self.message_count}")
        self.running = False
        sys.exit(0)
    
    def kill_existing_monitors(self):
        """Kill any existing monitoring processes"""
        print("🔍 Checking for existing monitoring processes...")
        
        killed_processes = []
        current_pid = os.getpid()
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue  # Skip self
                    
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Look for our monitoring scripts
                if any(script in cmdline for script in [
                    'comprehensive_flow_monitor.py',
                    'simple_mqtt_subscriber.py', 
                    'monitor_messages.py',
                    'simple_mqtt_monitor.py',
                    'connection_manager.py'
                ]):
                    print(f"🔪 Killing existing process: PID {proc.info['pid']} - {cmdline}")
                    proc.kill()
                    killed_processes.append(proc.info['pid'])
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if killed_processes:
            print(f"✅ Killed {len(killed_processes)} existing processes: {killed_processes}")
            time.sleep(2)  # Wait for processes to fully terminate
        else:
            print("✅ No existing monitoring processes found")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print("✅ Connected to MQTT broker")
            result = client.subscribe("nemo/#", qos=1)
            print(f"📡 Subscribed to nemo/# topics (result: {result})")
        else:
            self.connected = False
            print(f"❌ Connection failed with code {rc}")
            print("   Common codes: 0=Success, 1=Invalid protocol, 2=Invalid client ID, 3=Server unavailable, 4=Bad username/password, 5=Not authorized")
    
    def on_message(self, client, userdata, msg):
        self.message_count += 1
        self.last_message_time = time.time()
        timestamp = time.strftime("%H:%M:%S.%f")[:-3]
        
        print(f"\n📨 Message #{self.message_count} received at {timestamp}")
        print(f"   Topic: {msg.topic}")
        print(f"   QoS: {msg.qos}")
        print(f"   Retain: {msg.retain}")
        print(f"   Payload length: {len(msg.payload)} bytes")
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            print(f"   Event: {payload.get('event', 'unknown')}")
            print(f"   Usage ID: {payload.get('usage_id', 'unknown')}")
        except json.JSONDecodeError:
            print(f"   Raw payload: {msg.payload.decode('utf-8')[:100]}...")
        
        print("=" * 50)
    
    def run(self):
        print("🚀 Starting Simple MQTT Subscriber")
        print("=" * 50)
        
        # Kill any existing monitoring processes first
        self.kill_existing_monitors()
        
        # Create MQTT client (use same version as working monitor)
        import uuid
        client_id = f"simple_subscriber_{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        
        try:
            # Connect to broker
            print("🔍 Connecting to MQTT broker...")
            client.connect('localhost', 1883, 60)
            client.loop_start()
            
            # Wait a moment for connection to establish
            time.sleep(1)
            
            print("📋 Listening for messages...")
            print("   Press Ctrl+C to stop")
            print("=" * 50)
            
            # Keep running until interrupted
            status_counter = 0
            while self.running:
                time.sleep(1)
                status_counter += 1
                
                # Show status every 10 seconds
                if status_counter % 10 == 0:
                    status = "✅ Connected" if self.connected else "❌ Disconnected"
                    last_msg = f" (last: {self.last_message_time})" if self.last_message_time else " (no messages yet)"
                    print(f"📊 Status: {status} | Messages: {self.message_count}{last_msg}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            client.loop_stop()
            client.disconnect()
            print(f"\n👋 Disconnected. Total messages received: {self.message_count}")

if __name__ == "__main__":
    subscriber = SimpleMQTTSubscriber()
    subscriber.run()
