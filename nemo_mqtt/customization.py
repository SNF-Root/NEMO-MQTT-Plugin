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
        config.username = request.POST.get('mqtt_broker_username', config.username) or None
        broker_password = request.POST.get('mqtt_broker_password', '')
        if broker_password:
            config.password = broker_password
        # else: leave config.password unchanged (blank in form = keep current)
        
        # HMAC message authentication
        config.use_hmac = request.POST.get('mqtt_use_hmac') == 'enabled'
        hmac_key = request.POST.get('mqtt_hmac_secret_key', '')
        if hmac_key:
            config.hmac_secret_key = hmac_key
        config.hmac_algorithm = request.POST.get('mqtt_hmac_algorithm', config.hmac_algorithm) or 'sha256'
        
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