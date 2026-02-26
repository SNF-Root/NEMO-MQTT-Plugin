#!/usr/bin/env python3
"""
Quick diagnostic script to check Redis-MQTT Bridge status

Usage (from project root or NEMO project root):
    python scripts/check_bridge_status.py
"""
import redis
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django
django.setup()

print("=" * 60)
print("Redis-MQTT Bridge Diagnostic")
print("=" * 60)

# Check Redis connection
print("\n1. Checking Redis connection...")
try:
    r = redis.Redis(host='localhost', port=6379, db=1)
    r.ping()
    print("   [OK] Redis is accessible")

    # Check queue length
    queue_len = r.llen('nemo_mqtt_events')
    print(f"   Redis queue length: {queue_len} messages")

    if queue_len > 0:
        print(f"   WARNING: {queue_len} messages waiting to be consumed!")
        print("   Peeking at first message:")
        first_msg = r.lindex('nemo_mqtt_events', -1)
        if first_msg:
            print(f"      {str(first_msg)[:200]}...")

except Exception as e:
    print(f"   [ERROR] Redis error: {e}")

# Check lock file
print("\n2. Checking lock file...")
lock_path = "/tmp/nemo_mqtt_bridge.lock"
if os.path.exists(lock_path):
    with open(lock_path, 'r') as f:
        pid = f.read().strip()
    print(f"   [OK] Lock file exists: {lock_path}")
    print(f"   PID: {pid}")

    # Check if process is running
    try:
        os.kill(int(pid), 0)
        print(f"   [OK] Process {pid} is running")
    except (OSError, ValueError):
        print(f"   [ERROR] Process {pid} is NOT running (stale lock)")
else:
    print(f"   [ERROR] No lock file found")
    print(f"   WARNING: Bridge might not be running!")

# Check MQTT config
print("\n3. Checking MQTT configuration...")
try:
    from nemo_mqtt.utils import get_mqtt_config
    config = get_mqtt_config()
    if config:
        print(f"   [OK] Config found: {config.name}")
        print(f"   Broker: {config.broker_host}:{config.broker_port}")
        print(f"   Enabled: {config.enabled}")
    else:
        print("   [ERROR] No MQTT configuration found")
except Exception as e:
    print(f"   [ERROR] Config error: {e}")

# Try to access bridge instance
print("\n4. Checking bridge instance...")
try:
    from nemo_mqtt.redis_mqtt_bridge import get_mqtt_bridge, _mqtt_bridge_instance

    if _mqtt_bridge_instance is None:
        print("   [ERROR] Bridge instance is None - NOT INITIALIZED!")
        print("   Trying to initialize...")
        bridge = get_mqtt_bridge()
        print(f"   [OK] Bridge initialized: {bridge}")
        print(f"   Running: {bridge.running}")
    else:
        bridge = _mqtt_bridge_instance
        print(f"   [OK] Bridge instance exists")
        print(f"   Running: {bridge.running}")
        print(f"   Connection count: {bridge.connection_count}")

except Exception as e:
    print(f"   [ERROR] Bridge error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnostic complete")
print("=" * 60)
