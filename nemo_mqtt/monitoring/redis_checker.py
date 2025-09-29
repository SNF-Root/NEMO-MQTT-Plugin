#!/usr/bin/env python3
"""
Simple Redis Message Checker
This script checks for messages in Redis and shows recent activity.
"""

import os
import sys
import django
import redis
import json
import time
import fcntl
import atexit
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_dev')
django.setup()

# Global lock file handle
lock_file = None

def acquire_lock():
    """Acquire an exclusive lock to prevent multiple instances"""
    global lock_file
    lock_file_path = '/tmp/nemo_redis_monitor.lock'
    
    try:
        lock_file = open(lock_file_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        print("🔒 Redis monitor lock acquired")
        return True
    except (IOError, OSError):
        print("❌ Another Redis monitor is already running!")
        print("   If you're sure no other monitor is running, delete:")
        print(f"   rm {lock_file_path}")
        return False

def release_lock():
    """Release the lock"""
    global lock_file
    if lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
            os.unlink('/tmp/nemo_redis_monitor.lock')
            print("🔓 Redis monitor lock released")
        except:
            pass

def check_redis_messages():
    """Check for messages in Redis"""
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
        
        # Check current list length
        list_length = r.llen('nemo_mqtt_events')
        print(f"📊 Current messages in Redis list: {list_length}")
        
        if list_length > 0:
            print(f"\n📨 Recent messages (last 10):")
            print("-" * 60)
            
            # Get the last 10 messages (without removing them)
            messages = r.lrange('nemo_mqtt_events', -10, -1)
            
            for i, message in enumerate(messages, 1):
                try:
                    event_data = json.loads(message)
                    print(f"\n{i}. Topic: {event_data.get('topic', 'unknown')}")
                    print(f"   Payload: {event_data.get('payload', 'unknown')}")
                    print(f"   Timestamp: {event_data.get('timestamp', 'unknown')}")
                    print(f"   QoS: {event_data.get('qos', 0)}")
                    print(f"   Retain: {event_data.get('retain', False)}")
                except json.JSONDecodeError as e:
                    print(f"\n{i}. Raw message: {message}")
                    print(f"   Error parsing JSON: {e}")
        else:
            print("📭 No messages found in Redis list")
            print("\n💡 Try enabling/disabling a tool in NEMO to generate messages")
        
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        return False

def monitor_redis_realtime():
    """Monitor Redis in real-time without consuming messages"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
        print("\n🔍 Monitoring Redis for new messages...")
        print("   (Press Ctrl+C to stop)")
        print("-" * 60)
        
        last_count = r.llen('nemo_mqtt_events')
        
        while True:
            current_count = r.llen('nemo_mqtt_events')
            
            if current_count > last_count:
                new_messages = current_count - last_count
                print(f"\n🆕 {new_messages} new message(s) detected!")
                
                # Get the new messages without removing them
                messages = r.lrange('nemo_mqtt_events', -new_messages, -1)
                for i, message in enumerate(messages, 1):
                    try:
                        event_data = json.loads(message)
                        print(f"\n  {i}. Topic: {event_data.get('topic', 'unknown')}")
                        print(f"     Payload: {event_data.get('payload', 'unknown')}")
                        print(f"     Time: {datetime.now().isoformat()}")
                    except json.JSONDecodeError as e:
                        print(f"\n  {i}. Raw message: {message}")
                
                last_count = current_count
                print("-" * 60)
            
            time.sleep(0.05)  # Check every 50ms for even faster response
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
    except Exception as e:
        print(f"❌ Error monitoring Redis: {e}")

def main():
    print("🔍 Redis Message Checker")
    print("=" * 40)
    
    # Try to acquire lock
    if not acquire_lock():
        return
    
    # Register cleanup function
    atexit.register(release_lock)
    
    try:
        if not check_redis_messages():
            return
        
        print("\n" + "=" * 40)
        choice = input("Do you want to monitor in real-time? (y/n): ").lower().strip()
        
        if choice in ['y', 'yes']:
            monitor_redis_realtime()
        else:
            print("👋 Done!")
    
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
