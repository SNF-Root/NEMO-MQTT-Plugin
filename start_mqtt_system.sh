#!/bin/bash
# Master script to start the complete MQTT system
# Kills all existing processes, starts Redis, MQTT broker, and monitoring

echo "🚀 Starting NEMO MQTT System"
echo "================================"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Kill all existing MQTT and Redis processes
echo "🧹 Cleaning up existing processes..."
pkill -f mqtt 2>/dev/null || true
pkill -f redis 2>/dev/null || true
pkill -f external_mqtt_service 2>/dev/null || true
pkill -f monitor_messages 2>/dev/null || true
pkill -f redis_checker 2>/dev/null || true
pkill -f watch_mqtt 2>/dev/null || true

# Force kill mosquitto to avoid multiple instances
echo "🔨 Force killing any existing MQTT brokers..."
pkill -9 mosquitto 2>/dev/null || true

# Wait a moment for processes to die
sleep 3

# Check if Redis is installed and running
echo "🔍 Checking Redis..."
if command_exists redis-server; then
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "📦 Starting Redis server..."
        redis-server --daemonize yes
        sleep 2
    else
        echo "✅ Redis server already running"
    fi
else
    echo "❌ Redis server not found. Please install Redis first."
    exit 1
fi

# Test Redis connection
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis connection successful"
else
    echo "❌ Redis connection failed"
    exit 1
fi

# Check if MQTT broker is running
echo "🔍 Checking MQTT broker..."
if command_exists mosquitto; then
    if ! pgrep -x "mosquitto" > /dev/null; then
        echo "📦 Starting MQTT broker (mosquitto)..."
        mosquitto -d
        sleep 2
    else
        echo "✅ MQTT broker already running"
    fi
else
    echo "⚠️  Mosquitto not found. Make sure MQTT broker is running on localhost:1883"
fi

# Test MQTT broker connection
if command_exists mosquitto_pub; then
    if mosquitto_pub -h localhost -p 1883 -t "test/connection" -m "test" > /dev/null 2>&1; then
        echo "✅ MQTT broker connection successful"
    else
        echo "❌ MQTT broker connection failed"
        exit 1
    fi
else
    echo "⚠️  Cannot test MQTT broker connection (mosquitto_pub not found)"
fi

# Set up Python virtual environment
echo "🔍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
if [ -f "requirements_simple.txt" ]; then
    pip install -r requirements_simple.txt
else
    pip install redis paho-mqtt
fi

# Start the standalone MQTT service (for development)
echo "🚀 Starting Standalone MQTT Service (Development Mode)..."
echo "📋 Note: This uses hardcoded configuration for development"
echo "   For production, install plugin in NEMO-CE and use external_mqtt_service.py"
echo ""
python standalone_mqtt_service.py &
MQTT_SERVICE_PID=$!
echo "✅ Standalone MQTT Service started (PID: $MQTT_SERVICE_PID)"

# Wait a moment for the service to start
sleep 3

# Start the monitor
echo "📡 Starting MQTT Monitor..."
python monitor_messages.py &
MONITOR_PID=$!
echo "✅ MQTT Monitor started (PID: $MONITOR_PID)"

echo ""
echo "🎉 NEMO MQTT System is running!"
echo "================================"
echo "📋 Services running:"
echo "   - Redis server"
echo "   - MQTT broker"
echo "   - Standalone MQTT Service (PID: $MQTT_SERVICE_PID)"
echo "   - MQTT Monitor (PID: $MONITOR_PID)"
echo ""
echo "💡 Try enabling/disabling tools in NEMO to see MQTT messages!"
echo "🛑 Press Ctrl+C to stop all services"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping NEMO MQTT System..."
    kill $MQTT_SERVICE_PID 2>/dev/null || true
    kill $MONITOR_PID 2>/dev/null || true
    # Deactivate virtual environment
    deactivate 2>/dev/null || true
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Keep the script running
wait
