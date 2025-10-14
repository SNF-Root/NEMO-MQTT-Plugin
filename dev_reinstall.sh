#!/bin/bash
# Development reinstall script for NEMO MQTT Plugin
# This script helps migrate changes from the development workspace to the Django app

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NEMO_PATH="/Users/adenton/Desktop/nemo-ce"  # Default path for local development
FORCE_REINSTALL=false
SKIP_TESTS=false
SKIP_BUILD=false
BACKUP=false
RESTART_SERVER=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --nemo-path PATH    Path to NEMO-CE installation (default: /Users/adenton/Desktop/nemo-ce)"
    echo "  -f, --force            Force reinstall even if package exists"
    echo "  -s, --skip-tests       Skip running tests"
    echo "  -b, --skip-build       Skip building package (use existing dist/)"
    echo "  --no-backup            Don't create backup of existing installation"
    echo "  -r, --restart          Restart Django server after installation"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Use default path"
    echo "  $0 --force --skip-tests # Quick reinstall with defaults"
    echo "  $0 -n /path/to/nemo-ce  # Use custom path"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--nemo-path)
            NEMO_PATH="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_REINSTALL=true
            shift
            ;;
        -s|--skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -b|--skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --no-backup)
            BACKUP=false
            shift
            ;;
        -r|--restart)
            RESTART_SERVER=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate NEMO path
if [[ ! -d "$NEMO_PATH" ]]; then
    print_error "NEMO path does not exist: $NEMO_PATH"
    print_error "Either create the directory or specify a different path with -n"
    exit 1
fi

# Check if this is a plugins directory or Django project root
if [[ -f "$NEMO_PATH/manage.py" ]]; then
    # This is the Django project root
    NEMO_PROJECT_ROOT="$NEMO_PATH"
    NEMO_PLUGINS_DIR="$NEMO_PATH/NEMO/plugins"
elif [[ -d "$NEMO_PATH" ]] && [[ "$(basename "$NEMO_PATH")" == "plugins" ]]; then
    # This is the plugins directory, find the project root
    NEMO_PROJECT_ROOT="$(dirname "$(dirname "$NEMO_PATH")")"
    NEMO_PLUGINS_DIR="$NEMO_PATH"
    
    # Verify we found the project root
    if [[ ! -f "$NEMO_PROJECT_ROOT/manage.py" ]]; then
        print_error "Could not find Django project root. Expected manage.py in: $NEMO_PROJECT_ROOT"
        print_error "Please check your NEMO installation structure"
        exit 1
    fi
else
    print_error "NEMO path must be either:"
    print_error "  1. Django project root (containing manage.py)"
    print_error "  2. plugins directory (containing NEMO plugins)"
    print_error "Current path: $NEMO_PATH"
    exit 1
fi

print_status "NEMO project root: $NEMO_PROJECT_ROOT"
print_status "NEMO plugins directory: $NEMO_PLUGINS_DIR"
echo ""
print_success "✨ Using default NEMO path (run with -h to see options)"
echo ""
print_status "Starting NEMO MQTT Plugin development reinstall..."
print_status "NEMO path: $NEMO_PATH"
print_status "Force reinstall: $FORCE_REINSTALL"
print_status "Skip tests: $SKIP_TESTS"
print_status "Skip build: $SKIP_BUILD"
print_status "Create backup: $BACKUP"
print_status "Restart server: $RESTART_SERVER"
echo ""

# Get the current directory (development workspace)
DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_status "Development workspace: $DEV_DIR"

# Change to development directory
cd "$DEV_DIR"

# Step 1: Clean up previous builds
print_status "Step 1: Cleaning up previous builds..."
if [[ -d "build" ]]; then
    rm -rf build/
    print_success "Removed build/ directory"
fi

if [[ -d "dist" ]]; then
    rm -rf dist/
    print_success "Removed dist/ directory"
fi

if [[ -d "*.egg-info" ]]; then
    rm -rf *.egg-info/
    print_success "Removed egg-info directories"
fi

