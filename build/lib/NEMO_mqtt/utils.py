"""
Utility functions for MQTT plugin.
"""
import json
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_mqtt_config() -> Optional['MQTTConfiguration']:
    """
    Get MQTT configuration from database.
    
    Returns:
        MQTTConfiguration instance or None if not configured
    """
    try:
        from .models import MQTTConfiguration
        
        # Get the first enabled configuration
        config = MQTTConfiguration.objects.filter(enabled=True).first()
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
