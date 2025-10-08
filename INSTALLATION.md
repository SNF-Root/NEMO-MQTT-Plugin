# NEMO MQTT Plugin Installation Guide

## Development vs Production Setup

### 🛠️ **Development Setup** (Current)
- **Location**: `/path/to/nemo-mqtt-plugin/`
- **Service**: `standalone_mqtt_service.py`
- **Configuration**: Hardcoded in the service
- **Purpose**: Plugin development and testing

### 🚀 **Production Setup** (NEMO-CE Integration)
- **Location**: `/path/to/your/nemo-ce/`
- **Service**: `NEMO/plugins/mqtt/external_mqtt_service.py`
- **Configuration**: Django admin interface
- **Purpose**: Real NEMO integration

## Development Workflow

### 1. **Develop Here** ✅
```bash
cd /path/to/nemo-mqtt-plugin/
./start_mqtt_system.sh  # Uses standalone_mqtt_service.py
```

### 2. **Build Package**
```bash
cd /path/to/nemo-mqtt-plugin/
python setup.py sdist bdist_wheel
```

### 3. **Install in NEMO-CE**
```bash
cd /path/to/your/nemo-ce/
pip install /path/to/nemo-mqtt-plugin/dist/nemo_mqtt_plugin-1.0.0-py3-none-any.whl
```

### 4. **Configure in NEMO-CE**
1. Add to `INSTALLED_APPS` in settings.py:
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'NEMO.plugins.NEMO_mqtt',
   ]
   ```

2. Run migrations:
   ```bash
   python manage.py migrate
   ```

3. Configure MQTT settings:
   - Go to `http://localhost:8000/customization/mqtt/`
   - Set broker host, port, authentication, etc.

### 5. **Run Production Service**
```bash
cd /path/to/your/nemo-ce/
python NEMO/plugins/NEMO_mqtt/external_mqtt_service.py
```

## Configuration

### Development (standalone_mqtt_service.py)
Edit the `config` dictionary in the service:
```python
self.config = {
    'broker_host': 'localhost',
    'broker_port': 1883,
    'username': None,  # Set if needed
    'password': None,  # Set if needed
    'use_tls': False,
    'keepalive': 60,
    'client_id': 'nemo_dev_client'
}
```

### Production (Django Admin)
- Configure via web interface at `/customization/mqtt/`
- Settings are stored in database
- Supports authentication, TLS, certificates, etc.

## Services

### Development Services
- `standalone_mqtt_service.py` - No Django dependencies
- `monitor_messages.py` - MQTT message monitor
- `test_message_flow.py` - Test script

### Production Services
- `external_mqtt_service.py` - Full Django integration
- Uses database configuration
- Runs from NEMO-CE directory

## Quick Start

### Development Testing
```bash
# Start everything
./start_mqtt_system.sh

# Test the flow
./test_mqtt_flow.py

# Stop everything
./stop_mqtt_system.sh
```

### Production Deployment
```bash
# Install plugin
cd /path/to/your/nemo-ce/
pip install /path/to/nemo-mqtt-plugin/dist/nemo_mqtt_plugin-1.0.0-py3-none-any.whl

# Configure in Django admin
# Then run:
python NEMO/plugins/mqtt/external_mqtt_service.py
```

## Troubleshooting

### Development Issues
- **Django import errors**: Use `standalone_mqtt_service.py`
- **Redis connection**: Make sure Redis is running
- **MQTT connection**: Check broker settings in service config

### Production Issues
- **Django setup errors**: Run from NEMO-CE directory
- **Database errors**: Run migrations first
- **Configuration errors**: Check Django admin settings
