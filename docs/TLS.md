# TLS/SSL Setup Guide

## Overview

The NEMO MQTT plugin supports TLS for secure connections to MQTT brokers. This guide covers both simple (CA-only) and advanced (client certificate) setups.

## Simple Setup (Recommended)

**For production TLS, you typically only need:**
- **CA Certificate** – to verify the broker's identity
- **TLS settings** – version, port (usually 8883)

### How TLS Client Verification Works

1. NEMO connects to your MQTT broker
2. Broker sends its server certificate
3. NEMO uses your CA certificate to verify the server certificate
4. If verification passes → TLS connection established
5. If verification fails → Connection rejected

### Setup Steps

1. **Get CA certificate from your broker:**
   ```bash
   scp user@broker-vm:/path/to/ca.crt ./
   ```

2. **Configure NEMO**: Go to NEMO Admin → Customization → MQTT
   - Enable SSL/TLS encryption
   - Set TLS version (e.g., TLSv1.2)
   - Paste CA certificate content
   - Set Broker Host and Broker Port (8883 for TLS)

3. **Test**: Connection succeeds if the broker's certificate is signed by your CA.

### Development vs Production

- **AUTO mode**: Generates self-signed certs for local broker; uses your CA for client verification
- **EXTERNAL mode**: Connects to your broker; uses your CA to verify the broker

## Advanced: Production Certificates for Development

To match production exactly during development:

1. Copy from your VM broker: `ca.crt`, `server.crt`, `server.key`
2. Configure NEMO with all three (CA, server cert, server key)
3. AUTO mode will use these for the local development broker

```bash
# Find cert paths on VM
sudo find / -name "*.conf" -exec grep -l "cafile\|certfile\|keyfile" {} \;
# Typically in /etc/mosquitto/
```

## Security Best Practices

| Method | Security | When to Use |
|--------|----------|-------------|
| **File paths** | High | Production – private keys stay on filesystem with proper permissions |
| **Certificate content in DB** | Medium | Development – convenient but avoid for production |
| **Environment variables** | High | Production – e.g. `NEMO_MQTT_CLIENT_KEY_PATH` |

### Secure File Path Setup

```bash
sudo mkdir -p /etc/nemo-mqtt/certs
sudo chown nemo:nemo /etc/nemo-mqtt/certs
sudo chmod 700 /etc/nemo-mqtt/certs

# CA (public)
sudo cp ca.crt /etc/nemo-mqtt/certs/
sudo chmod 644 /etc/nemo-mqtt/certs/ca.crt

# Client key (private – must be secure)
sudo cp client.key /etc/nemo-mqtt/certs/
sudo chmod 600 /etc/nemo-mqtt/certs/client.key
```

Configure NEMO with file paths instead of pasting content when possible.

### Avoid in Production

- Storing private keys in the database
- Exposing private keys in the admin UI
- Using database content fields for production credentials

## Troubleshooting

- **Connection fails**: Check cert format (PEM), verify chain, ensure hostname matches cert
- **Certificate errors**: Ensure certs are not expired; server cert must be signed by CA
- **Debug**: Set `log_level` to DEBUG in MQTT configuration
