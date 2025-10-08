# NEMO-CE MQTT Plugin Setup Checklist

## Pre-Setup Requirements ✅

### **1. NEMO-CE Installation**
- [ ] NEMO-CE is installed and running
- [ ] You can access NEMO-CE at `http://localhost:8000`
- [ ] You have admin access to NEMO-CE
- [ ] You know the path to your NEMO-CE directory

### **2. Dependencies**
- [ ] Redis is installed and running (`redis-cli ping` should work)
- [ ] MQTT broker (mosquitto) is installed
- [ ] Python virtual environment is set up in NEMO-CE

## Plugin Integration Setup ✅

### **3. Run Integration Script**
```bash
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
./setup_nemo_integration.sh /path/to/your/nemo-ce
```
- [ ] Script runs without errors
- [ ] Symlink is created successfully
- [ ] You can see the plugin directory in NEMO-CE: `ls -la /path/to/your/nemo-ce/NEMO/plugins/`

### **4. Django Settings Configuration**

#### **Add to `settings.py`:**
```python
INSTALLED_APPS = [
    # ... other apps
    'NEMO.plugins.mqtt',
]
```
- [ ] Plugin is added to `INSTALLED_APPS`
- [ ] No syntax errors in `settings.py`
- [ ] Settings file saves successfully

#### **Add to `urls.py`:**
```python
from django.urls import path, include

urlpatterns = [
    # ... other patterns
    path('mqtt/', include('NEMO.plugins.mqtt.urls')),
]
```
- [ ] URL pattern is added
- [ ] Import statements are correct
- [ ] No syntax errors in `urls.py`

### **5. Database Setup**
```bash
cd /path/to/your/nemo-ce/
python manage.py migrate
```
- [ ] Migrations run successfully
- [ ] No migration errors
- [ ] Database tables are created

### **6. Verify Django Integration**
```bash
cd /path/to/your/nemo-ce/
python manage.py runserver
```
- [ ] NEMO-CE starts without errors
- [ ] No import errors in the console
- [ ] You can access the main NEMO-CE interface

## Plugin-Specific Verification ✅

### **7. Check Plugin URLs**
- [ ] Visit: `http://localhost:8000/mqtt/monitor/`
- [ ] Page loads without 404 errors
- [ ] You see the MQTT Monitor interface
- [ ] No template errors in the browser console

### **8. Check Admin Interface**
- [ ] Visit: `http://localhost:8000/admin/`
- [ ] Look for "MQTT Configurations" in the admin
- [ ] You can create/edit MQTT configurations
- [ ] No admin interface errors

### **9. Check Customization Page**
- [ ] Visit: `http://localhost:8000/customization/mqtt/`
- [ ] Page loads and shows MQTT configuration form
- [ ] You can save configuration settings
- [ ] Settings persist after page refresh

## MQTT System Testing ✅

### **10. Start MQTT System**
```bash
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
./start_mqtt_system.sh
```
- [ ] Redis starts successfully
- [ ] MQTT broker starts successfully
- [ ] Standalone MQTT service starts
- [ ] Monitor service starts
- [ ] No error messages in the output

### **11. Test Message Flow**
```bash
cd /Users/adenton/Desktop/nemo-mqtt-plugin/
python test_message_flow.py
```
- [ ] Test script runs without errors
- [ ] Messages are generated
- [ ] You see message output in the terminal

### **12. Verify Monitor Integration**
- [ ] Go to: `http://localhost:8000/mqtt/monitor/`
- [ ] Click "Start Monitoring"
- [ ] Enable "Auto Refresh"
- [ ] You see messages appearing in the monitor
- [ ] Messages show both MQTT and Redis sources
- [ ] JSON messages are properly formatted

## Advanced Testing ✅

### **13. Test with Real NEMO Events**
- [ ] Create a tool in NEMO-CE
- [ ] Enable/disable the tool
- [ ] Check if MQTT messages are generated
- [ ] Verify messages appear in the monitor

### **14. Test Configuration Changes**
- [ ] Go to: `http://localhost:8000/customization/mqtt/`
- [ ] Change broker host/port settings
- [ ] Save the configuration
- [ ] Verify changes are reflected in the monitor

### **15. Test Error Handling**
- [ ] Stop Redis: `redis-cli shutdown`
- [ ] Check if monitor shows connection errors
- [ ] Restart Redis and verify recovery
- [ ] Stop MQTT broker and check error handling

## Production Readiness ✅

### **16. External Service Testing**
```bash
cd /path/to/your/nemo-ce/
python NEMO/plugins/mqtt/external_mqtt_service.py
```
- [ ] External service starts without Django errors
- [ ] Service connects to MQTT broker using Django config
- [ ] Service processes messages from Redis
- [ ] Service publishes messages to MQTT broker

### **17. Performance Testing**
- [ ] Monitor handles multiple messages without lag
- [ ] Auto-refresh works smoothly
- [ ] No memory leaks in long-running sessions
- [ ] Database queries are efficient

## Troubleshooting Common Issues ❌

### **If symlink doesn't work:**
```bash
# Check if symlink exists
ls -la /path/to/your/nemo-ce/NEMO/plugins/

# Recreate symlink
rm /path/to/your/nemo-ce/NEMO/plugins/mqtt
ln -s /Users/adenton/Desktop/nemo-mqtt-plugin/NEMO_mqtt /path/to/your/nemo-ce/NEMO/plugins/mqtt
```

### **If Django import errors:**
- [ ] Check `INSTALLED_APPS` includes the plugin
- [ ] Verify the symlink is correct
- [ ] Check for syntax errors in plugin files
- [ ] Run `python manage.py check` for validation

### **If MQTT connection fails:**
- [ ] Check Redis is running: `redis-cli ping`
- [ ] Check MQTT broker: `mosquitto_pub -h localhost -p 1883 -t test -m test`
- [ ] Verify firewall settings
- [ ] Check broker authentication settings

### **If monitor page doesn't load:**
- [ ] Check URL pattern in `urls.py`
- [ ] Verify template exists: `templates/NEMO_mqtt/monitor.html`
- [ ] Check for JavaScript errors in browser console
- [ ] Verify CSRF token handling

## Success Criteria 🎉

### **Everything is working correctly when:**
- [ ] You can access the MQTT monitor at `http://localhost:8000/mqtt/monitor/`
- [ ] Messages appear in real-time when you generate them
- [ ] You can configure MQTT settings via the admin interface
- [ ] The external service runs without errors
- [ ] NEMO events trigger MQTT messages
- [ ] All services start/stop cleanly

## Next Steps 🚀

Once everything is checked off:
1. **Develop your features** - Edit files in the plugin directory
2. **Test changes** - Refresh browser to see updates
3. **Iterate quickly** - No need to reinstall the plugin
4. **Deploy when ready** - Build package and install in production

---

**Need help?** Check the console output for error messages and refer to the troubleshooting section above.
