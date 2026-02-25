# HMAC Message Authentication

## Overview

The NEMO MQTT plugin uses **HMAC (Hash-based Message Authentication Code)** to sign MQTT payloads. This provides:

- **Authenticity** – Subscribers can verify messages came from a sender that shares the secret.
- **Integrity** – Any change to the payload invalidates the signature.

The MQTT connection itself is **plain TCP** (no TLS). Security is at the message level: each published payload is optionally wrapped in a JSON envelope containing the original payload, an HMAC signature, and the algorithm name.

## How It Works

1. **Configuration** – In NEMO Admin → Customization → MQTT you enable “Sign MQTT payloads with HMAC” and set a **shared secret key** (and optionally the hash algorithm: SHA-256, SHA-384, or SHA-512).

2. **Publishing** – When the bridge publishes to the broker, it computes `HMAC(secret_key, payload)` and sends a JSON object:
   ```json
   {"payload": "<original payload>", "hmac": "<hex signature>", "algo": "sha256"}
   ```

3. **Subscribing** – Your subscriber uses the same secret and algorithm. It parses the JSON, recomputes `HMAC(secret_key, payload)`, and compares it to `hmac` (using a constant-time comparison). If they match, the message is authentic and unchanged.

## Setup

1. **Configure NEMO**: Admin → Customization → MQTT  
   - Enable **Use HMAC signing**.  
   - Set **HMAC secret key** (shared with your subscribers).  
   - Choose **Hash algorithm** (e.g. SHA-256).

2. **Broker** – Use standard port **1883** (no TLS). Ensure the broker is only reachable on a trusted network if the transport is unencrypted.

3. **Subscribers** – Use the same secret and algorithm. You can use the plugin’s `verify_payload_hmac()` helper (see below) or implement verification in your own stack.

## Verifying Messages (Python)

The plugin provides a helper in `nemo_mqtt.utils`:

```python
from nemo_mqtt.utils import verify_payload_hmac

# envelope_json is the MQTT message payload (JSON string)
valid, original_payload = verify_payload_hmac(envelope_json, your_secret_key)
if valid:
    # Use original_payload (the inner payload string)
    process(original_payload)
else:
    # Reject: invalid or tampered
    pass
```

## Security Notes

- **Secret key** – Store the HMAC secret securely (e.g. environment variable or secrets manager). Do not commit it to version control.
- **Transport** – Without TLS, the wire is unencrypted. HMAC does not provide confidentiality. Use HMAC on trusted or isolated networks, or combine with network-level encryption (e.g. VPN) if needed.
- **Algorithm** – SHA-256 is a good default; SHA-384 or SHA-512 are also supported.

## Disabling HMAC

If **Use HMAC signing** is off (or no secret is set), payloads are published as-is with no envelope. Subscribers then receive the raw JSON payload from NEMO (e.g. event data) and do not need to verify an HMAC.
