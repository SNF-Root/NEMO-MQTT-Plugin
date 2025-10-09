#!/usr/bin/env python3
"""
Comprehensive Flow Monitor
Tracks the complete message flow: Django Signal → Redis → MQTT Publisher → MQTT Broker
Shows all output in one place with clear flow tracking
"""

import redis
import paho.mqtt.client as mqtt
import json
import time
import threading
import psutil
import os
import signal
import sys
from datetime import datetime

class ComprehensiveFlowMonitor:
    def __init__(self):
        self.redis_client = None
        self.mqtt_client = None
        self.running = True
        self.message_flow = []
        self.max_flow_entries = 50
        self.message_count = 0
        self.connected = False
        self.last_message_time = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.disconnect()
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
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                decode_responses=True
            )
            self.redis_client.ping()
            print("✅ [MONITOR] Connected to Redis")
            return True
        except Exception as e:
            print(f"❌ [MONITOR] Failed to connect to Redis: {e}")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            import uuid
            client_id = f"comprehensive_monitor_{uuid.uuid4().hex[:8]}"
            self.mqtt_client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            self.mqtt_client.connect('localhost', 1883, 60)
            self.mqtt_client.loop_start()
            
            # Wait a moment for connection to establish
            time.sleep(1)
            return True
        except Exception as e:
            print(f"❌ [MONITOR] Failed to connect to MQTT broker: {e}")
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            print("✅ [MONITOR] Connected to MQTT broker")
            result = client.subscribe("nemo/#", qos=1)
            print(f"📡 [MONITOR] Subscribed to nemo/# topics (result: {result})")
        else:
            self.connected = False
            print(f"❌ [MONITOR] MQTT connection failed with code {rc}")
            print("   Common codes: 0=Success, 1=Invalid protocol, 2=Invalid client ID, 3=Server unavailable, 4=Bad username/password, 5=Not authorized")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback - Final destination of the flow"""
        import uuid
        mqtt_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        self.message_count += 1
        self.last_message_time = time.time()
        
        print(f"\n🎯 [MQTT-{mqtt_id}] FINAL DESTINATION - MQTT Message Received")
        print(f"   📊 Message #: {self.message_count}")
        print(f"   ⏰ Time: {timestamp}")
        print(f"   📍 Topic: {msg.topic}")
        print(f"   🎯 QoS: {msg.qos}")
        print(f"   🔒 Retain: {msg.retain}")
        print(f"   📏 Payload length: {len(msg.payload)} bytes")
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            print(f"   📦 Payload: {json.dumps(payload, indent=4)}")
            
            # Add to flow tracking
            self.add_flow_entry("MQTT_RECEIVED", {
                "id": mqtt_id,
                "topic": msg.topic,
                "payload": payload,
                "timestamp": timestamp
            })
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON decode error: {e}")
            print(f"   📦 Raw payload: {msg.payload.decode('utf-8')}")
        
        print(f"🏁 [MQTT-{mqtt_id}] Message flow complete!")
        print("=" * 80)
        
        # Add a small delay to see if messages are being processed too quickly
        time.sleep(0.1)
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.connected = False
        print(f"⚠️  [MONITOR] MQTT disconnected with code {rc}")
    
    def add_flow_entry(self, stage, data):
        """Add an entry to the flow tracking"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "data": data
        }
        self.message_flow.append(entry)
        
        # Keep only the last max_flow_entries
        if len(self.message_flow) > self.max_flow_entries:
            self.message_flow = self.message_flow[-self.max_flow_entries:]
    
    def monitor_redis_consumption(self):
        """Monitor Redis to see what the standalone service is consuming"""
        print("🔍 [MONITOR] Starting Redis consumption monitoring...")
        
        while self.running:
            try:
                # Check Redis list length
                list_length = self.redis_client.llen('NEMO_mqtt_events')
                if list_length > 0:
                    print(f"📊 [MONITOR] Redis has {list_length} messages waiting to be consumed")
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                print(f"❌ [MONITOR] Error monitoring Redis: {e}")
                time.sleep(1)
    
    def show_flow_summary(self):
        """Show a summary of the message flow"""
        print(f"\n📊 [MONITOR] Message Flow Summary")
        print(f"   Total MQTT messages received: {self.message_count}")
        print(f"   Total flow entries: {len(self.message_flow)}")
        
        # Count by stage
        stage_counts = {}
        for entry in self.message_flow:
            stage = entry['stage']
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        for stage, count in stage_counts.items():
            print(f"   {stage}: {count}")
    
    def run(self):
        """Run the comprehensive monitor"""
        print("🚀 [MONITOR] Starting Comprehensive Flow Monitor")
        print("=" * 80)
        print("📋 This monitor tracks the complete message flow:")
        print("   1. Django Signal → Redis (via signals.py)")
        print("   2. Redis → MQTT Publisher (via standalone_mqtt_service.py)")
        print("   3. MQTT Publisher → MQTT Broker (mosquitto)")
        print("   4. MQTT Broker → This Monitor (final destination)")
        print("=" * 80)
        
        # Kill any existing monitoring processes first
        self.kill_existing_monitors()
        
        # Connect to Redis
        if not self.connect_redis():
            return
        
        # Connect to MQTT
        if not self.connect_mqtt():
            return
        
        print("\n📋 Instructions:")
        print("1. Enable/disable a tool in NEMO")
        print("2. Watch the complete message flow below")
        print("3. Press Ctrl+C to stop monitoring")
        print("\n" + "=" * 80)
        
        # Start Redis monitoring in a separate thread
        redis_thread = threading.Thread(target=self.monitor_redis_consumption, daemon=True)
        redis_thread.start()
        
        try:
            status_counter = 0
            while self.running:
                time.sleep(1)
                status_counter += 1
                
                # Show status every 10 seconds
                if status_counter % 10 == 0:
                    status = "✅ Connected" if self.connected else "❌ Disconnected"
                    last_msg = f" (last: {self.last_message_time})" if self.last_message_time else " (no messages yet)"
                    print(f"📊 [MONITOR] Status: {status} | MQTT Messages: {self.message_count}{last_msg}")
        except KeyboardInterrupt:
            self.running = False
            self.show_flow_summary()
            print("\n👋 [MONITOR] Comprehensive Flow Monitor stopped")

def main():
    monitor = ComprehensiveFlowMonitor()
    monitor.run()

if __name__ == "__main__":
    main()
