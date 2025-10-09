#!/bin/bash
# Start the comprehensive flow monitor

echo "🚀 Starting Comprehensive Flow Monitor"
echo "======================================"
echo "This monitor tracks the complete message flow:"
echo "  Django Signal → Redis → MQTT Publisher → MQTT Broker → Monitor"
echo ""

# Kill any existing monitoring processes first
echo "🔍 Checking for existing monitoring processes..."
pids=$(ps aux | grep -E "(comprehensive_flow_monitor|simple_mqtt_subscriber|monitor_messages|simple_mqtt_monitor)" | grep -v grep | awk '{print $2}')

if [ ! -z "$pids" ]; then
    echo "🔪 Killing existing processes: $pids"
    echo $pids | xargs kill -9 2>/dev/null
    sleep 2
    echo "✅ Existing processes terminated"
else
    echo "✅ No existing processes found"
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first."
    exit 1
fi

# Check if MQTT broker is running
if ! mosquitto_pub -h localhost -p 1883 -t "test/connection" -m "test" > /dev/null 2>&1; then
    echo "❌ MQTT broker is not running. Please start mosquitto first."
    exit 1
fi

echo "✅ Redis and MQTT broker are running"
echo ""

# Start the comprehensive monitor
python comprehensive_flow_monitor.py
