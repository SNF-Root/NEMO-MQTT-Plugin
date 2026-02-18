#!/usr/bin/env python3
"""
Django management command to install the MQTT plugin
Usage: python manage.py install_mqtt_plugin
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Install the MQTT plugin with all required configurations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reinstallation even if plugin is already installed',
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup files before modifying settings',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 Installing NEMO MQTT Plugin...')
        )
        
        # Check if already installed
        if not options['force'] and self.is_plugin_installed():
            self.stdout.write(
                self.style.WARNING('⚠️  Plugin appears to be already installed. Use --force to reinstall.')
            )
            return
        
        try:
            # Step 1: Install Python package
            self.install_python_package()
            
            # Step 2: Add to INSTALLED_APPS
            self.add_to_installed_apps(options['backup'])
            
            # Step 3: Add URL patterns
            self.add_url_patterns(options['backup'])
            
            # Step 4: Run migrations
            self.run_migrations()
            
            # Step 5: Verify installation
            self.verify_installation()
            
            self.stdout.write(
                self.style.SUCCESS('🎉 MQTT Plugin installation completed successfully!')
            )
            self.stdout.write('\n📋 Next steps:')
            self.stdout.write('1. Start NEMO: python manage.py runserver')
            self.stdout.write('2. Access monitor: http://localhost:8000/mqtt/monitor/')
            self.stdout.write('3. Configure MQTT settings in Django admin')
            
        except Exception as e:
            raise CommandError(f'Installation failed: {e}')

    def is_plugin_installed(self):
        """Check if plugin is already installed"""
        return 'nemo_mqtt' in settings.INSTALLED_APPS

    def install_python_package(self):
        """Install the plugin as a Python package"""
        self.stdout.write('📦 Installing Python package...')
        
        # Get the plugin directory (where this command is located)
        plugin_dir = Path(__file__).parent.parent.parent.parent
        
        try:
            # Install in development mode
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-e', str(plugin_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            self.stdout.write(self.style.SUCCESS('✅ Python package installed'))
        except subprocess.CalledProcessError as e:
            raise CommandError(f'Failed to install Python package: {e.stderr}')

    def add_to_installed_apps(self, create_backup=False):
        """Add nemo_mqtt to INSTALLED_APPS"""
        self.stdout.write('📝 Adding to INSTALLED_APPS...')
        
        # Find settings file
        settings_file = self.find_settings_file()
        if not settings_file:
            raise CommandError('Could not find Django settings file')
        
        if create_backup:
            self.create_backup(settings_file)
        
        # Read current settings
        with open(settings_file, 'r') as f:
            content = f.read()
        
        # Check if already added
        if "'nemo_mqtt'" in content or '"nemo_mqtt"' in content:
            self.stdout.write(self.style.WARNING('⚠️  nemo_mqtt already in INSTALLED_APPS'))
            return
        
        # Add to INSTALLED_APPS
        import re
        pattern = r'(INSTALLED_APPS\s*=\s*\[[^\]]*)(\]\s*$)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            new_content = content[:match.start(2)] + "    'nemo_mqtt',\n" + match.group(2)
            
            with open(settings_file, 'w') as f:
                f.write(new_content)
            self.stdout.write(self.style.SUCCESS('✅ Added to INSTALLED_APPS'))
        else:
            raise CommandError('Could not find INSTALLED_APPS in settings file')

    def add_url_patterns(self, create_backup=False):
        """Add MQTT URLs to main urls.py"""
        self.stdout.write('🔗 Adding URL patterns...')
        
        urls_file = Path(settings.BASE_DIR) / 'NEMO' / 'urls.py'
        
        if not urls_file.exists():
            raise CommandError(f'Could not find NEMO/urls.py at {urls_file}')
        
        if create_backup:
            self.create_backup(urls_file)
        
        with open(urls_file, 'r') as f:
            content = f.read()
        
        # Check if already added
        if "nemo_mqtt.urls" in content:
            self.stdout.write(self.style.WARNING('⚠️  MQTT URLs already added'))
            return
        
        # Add URL patterns
        import re
        pattern = r'(\s+)(# Add.*URLs.*\n.*\])'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            mqtt_urls = f"""
    # Add MQTT plugin URLs
    urlpatterns += [
        path("mqtt/", include("nemo_mqtt.urls")),
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
                "        path(\"mqtt/\", include(\"nemo_mqtt.urls\")),",
                "    ]"
            ]
            lines.extend(mqtt_urls)
            new_content = '\n'.join(lines)
        
        with open(urls_file, 'w') as f:
            f.write(new_content)
        self.stdout.write(self.style.SUCCESS('✅ URL patterns added'))

    def run_migrations(self):
        """Run database migrations"""
        self.stdout.write('🗄️  Running migrations...')
        
        try:
            result = subprocess.run(
                [sys.executable, 'manage.py', 'migrate', 'nemo_mqtt'],
                capture_output=True,
                text=True,
                check=True
            )
            self.stdout.write(self.style.SUCCESS('✅ Migrations completed'))
        except subprocess.CalledProcessError as e:
            raise CommandError(f'Migration failed: {e.stderr}')

    def verify_installation(self):
        """Verify the installation"""
        self.stdout.write('🔍 Verifying installation...')
        
        # Check if plugin is in INSTALLED_APPS
        if 'nemo_mqtt' not in settings.INSTALLED_APPS:
            raise CommandError('Plugin not found in INSTALLED_APPS')
        
        # Check if URLs are accessible
        try:
            from django.urls import reverse
            reverse('mqtt_plugin:monitor')
            self.stdout.write(self.style.SUCCESS('✅ Installation verified'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  URL verification failed: {e}'))

    def find_settings_file(self):
        """Find the main Django settings file"""
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
        
        if settings_module:
            # Convert module path to file path
            settings_path = settings_module.replace('.', '/') + '.py'
            if os.path.exists(settings_path):
                return settings_path
        
        # Fallback: look for common settings files
        for filename in ['settings.py', 'settings_dev.py', 'settings_prod.py']:
            if os.path.exists(filename):
                return filename
        
        return None

    def create_backup(self, file_path):
        """Create a backup of a file"""
        backup_path = f"{file_path}.backup"
        if not os.path.exists(backup_path):
            shutil.copy2(file_path, backup_path)
            self.stdout.write(f'📋 Created backup: {backup_path}')

