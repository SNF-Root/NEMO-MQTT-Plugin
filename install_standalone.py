#!/usr/bin/env python3
"""
Standalone MQTT Plugin Installation Script
Usage: python install_standalone.py --nemo-path /path/to/nemo-ce
"""

import os
import sys
import subprocess
import argparse
import re
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Standalone MQTT Plugin Installation')
    parser.add_argument('--nemo-path', required=True, help='Path to NEMO-CE installation')
    parser.add_argument('--force', action='store_true', help='Force reinstallation')
    parser.add_argument('--backup', action='store_true', help='Create backup files')
    
    args = parser.parse_args()
    
    nemo_path = Path(args.nemo_path)
    if not nemo_path.exists():
        print(f"❌ NEMO path does not exist: {nemo_path}")
        sys.exit(1)
    
    plugin_dir = Path(__file__).parent
    print(f"🔧 Installing MQTT Plugin from: {plugin_dir}")
    print(f"📁 Target NEMO installation: {nemo_path}")
    
    try:
        # Step 1: Install Python package
        print("\n📦 Installing Python package...")
        install_python_package(plugin_dir, nemo_path)
        
        # Step 2: Copy plugin files
        print("\n📁 Copying plugin files...")
        copy_plugin_files(plugin_dir, nemo_path)
        
        # Step 3: Add to INSTALLED_APPS
        print("\n📝 Adding to INSTALLED_APPS...")
        add_to_installed_apps(nemo_path, args.backup)
        
        # Step 4: Add URL patterns
        print("\n🔗 Adding URL patterns...")
        add_url_patterns(nemo_path, args.backup)
        
        # Step 5: Run migrations
        print("\n🗄️  Running migrations...")
        run_migrations(nemo_path)
        
        # Step 6: Verify installation
        print("\n🔍 Verifying installation...")
        verify_installation(nemo_path)
        
        print("\n🎉 MQTT Plugin installation completed successfully!")
        print("\n📋 Next steps:")
        print("1. Start NEMO: python manage.py runserver")
        print("2. Access monitor: http://localhost:8000/mqtt/monitor/")
        print("3. Configure MQTT settings in Django admin")
        
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)


def install_python_package(plugin_dir, nemo_path):
    """Install the plugin as a Python package"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-e', str(plugin_dir)],
            cwd=nemo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Python package installed")
    except subprocess.CalledProcessError as e:
        raise Exception(f'Failed to install Python package: {e.stderr}')


def copy_plugin_files(plugin_dir, nemo_path):
    """Copy plugin files to NEMO directory"""
    plugin_source = plugin_dir / 'NEMO_mqtt'
    plugin_target = nemo_path / 'NEMO_mqtt'
    
    if plugin_target.exists():
        shutil.rmtree(plugin_target)
    
    shutil.copytree(plugin_source, plugin_target)
    print("✅ Plugin files copied")


def add_to_installed_apps(nemo_path, create_backup=False):
    """Add NEMO_mqtt to INSTALLED_APPS"""
    settings_file = find_settings_file(nemo_path)
    if not settings_file:
        raise Exception('Could not find Django settings file')
    
    if create_backup:
        create_backup_file(settings_file)
    
    with open(settings_file, 'r') as f:
        content = f.read()
    
    # Check if already added
    if "'NEMO_mqtt'" in content or '"NEMO_mqtt"' in content:
        print("⚠️  NEMO_mqtt already in INSTALLED_APPS")
        return
    
    # Add to INSTALLED_APPS
    pattern = r'(INSTALLED_APPS\s*=\s*\[[^\]]*)(\]\s*$)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if match:
        new_content = content[:match.start(2)] + "    'NEMO_mqtt',\n" + match.group(2)
        
        with open(settings_file, 'w') as f:
            f.write(new_content)
        print("✅ Added to INSTALLED_APPS")
    else:
        raise Exception('Could not find INSTALLED_APPS in settings file')


def add_url_patterns(nemo_path, create_backup=False):
    """Add MQTT URLs to main urls.py"""
    urls_file = nemo_path / 'NEMO' / 'urls.py'
    
    if not urls_file.exists():
        raise Exception(f'Could not find NEMO/urls.py at {urls_file}')
    
    if create_backup:
        create_backup_file(urls_file)
    
    with open(urls_file, 'r') as f:
        content = f.read()
    
    # Check if already added
    if "NEMO_mqtt.urls" in content:
        print("⚠️  MQTT URLs already added")
        return
    
    # Add URL patterns
    pattern = r'(\s+)(# Add.*URLs.*\n.*\])'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    
    if match:
        mqtt_urls = f"""
    # Add MQTT plugin URLs
    urlpatterns += [
        path("mqtt/", include("NEMO_mqtt.urls")),
    ]"""
        new_content = content[:match.end()] + mqtt_urls + content[match.end():]
    else:
        # Add at the end of the file
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
    print("✅ URL patterns added")


def run_migrations(nemo_path):
    """Run database migrations"""
    try:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate', 'NEMO_mqtt'],
            cwd=nemo_path,
            env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'settings_dev'},
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Migrations completed")
    except subprocess.CalledProcessError as e:
        raise Exception(f'Migration failed: {e.stderr}')


def verify_installation(nemo_path):
    """Verify the installation"""
    # Check if plugin directory exists
    plugin_dir = nemo_path / 'NEMO_mqtt'
    if not plugin_dir.exists():
        raise Exception('Plugin directory not found')
    
    # Check if settings file has the plugin
    settings_file = find_settings_file(nemo_path)
    if settings_file:
        with open(settings_file, 'r') as f:
            content = f.read()
        if 'NEMO_mqtt' not in content:
            raise Exception('Plugin not found in INSTALLED_APPS')
    
    print("✅ Installation verified")


def find_settings_file(nemo_path):
    """Find the main Django settings file"""
    for filename in ['settings_dev.py', 'settings.py', 'settings_prod.py']:
        settings_file = nemo_path / filename
        if settings_file.exists():
            return settings_file
    return None


def create_backup_file(file_path):
    """Create a backup of a file"""
    backup_path = f"{file_path}.backup"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        print(f"📋 Created backup: {backup_path}")


if __name__ == "__main__":
    main()

