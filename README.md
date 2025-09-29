# NEMO MQTT Plugin

MQTT integration for NEMO tool usage events.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Redis:**
   ```bash
   # Ubuntu/Debian
   sudo systemctl start redis-server
   
   # macOS
   brew services start redis
   ```

3. **Start MQTT broker:**
   ```bash
   # Using mosquitto
   mosquitto -c /path/to/mosquitto.conf
   
   # Or using Docker
   docker run -d -p 1883:1883 eclipse-mosquitto
   ```

4. **Start external MQTT service:**
   ```bash
   python external_mqtt_service.py
   ```

5. **Start Django:**
   ```bash
   python manage.py runserver
   ```

## Configuration

Configure MQTT settings in Django admin → MQTT Plugin → MQTT Configurations.

## Testing

```bash
python test_mqtt.py
```

## Architecture

```
Django NEMO → Redis → External MQTT Service → MQTT Broker
```

The plugin uses Redis as an intermediary to separate Django from MQTT connection management, preventing reconnection loops.