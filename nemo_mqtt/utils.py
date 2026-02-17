"""
Utility functions for MQTT plugin.
"""
import json
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse

logger = logging.getLogger(__name__)


def get_mqtt_config() -> Optional['MQTTConfiguration']:
    """
    Get MQTT configuration from database with caching.
    
    Cache is automatically cleared when configuration is saved in Django admin.
    This ensures configuration changes take effect immediately without restart.
    
    Returns:
        MQTTConfiguration instance or None if not configured
    """
    from django.core.cache import cache
    
    # Try to get from cache first
    config = cache.get('mqtt_active_config')
    
    if config is not None:
        # Return cached config (could be None if no config exists)
        return config if config != 'NO_CONFIG' else None
    
    # Cache miss - query database
    try:
        from .models import MQTTConfiguration
        
        # Get the first enabled configuration
        config = MQTTConfiguration.objects.filter(enabled=True).first()
        
        # Cache the result (cache None as special value to avoid repeated queries)
        # Cache timeout: 300 seconds (5 minutes) as fallback if signals don't fire
        if config:
            cache.set('mqtt_active_config', config, 300)
        else:
            cache.set('mqtt_active_config', 'NO_CONFIG', 300)
        
        return config
    except Exception as e:
        logger.warning(f"Could not load MQTT configuration from database: {e}")
        return None


def format_topic(topic_prefix: str, event_type: str, resource_id: Optional[str] = None) -> str:
    """
    Format MQTT topic based on event type and resource ID.
    
    Args:
        topic_prefix: Base topic prefix
        event_type: Type of event (e.g., 'tool_save', 'reservation_created')
        resource_id: Optional resource ID to include in topic
        
    Returns:
        Formatted MQTT topic string
    """
    topic_parts = [topic_prefix, event_type]
    if resource_id:
        topic_parts.append(str(resource_id))
    
    return "/".join(topic_parts)


def serialize_model_instance(instance, fields: Optional[list] = None) -> Dict[str, Any]:
    """
    Serialize a Django model instance to a dictionary.
    
    Args:
        instance: Django model instance
        fields: Optional list of fields to include (if None, includes all fields)
        
    Returns:
        Dictionary representation of the model instance
    """
    if fields is None:
        fields = [field.name for field in instance._meta.fields]
    
    data = {}
    for field_name in fields:
        if hasattr(instance, field_name):
            value = getattr(instance, field_name)
            if hasattr(value, 'isoformat'):  # Handle datetime fields
                data[field_name] = value.isoformat()
            elif hasattr(value, 'id'):  # Handle foreign key fields
                data[field_name] = value.id
            else:
                data[field_name] = value
    
    return data


def log_mqtt_message(topic: str, payload: str, qos: int = 0, retained: bool = False, 
                    success: bool = True, error_message: str = None):
    """
    Log MQTT message to database for debugging and monitoring.
    
    Args:
        topic: MQTT topic
        payload: Message payload
        qos: Quality of Service level
        retained: Whether message was retained
        success: Whether message was sent successfully
        error_message: Error message if sending failed
    """
    try:
        from .models import MQTTMessageLog
        
        MQTTMessageLog.objects.create(
            topic=topic,
            payload=payload,
            qos=qos,
            retained=retained,
            success=success,
            error_message=error_message
        )
    except Exception as e:
        logger.error(f"Failed to log MQTT message: {e}")


def is_event_enabled(event_type: str) -> bool:
    """
    Check if a specific event type is enabled for MQTT publishing.
    
    Args:
        event_type: Type of event to check
        
    Returns:
        True if event is enabled, False otherwise
    """
    try:
        from .models import MQTTEventFilter
        
        filter_obj = MQTTEventFilter.objects.filter(event_type=event_type).first()
        if filter_obj:
            return filter_obj.enabled
        
        # Default to enabled if no filter exists
        return True
    except Exception as e:
        logger.warning(f"Could not check event filter for {event_type}: {e}")
        return True


def get_event_topic_override(event_type: str) -> Optional[str]:
    """
    Get custom topic override for an event type.
    
    Args:
        event_type: Type of event
        
    Returns:
        Custom topic string if configured, None otherwise
    """
    try:
        from .models import MQTTEventFilter
        
        filter_obj = MQTTEventFilter.objects.filter(event_type=event_type).first()
        if filter_obj and filter_obj.topic_override:
            return filter_obj.topic_override
        
        return None
    except Exception as e:
        logger.warning(f"Could not get topic override for {event_type}: {e}")
        return None


