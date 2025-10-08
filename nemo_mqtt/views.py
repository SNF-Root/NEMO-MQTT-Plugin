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
        import uuid
        monitor_id = str(uuid.uuid4())[:8]
        
        print(f"\n" + "="*80)
        print(f"📨 [MONITOR-{monitor_id}] MQTT MESSAGE RECEIVED")
        print(f"="*80)
        print(f"📍 Topic: '{msg.topic}'")
        print(f"🎯 QoS: {msg.qos}")
        print(f"🔒 Retain: {msg.retain}")
        print(f"📦 Raw payload: {msg.payload}")
        print(f"📏 Payload length: {len(msg.payload)} bytes")
        
        try:
            payload = msg.payload.decode('utf-8')
            print(f"✅ [MONITOR-{monitor_id}] Payload decoded successfully")
            print(f"📦 Decoded payload: {payload}")
            print(f"📏 Decoded length: {len(payload)} characters")
            
            message_data = {
                'id': len(self.messages) + 1,
                'timestamp': datetime.now().isoformat(),
                'source': 'MQTT',
                'topic': msg.topic,
                'payload': payload,
                'qos': msg.qos,
                'retain': msg.retain,
                'monitor_id': monitor_id
            }
            
            print(f"\n🔍 [MONITOR-{monitor_id}] MESSAGE DATA CREATED:")
            print(f"   ID: {message_data['id']}")
            print(f"   Timestamp: {message_data['timestamp']}")
            print(f"   Source: {message_data['source']}")
            print(f"   Topic: {message_data['topic']}")
            print(f"   QoS: {message_data['qos']}")
            print(f"   Retain: {message_data['retain']}")
            print(f"   Payload: {message_data['payload'][:100]}{'...' if len(message_data['payload']) > 100 else ''}")
            
            print(f"\n📤 [MONITOR-{monitor_id}] ADDING TO MESSAGE LIST...")
            self.add_message(message_data)
            print(f"✅ [MONITOR-{monitor_id}] MESSAGE ADDED SUCCESSFULLY")
            print(f"   Total messages: {len(self.messages)}")
            
        except UnicodeDecodeError as e:
            print(f"❌ [MONITOR-{monitor_id}] UNICODE DECODE ERROR")
            print(f"   Error: {e}")
            print(f"   Raw payload: {msg.payload}")
        except Exception as e:
            print(f"❌ [MONITOR-{monitor_id}] ERROR PROCESSING MQTT MESSAGE")
            print(f"   Exception type: {type(e).__name__}")
            print(f"   Exception message: {e}")
            print(f"   Topic: {msg.topic}")
            print(f"   Payload: {msg.payload}")
        
        print(f"="*80)
    
    def add_message(self, message_data):
        """Add message to the list"""
        import uuid
        add_id = str(uuid.uuid4())[:8]
        
        print(f"\n🔍 [ADD-{add_id}] ADDING MESSAGE TO MONITOR")
        print(f"   Message ID: {message_data.get('id', 'unknown')}")
        print(f"   Topic: {message_data.get('topic', 'unknown')}")
        print(f"   Source: {message_data.get('source', 'unknown')}")
        print(f"   Current message count: {len(self.messages)}")
        
        self.messages.append(message_data)
        print(f"✅ [ADD-{add_id}] Message appended to list")
        print(f"   New message count: {len(self.messages)}")
        
        # Keep only the last max_messages
        if len(self.messages) > self.max_messages:
            old_count = len(self.messages)
            self.messages = self.messages[-self.max_messages:]
            print(f"🔍 [ADD-{add_id}] Trimmed messages from {old_count} to {len(self.messages)}")
        
        # Store in cache for web access
        print(f"🔍 [ADD-{add_id}] Storing in cache...")
        cache.set('mqtt_monitor_messages', self.messages, timeout=3600)  # 1 hour timeout
        print(f"✅ [ADD-{add_id}] Messages stored in cache")
        print(f"   Cache key: mqtt_monitor_messages")
        print(f"   Cache timeout: 3600 seconds (1 hour)")
        print(f"   Stored message count: {len(self.messages)}")
    
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
        # Connect to MQTT
        if not self.connect_mqtt():
            return
        
        # Monitor loop - just keep the thread alive
        # MQTT messages are handled by the on_mqtt_message callback
        while self.running:
            try:
                time.sleep(1)  # Just keep the thread alive
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(1)


