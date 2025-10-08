# MQTT Plugin Development Guide

## Quick Setup for NEMO-CE Integration

### 1. **Run the Setup Script**
```bash
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
./setup_nemo_integration.sh /path/to/your/nemo-ce
```

### 2. **Configure NEMO-CE**

#### Add to `settings.py`:
```python
INSTALLED_APPS = [
    # ... other apps
    'NEMO.plugins.mqtt',
]
```

#### Add to `urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('mqtt/', include('NEMO.plugins.mqtt.urls')),
]
```

### 3. **Run Migrations**
```bash
cd /path/to/your/nemo-ce/
python manage.py migrate
```

### 4. **Start Development**
```bash
# Terminal 1: Start NEMO-CE
cd /path/to/your/nemo-ce/
python manage.py runserver

# Terminal 2: Start MQTT system (for testing)
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
./start_mqtt_system.sh
```

### 5. **Access the Monitor**
- **MQTT Monitor**: http://localhost:8000/mqtt/monitor/
- **MQTT Configuration**: http://localhost:8000/customization/mqtt/

## Development Workflow

### **Edit Files Here** ✅
- All changes in `/Users/adenton/Desktop/nemo-mqtt-plugin/NEMO_mqtt/`
- Changes are immediately reflected in NEMO-CE
- No need to reinstall the plugin

### **Test in NEMO-CE** ✅
- Refresh browser to see changes
- Full Django environment available
- Database integration working

### **Key Files to Edit**
- `templates/NEMO_mqtt/monitor.html` - The monitor page UI
- `views.py` - Backend logic for the monitor
- `urls.py` - URL routing
- `models.py` - Database models
- `admin.py` - Admin interface

## Features Available

### **MQTT Monitor Page**
- ✅ Real-time message display
- ✅ JSON syntax highlighting
- ✅ Message filtering (source, topic)
- ✅ Auto-refresh option
- ✅ Start/stop monitoring controls
- ✅ Message history (last 100 messages)

### **MQTT Configuration**
- ✅ Broker settings (host, port, auth)
- ✅ TLS/SSL configuration
- ✅ Topic prefixes and QoS settings
- ✅ Django admin interface

## Testing the Integration

### 1. **Start the MQTT System**
```bash
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
./start_mqtt_system.sh
```

### 2. **Generate Test Messages**
```bash
python test_message_flow.py
```

### 3. **View in NEMO-CE**
- Go to http://localhost:8000/mqtt/monitor/
- Click "Start Monitoring"
- Enable "Auto Refresh"
- Watch messages appear in real-time

## Troubleshooting

### **Symlink Issues**
```bash
# Check if symlink exists
ls -la /path/to/your/nemo-ce/NEMO/plugins/

# Recreate if needed
rm /path/to/your/nemo-ce/NEMO/plugins/mqtt
ln -s /Users/adenton/Desktop/nemo-mqtt-plugin/NEMO_mqtt /path/to/your/nemo-ce/NEMO/plugins/mqtt
```

### **Django Import Errors**
- Make sure you're running from the NEMO-CE directory
- Check that the plugin is in `INSTALLED_APPS`
- Run migrations: `python manage.py migrate`

### **MQTT Connection Issues**
- Check Redis is running: `redis-cli ping`
- Check MQTT broker is running: `mosquitto_pub -h localhost -p 1883 -t test -m test`
- Check the standalone MQTT service is running

## Production Deployment

When ready for production:

1. **Build the package**:
   ```bash
   python setup.py sdist bdist_wheel
   ```

2. **Install in production NEMO-CE**:
   ```bash
   pip install dist/nemo_mqtt_plugin-1.0.0-py3-none-any.whl
   ```

3. **Configure and run**:
   ```bash
   # Configure in Django admin
   # Then run the external service
   python NEMO/plugins/mqtt/external_mqtt_service.py
   ```
