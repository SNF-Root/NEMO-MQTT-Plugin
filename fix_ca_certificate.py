#!/usr/bin/env python3
"""
Fix CA Certificate - Generate a proper CA certificate with Key Usage extensions
"""

import os
import subprocess
import tempfile

def generate_proper_ca_certificate():
    """Generate a CA certificate with proper Key Usage extensions"""
    
    print("🔐 Generating proper CA certificate with Key Usage extensions...")
    
    # Create temporary directory
    cert_dir = tempfile.mkdtemp(prefix='proper_ca_cert_')
    print(f"📁 Working directory: {cert_dir}")
    
    try:
        # 1. Generate CA private key
        print("🔑 Generating CA private key...")
        ca_key_path = os.path.join(cert_dir, 'ca.key')
        subprocess.run([
            'openssl', 'genrsa', '-out', ca_key_path, '2048'
        ], check=True)
        print("✅ CA private key generated")
        
        # 2. Create CA certificate with proper extensions
        print("📜 Generating CA certificate with Key Usage extensions...")
        ca_cert_path = os.path.join(cert_dir, 'ca.crt')
        
        # Create a config file for the CA certificate with proper extensions
        config_content = """
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[req_distinguished_name]
C = US
ST = Development
L = NEMO
O = NEMO MQTT Plugin
CN = NEMO MQTT CA

[v3_ca]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical,CA:true
keyUsage = critical,keyCertSign,cRLSign
"""
        
        config_path = os.path.join(cert_dir, 'ca.conf')
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Generate CA certificate with extensions
        subprocess.run([
            'openssl', 'req', '-new', '-x509', '-days', '365',
            '-key', ca_key_path,
            '-out', ca_cert_path,
            '-config', config_path,
            '-extensions', 'v3_ca'
        ], check=True)
        print("✅ CA certificate generated with proper extensions")
        
        # 3. Verify the certificate
        print("🔍 Verifying CA certificate...")
        result = subprocess.run([
            'openssl', 'x509', '-in', ca_cert_path, '-text', '-noout'
        ], check=True, capture_output=True, text=True)
        
        # Check if Key Usage is present
        if 'Key Usage' in result.stdout and 'Certificate Sign' in result.stdout:
            print("✅ CA certificate has proper Key Usage extensions")
        else:
            print("❌ CA certificate missing Key Usage extensions")
            return None
        
        # 4. Generate server certificate signed by this CA
        print("🔐 Generating server certificate signed by CA...")
        server_key_path = os.path.join(cert_dir, 'server.key')
        server_cert_path = os.path.join(cert_dir, 'server.crt')
        
        # Generate server private key
        subprocess.run([
            'openssl', 'genrsa', '-out', server_key_path, '2048'
        ], check=True)
        
        # Generate server certificate request
        subprocess.run([
            'openssl', 'req', '-new', '-key', server_key_path,
            '-out', os.path.join(cert_dir, 'server.csr'),
            '-subj', '/C=US/ST=Development/L=NEMO/O=NEMO MQTT Plugin/CN=localhost'
        ], check=True)
        
        # Sign server certificate with CA
        subprocess.run([
            'openssl', 'x509', '-req', '-days', '365',
            '-in', os.path.join(cert_dir, 'server.csr'),
            '-CA', ca_cert_path,
            '-CAkey', ca_key_path,
            '-CAcreateserial',
            '-out', server_cert_path
        ], check=True)
        
        print("✅ Server certificate generated and signed by CA")
        
        # 5. Display the certificates
        print("\n🎉 Success! Generated proper certificates:")
        print(f"📁 Certificate directory: {cert_dir}")
        print(f"🔐 CA Certificate: {ca_cert_path}")
        print(f"🔐 Server Certificate: {server_cert_path}")
        print(f"🔐 Server Key: {server_key_path}")
        
        # Read and display the CA certificate content
        with open(ca_cert_path, 'r') as f:
            ca_content = f.read()
        
        print(f"\n📋 CA Certificate Content (copy this to NEMO):")
        print("=" * 60)
        print(ca_content)
        print("=" * 60)
        
        return {
            'ca_cert_path': ca_cert_path,
            'server_cert_path': server_cert_path,
            'server_key_path': server_key_path,
            'ca_content': ca_content,
            'cert_dir': cert_dir
        }
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error generating certificates: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def main():
    print("🔐 CA Certificate Fix Tool")
    print("=" * 50)
    print("This tool generates a proper CA certificate with Key Usage extensions")
    print("that will work with Python's SSL library.")
    print()
    
    result = generate_proper_ca_certificate()
    
    if result:
        print("\n✅ Success! Use the CA certificate content above in your NEMO configuration.")
        print("\n📝 Next steps:")
        print("1. Copy the CA certificate content above")
        print("2. Paste it in NEMO Admin → Customization → MQTT → CA Certificate")
        print("3. Save the configuration")
        print("4. Test the TLS connection")
    else:
        print("\n❌ Failed to generate certificates. Check the error messages above.")

if __name__ == "__main__":
    main()
