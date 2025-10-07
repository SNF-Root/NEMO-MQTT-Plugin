"""
Django signal handlers for MQTT plugin.
These signals will trigger MQTT message publishing when NEMO events occur.
"""
import json
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from NEMO.models import Tool, Area, User, Reservation, UsageEvent, AreaAccessRecord
from NEMO.signals import tool_enabled, tool_disabled

logger = logging.getLogger(__name__)


class MQTTSignalHandler:
    """Handles MQTT signal processing and message publishing via Redis"""
    
    def __init__(self):
        self.redis_publisher = None
        self._initialize_redis_publisher()
    
    def _initialize_redis_publisher(self):
        """Initialize Redis publisher for MQTT events"""
        try:
            from .redis_publisher import redis_publisher
            self.redis_publisher = redis_publisher
            logger.info("Redis MQTT publisher initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis publisher: {e}")
            self.redis_publisher = None
    
    def publish_message(self, topic, data):
        """Publish a message via Redis to external MQTT service"""
        import uuid
        signal_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [SIGNAL-{signal_id}] Starting message publish process")
        print(f"   Topic: {topic}")
        print(f"   Data: {json.dumps(data, indent=2)}")
        
        if self.redis_publisher:
            try:
                print(f"🔍 [SIGNAL-{signal_id}] Redis publisher available, calling publish_event...")
                success = self.redis_publisher.publish_event(topic, json.dumps(data))
                if success:
                    print(f"✅ [SIGNAL-{signal_id}] Successfully published to Redis: {topic}")
                    logger.info(f"Successfully published to Redis: {topic}")
                else:
                    print(f"❌ [SIGNAL-{signal_id}] Failed to publish to Redis: {topic}")
                    logger.error(f"Failed to publish to Redis: {topic}")
            except Exception as e:
                print(f"❌ [SIGNAL-{signal_id}] Exception publishing to Redis: {e}")
                logger.error(f"Failed to publish MQTT message via Redis: {e}")
        else:
            print(f"❌ [SIGNAL-{signal_id}] Redis publisher not available")
            logger.warning("Redis publisher not available")


# Global signal handler instance
print("🔧 Initializing MQTT Signal Handler...")
signal_handler = MQTTSignalHandler()
print(f"🔧 MQTT Signal Handler initialized: {id(signal_handler)}")


# Tool-related signals
@receiver(post_save, sender=Tool)
def tool_saved(sender, instance, created, **kwargs):
    """Signal handler for tool save events"""
    import uuid
    signal_id = str(uuid.uuid4())[:8]
    print(f"\n🔍 [TOOL-SIGNAL-{signal_id}] Tool save event triggered")
    print(f"   Tool: {instance.name} (ID: {instance.id})")
    print(f"   Created: {created}")
    print(f"   Operational: {instance.operational}")
    
    if signal_handler.redis_publisher:
        action = "created" if created else "updated"
        data = {
            "event": f"tool_{action}",
            "tool_id": instance.id,
            "tool_name": instance.name,
            "tool_status": instance.operational,
            "timestamp": instance._state.adding
        }
        print(f"🔍 [TOOL-SIGNAL-{signal_id}] Publishing tool_{action} event...")
        signal_handler.publish_message(f"nemo/tools/{instance.id}", data)
    else:
        print(f"❌ [TOOL-SIGNAL-{signal_id}] Redis publisher not available")


