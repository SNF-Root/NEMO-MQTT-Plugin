"""
MQTT Plugin Customization for NEMO.
"""
from NEMO.decorators import customization
from NEMO.views.customization import CustomizationBase
from .models import MQTTConfiguration, MQTTMessageLog, MQTTEventFilter


@customization("mqtt", "MQTT Plugin")
class MQTTCustomization(CustomizationBase):
    """
    Customization class for MQTT plugin configuration.
    """
    
    def template(self) -> str:
        """Return the template path for MQTT customization."""
        # Let the parent class handle template discovery automatically
        # This will look for templates in the plugin's templates directory first
        return super().template()
    
    def context(self) -> dict:
        """Return context data for the MQTT customization template."""
        # Get the base context from parent class
        context_dict = super().context()
        
        # Get the single MQTT configuration (create one if none exists)
        import os
        import socket
        # Create unique client ID using hostname and process ID
        unique_client_id = f"nemo_{socket.gethostname()}_{os.getpid()}"
        
        config, created = MQTTConfiguration.objects.get_or_create(
            defaults={
                'name': 'Default MQTT Configuration',
                'enabled': False,
                'broker_host': 'localhost',
                'broker_port': 1883,
                'client_id': unique_client_id,
                'topic_prefix': 'nemo/',
                'qos_level': 1,
                'retain_messages': False,
                'clean_session': True,
                'auto_reconnect': True,
                'reconnect_delay': 5,
                'max_reconnect_attempts': 10,
                'log_messages': True,
                'log_level': 'INFO',
            }
        )
        
        recent_messages = MQTTMessageLog.objects.order_by('-sent_at')[:5]
        event_filters = MQTTEventFilter.objects.all()
        
        # Add MQTT-specific context data
        context_dict.update({
            'config': config,
            'recent_messages': recent_messages,
            'event_filters': event_filters,
        })
        
        return context_dict
    
    def validate(self, request) -> list:
        """Validate MQTT configuration data."""
        errors = []
        # Add any validation logic here if needed
        return errors
    
    def save(self, request, element=None):
        """Save MQTT configuration data."""
        from django.contrib import messages
        
        # Get the single MQTT configuration
        config, created = MQTTConfiguration.objects.get_or_create(
            defaults={'name': 'Default MQTT Configuration'}
        )
        
        # Update configuration with form data
        config.name = request.POST.get('mqtt_name', config.name)
        config.enabled = request.POST.get('mqtt_enabled') == 'enabled'
        config.broker_host = request.POST.get('mqtt_broker_host', config.broker_host)
        config.broker_port = int(request.POST.get('mqtt_broker_port', config.broker_port))
        config.keepalive = int(request.POST.get('mqtt_keepalive', config.keepalive))
        config.client_id = request.POST.get('mqtt_client_id', config.client_id)
        
        # SSL/TLS settings
        config.use_tls = request.POST.get('mqtt_use_tls') == 'enabled'
        config.tls_version = 'tlsv1.2'  # Hardcoded to TLS 1.2
        config.ca_cert_content = request.POST.get('mqtt_ca_cert', config.ca_cert_content)
        config.insecure = False  # Always use secure TLS connections
        
        # Validate TLS certificates if TLS is enabled
        if config.use_tls:
            print("🔐 TLS Configuration Validation:")
            print(f"   🔐 TLS Version: {config.tls_version}")
            
            # Validate CA certificate
            if config.ca_cert_content:
                from .utils import validate_tls_certificate
                ca_validation = validate_tls_certificate(config.ca_cert_content, "CA")
                print(f"   🔐 CA Certificate Validation:")
                print(f"   🔐   Valid: {ca_validation['valid']}")
                if ca_validation['valid']:
                    print(f"   🔐   Subject: {ca_validation['cert_info'].get('subject', 'N/A')}")
                    print(f"   🔐   Issuer: {ca_validation['cert_info'].get('issuer', 'N/A')}")
                    print(f"   🔐   Valid Until: {ca_validation['cert_info'].get('not_after', 'N/A')}")
                else:
                    print(f"   🔐   Error: {ca_validation['error']}")
                    print(f"   🔐   Preview: {ca_validation['preview']}")
            else:
                print(f"   🔐 CA Certificate: Not provided")
            
            # Test TLS connection if all required components are present
            if config.ca_cert_content or config.ca_cert_path:
                print(f"   🔐 Testing TLS connection...")
                from .utils import test_tls_connection
                tls_test = test_tls_connection(config)
                print(f"   🔐 TLS Connection Test:")
                print(f"   🔐   Success: {tls_test['success']}")
                if tls_test['success']:
                    print(f"   🔐   ✅ TLS connection test passed!")
                    if 'server_cert' in tls_test['debug_info']:
                        server_cert = tls_test['debug_info']['server_cert']
                        print(f"   🔐   Server Certificate:")
                        print(f"   🔐     Subject: {server_cert.get('subject', 'N/A')}")
                        print(f"   🔐     Issuer: {server_cert.get('issuer', 'N/A')}")
                        print(f"   🔐     Valid Until: {server_cert.get('not_after', 'N/A')}")
                else:
                    print(f"   🔐   ❌ TLS connection test failed: {tls_test['error']}")
                    print(f"   🔐   Steps:")
                    for step in tls_test['steps']:
                        print(f"   🔐     {step}")
            else:
                print(f"   🔐 TLS Connection Test: Skipped (no CA certificate provided)")
        
        config.topic_prefix = request.POST.get('mqtt_topic_prefix', config.topic_prefix)
        config.qos_level = int(request.POST.get('mqtt_qos_level', config.qos_level))
        config.retain_messages = request.POST.get('mqtt_retain_messages') == 'enabled'
        config.clean_session = request.POST.get('mqtt_clean_session') == 'enabled'
        config.auto_reconnect = request.POST.get('mqtt_auto_reconnect') == 'enabled'
        config.reconnect_delay = int(request.POST.get('mqtt_reconnect_delay', config.reconnect_delay))
        config.max_reconnect_attempts = int(request.POST.get('mqtt_max_reconnect_attempts', config.max_reconnect_attempts))
        config.log_messages = request.POST.get('mqtt_log_messages') == 'enabled'
        config.log_level = request.POST.get('mqtt_log_level', config.log_level)
        
        config.save()
        
        messages.success(request, 'MQTT configuration saved successfully!')
        
        return {}