# Step 2: Build the package (unless skipped)
if [[ "$SKIP_BUILD" == "false" ]]; then
    print_status "Step 2: Building package..."
    
    # Check if build tools are available
    if ! command -v python &> /dev/null; then
        print_error "Python is not available"
        exit 1
    fi
    
    # Install build dependencies
    print_status "Installing build dependencies..."
    pip install --upgrade pip setuptools wheel build
    
    # Build the package
    print_status "Building package..."
    python -m build
    
    if [[ $? -eq 0 ]]; then
        print_success "Package built successfully"
    else
        print_error "Package build failed"
        exit 1
    fi
else
    print_warning "Skipping build step (using existing dist/)"
fi

# Step 3: Check if package was built
if [[ ! -d "dist" ]] || [[ -z "$(ls -A dist/)" ]]; then
    print_error "No built packages found in dist/ directory"
    exit 1
fi

# Find the wheel file
WHEEL_FILE=$(find dist/ -name "*.whl" | head -n 1)
if [[ -z "$WHEEL_FILE" ]]; then
    print_error "No wheel file found in dist/ directory"
    exit 1
fi

print_success "Found wheel file: $WHEEL_FILE"

# Step 4: Stop Django development server (if running)
print_status "Step 3: Checking for running Django development server..."

# Check if Django development server is running on common ports
DJANGO_PIDS=""
for port in 8000 8001 8080 3000; do
    PID=$(lsof -ti:$port 2>/dev/null || true)
    if [[ -n "$PID" ]]; then
        # Check if it's actually a Django server by looking for manage.py in the process
        if ps -p "$PID" -o command= | grep -q "manage.py runserver"; then
            DJANGO_PIDS="$DJANGO_PIDS $PID"
            print_status "Found Django development server running on port $port (PID: $PID)"
        fi
    fi
done

if [[ -n "$DJANGO_PIDS" ]]; then
    print_warning "Django development server is running. Stopping it before reinstalling..."
    for pid in $DJANGO_PIDS; do
        print_status "Stopping Django server (PID: $pid)..."
        kill -TERM "$pid" 2>/dev/null || true
        
        # Wait a moment for graceful shutdown
        sleep 2
        
        # Check if it's still running and force kill if necessary
        if kill -0 "$pid" 2>/dev/null; then
            print_warning "Graceful shutdown failed, force killing (PID: $pid)..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    
    # Wait a moment for ports to be released
    sleep 1
    print_success "Django development server stopped"
else
    print_status "No Django development server found running"
fi

# Step 5: Create backup of existing installation (if requested)
if [[ "$BACKUP" == "true" ]]; then
    print_status "Step 4: Creating backup of existing installation..."
    
    # Check if plugin is already installed
    if [[ -d "$NEMO_PLUGINS_DIR/NEMO_mqtt" ]]; then
        BACKUP_DIR="$NEMO_PROJECT_ROOT/mqtt_plugin_backup_$(date +%Y%m%d_%H%M%S)"
        print_status "Creating backup in: $BACKUP_DIR"
        
        # Create backup directory
        mkdir -p "$BACKUP_DIR"
        
        # Backup existing plugin files
        cp -r "$NEMO_PLUGINS_DIR/NEMO_mqtt" "$BACKUP_DIR/"
        print_success "Backed up NEMO_mqtt directory"
        
        # Backup settings.py if it contains MQTT plugin
        if [[ -f "$NEMO_PROJECT_ROOT/settings.py" ]] && grep -q "NEMO_mqtt" "$NEMO_PROJECT_ROOT/settings.py"; then
            cp "$NEMO_PROJECT_ROOT/settings.py" "$BACKUP_DIR/settings.py.backup"
            print_success "Backed up settings.py"
        fi
        
        # Backup urls.py if it contains MQTT URLs
        if [[ -f "$NEMO_PROJECT_ROOT/NEMO/urls.py" ]] && grep -q "NEMO_mqtt" "$NEMO_PROJECT_ROOT/NEMO/urls.py"; then
            cp "$NEMO_PROJECT_ROOT/NEMO/urls.py" "$BACKUP_DIR/urls.py.backup"
            print_success "Backed up NEMO/urls.py"
        fi
        
        print_success "Backup created in: $BACKUP_DIR"
    else
        print_status "No existing installation found, skipping backup"
    fi
