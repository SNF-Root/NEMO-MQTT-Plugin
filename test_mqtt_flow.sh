#!/bin/bash
# Test script to verify the MQTT flow is working

echo "🧪 Testing NEMO MQTT Flow"
echo "=========================="

# Check if Redis is running
echo "🔍 Checking Redis connection..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is running"
else
    echo "❌ Redis is not running. Please start it first."
    exit 1
fi

# Check if MQTT broker is running
echo "🔍 Checking MQTT broker connection..."
if command -v mosquitto_pub >/dev/null 2>&1; then
    if mosquitto_pub -h localhost -p 1883 -t "test/connection" -m "test" > /dev/null 2>&1; then
        echo "✅ MQTT broker is running"
    else
        echo "❌ MQTT broker is not responding. Please start it first."
        exit 1
    fi
else
    echo "⚠️  Cannot test MQTT broker (mosquitto_pub not found)"
fi

# Check if our services are running
echo "🔍 Checking MQTT services..."
if pgrep -f standalone_mqtt_service > /dev/null; then
    echo "✅ Standalone MQTT Service is running"
elif pgrep -f external_mqtt_service > /dev/null; then
    echo "✅ External MQTT Service is running"
else
    echo "❌ No MQTT Service is running"
    exit 1
fi

if pgrep -f monitor_messages > /dev/null; then
    echo "✅ MQTT Monitor is running"
else
    echo "❌ MQTT Monitor is not running"
    exit 1
fi

# Run the test
echo ""
echo "🧪 Running MQTT flow test..."
python3 test_message_flow.py

echo ""
echo "✅ Test completed!"
echo "💡 Check the monitor output above to see if messages were received"