def validate_tls_certificate(cert_content: str, cert_type: str = "CA") -> dict:
    """
    Validate TLS certificate content and return detailed information.
    
    Args:
        cert_content: Certificate content in PEM format
        cert_type: Type of certificate ("CA", "CLIENT", "KEY")
    
    Returns:
        Dictionary with validation results and certificate info
    """
    import ssl
    import tempfile
    import os
    from datetime import datetime
    
    result = {
        'valid': False,
        'error': None,
        'cert_info': {},
        'preview': cert_content[:100] + "..." if len(cert_content) > 100 else cert_content
    }
    
    if not cert_content or not cert_content.strip():
        result['error'] = f"No {cert_type} certificate content provided"
        return result
    
    try:
        # Check if it looks like a PEM certificate
        if cert_type == "KEY":
            if not ("-----BEGIN PRIVATE KEY-----" in cert_content or "-----BEGIN RSA PRIVATE KEY-----" in cert_content):
                result['error'] = "Certificate content doesn't look like a private key (missing BEGIN PRIVATE KEY)"
                return result
        else:
            if not "-----BEGIN CERTIFICATE-----" in cert_content:
                result['error'] = "Certificate content doesn't look like a certificate (missing BEGIN CERTIFICATE)"
                return result
        
        # Create temporary file for certificate
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as temp_file:
            temp_file.write(cert_content)
            temp_file_path = temp_file.name
        
        try:
            if cert_type == "KEY":
                # For private keys, we can't easily validate without the certificate
                result['valid'] = True
                result['cert_info'] = {
                    'type': 'private_key',
                    'size': len(cert_content),
                    'preview': cert_content[:50] + "..."
                }
            else:
                # Load and validate certificate
                cert = ssl._ssl._test_decode_cert(temp_file_path)
                if cert:
                    result['valid'] = True
                    result['cert_info'] = {
                        'subject': dict(x[0] for x in cert.get('subject', [])),
                        'issuer': dict(x[0] for x in cert.get('issuer', [])),
                        'version': cert.get('version'),
                        'serial_number': cert.get('serialNumber'),
                        'not_before': cert.get('notBefore'),
                        'not_after': cert.get('notAfter'),
                        'size': len(cert_content)
                    }
                else:
                    result['error'] = "Failed to parse certificate"
        finally:
            # Clean up temp file
            os.unlink(temp_file_path)
            
    except Exception as e:
        result['error'] = f"Certificate validation failed: {str(e)}"
    
    return result