@receiver(post_save, sender=Area)
def area_saved(sender, instance, created, **kwargs):
    """Signal handler for area save events"""
    if signal_handler.redis_publisher:
        action = "created" if created else "updated"
        data = {
            "event": f"area_{action}",
            "area_id": instance.id,
            "area_name": instance.name,
            "area_requires_reservation": instance.requires_reservation,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/areas/{instance.id}", data)


# Reservation-related signals
@receiver(post_save, sender=Reservation)
def reservation_saved(sender, instance, created, **kwargs):
    """Signal handler for reservation save events"""
    if signal_handler.redis_publisher:
        action = "created" if created else "updated"
        data = {
            "event": f"reservation_{action}",
            "reservation_id": instance.id,
            "user_id": instance.user.id,
            "user_name": instance.user.get_full_name(),
            "start_time": instance.start.isoformat() if instance.start else None,
            "end_time": instance.end.isoformat() if instance.end else None,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/reservations/{instance.id}", data)


# Usage event signals
@receiver(post_save, sender=UsageEvent)
def usage_event_saved(sender, instance, created, **kwargs):
    """Signal handler for usage event save events"""
    import uuid
    signal_id = str(uuid.uuid4())[:8]
    print(f"🔍 MQTT Signal [{signal_id}]: UsageEvent {instance.id} - created={created}, end={instance.end}, has_ended={instance.has_ended}")
    
    if not signal_handler.redis_publisher:
        print(f"❌ [{signal_id}] Redis publisher not available")
        return
    
    # Debug logging for all events
    print(f"🔍 MQTT Signal [{signal_id}]: UsageEvent {instance.id} - created={created}, end={instance.end}, has_ended={instance.has_ended}")
    logger.info(f"UsageEvent {instance.id} signal: created={created}, end={instance.end}, has_ended={instance.has_ended}")
    
    # Check if this is a new usage event (tool usage starts)
    if created:
        data = {
            "event": "tool_usage_start",
            "usage_id": instance.id,
            "user_id": instance.user.id,
            "user_name": instance.user.get_full_name(),
            "tool_id": instance.tool.id,
            "tool_name": instance.tool.name,
            "start_time": instance.start.isoformat() if instance.start else None,
            "end_time": instance.end.isoformat() if instance.end else None,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/tools/{instance.tool.name}/start", data)
        print(f"✅ [{signal_id}] Published tool_usage_start for UsageEvent {instance.id}")
        logger.info(f"Published tool_usage_start for UsageEvent {instance.id}")
    
    # Check if this is an update and the tool usage has ended
    elif not created and instance.end is not None and instance.has_ended > 0:
        data = {
            "event": "tool_usage_end",
            "usage_id": instance.id,
            "user_id": instance.user.id,
            "user_name": instance.user.get_full_name(),
            "tool_id": instance.tool.id,
            "tool_name": instance.tool.name,
            "start_time": instance.start.isoformat() if instance.start else None,
            "end_time": instance.end.isoformat() if instance.end else None,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/tools/{instance.tool.name}/end", data)
        print(f"✅ [{signal_id}] Published tool_usage_end for UsageEvent {instance.id}")
        logger.info(f"Published tool_usage_end for UsageEvent {instance.id}")


# Area access signals
@receiver(post_save, sender=AreaAccessRecord)
def area_access_saved(sender, instance, created, **kwargs):
    """Signal handler for area access save events"""
    if signal_handler.redis_publisher and created:
        data = {
            "event": "area_access",
            "access_id": instance.id,
            "user_id": instance.customer.id,
            "user_name": instance.customer.get_full_name(),
            "area_id": instance.area.id,
            "area_name": instance.area.name,
            "access_time": instance.start.isoformat() if instance.start else None,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/area_access/{instance.id}", data)


# Custom tool operational status signals
@receiver(tool_enabled)
def tool_enabled_signal(sender, instance, **kwargs):
    """Signal handler for when a tool is enabled"""
    if signal_handler.redis_publisher:
        data = {
            "event": "tool_enabled",
            "tool_id": instance.id,
            "tool_name": instance.name,
            "tool_status": instance.operational,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/tools/{instance.id}/enabled", data)


@receiver(tool_disabled)
def tool_disabled_signal(sender, instance, **kwargs):
    """Signal handler for when a tool is disabled"""
    if signal_handler.redis_publisher:
        data = {
            "event": "tool_disabled",
            "tool_id": instance.id,
            "tool_name": instance.name,
            "tool_status": instance.operational,
            "timestamp": instance._state.adding
        }
        signal_handler.publish_message(f"nemo/tools/{instance.id}/disabled", data)