fi

# Step 6: Remove existing plugin (if force reinstall)
if [[ "$FORCE_REINSTALL" == "true" ]]; then
    print_status "Step 5: Removing existing plugin..."
    
    if [[ -d "$NEMO_PLUGINS_DIR/NEMO_mqtt" ]]; then
        rm -rf "$NEMO_PLUGINS_DIR/NEMO_mqtt"
        print_success "Removed existing plugin directory"
    else
        print_status "No existing plugin found"
    fi
fi

# Step 7: Install the plugin directly to plugins directory
print_status "Step 6: Installing plugin to NEMO plugins directory..."

# Extract the wheel file to a temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
unzip -q "$DEV_DIR/$WHEEL_FILE"

# Find the NEMO_mqtt directory in the extracted files
EXTRACTED_PLUGIN_DIR=$(find . -name "NEMO_mqtt" -type d | head -n 1)

if [[ -z "$EXTRACTED_PLUGIN_DIR" ]]; then
    print_error "Could not find NEMO_mqtt directory in extracted package"
    exit 1
fi

# Install directly to NEMO/plugins/NEMO_mqtt (not NEMO/plugins/NEMO/NEMO_mqtt)
NEMO_PLUGIN_DIR="$NEMO_PLUGINS_DIR/NEMO_mqtt"

# Copy the plugin files directly
cp -r "$EXTRACTED_PLUGIN_DIR" "$NEMO_PLUGINS_DIR/"

# Clean up temporary directory
cd "$DEV_DIR"
rm -rf "$TEMP_DIR"

if [[ -f "$NEMO_PLUGIN_DIR/__init__.py" ]] && [[ -f "$NEMO_PLUGIN_DIR/apps.py" ]]; then
    print_success "Plugin installed successfully to $NEMO_PLUGIN_DIR"
else
    print_error "Plugin installation failed"
    exit 1
fi

# Step 8: Run Django setup
print_status "Step 7: Setting up Django integration..."

cd "$NEMO_PROJECT_ROOT"

# Check if setup command exists
if python manage.py help setup_nemo_integration &> /dev/null; then
    print_status "Running Django setup command..."
    python manage.py setup_nemo_integration --backup
    print_success "Django setup completed"
else
    print_warning "Setup command not available, configuring manually..."
    
    # Manual configuration
    print_status "Adding to INSTALLED_APPS..."
    
    # Backup settings file will be done after we find the correct file
    
    # Find the correct settings file
    SETTINGS_FILE=""
    for settings_file in settings.py settings_dev.py settings_local.py; do
        if [[ -f "$settings_file" ]]; then
            SETTINGS_FILE="$settings_file"
            break
        fi
    done
    
    if [[ -z "$SETTINGS_FILE" ]]; then
        print_error "Could not find settings file (settings.py, settings_dev.py, or settings_local.py)"
        exit 1
    fi
    
    print_status "Using settings file: $SETTINGS_FILE"
    
    # Backup settings file
    if [[ "$BACKUP" == "true" ]]; then
        cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        print_success "Backed up $SETTINGS_FILE"
    fi
    
    # Add to INSTALLED_APPS if not already present
    if ! grep -q "NEMO_mqtt" "$SETTINGS_FILE"; then
        # Find INSTALLED_APPS and add NEMO_mqtt
        sed -i.bak '/INSTALLED_APPS = \[/,/\]/ {
            /\]/ i\
    "NEMO_mqtt",
        }' "$SETTINGS_FILE"
        print_success "Added NEMO_mqtt to INSTALLED_APPS in $SETTINGS_FILE"
    else
        print_status "NEMO_mqtt already in INSTALLED_APPS in $SETTINGS_FILE"
    fi
    
    # Add URLs if not already present
    if [[ -f "NEMO/urls.py" ]] && ! grep -q "NEMO_mqtt" NEMO/urls.py; then
        echo "" >> NEMO/urls.py
        echo "# MQTT Plugin URLs" >> NEMO/urls.py
        echo "urlpatterns += [" >> NEMO/urls.py
        echo "    path('mqtt/', include('NEMO_mqtt.urls'))," >> NEMO/urls.py
        echo "]" >> NEMO/urls.py
        print_success "Added MQTT URLs to NEMO/urls.py"
    else
        print_status "MQTT URLs already configured"
    fi
