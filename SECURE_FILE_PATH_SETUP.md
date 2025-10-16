# 🔒 Secure File Path Setup Guide

## ✅ **Database Storage Removed - File Paths Only**

I've removed all database storage options for server certificates. Now it's **file paths only** - much more secure!

## 🛠️ **Setup Steps**

### **Step 1: Get Certificates from Your VM Broker**

```bash
# Copy certificates from your VM to your local machine
scp user@vm:/path/to/ca.crt ./
scp user@vm:/path/to/server.crt ./
scp user@vm:/path/to/server.key ./
```

### **Step 2: Create Secure Certificate Directory**

```bash
# Create dedicated directory for certificates
sudo mkdir -p /etc/nemo-mqtt/certs

# Set proper ownership (replace 'nemo' with your NEMO user)
sudo chown nemo:nemo /etc/nemo-mqtt/certs

# Set secure permissions
sudo chmod 700 /etc/nemo-mqtt/certs
```

### **Step 3: Copy Certificates with Proper Permissions**

```bash
# Copy CA certificate (public - can be readable)
sudo cp ca.crt /etc/nemo-mqtt/certs/
sudo chmod 644 /etc/nemo-mqtt/certs/ca.crt
sudo chown nemo:nemo /etc/nemo-mqtt/certs/ca.crt

# Copy server certificate (public - can be readable)
sudo cp server.crt /etc/nemo-mqtt/certs/
sudo chmod 644 /etc/nemo-mqtt/certs/server.crt
sudo chown nemo:nemo /etc/nemo-mqtt/certs/server.crt

# Copy server private key (PRIVATE - must be secure)
sudo cp server.key /etc/nemo-mqtt/certs/
sudo chmod 600 /etc/nemo-mqtt/certs/server.key  # Only owner can read/write
sudo chown nemo:nemo /etc/nemo-mqtt/certs/server.key
```

### **Step 4: Configure NEMO**

1. **Go to NEMO Admin** → Customization → MQTT
2. **Fill in the TLS settings:**
   - ✅ Enable SSL/TLS encryption
   - Set TLS version (e.g., TLSv1.2)
   - **CA Certificate**: Paste your CA certificate content
   - **Server Certificate Path**: `/etc/nemo-mqtt/certs/server.crt`
   - **Server Private Key Path**: `/etc/nemo-mqtt/certs/server.key`
3. **Save the configuration**

## 🔒 **Security Benefits**

- ✅ **No private keys in database**
- ✅ **No private keys in admin interface**
- ✅ **Proper file permissions (600 for private keys)**
- ✅ **Standard security practice**
- ✅ **Production-ready approach**

## 🎯 **How It Works**

### **Development Broker:**
```
Uses your production server certificate + key from files
Uses your production CA certificate for client verification
Result: Perfect production match! 🎉
```

### **Client Connection:**
```
Uses your production CA certificate for verification
Connects to broker using production certificates
Result: Full TLS encryption with production certificates! 🔐
```

## 🔍 **Verification**

When it works, you'll see:
```
🔐 Using production server certificate and key from files...
✅ Using production certificates from files:
🔐   CA: /tmp/ca_xyz.pem
🔐   Server Cert: /etc/nemo-mqtt/certs/server.crt
🔐   Server Key: /etc/nemo-mqtt/certs/server.key
```

## 🚨 **Security Notes**

- **Private keys are never stored in the database**
- **Private keys are never visible in the admin interface**
- **File permissions protect private keys (600 = owner only)**
- **This is the standard approach for production systems**

## 🎉 **Result**

You now have a **secure, production-ready TLS setup** that:
- Uses file paths only (no database storage)
- Matches your production environment exactly
- Follows security best practices
- Is ready for production use

**This is the most secure approach possible!** 🛡️
