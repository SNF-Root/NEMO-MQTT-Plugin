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

## 🌐 Web monitor (Redis stream)

The plugin’s web dashboard at **`/mqtt/monitor/`** shows a **stream of what NEMO publishes**: it reads from the Redis list `nemo_mqtt_monitor` (last 100 events). This is the same pipeline that the Redis–MQTT bridge consumes; the monitor does not subscribe to the MQTT broker, so you only see events emitted by this plugin. The page auto-refreshes every 3 seconds.

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

## ⚙️ Configuration Settings

### Keep Alive (seconds)

The **Keep Alive** setting (default: 60 seconds) controls how the MQTT client maintains its connection with the broker.

**What it does:**

1. **Heartbeat mechanism**: The client must send at least one packet (data or PING) to the broker within the keep-alive interval to prove it's still alive.

2. **Connection monitoring**: If the broker doesn't receive any packet within 1.5× the keep-alive interval (e.g., 90 seconds for a 60-second keep-alive), it considers the client disconnected and may close the connection.

3. **Prevents stale connections**: Helps detect and clean up dead or unresponsive connections automatically.

**In practice:**

- **Default (60 seconds)**: Works well for most NEMO deployments. The plugin sends messages regularly, so the keep-alive mainly acts as a safety net.
- **Increase (120-300 seconds)**: Useful for battery-constrained devices or when you want to reduce network traffic. Allows longer periods between messages.
- **Decrease (30 seconds)**: Provides faster detection of disconnections, useful in unstable network environments.

**Note**: Since the NEMO MQTT plugin publishes messages regularly (tool events, area events, etc.), the keep-alive interval primarily serves as a connection health check rather than the primary mechanism for maintaining connectivity.

## 📡 Tool enable/disable: single source of truth (UsageEvent.post_save)

Tool “enable” and “disable” in NEMO (and nemo-ce) are **not** separate Django signals. They are:

- **Enable** = a new usage session starts → NEMO saves a **UsageEvent** with no `end` time.
- **Disable** = the session ends → NEMO saves the same **UsageEvent** with `end` set.

The plugin uses **`UsageEvent.post_save`** as the **single source of truth** for both. When a UsageEvent is saved:

| NEMO action | UsageEvent state | Events published to Redis |
|-------------|------------------|----------------------------|
| User enables tool (starts use) | `end` is `None` | `tool_usage_start` + `tool_enabled` |
| User disables tool (stops use)  | `end` is set     | `tool_usage_end` + `tool_disabled` |

**Topics published:**

- **By tool name (usage lifecycle):**  
  `nemo/tools/{tool_name}/start`, `nemo/tools/{tool_name}/end`
- **By tool id (enable/disable semantics):**  
  `nemo/tools/{tool_id}/enabled`, `nemo/tools/{tool_id}/disabled`

All of these are emitted from the same **UsageEvent** handler, so you get consistent, instantaneous updates (same request as the NEMO enable/disable action).

## 🧪 Testing Tool Enable/Disable

1. **Start monitoring**:
   ```bash
   ./monitor_mqtt.sh mqtt
   ```

2. **Enable/disable a tool** in the NEMO web interface (e.g. “Enable” to start use, “Disable” / “Stop” to end use).

3. **Watch for messages**:
   - On **enable**: `nemo/tools/{name}/start` and `nemo/tools/{id}/enabled`
   - On **disable**: `nemo/tools/{name}/end` and `nemo/tools/{id}/disabled`
   - MQTT will show the same if the bridge is running.

## 🔍 What to Look For

When you **enable** a tool (start use), you should see two Redis (and MQTT) messages:

**1. Start / usage lifecycle**
- Topic: `nemo/tools/Fiji2/start` (example tool name)
- Payload includes: `"event": "tool_usage_start"`, `tool_id`, `tool_name`, `user_name`, `start_time`

**2. Enabled (semantic alias)**
- Topic: `nemo/tools/2/enabled` (example tool id)
- Payload includes: `"event": "tool_enabled"`, `tool_id`, `tool_name`, `usage_id`, `user_name`, `start_time`

When you **disable** a tool (stop use), you should see:

**1. End / usage lifecycle**
- Topic: `nemo/tools/Fiji2/end`
- Payload includes: `"event": "tool_usage_end"`, `start_time`, `end_time`, `user_name`

**2. Disabled (semantic alias)**
- Topic: `nemo/tools/2/disabled`
- Payload includes: `"event": "tool_disabled"`, `tool_id`, `tool_name`, `usage_id`, `user_name`, `end_time`

## 🚨 Troubleshooting

If you don't see messages:

1. **Check Redis**: `redis-cli ping`
2. **Check MQTT broker**: `lsof -i :1883`
3. **Check Redis-MQTT Bridge service**: `pgrep -f redis_mqtt_bridge` or `python -m nemo_mqtt.redis_mqtt_bridge`
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
