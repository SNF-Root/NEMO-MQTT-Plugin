"""
Views for MQTT plugin.
"""
import json
import redis
import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache


class MQTTWebMonitor:
    """Web-based MQTT monitoring for Django views"""
    
    def __init__(self):
        self.redis_client = None
        self.mqtt_client = None
        self.messages = []
        self.max_messages = 100  # Keep last 100 messages
        self.running = False
        self.monitor_thread = None
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True
            )
            self.redis_client.ping()
            return True
        except Exception as e:
            print(f"Redis connection failed: {e}")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            # Use the newer callback API to avoid deprecation warning
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            
            # Get MQTT settings from Django settings or use defaults
            mqtt_host = getattr(settings, 'MQTT_BROKER_HOST', 'localhost')
            mqtt_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
            
            self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            return False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            client.subscribe("nemo/#")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            payload = msg.payload.decode('utf-8')
            message_data = {
                'id': len(self.messages) + 1,
                'timestamp': datetime.now().isoformat(),
                'source': 'MQTT',
                'topic': msg.topic,
                'payload': payload,
                'qos': msg.qos,
                'retain': msg.retain
            }
            
            self.add_message(message_data)
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    def add_message(self, message_data):
        """Add message to the list"""
        self.messages.append(message_data)
        
        # Keep only the last max_messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        
        # Store in cache for web access
        cache.set('mqtt_monitor_messages', self.messages, timeout=300)
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.disconnect()
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        # Connect to Redis
        if not self.connect_redis():
            return
        
        # Connect to MQTT
        if not self.connect_mqtt():
            return
        
        # Monitor Redis
        while self.running:
            try:
                if self.redis_client:
                    message = self.redis_client.rpop('NEMO_mqtt_events')
                    if message:
                        try:
                            event_data = json.loads(message)
                            redis_message = {
                                'id': len(self.messages) + 1,
                                'timestamp': datetime.now().isoformat(),
                                'source': 'Redis',
                                'topic': event_data.get('topic', 'unknown'),
                                'payload': event_data.get('payload', 'unknown'),
                                'qos': event_data.get('qos', 0),
                                'retain': event_data.get('retain', False)
                            }
                            self.add_message(redis_message)
                        except json.JSONDecodeError:
                            pass
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(1)


# Global monitor instance
monitor = MQTTWebMonitor()


@login_required
def mqtt_monitor(request):
    """Web-based MQTT monitoring dashboard"""
    # Start monitoring if not already running
    if not monitor.running:
        monitor.start_monitoring()
    
    # Get messages from cache (more reliable than direct access)
    messages = cache.get('mqtt_monitor_messages', [])
    
    return render(request, 'NEMO_mqtt/monitor.html', {
        'title': 'MQTT Message Monitor',
        'messages': messages[-20:],  # Show last 20 messages
    })


@login_required
@require_http_methods(["GET"])
def mqtt_monitor_api(request):
    """API endpoint for fetching monitoring data"""
    messages = cache.get('mqtt_monitor_messages', [])
    
    # Filter by time if requested
    since = request.GET.get('since')
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            messages = [msg for msg in messages if datetime.fromisoformat(msg['timestamp']) > since_dt]
        except ValueError:
            pass
    
    # Filter by source if requested
    source = request.GET.get('source')
    if source:
        messages = [msg for msg in messages if msg['source'].lower() == source.lower()]
    
    return JsonResponse({
        'messages': messages,
        'count': len(messages),
        'monitoring': monitor.running
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def mqtt_monitor_control(request):
    """Control monitoring (start/stop)"""
    action = request.POST.get('action')
    
    if action == 'start':
        if not monitor.running:
            monitor.start_monitoring()
        return JsonResponse({'status': 'started'})
    elif action == 'stop':
        monitor.stop_monitoring()
        return JsonResponse({'status': 'stopped'})
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)
