"""
URL patterns for MQTT plugin.
"""
from django.urls import path
from . import views

app_name = 'mqtt_plugin'

urlpatterns = [
    # MQTT Monitoring Dashboard
    path('monitor/', views.mqtt_monitor, name='monitor'),
    path('monitor/api/', views.mqtt_monitor_api, name='monitor_api'),
    path('monitor/control/', views.mqtt_monitor_control, name='monitor_control'),
    
    # Health Check Endpoint
    path('health/', views.health_check, name='health_check'),
]
