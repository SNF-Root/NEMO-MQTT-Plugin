# MQTT Plugin Monitoring Tools

This directory contains monitoring and debugging tools for the NEMO MQTT plugin.

## 🚀 Quick Start

From the NEMO project root directory, run:

```bash
# Full MQTT + Redis monitoring
./monitor_mqtt.sh mqtt

# Redis-only checking
./monitor_mqtt.sh redis

# Test MQTT signals
./monitor_mqtt.sh test
```

## 📁 Files

- **`mqtt_monitor.py`** - Full monitoring tool that watches both Redis and MQTT
- **`redis_checker.py`** - Simple Redis message checker
- **`run_monitor.py`** - Python runner with virtual environment detection
- **`monitor_mqtt.sh`** - Shell script wrapper for easy access

## 🔧 Usage

### Full MQTT Monitor
```bash
python3 NEMO/plugins/mqtt/monitoring/mqtt_monitor.py
```
- Connects to both Redis and MQTT broker
- Subscribes to all `nemo/#` topics
- Shows real-time messages from both sources
- Press Ctrl+C to stop

### Redis Checker
```bash
python3 NEMO/plugins/mqtt/monitoring/redis_checker.py
```
- Connects to Redis only
- Shows current message count
- Displays recent messages
- Option to monitor in real-time

### Test Signals
```bash
python3 NEMO/plugins/mqtt/monitoring/../test_mqtt.py
```
- Tests MQTT plugin functionality
- Creates test configuration
- Emits test signals
- Publishes test messages

## 🧪 Testing Tool Enable/Disable

1. **Start monitoring**:
   ```bash
   ./monitor_mqtt.sh mqtt
   ```

2. **Enable/disable a tool** in NEMO web interface

3. **Watch for messages**:
   - Redis messages with topics like `nemo/tools/{tool_id}/enabled`
   - MQTT messages (if external service is running)

## 🔍 What to Look For

When you enable/disable a tool, you should see:

**Redis Message:**
```json
{
  "topic": "nemo/tools/1/enabled",
  "payload": "{\"event\":\"tool_enabled\",\"tool_id\":1,\"tool_name\":\"Tool Name\",\"tool_status\":true,\"timestamp\":1234567890.123}",
  "qos": 0,
  "retain": false,
  "timestamp": 1234567890.123
}
```

**MQTT Message:**
- Topic: `nemo/tools/1/enabled`
- Payload: Same as Redis payload
- QoS: 0
- Retain: false

## 🚨 Troubleshooting

If you don't see messages:

1. **Check Redis**: `redis-cli ping`
2. **Check MQTT broker**: `lsof -i :1883`
3. **Check external MQTT service**: `python3 start_mqtt_service.py`
4. **Check Django logs** for signal handler errors
5. **Verify MQTT plugin is enabled** in Django settings

## 📋 Requirements

- Python 3.6+
- Django (configured)
- Redis server
- MQTT broker (for full monitoring)
- paho-mqtt (for MQTT monitoring)
- redis-py (for Redis monitoring)

The scripts automatically detect and use the project's virtual environment if available.
