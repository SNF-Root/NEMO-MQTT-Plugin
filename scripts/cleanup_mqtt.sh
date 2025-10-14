#!/bin/bash
# Clean up MQTT Bridge lock file and processes

echo "🧹 Cleaning up MQTT Bridge..."

# Kill any running Redis-MQTT Bridge processes
echo "🔍 Looking for Redis-MQTT Bridge processes..."
pids=$(ps aux | grep "redis_mqtt_bridge" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "✅ No Redis-MQTT Bridge processes found"
else
    echo "🛑 Killing Redis-MQTT Bridge processes: $pids"
    kill -TERM $pids 2>/dev/null || kill -9 $pids 2>/dev/null
    sleep 1
    echo "✅ Processes terminated"
fi

# Remove lock file
lock_file="/tmp/nemo_mqtt_bridge.lock"
if [ -f "$lock_file" ]; then
    echo "🔓 Removing lock file: $lock_file"
    rm -f "$lock_file"
    echo "✅ Lock file removed"
else
    echo "✅ No lock file found"
fi

# Kill any stray mosquitto/redis processes started in AUTO mode
echo "🔍 Looking for AUTO mode Redis/Mosquitto processes..."
mosquitto_pids=$(ps aux | grep "mosquitto.*1884" | grep -v grep | awk '{print $2}')
redis_pids=$(ps aux | grep "redis-server.*6380" | grep -v grep | awk '{print $2}')

if [ ! -z "$mosquitto_pids" ]; then
    echo "🛑 Killing Mosquitto processes: $mosquitto_pids"
    kill -TERM $mosquitto_pids 2>/dev/null || kill -9 $mosquitto_pids 2>/dev/null
fi

if [ ! -z "$redis_pids" ]; then
    echo "🛑 Killing Redis processes: $redis_pids"
    kill -TERM $redis_pids 2>/dev/null || kill -9 $redis_pids 2>/dev/null
fi

echo "✅ Cleanup complete!"