def test_tls_connection(config) -> dict:
    """
    Test TLS connection to MQTT broker with detailed debugging.
    
    Args:
        config: MQTTConfiguration instance
    
    Returns:
        Dictionary with test results and debugging information
    """
    import ssl
    import socket
    import tempfile
    import os
    
    result = {
        'success': False,
        'error': None,
        'debug_info': {},
        'steps': []
    }
    
    if not config.use_tls:
        result['error'] = "TLS is not enabled in configuration"
        return result
    
    try:
        # Step 1: Basic connectivity test
        result['steps'].append("Testing basic connectivity...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((config.broker_host, config.broker_port))
        sock.close()
        result['steps'].append("✅ Basic connectivity successful")
        
        # Step 2: Create SSL context
        result['steps'].append("Creating SSL context...")
        context = ssl.create_default_context()
        
        # Step 3: Configure TLS version
        result['steps'].append(f"Configuring TLS version: {config.tls_version}")
        
        # Set minimum and maximum TLS versions
        if config.tls_version == 'tlsv1':
            context.minimum_version = ssl.TLSVersion.TLSv1
            context.maximum_version = ssl.TLSVersion.TLSv1
        elif config.tls_version == 'tlsv1.1':
            context.minimum_version = ssl.TLSVersion.TLSv1_1
            context.maximum_version = ssl.TLSVersion.TLSv1_1
        elif config.tls_version == 'tlsv1.2':
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_2
        elif config.tls_version == 'tlsv1.3':
            context.minimum_version = ssl.TLSVersion.TLSv1_3
            context.maximum_version = ssl.TLSVersion.TLSv1_3
        else:
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.maximum_version = ssl.TLSVersion.TLSv1_2
            result['steps'].append(f"⚠️  Unknown TLS version {config.tls_version}, using default (TLSv1.2)")
        
        result['steps'].append(f"✅ TLS version range: {context.minimum_version} to {context.maximum_version}")
        
        # Step 4: Load CA certificate
        ca_loaded = False
        if config.ca_cert_content:
            result['steps'].append("Loading CA certificate from content...")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as ca_file:
                ca_file.write(config.ca_cert_content)
                ca_file_path = ca_file.name
            
            try:
                context.load_verify_locations(ca_file_path)
                ca_loaded = True
                result['steps'].append("✅ CA certificate loaded successfully")
            except Exception as e:
                result['steps'].append(f"❌ Failed to load CA certificate: {e}")
            finally:
                os.unlink(ca_file_path)
        elif config.ca_cert_path:
            result['steps'].append(f"Loading CA certificate from file: {config.ca_cert_path}")
            try:
                context.load_verify_locations(config.ca_cert_path)
                ca_loaded = True
                result['steps'].append("✅ CA certificate loaded successfully")
            except Exception as e:
                result['steps'].append(f"❌ Failed to load CA certificate: {e}")
        else:
            result['steps'].append("ℹ️  No CA certificate provided, using system defaults")
        
        # Step 5: Load client certificate
        client_cert_loaded = False
        if config.client_cert_content and config.client_key_content:
            result['steps'].append("Loading client certificate from content...")
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as cert_file:
                cert_file.write(config.client_cert_content)
                cert_file_path = cert_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as key_file:
                key_file.write(config.client_key_content)
                key_file_path = key_file.name
            
            try:
                context.load_cert_chain(cert_file_path, key_file_path)
                client_cert_loaded = True
                result['steps'].append("✅ Client certificate loaded successfully")
            except Exception as e:
                result['steps'].append(f"❌ Failed to load client certificate: {e}")
            finally:
                os.unlink(cert_file_path)
                os.unlink(key_file_path)
        elif config.client_cert_path and config.client_key_path:
            result['steps'].append("Loading client certificate from files...")
            try:
                context.load_cert_chain(config.client_cert_path, config.client_key_path)
                client_cert_loaded = True
                result['steps'].append("✅ Client certificate loaded successfully")
            except Exception as e:
                result['steps'].append(f"❌ Failed to load client certificate: {e}")
        else:
            result['steps'].append("ℹ️  No client certificate provided")
        
        # Step 6: Configure verification (always use secure mode)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        result['steps'].append("✅ TLS verification enabled")
        
        # Step 7: Test SSL connection
        result['steps'].append("Testing SSL connection...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        ssl_sock = context.wrap_socket(sock, server_hostname=config.broker_host)
        
        try:
            ssl_sock.connect((config.broker_host, config.broker_port))
            result['steps'].append("✅ SSL connection successful!")
            
            # Get certificate info
            cert = ssl_sock.getpeercert()
            if cert:
                result['debug_info']['server_cert'] = {
                    'subject': dict(x[0] for x in cert.get('subject', [])),
                    'issuer': dict(x[0] for x in cert.get('issuer', [])),
                    'version': cert.get('version'),
                    'serial_number': cert.get('serialNumber'),
                    'not_before': cert.get('notBefore'),
                    'not_after': cert.get('notAfter')
                }
                result['steps'].append("✅ Server certificate retrieved")
            
            result['success'] = True
            
        finally:
            ssl_sock.close()
        
    except Exception as e:
        result['error'] = str(e)
        result['steps'].append(f"❌ TLS connection failed: {e}")
    
    return result


def render_combine_responses(*responses) -> HttpResponse:
    """
    Combine multiple HttpResponse objects into a single response.
    
    This function is required by NEMO's plugin system.
    
    Args:
        *responses: Variable number of HttpResponse objects
        
    Returns:
        Combined HttpResponse
    """
    if not responses:
        return HttpResponse()
    
    if len(responses) == 1:
        return responses[0]
    
    # Combine content from all responses
    combined_content = b''.join(response.content for response in responses if response.content)
    
    # Use the first response as the base and update its content
    combined_response = HttpResponse(combined_content)
    combined_response.status_code = responses[0].status_code
    
    # Copy headers from all responses
    for response in responses:
        for header, value in response.items():
            combined_response[header] = value
    
    return combined_response
