# NEMO MQTT Plugin

[![PyPI version](https://badge.fury.io/py/nemo-mqtt-plugin.svg)](https://badge.fury.io/py/nemo-mqtt-plugin)
[![Python Support](https://img.shields.io/pypi/pyversions/nemo-mqtt-plugin.svg)](https://pypi.org/project/nemo-mqtt-plugin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Django plugin that provides MQTT integration for NEMO tool usage events. This plugin enables real-time publishing of tool usage data to MQTT brokers, making it easy to integrate NEMO with IoT systems and real-time monitoring dashboards.

## Features

- 🔌 **Easy Integration**: Simple Django plugin installation
- 📡 **MQTT Publishing**: Real-time tool usage event publishing
- 🔄 **Redis Bridge**: Uses Redis as intermediary to prevent connection issues
- 📊 **Monitoring**: Built-in monitoring and health checks
- ⚙️ **Configurable**: Admin interface for MQTT configuration
- 🔒 **Secure**: Supports SSL/TLS connections and authentication

## Installation

### From PyPI (Recommended)

```bash
pip install nemo-mqtt-plugin
```

### From Source

```bash
git clone https://github.com/SNF-Root/NEMO-MQTT-Plugin.git
cd NEMO-MQTT-Plugin
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/SNF-Root/NEMO-MQTT-Plugin.git
cd NEMO-MQTT-Plugin
pip install -e .[dev]
```

## Quick Start

### **Option 1: Automatic Setup (Recommended)**

1. **Install the plugin:**
   ```bash
   pip install nemo-mqtt-plugin
   ```

2. **Run the setup command:**
   ```bash
   cd /path/to/your/nemo-ce
   python manage.py setup_nemo_integration
   ```

3. **Run migrations:**
   ```bash
   python manage.py migrate nemo_mqtt
   ```

4. **Start Redis:**
   ```bash
   # Ubuntu/Debian
   sudo systemctl start redis-server
   
   # macOS
   brew services start redis
   ```

5. **Start MQTT broker:**
   ```bash
   # Using mosquitto
   mosquitto -c /path/to/mosquitto.conf
   
   # Or using Docker
   docker run -d -p 1883:1883 eclipse-mosquitto
   ```

6. **Start external MQTT service:**
   ```bash
   python -m nemo_mqtt.external_mqtt_service
   ```

7. **Configure MQTT settings:**
   - Go to Django admin → MQTT Plugin → MQTT Configurations
   - Add your MQTT broker details

### **Option 2: Manual Setup**

1. **Install the plugin:**
   ```bash
   pip install nemo-mqtt-plugin
   ```

2. **Add to Django settings:**
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'nemo_mqtt',
   ]
   ```

3. **Add URLs to NEMO/urls.py:**
   ```python
   urlpatterns += [
       path("mqtt/", include("nemo_mqtt.urls")),
   ]
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate nemo_mqtt
   ```

5. **Continue with steps 4-7 from Option 1**

## Configuration

Configure MQTT settings through the Django admin interface:
- **Broker Host**: MQTT broker address
- **Port**: MQTT broker port (default: 1883)
- **Username/Password**: Authentication credentials
- **SSL/TLS**: Enable secure connections
- **Topics**: Customize MQTT topic structure

## Architecture

```
Django NEMO → Redis → External MQTT Service → MQTT Broker
```

The plugin uses Redis as an intermediary to separate Django from MQTT connection management, preventing reconnection loops and ensuring reliable message delivery.

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black nemo_mqtt/
isort nemo_mqtt/
```

### Linting

```bash
flake8 nemo_mqtt/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](https://github.com/SNF-Root/NEMO-MQTT-Plugin#readme)
- 🐛 [Issue Tracker](https://github.com/SNF-Root/NEMO-MQTT-Plugin/issues)
- 💬 [Discussions](https://github.com/SNF-Root/NEMO-MQTT-Plugin/discussions)