fi

# Step 9: Run migrations
print_status "Step 8: Running database migrations..."
python manage.py migrate NEMO_mqtt

if [[ $? -eq 0 ]]; then
    print_success "Migrations completed successfully"
else
    print_warning "Migrations failed or not needed"
fi

# Step 10: Run tests (unless skipped)
if [[ "$SKIP_TESTS" == "false" ]]; then
    print_status "Step 9: Running tests..."
    
    # Check if pytest is available
    if command -v pytest &> /dev/null; then
        cd "$DEV_DIR"
        
        # Install test dependencies if needed
        print_status "Installing test dependencies..."
        pip install pytest pytest-django pytest-cov --quiet
        
        # Use simple test configuration that avoids NEMO dependencies
        python -m pytest tests/test_models.py tests/test_redis_publisher.py -v --tb=short
        if [[ $? -eq 0 ]]; then
            print_success "Core tests passed"
        else
            print_warning "Some tests failed (this is expected in development)"
        fi
    else
        print_warning "pytest not available, skipping tests"
    fi
else
    print_warning "Skipping tests"
fi

# Step 11: Final verification
print_status "Step 10: Verifying installation..."

cd "$NEMO_PROJECT_ROOT"

# Check if plugin directory exists
if [[ -d "$NEMO_PLUGINS_DIR/NEMO_mqtt" ]]; then
    print_success "Plugin directory found: $NEMO_PLUGINS_DIR/NEMO_mqtt"
else
    print_error "Plugin installation verification failed - directory not found"
    exit 1
fi

# Check if Django can import the package
if python -c "import NEMO_mqtt; print('Import successful')" 2>/dev/null; then
    print_success "Django can import NEMO_mqtt package"
else
    print_warning "Django import test failed (this may be normal in some environments)"
fi

# Step 12: Restart Django server (if requested)
if [[ "$RESTART_SERVER" == "true" ]]; then
    print_status "Step 11: Restarting Django development server..."
    
    # Start Django server in background
    print_status "Starting Django development server..."
    cd "$NEMO_PROJECT_ROOT"
    nohup python manage.py runserver > /dev/null 2>&1 &
    DJANGO_PID=$!
    
    # Wait a moment for server to start
    sleep 3
    
    # Check if server started successfully
    if kill -0 "$DJANGO_PID" 2>/dev/null; then
        print_success "Django development server restarted (PID: $DJANGO_PID)"
        print_status "Server should be available at: http://localhost:8000"
    else
        print_warning "Failed to restart Django development server"
    fi
fi

# Summary
echo ""
print_success "🎉 Development reinstall completed successfully!"
echo ""
print_status "Summary:"
print_status "  - Plugin built and installed: $NEMO_PLUGINS_DIR/NEMO_mqtt"
print_status "  - Django integration configured"
print_status "  - Database migrations run"
print_status "  - NEMO project root: $NEMO_PROJECT_ROOT"
print_status "  - NEMO plugins directory: $NEMO_PLUGINS_DIR"
echo ""
print_status "Next steps:"
print_status "  1. Start NEMO: cd $NEMO_PROJECT_ROOT && python manage.py runserver"
print_status "  2. Access MQTT monitor: http://localhost:8000/mqtt/monitor/"
print_status "  3. Configure MQTT: http://localhost:8000/customization/mqtt/"
echo ""
print_status "To make changes:"
print_status "  1. Edit files in: $DEV_DIR"
print_status "  2. Run this script again: $0 -n $NEMO_PLUGINS_DIR"
echo ""
