#!/usr/bin/env python3
"""
NEMO MQTT Plugin Installation Script

This script helps integrate the MQTT plugin with an existing NEMO installation.
It automatically configures settings and URLs for seamless integration.

Usage:
    python install_nemo_integration.py --nemo-path /path/to/nemo-ce
"""

import os
import sys
import argparse
import re
from pathlib import Path


def find_nemo_settings(nemo_path):
    """Find NEMO settings files"""
    settings_files = []
    
    # Look for common settings file patterns
    patterns = [
        "settings.py",
        "settings_dev.py", 
        "settings_prod.py",
        "settings_local.py"
    ]
    
    for pattern in patterns:
        settings_file = Path(nemo_path) / pattern
        if settings_file.exists():
            settings_files.append(str(settings_file))
    
    return settings_files


def backup_file(file_path):
    """Create a backup of the file"""
    backup_path = f"{file_path}.backup"
    if not os.path.exists(backup_path):
        with open(file_path, 'r') as original:
            with open(backup_path, 'w') as backup:
                backup.write(original.read())
        print(f"✅ Created backup: {backup_path}")
    return backup_path


def add_to_installed_apps(settings_file):
    """Add NEMO_mqtt to INSTALLED_APPS"""
    with open(settings_file, 'r') as f:
        content = f.read()
    
    # Check if already added
    if "'NEMO_mqtt'" in content or '"NEMO_mqtt"' in content:
        print(f"✅ NEMO_mqtt already in INSTALLED_APPS in {settings_file}")
        return True
    
    # Find INSTALLED_APPS and add NEMO_mqtt
    pattern = r'(INSTALLED_APPS\s*=\s*\[[^\]]*)(\]\s*$)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if match:
        # Add NEMO_mqtt before the closing bracket
        new_content = content[:match.start(2)] + "    'NEMO_mqtt',\n" + match.group(2)
        
        with open(settings_file, 'w') as f:
            f.write(new_content)
        print(f"✅ Added NEMO_mqtt to INSTALLED_APPS in {settings_file}")
        return True
    else:
        print(f"⚠️  Could not find INSTALLED_APPS in {settings_file}")
        return False


def add_mqtt_urls(nemo_path):
    """Add MQTT URLs to NEMO's main urls.py"""
    urls_file = Path(nemo_path) / "NEMO" / "urls.py"
    
    if not urls_file.exists():
        print(f"⚠️  Could not find NEMO/urls.py at {urls_file}")
        return False
    
    with open(urls_file, 'r') as f:
        content = f.read()
    
    # Check if already added
    if "NEMO_mqtt.urls" in content:
        print(f"✅ MQTT URLs already added to {urls_file}")
        return True
    
    # Find a good place to add the MQTT URLs (after other includes)
    pattern = r'(\s+)(# Add.*URLs.*\n.*\])'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if match:
        # Add MQTT URLs after existing URL patterns
        mqtt_urls = f"""
    # Add MQTT plugin URLs
    urlpatterns += [
        path("mqtt/", include("NEMO_mqtt.urls")),
    ]"""
        new_content = content[:match.end()] + mqtt_urls + content[match.end():]
    else:
        # Add at the end of the file before the last line
        lines = content.split('\n')
        if lines and lines[-1].strip() == '':
            lines = lines[:-1]
        
        mqtt_urls = [
            "",
            "    # Add MQTT plugin URLs",
            "    urlpatterns += [",
            "        path(\"mqtt/\", include(\"NEMO_mqtt.urls\")),",
            "    ]"
        ]
        lines.extend(mqtt_urls)
        new_content = '\n'.join(lines)
    
    with open(urls_file, 'w') as f:
        f.write(new_content)
    print(f"✅ Added MQTT URLs to {urls_file}")
    return True


def add_logging_config(settings_file):
    """Add MQTT logging configuration"""
    with open(settings_file, 'r') as f:
        content = f.read()
    
    # Check if logging already configured
    if "'NEMO_mqtt'" in content and "loggers" in content:
        print(f"✅ MQTT logging already configured in {settings_file}")
        return True
    
    # Look for existing LOGGING configuration
    if "LOGGING" in content:
        # Add NEMO_mqtt logger to existing configuration
        pattern = r'(\s+)(\'loggers\':\s*\{[^}]*)(\})'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            logger_config = """
        'NEMO_mqtt': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },"""
            new_content = content[:match.start(2)] + match.group(2) + logger_config + content[match.start(3):]
            
            with open(settings_file, 'w') as f:
                f.write(new_content)
            print(f"✅ Added MQTT logging to {settings_file}")
            return True
    
    print(f"⚠️  Could not add logging configuration to {settings_file}")
    return False


def main():
    parser = argparse.ArgumentParser(description='Install NEMO MQTT Plugin integration')
    parser.add_argument('--nemo-path', required=True, help='Path to NEMO-CE installation')
    parser.add_argument('--backup', action='store_true', help='Create backup files before modifying')
    
    args = parser.parse_args()
    
    nemo_path = Path(args.nemo_path)
    if not nemo_path.exists():
        print(f"❌ NEMO path does not exist: {nemo_path}")
        sys.exit(1)
    
    print(f"🔧 Installing NEMO MQTT Plugin integration in: {nemo_path}")
    
    # Find settings files
    settings_files = find_nemo_settings(nemo_path)
    if not settings_files:
        print("❌ No NEMO settings files found!")
        sys.exit(1)
    
    print(f"📁 Found settings files: {settings_files}")
    
    success_count = 0
    
    for settings_file in settings_files:
        print(f"\n📝 Processing: {settings_file}")
        
        if args.backup:
            backup_file(settings_file)
        
        # Add to INSTALLED_APPS
        if add_to_installed_apps(settings_file):
            success_count += 1
        
        # Add logging configuration
        add_logging_config(settings_file)
    
    # Add URLs
    if add_mqtt_urls(nemo_path):
        success_count += 1
    
    print(f"\n🎉 Installation complete! Modified {success_count} files.")
    print("\n📋 Next steps:")
    print("1. Run migrations: python manage.py migrate NEMO_mqtt")
    print("2. Start NEMO: python manage.py runserver")
    print("3. Configure MQTT in Django admin")


if __name__ == "__main__":
    main()
