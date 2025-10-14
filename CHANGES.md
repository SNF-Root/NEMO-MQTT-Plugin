# Automatic Cleanup and Instance Management Changes

## Problem
Multiple instances of the Redis-MQTT Bridge were starting simultaneously, causing:
- Connection/reconnection loops
- "Keepalive timeout" errors (brokers kicking out duplicate client IDs)
- Mosquitto not starting reliably on the correct port
- False "started successfully" messages when Mosquitto wasn't actually ready

## Solution Implemented

### 1. **Singleton Pattern for Global Instance**
**Before:** Global instance created immediately on module import
```python
mqtt_bridge = RedisMQTTBridge(auto_start=True)  # Multiple imports = multiple instances!
```

**After:** Lazy initialization with thread-safe singleton
```python
def get_mqtt_bridge():  # Only creates ONE instance ever
    global _mqtt_bridge_instance
    with _mqtt_bridge_lock:
        if _mqtt_bridge_instance is None:
            _mqtt_bridge_instance = RedisMQTTBridge(auto_start=True)
        return _mqtt_bridge_instance
```

### 2. **Automatic Lock File Management** (`_acquire_lock()`)
- Creates lock file `/tmp/nemo_mqtt_bridge.lock` with PID
- **Automatically detects and kills stale instances** on startup
- Cleans up stale lock files if old process is dead
- Prevents multiple bridge instances from running simultaneously

### 3. **Robust Mosquitto Startup** (`_start_mosquitto()`)
**Before:** Quick connection test that passed but service wasn't ready
- Claimed "started successfully" after 1 second
- Actually took 30+ seconds to be ready
- Caused connection refused errors

**After:** Robust readiness check
- Tests connection with `is_connected()` check
- Waits up to 20 seconds with progress messages
- Only reports success when ACTUALLY ready
- Shows exactly how long it took (e.g., "took 3s")

### 4. **Config Load Order Fix**
- Loads Django configuration **before** starting services
- Ensures Mosquitto starts on correct port from config

## How It Works

### On Startup:
1. **Singleton check** - only creates ONE instance across all imports
2. **Lock file check:**
   - If lock exists, checks if old process running
   - **Automatically kills** old process (SIGTERM, then SIGKILL if needed)
   - Cleans up stale lock
3. Acquires new lock with current PID
4. Loads configuration from Django
5. **Waits for Mosquitto to be ACTUALLY ready** (not just started)
6. Connects to services

### On Shutdown:
- Releases lock file automatically
- Cleans up processes

## Benefits

✅ **No manual cleanup needed** - handles stale processes automatically  
✅ **No duplicate instances** - singleton + lock file prevents conflicts  
✅ **Correct port detection** - uses config from Django  
✅ **Reliable startup** - waits for services to be ready  
✅ **Clear status messages** - see exactly what's happening  
✅ **Fast connection** - no 30-second delays  

## Expected Output

```bash
Starting development server at http://127.0.0.1:8000/

🔒 Acquired lock: /tmp/nemo_mqtt_bridge.lock (PID: 12345)
🔍 Loading MQTT configuration from Django...
✅ MQTT configuration loaded: Default MQTT Configuration
   Broker: localhost:1884
🔍 Checking if Mosquitto is already running on port 1884...
   Mosquitto not running on port 1884, starting it...
🚀 Starting Mosquitto on port 1884...
⏳ Waiting for Mosquitto to be fully ready...
   Attempt 1/20: Not ready yet, waiting...
   Attempt 2/20: Not ready yet, waiting...
✅ MQTT broker started successfully on port 1884 (took 3s)
🔍 Connecting to Redis...
✅ Connected to Redis
🔍 Connecting to MQTT broker...
✅ Connected to MQTT broker
✅ Redis-MQTT Bridge started successfully
```

## Usage

Just restart your Django server as normal:
```bash
python manage.py runserver
```

The bridge will automatically:
- Kill any old instances
- Clean up lock files  
- Start Mosquitto if needed
- **Wait for it to be ready**
- Connect everything properly

No more connection refused errors! 🎉

