#!/bin/bash

#===============================================================================
# NASA APOD Wallpaper - Setup Script
# 
# This script sets up the NASA APOD Wallpaper application on macOS.
# It checks prerequisites, installs dependencies, and configures the
# launchd agent for automatic daily execution.
#
# Usage: ./setup.sh [--no-test] [--api-key YOUR_KEY]
#===============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory./setup.sh --api-key YOUR_API_KEY
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/nasa_wallpaper.py"
PLIST_TEMPLATE="${SCRIPT_DIR}/com.nasa.wallpaper.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.nasa.wallpaper.plist"
LOG_DIR="${HOME}/Library/Logs"
PICTURES_DIR="${HOME}/Pictures/NASA_APOD"
CONFIG_FILE="${SCRIPT_DIR}/config.json"
CONFIG_EXAMPLE="${SCRIPT_DIR}/config.json.example"

# Default options
RUN_TEST=true
API_KEY=""

#===============================================================================
# Helper Functions
#===============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  🚀 NASA APOD Wallpaper - Setup${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "  $1"
}

#===============================================================================
# Parse Arguments
#===============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-test)
            RUN_TEST=false
            shift
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./setup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-test        Skip the initial test run"
            echo "  --api-key KEY    Set NASA API key during setup"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

#===============================================================================
# Main Setup
#===============================================================================

print_header

# Check macOS
print_step "Checking operating system..."
if [[ "$(uname)" != "Darwin" ]]; then
    print_error "This script is designed for macOS only."
    exit 1
fi
print_success "macOS detected: $(sw_vers -productVersion)"

# Check Python 3
print_step "Checking Python 3..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed."
    print_info "Please install Python 3 using one of these methods:"
    print_info "  • Download from https://www.python.org/downloads/"
    print_info "  • Install via Homebrew: brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 8 ]]; then
    print_error "Python 3.8+ is required. Found: Python $PYTHON_VERSION"
    exit 1
fi
print_success "Python $PYTHON_VERSION found"

# Check pip
print_step "Checking pip..."
if ! python3 -m pip --version &> /dev/null; then
    print_warning "pip not found. Attempting to install..."
    python3 -m ensurepip --default-pip 2>/dev/null || {
        print_error "Could not install pip. Please install it manually."
        exit 1
    }
fi
print_success "pip is available"

# Install Python dependencies
print_step "Installing Python dependencies..."
if python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt" --quiet; then
    print_success "Dependencies installed"
else
    print_warning "Could not install with pip. Trying with --user flag..."
    python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt" --user --quiet
    print_success "Dependencies installed (user mode)"
fi

# Create necessary directories
print_step "Creating directories..."
mkdir -p "$PICTURES_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$PLIST_DEST")"
print_success "Directories created"
print_info "  • Pictures: $PICTURES_DIR"
print_info "  • Logs: $LOG_DIR"

# Create config file if it doesn't exist
print_step "Setting up configuration..."
if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        cp "$CONFIG_EXAMPLE" "$CONFIG_FILE"
        print_success "Created config.json from example"
    else
        cat > "$CONFIG_FILE" << EOF
{
    "api_key": "DEMO_KEY",
    "keep_last_n_wallpapers": 30,
    "show_notifications": true,
    "max_retries": 3,
    "retry_delay_base": 2,
    "timeout": 30,
    "hd_preferred": true
}
EOF
        print_success "Created default config.json"
    fi
else
    print_success "config.json already exists"
fi

# Update API key if provided
if [[ -n "$API_KEY" ]]; then
    print_step "Updating API key..."
    # Use Python to safely update JSON
    python3 << EOF
import json
with open("$CONFIG_FILE", "r") as f:
    config = json.load(f)
config["api_key"] = "$API_KEY"
with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=4)
EOF
    print_success "API key updated in config.json"
fi

# Make Python script executable
print_step "Setting script permissions..."
chmod +x "$PYTHON_SCRIPT"
print_success "Script is executable"

# Unload existing launch agent if present
print_step "Configuring launchd agent..."
if launchctl list | grep -q "com.nasa.wallpaper"; then
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    print_info "  Unloaded existing agent"
fi

# Create and install plist
print_step "Installing launchd agent..."

# Read template and replace placeholders
sed -e "s|__SCRIPT_PATH__|${PYTHON_SCRIPT}|g" \
    -e "s|__WORKING_DIR__|${SCRIPT_DIR}|g" \
    -e "s|__LOG_DIR__|${LOG_DIR}|g" \
    "$PLIST_TEMPLATE" > "$PLIST_DEST"

# Verify plist is valid
if plutil -lint "$PLIST_DEST" > /dev/null 2>&1; then
    print_success "Launchd plist is valid"
else
    print_error "Invalid plist file. Please check the template."
    exit 1
fi

# Load the launch agent
if launchctl load "$PLIST_DEST"; then
    print_success "Launchd agent loaded"
else
    print_error "Failed to load launchd agent"
    exit 1
fi

# Run initial test
if [[ "$RUN_TEST" == true ]]; then
    echo ""
    print_step "Running initial test..."
    echo ""
    
    if python3 "$PYTHON_SCRIPT"; then
        echo ""
        print_success "Initial test completed successfully!"
    else
        echo ""
        print_warning "Test completed with warnings. Check logs for details."
        print_info "Log file: $LOG_DIR/nasa_wallpaper.log"
    fi
fi

#===============================================================================
# Setup Complete
#===============================================================================

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  The NASA APOD wallpaper will automatically update daily at 8:00 AM."
echo ""
echo -e "  ${BLUE}Important Paths:${NC}"
echo "  • Config file:    $CONFIG_FILE"
echo "  • Wallpapers:     $PICTURES_DIR"
echo "  • Log file:       $LOG_DIR/nasa_wallpaper.log"
echo "  • Launchd plist:  $PLIST_DEST"
echo ""
echo -e "  ${BLUE}Useful Commands:${NC}"
echo "  • Manual run:     python3 $PYTHON_SCRIPT"
echo "  • View logs:      tail -f $LOG_DIR/nasa_wallpaper.log"
echo "  • Check status:   launchctl list | grep nasa"
echo "  • Uninstall:      ./uninstall.sh"
echo ""
echo -e "  ${YELLOW}Note:${NC} For higher API rate limits, get a free API key at:"
echo "  https://api.nasa.gov/"
echo ""
