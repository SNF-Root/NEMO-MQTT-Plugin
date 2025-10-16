# NEMO MQTT Plugin - AUTO vs EXTERNAL Modes

## 🎯 **Your Requirement: Always Use NEMO Configuration**

Both AUTO and EXTERNAL modes now **always** use the port number and CA certificate from your NEMO configuration page, regardless of which mode is active.

## 📋 **Mode Comparison**

| Aspect | AUTO Mode | EXTERNAL Mode |
|--------|-----------|---------------|
| **Port Number** | ✅ Uses `broker_port` from NEMO config | ✅ Uses `broker_port` from NEMO config |
| **CA Certificate** | ✅ Uses `ca_cert_content` from NEMO config | ✅ Uses `ca_cert_content` from NEMO config |
| **TLS Version** | ✅ Uses `tls_version` from NEMO config | ✅ Uses `tls_version` from NEMO config |
| **Authentication** | ✅ Uses `username/password` from NEMO config | ✅ Uses `username/password` from NEMO config |
| **Redis** | 🔧 Starts its own Redis server | 🔌 Connects to existing Redis |
| **MQTT Broker** | 🔧 Starts its own Mosquitto broker | 🔌 Connects to existing MQTT broker |

## 🔧 **AUTO Mode (Development/Testing)**

### **What it does:**
1. **Loads your NEMO configuration** (port, CA cert, TLS settings, auth)
2. **Starts its own Redis server** (for development)
3. **Starts its own Mosquitto broker** using your configuration:
   - Uses your `broker_port` (e.g., 8883)
   - Uses your `ca_cert_content` for TLS
   - Uses your `tls_version` setting
   - Uses your `username/password` for auth
4. **Connects to both services** using your configuration

### **When to use:**
- Development and testing
- When you don't have external Redis/MQTT services
- When you want everything managed automatically

## 🔌 **EXTERNAL Mode (Production)**

### **What it does:**
1. **Loads your NEMO configuration** (port, CA cert, TLS settings, auth)
2. **Connects to existing Redis server** (you manage it)
3. **Connects to existing MQTT broker** using your configuration:
   - Uses your `broker_port` (e.g., 8883)
   - Uses your `ca_cert_content` for TLS
   - Uses your `tls_version` setting
   - Uses your `username/password` for auth

### **When to use:**
- Production environments
- When you have external Redis/MQTT services
- When you want full control over your infrastructure

## 🔐 **TLS Configuration Behavior**

### **Both Modes:**
- **Always use your CA certificate** from the NEMO configuration page
- **Always use your port number** from the NEMO configuration page
- **Always use your TLS version** from the NEMO configuration page
- **Always use your authentication** from the NEMO configuration page

### **AUTO Mode TLS Process:**
1. Reads your `ca_cert_content` from NEMO config
2. Creates temporary CA certificate file
3. Generates server certificate signed by your CA
4. Configures Mosquitto with your CA and generated server cert
5. Client connects using your CA certificate

### **EXTERNAL Mode TLS Process:**
1. Reads your `ca_cert_content` from NEMO config
2. Creates temporary CA certificate file
3. Client connects to external broker using your CA certificate

## 🚀 **How to Use**

### **For Development (AUTO Mode):**
```bash
# This is the default when running through Django
# The bridge automatically starts in AUTO mode
python manage.py runserver
```

### **For Production (EXTERNAL Mode):**
```bash
# Run as standalone service
python nemo_mqtt/redis_mqtt_bridge.py
```

## 📝 **Configuration Steps**

1. **Go to NEMO Admin** → Customization → MQTT
2. **Set your broker details:**
   - Broker Host: `localhost` (or your broker IP)
   - Broker Port: `8883` (or your TLS port)
   - Enable SSL/TLS: ✅
   - TLS Version: `TLSv1.2` (or your preferred version)
   - CA Certificate: Paste your CA certificate content
   - Username/Password: If required
3. **Save the configuration**
4. **Start the bridge** (it will use your settings in both modes)

## ✅ **Key Benefits**

- **Consistent Configuration**: Both modes use the same NEMO configuration
- **No Mode Switching**: Your settings work regardless of mode
- **Easy Testing**: AUTO mode uses your real configuration for testing
- **Production Ready**: EXTERNAL mode uses your real configuration for production
- **TLS Support**: Both modes properly handle your CA certificates

## 🔍 **Debugging**

The bridge provides detailed logging showing:
- Which configuration values are being used
- Which mode is active (AUTO/EXTERNAL)
- TLS certificate loading process
- Connection attempts and results

Look for these log messages:
- `✅ MQTT configuration loaded: [name]`
- `📍 Broker: [host]:[port]`
- `🔐 TLS: Enabled`
- `🔐 CA Certificate: Found in content field`
- `✅ CA Certificate: Successfully loaded into SSL context`