# Global monitor instance
monitor = MQTTWebMonitor()


@login_required
def mqtt_monitor(request):
    """Web-based MQTT monitoring dashboard - shows last 10 MQTT messages"""
    import uuid
    view_id = str(uuid.uuid4())[:8]
    
    print(f"\n" + "="*80)
    print(f"🌐 [VIEW-{view_id}] MQTT MONITOR PAGE REQUESTED")
    print(f"="*80)
    print(f"   User: {request.user}")
    print(f"   Monitor running: {monitor.running}")
    print(f"   Monitor messages: {len(monitor.messages)}")
    
    # Always start monitoring when page loads
    if not monitor.running:
        print(f"🚀 [VIEW-{view_id}] Starting MQTT monitor from web interface...")
        monitor.start_monitoring()
        print(f"✅ [VIEW-{view_id}] Monitor started")
    else:
        print(f"✅ [VIEW-{view_id}] Monitor already running")
    
    # Get messages from cache and filter for MQTT only
    print(f"🔍 [VIEW-{view_id}] Retrieving messages from cache...")
    messages = cache.get('mqtt_monitor_messages', [])
    print(f"📊 [VIEW-{view_id}] Cache retrieval:")
    print(f"   Total cached messages: {len(messages)}")
    print(f"   Cache key: mqtt_monitor_messages")
    
    # Fallback to in-memory messages if cache is empty
    if not messages and monitor.messages:
        print(f"🔄 [VIEW-{view_id}] Cache empty, using in-memory messages as fallback")
        messages = monitor.messages
        # Re-store in cache
        cache.set('mqtt_monitor_messages', messages, timeout=3600)
        print(f"✅ [VIEW-{view_id}] Re-stored {len(messages)} messages in cache")
    
    mqtt_messages = [msg for msg in messages if msg.get('source') == 'MQTT']
    print(f"📨 [VIEW-{view_id}] MQTT message filtering:")
    print(f"   Total messages: {len(messages)}")
    print(f"   MQTT messages: {len(mqtt_messages)}")
    
    # Show details of MQTT messages
    for i, msg in enumerate(mqtt_messages[-5:]):  # Show last 5
        print(f"   {i+1}. Topic: {msg.get('topic', 'unknown')} - {msg.get('payload', 'unknown')[:50]}...")
    
    # Prepare response
    response_messages = mqtt_messages[-10:]  # Show last 10 MQTT messages
    print(f"📤 [VIEW-{view_id}] Sending {len(response_messages)} messages to template")
    
    print(f"="*80)
    
    print(f"🔍 [VIEW-{view_id}] Rendering template with context:")
    print(f"   Title: MQTT Messages")
    print(f"   Template: NEMO_mqtt/monitor.html")
    print(f"   User agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
    print(f"   Request method: {request.method}")
    print(f"   Request path: {request.path}")
    
    # Test template rendering
    try:
        from django.template.loader import get_template
        template = get_template('NEMO_mqtt/monitor.html')
        print(f"✅ [VIEW-{view_id}] Template loaded successfully")
        
        # Check if template has JavaScript block (fix source access)
        try:
            template_content = template.template.source
            if 'extra_js' in template_content:
                print(f"✅ [VIEW-{view_id}] Template contains extra_js block")
            else:
                print(f"❌ [VIEW-{view_id}] Template missing extra_js block")
                
            if 'JavaScript' in template_content:
                print(f"✅ [VIEW-{view_id}] Template contains JavaScript")
            else:
                print(f"❌ [VIEW-{view_id}] Template missing JavaScript")
        except Exception as e:
            print(f"⚠️ [VIEW-{view_id}] Could not access template source: {e}")
            print(f"✅ [VIEW-{view_id}] Template object exists and loaded successfully")
            
    except Exception as e:
        print(f"❌ [VIEW-{view_id}] Template loading error: {e}")
    
    print(f"🚀 [VIEW-{view_id}] About to render template...")
    
    response = render(request, 'NEMO_mqtt/monitor.html', {
        'title': 'MQTT Messages',
    })
    
    print(f"✅ [VIEW-{view_id}] Template rendered successfully")
    print(f"   Response status: {response.status_code}")
    print(f"   Response content length: {len(response.content)}")
    
    # Check if response contains our debug content
    content_str = response.content.decode('utf-8')
    if 'Django Template Debug' in content_str:
        print(f"✅ [VIEW-{view_id}] Response contains Django debug content")
    else:
        print(f"❌ [VIEW-{view_id}] Response missing Django debug content")
        
    if 'Static HTML Test' in content_str:
        print(f"✅ [VIEW-{view_id}] Response contains static HTML test")
    else:
        print(f"❌ [VIEW-{view_id}] Response missing static HTML test")
    
    return response


@login_required
@require_http_methods(["GET"])
def mqtt_monitor_api(request):
    """API endpoint for fetching MQTT messages only"""
    import uuid
    api_id = str(uuid.uuid4())[:8]
    
    try:
        print(f"\n" + "="*80)
        print(f"🔌 [API-{api_id}] MQTT MONITOR API CALLED")
        print(f"="*80)
        print(f"   User: {request.user}")
        print(f"   Monitor running: {monitor.running}")
        print(f"   Monitor messages: {len(monitor.messages)}")
        
        print(f"🔍 [API-{api_id}] Retrieving messages from cache...")
        messages = cache.get('mqtt_monitor_messages', [])
        print(f"📊 [API-{api_id}] Cache retrieval:")
        print(f"   Total cached messages: {len(messages)}")
        print(f"   Cache key: mqtt_monitor_messages")
        
        # Check TTL only if cache supports it (Redis does, LocMemCache doesn't)
        try:
            ttl = cache.ttl('mqtt_monitor_messages') if cache.get('mqtt_monitor_messages') else 'N/A'
            print(f"   Cache TTL: {ttl}")
        except AttributeError:
            print(f"   Cache TTL: Not supported by this cache backend")
        
        # Fallback to in-memory messages if cache is empty
        if not messages and monitor.messages:
            print(f"🔄 [API-{api_id}] Cache empty, using in-memory messages as fallback")
            messages = monitor.messages
            # Re-store in cache
            cache.set('mqtt_monitor_messages', messages, timeout=3600)
            print(f"✅ [API-{api_id}] Re-stored {len(messages)} messages in cache")
        
        # Filter for MQTT messages only
        mqtt_messages = [msg for msg in messages if msg.get('source') == 'MQTT']
        print(f"📨 [API-{api_id}] MQTT message filtering:")
        print(f"   Total messages: {len(messages)}")
        print(f"   MQTT messages: {len(mqtt_messages)}")
        
        # Show details of MQTT messages
        for i, msg in enumerate(mqtt_messages[-3:]):  # Show last 3
            print(f"   {i+1}. Topic: {msg.get('topic', 'unknown')} - {msg.get('payload', 'unknown')[:50]}...")
        
        response_data = {
            'messages': mqtt_messages,
            'count': len(mqtt_messages),
            'monitoring': monitor.running
        }
        
        print(f"📤 [API-{api_id}] API Response:")
        print(f"   Messages: {len(response_data['messages'])}")
        print(f"   Count: {response_data['count']}")
        print(f"   Monitoring: {response_data['monitoring']}")
        print(f"="*80)
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ [API-{api_id}] ERROR in API: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e), 'messages': [], 'count': 0, 'monitoring': False}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def mqtt_monitor_control(request):
    """Control monitoring (start/stop)"""
    action = request.POST.get('action')
    print(f"Monitor control action: {action}, current status: {monitor.running}")
    
    if action == 'start':
        if not monitor.running:
            print("Starting monitor...")
            monitor.start_monitoring()
        return JsonResponse({'status': 'started'})
    elif action == 'stop':
        print("Stopping monitor...")
        monitor.stop_monitoring()
        return JsonResponse({'status': 'stopped'})
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)
