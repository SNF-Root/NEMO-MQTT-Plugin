#!/bin/bash
# Master script to stop all MQTT and Redis processes

echo "🛑 Stopping NEMO MQTT System"
echo "============================="

# Kill all MQTT and Redis related processes
echo "🧹 Stopping all MQTT and Redis processes..."

# Stop our custom services first
pkill -f standalone_mqtt_service 2>/dev/null && echo "✅ Standalone MQTT Service stopped" || echo "ℹ️  Standalone MQTT Service not running"
pkill -f external_mqtt_service 2>/dev/null && echo "✅ External MQTT Service stopped" || echo "ℹ️  External MQTT Service not running"
pkill -f monitor_messages 2>/dev/null && echo "✅ MQTT Monitor stopped" || echo "ℹ️  MQTT Monitor not running"

# Stop any processes running in the venv
pkill -f "venv/bin/python" 2>/dev/null && echo "✅ Virtual environment processes stopped" || echo "ℹ️  No virtual environment processes running"

# Stop any other MQTT related processes
pkill -f redis_checker 2>/dev/null && echo "✅ Redis Checker stopped" || echo "ℹ️  Redis Checker not running"
pkill -f watch_mqtt 2>/dev/null && echo "✅ MQTT Watcher stopped" || echo "ℹ️  MQTT Watcher not running"
pkill -f external_mqtt_service 2>/dev/null && echo "✅ External MQTT Service stopped" || echo "ℹ️  External MQTT Service not running"

# Stop any Python MQTT listeners
pkill -f "python.*mqtt" 2>/dev/null && echo "✅ Python MQTT listeners stopped" || echo "ℹ️  No Python MQTT listeners running"

# Wait for processes to stop
sleep 2

# Check if any MQTT processes are still running
REMAINING=$(ps aux | grep -i mqtt | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Some MQTT processes may still be running:"
    ps aux | grep -i mqtt | grep -v grep
    echo ""
    echo "🔨 Force killing remaining processes..."
    pkill -9 -f mqtt 2>/dev/null || true
fi

# Check Redis processes
REDIS_RUNNING=$(pgrep -x "redis-server" | wc -l)
if [ "$REDIS_RUNNING" -gt 0 ]; then
    echo "ℹ️  Redis server is still running (this is normal if you want to keep it)"
    echo "   To stop Redis: redis-cli shutdown"
fi

# Force kill MQTT broker (mosquitto) to avoid multiple instances
echo "🔨 Force killing MQTT broker (mosquitto)..."
pkill -9 mosquitto 2>/dev/null && echo "✅ MQTT broker (mosquitto) stopped" || echo "ℹ️  MQTT broker (mosquitto) was not running"

echo ""
echo "✅ NEMO MQTT System stopped"
echo "============================="
