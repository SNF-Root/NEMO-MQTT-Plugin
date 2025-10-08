#!/bin/bash
# Development script to reinstall the MQTT plugin
# This clobbers the old plugin and installs a fresh one

echo "🔄 Reinstalling MQTT Plugin for Development"
echo "==========================================="

# Use the correct NEMO-CE path
NEMO_CE_PATH="/Users/adenton/Desktop/nemo-ce"
PLUGIN_SOURCE_PATH="$(pwd)/NEMO_mqtt"

echo "📁 NEMO-CE path: $NEMO_CE_PATH"
echo "📁 Plugin source: $PLUGIN_SOURCE_PATH"
echo ""

# Check if NEMO-CE directory exists
if [ ! -d "$NEMO_CE_PATH" ]; then
    echo "❌ NEMO-CE directory not found: $NEMO_CE_PATH"
    echo "   Please make sure NEMO-CE is installed at this location"
    exit 1
fi

# Check if NEMO-CE has the expected structure
if [ ! -f "$NEMO_CE_PATH/manage.py" ]; then
    echo "❌ This doesn't look like a NEMO-CE directory (no manage.py found)"
    echo "   Expected: $NEMO_CE_PATH/manage.py"
    exit 1
fi

# Stop any running Django server
echo "🛑 Stopping any running Django server..."
echo "   Checking for Django processes..."

# Kill Django runserver processes
pkill -f "manage.py runserver" 2>/dev/null || echo "   No Django runserver found"

# Kill any Python processes running NEMO
pkill -f "python.*manage.py" 2>/dev/null || echo "   No Django manage.py processes found"

# Kill any processes using the NEMO-CE directory
pkill -f "$NEMO_CE_PATH" 2>/dev/null || echo "   No processes using NEMO-CE directory found"

# Give processes a moment to shut down gracefully
sleep 2

# Force kill any remaining Django processes if needed
pkill -9 -f "manage.py" 2>/dev/null || true

echo "   ✅ Django server stopped"

# Remove old plugin completely
echo "🧹 Removing old plugin installation..."
if [ -d "$NEMO_CE_PATH/NEMO/plugins/mqtt" ]; then
    rm -rf "$NEMO_CE_PATH/NEMO/plugins/mqtt"
    echo "   ✅ Removed old plugin directory"
fi
if [ -d "$NEMO_CE_PATH/NEMO/plugins/mqtt_plugin" ]; then
    rm -rf "$NEMO_CE_PATH/NEMO/plugins/mqtt_plugin"
    echo "   ✅ Removed old plugin directory"
fi
if [ -d "$NEMO_CE_PATH/NEMO/plugins/NEMO_mqtt" ]; then
    rm -rf "$NEMO_CE_PATH/NEMO/plugins/NEMO_mqtt"
    echo "   ✅ Removed old plugin directory"
fi

# Remove from installed packages
echo "📦 Uninstalling old plugin package..."
if [ -d "$NEMO_CE_PATH/venv" ]; then
    "$NEMO_CE_PATH/venv/bin/pip" uninstall -y nemo-mqtt-plugin 2>/dev/null || true
else
    pip uninstall -y nemo-mqtt-plugin 2>/dev/null || true
fi

# Install the plugin package in NEMO-CE's virtual environment
echo "📦 Installing plugin package in NEMO-CE environment..."
cd "$(dirname "$0")"

# Check if NEMO-CE has a virtual environment
if [ -d "$NEMO_CE_PATH/venv" ]; then
    echo "   Using NEMO-CE virtual environment..."
    "$NEMO_CE_PATH/venv/bin/pip" install -e .
else
    echo "   Using system Python..."
    pip install -e .
fi

# Copy fresh plugin files to NEMO-CE
echo "📋 Copying fresh plugin files..."
mkdir -p "$NEMO_CE_PATH/NEMO/plugins"
cp -r "$PLUGIN_SOURCE_PATH" "$NEMO_CE_PATH/NEMO/plugins/NEMO_mqtt"

# Run migrations
echo "🗄️  Running database migrations..."
cd "$NEMO_CE_PATH"
python manage.py migrate

# Clear Django cache
echo "🧹 Clearing Django cache..."
python manage.py shell -c "from django.core.cache import cache; cache.clear()"

echo ""
echo "✅ Plugin reinstalled successfully!"
echo ""
echo "🚀 To start development:"
echo "   cd $NEMO_CE_PATH"
echo "   python manage.py runserver"
echo ""
echo "🔗 Access the MQTT monitor:"
echo "   http://localhost:8000/mqtt/monitor/"
echo ""
echo "💡 Development workflow:"
echo "   1. Edit files in: $PLUGIN_SOURCE_PATH"
echo "   2. Run: ./dev_reinstall.sh (this stops Django, reinstalls, then you restart)"
echo "   3. Start Django: cd $NEMO_CE_PATH && python manage.py runserver"
echo "   4. Refresh browser to see changes"
echo ""
echo "⚠️  Remember: Django server was stopped during reinstallation."
echo "   You need to restart it manually after each reinstall."
