#!/bin/bash
# Setup script to integrate MQTT plugin with NEMO-CE for development
# This creates a symlink so you can develop in the plugin directory
# but test in NEMO-CE without constant install/uninstall

echo "🔧 Setting up NEMO-CE integration for MQTT plugin development"
echo "=============================================================="

# Check if NEMO-CE path is provided
if [ -z "$1" ]; then
    echo "❌ Please provide the path to your NEMO-CE directory"
    echo "Usage: $0 /path/to/your/nemo-ce"
    echo ""
    echo "Example:"
    echo "  $0 /home/user/nemo-ce"
    echo "  $0 /opt/nemo-ce"
    exit 1
fi

NEMO_CE_PATH="$1"
PLUGIN_SOURCE_PATH="$(pwd)/NEMO_mqtt"
PLUGIN_TARGET_PATH="$NEMO_CE_PATH/NEMO/plugins/mqtt"

echo "📁 NEMO-CE path: $NEMO_CE_PATH"
echo "📁 Plugin source: $PLUGIN_SOURCE_PATH"
echo "📁 Plugin target: $PLUGIN_TARGET_PATH"
echo ""

# Check if NEMO-CE directory exists
if [ ! -d "$NEMO_CE_PATH" ]; then
    echo "❌ NEMO-CE directory not found: $NEMO_CE_PATH"
    exit 1
fi

# Check if NEMO-CE has the expected structure
if [ ! -f "$NEMO_CE_PATH/manage.py" ]; then
    echo "❌ This doesn't look like a NEMO-CE directory (no manage.py found)"
    exit 1
fi

# Check if plugins directory exists
if [ ! -d "$NEMO_CE_PATH/NEMO/plugins" ]; then
    echo "📁 Creating plugins directory..."
    mkdir -p "$NEMO_CE_PATH/NEMO/plugins"
fi

# Remove existing symlink or directory if it exists
if [ -L "$PLUGIN_TARGET_PATH" ] || [ -d "$PLUGIN_TARGET_PATH" ]; then
    echo "🧹 Removing existing plugin directory/symlink..."
    rm -rf "$PLUGIN_TARGET_PATH"
fi

# Create symlink
echo "🔗 Creating symlink..."
ln -s "$PLUGIN_SOURCE_PATH" "$PLUGIN_TARGET_PATH"

if [ $? -eq 0 ]; then
    echo "✅ Symlink created successfully"
else
    echo "❌ Failed to create symlink"
    exit 1
fi

echo ""
echo "📋 Next steps:"
echo "=============="
echo "1. Add to your NEMO-CE settings.py:"
echo "   INSTALLED_APPS = ["
echo "       # ... other apps"
echo "       'NEMO.plugins.mqtt',"
echo "   ]"
echo ""
echo "2. Add to your NEMO-CE urls.py:"
echo "   urlpatterns = ["
echo "       # ... other patterns"
echo "       path('mqtt/', include('NEMO.plugins.mqtt.urls')),"
echo "   ]"
echo ""
echo "3. Run migrations:"
echo "   cd $NEMO_CE_PATH"
echo "   python manage.py migrate"
echo ""
echo "4. Start NEMO-CE:"
echo "   cd $NEMO_CE_PATH"
echo "   python manage.py runserver"
echo ""
echo "5. Access the MQTT monitor:"
echo "   http://localhost:8000/mqtt/monitor/"
echo ""
echo "🎉 Development setup complete!"
echo "   - Edit files in: $PLUGIN_SOURCE_PATH"
echo "   - Changes will be reflected immediately in NEMO-CE"
echo "   - No need to reinstall the plugin"
