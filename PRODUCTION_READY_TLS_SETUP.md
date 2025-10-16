# 🎯 Production-Ready TLS Setup Guide

## 🚀 **Option A: Use Production Certificates (Recommended)**

This approach makes your development environment **exactly match production**, ensuring your tests are reliable.

## 📋 **What You Need from Your VM Broker**

Get these files from your production VM broker:

1. **CA Certificate** (`.crt` or `.pem` file) - You already have this ✅
2. **Server Certificate** (`.crt` or `.pem` file) - **You need this**
3. **Server Private Key** (`.key` file) - **You need this**

## 🔧 **How to Get the Certificates from Your VM**

### **Method 1: Copy from VM Broker Configuration**
```bash
# On your VM, find the Mosquitto configuration
sudo find / -name "*.conf" -exec grep -l "cafile\|certfile\|keyfile" {} \;

# Look for lines like:
# cafile /path/to/ca.crt
# certfile /path/to/server.crt  
# keyfile /path/to/server.key

# Copy these files to your local machine
scp user@vm:/path/to/ca.crt ./
scp user@vm:/path/to/server.crt ./
scp user@vm:/path/to/server.key ./
```

### **Method 2: Export from VM Broker**
```bash
# If you have access to the VM broker configuration
# Look in /etc/mosquitto/ or similar directories
ls -la /etc/mosquitto/
cat /etc/mosquitto/mosquitto.conf | grep -E "(cafile|certfile|keyfile)"
```

## 📝 **Configure NEMO with Production Certificates**

1. **Go to NEMO Admin** → Customization → MQTT
2. **Fill in the TLS settings:**
   - ✅ Enable SSL/TLS encryption
   - Set TLS version (e.g., TLSv1.2)
   - **CA Certificate**: Paste your VM's CA certificate content
   - **Server Certificate**: Paste your VM's server certificate content
   - **Server Private Key**: Paste your VM's server private key content
3. **Save the configuration**

## 🔄 **How It Works Now**

### **Development Environment (AUTO Mode):**
```
NEMO Client → Uses VM's CA certificate for verification
Development Broker → Uses VM's server certificate + key
Result: ✅ Perfect match with production!
```

### **Production Environment (EXTERNAL Mode):**
```
NEMO Client → Uses VM's CA certificate for verification  
VM Broker → Uses VM's server certificate + key
Result: ✅ Same certificates, same behavior!
```

## 🎯 **Benefits of This Approach**

1. **Perfect Production Match**: Development uses identical certificates
2. **Real TLS Testing**: Tests actual production TLS behavior
3. **No Certificate Mismatches**: Same CA verifies same server certificates
4. **Production Confidence**: What works in dev will work in production

## 🔍 **What Happens During Connection**

### **TLS Handshake Process:**
```
1. NEMO Client connects to broker
2. Broker sends VM's server certificate
3. NEMO Client checks: "Is this signed by VM's CA?"
4. Answer: "YES!" ✅
5. Connection established with full TLS encryption
```

## 🚨 **Security Notes**

- **Server Private Key**: Keep this secure - it's the broker's identity
- **CA Certificate**: This is public - safe to share
- **Development Only**: These certificates are for development testing
- **Production**: Use your actual production broker for real traffic

## 🛠️ **Troubleshooting**

### **If Connection Fails:**
1. **Check certificate format**: Must be PEM format
2. **Verify certificate chain**: Server cert must be signed by CA
3. **Check hostname**: Server cert should match broker hostname
4. **Check expiration**: Certificates must not be expired

### **Debug Output to Look For:**
```
🔐 Using production CA certificate for development broker...
🔐 Using production server certificate and key...
✅ Using production certificates:
🔐   CA: /tmp/ca_xyz.pem
🔐   Server Cert: /tmp/server_xyz.pem  
🔐   Server Key: /tmp/key_xyz.pem
```

## 🎉 **Success Indicators**

When it works, you'll see:
- ✅ Broker starts with production certificates
- ✅ Client connects using production CA
- ✅ TLS handshake succeeds
- ✅ Full encryption established
- ✅ Messages flow securely

This setup gives you **production-identical TLS testing**! 🚀
