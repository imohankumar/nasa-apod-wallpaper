#!/bin/bash

#===============================================================================
# NASA APOD Wallpaper - Uninstall Script
# 
# This script removes the NASA APOD Wallpaper application from macOS.
# It stops the launchd agent, removes configuration files, and optionally
# removes downloaded wallpapers.
#
# Usage: ./uninstall.sh [--keep-wallpapers] [--keep-config]
#===============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.nasa.wallpaper.plist"
LOG_DIR="${HOME}/Library/Logs"
PICTURES_DIR="${HOME}/Pictures/NASA_APOD"
CONFIG_FILE="${SCRIPT_DIR}/config.json"

# Options
KEEP_WALLPAPERS=false
KEEP_CONFIG=false

#===============================================================================
# Helper Functions
#===============================================================================

print_header() {
    echo ""
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  🗑️  NASA APOD Wallpaper - Uninstall${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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
        --keep-wallpapers)
            KEEP_WALLPAPERS=true
            shift
            ;;
        --keep-config)
            KEEP_CONFIG=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-wallpapers  Don't remove downloaded wallpapers"
            echo "  --keep-config      Don't remove config.json"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

#===============================================================================
# Confirmation
#===============================================================================

print_header

echo "This will remove the NASA APOD Wallpaper application."
echo ""
echo "The following will be removed:"
echo "  • Launchd agent (com.nasa.wallpaper)"
echo "  • Log files (nasa_wallpaper*.log)"
if [[ "$KEEP_CONFIG" == false ]]; then
    echo "  • Configuration file (config.json)"
fi
if [[ "$KEEP_WALLPAPERS" == false ]]; then
    echo "  • Downloaded wallpapers ($PICTURES_DIR)"
fi
echo ""

read -p "Are you sure you want to continue? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""

#===============================================================================
# Uninstall Steps
#===============================================================================

# Stop and unload launchd agent
print_step "Stopping launchd agent..."
if launchctl list | grep -q "com.nasa.wallpaper"; then
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    print_success "Launchd agent stopped"
else
    print_info "  Agent not running"
fi

# Remove plist file
print_step "Removing launchd plist..."
if [[ -f "$PLIST_DEST" ]]; then
    rm -f "$PLIST_DEST"
    print_success "Plist removed"
else
    print_info "  Plist not found"
fi

# Remove log files
print_step "Removing log files..."
LOG_COUNT=0
for logfile in "$LOG_DIR"/nasa_wallpaper*.log; do
    if [[ -f "$logfile" ]]; then
        rm -f "$logfile"
        ((LOG_COUNT++))
    fi
done
if [[ $LOG_COUNT -gt 0 ]]; then
    print_success "Removed $LOG_COUNT log file(s)"
else
    print_info "  No log files found"
fi

# Remove config file
if [[ "$KEEP_CONFIG" == false ]]; then
    print_step "Removing configuration..."
    if [[ -f "$CONFIG_FILE" ]]; then
        rm -f "$CONFIG_FILE"
        print_success "Config removed"
    else
        print_info "  Config not found"
    fi
else
    print_step "Keeping configuration file..."
    print_info "  $CONFIG_FILE"
fi

# Remove wallpapers
if [[ "$KEEP_WALLPAPERS" == false ]]; then
    print_step "Removing downloaded wallpapers..."
    if [[ -d "$PICTURES_DIR" ]]; then
        WALLPAPER_COUNT=$(find "$PICTURES_DIR" -name "NASA_APOD_*" -type f 2>/dev/null | wc -l | tr -d ' ')
        rm -rf "$PICTURES_DIR"
        print_success "Removed $WALLPAPER_COUNT wallpaper(s) and directory"
    else
        print_info "  Wallpaper directory not found"
    fi
else
    print_step "Keeping downloaded wallpapers..."
    if [[ -d "$PICTURES_DIR" ]]; then
        WALLPAPER_COUNT=$(find "$PICTURES_DIR" -name "NASA_APOD_*" -type f 2>/dev/null | wc -l | tr -d ' ')
        print_info "  $WALLPAPER_COUNT wallpaper(s) preserved in $PICTURES_DIR"
    fi
fi

#===============================================================================
# Cleanup Complete
#===============================================================================

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ Uninstall Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  The NASA APOD Wallpaper application has been removed."
echo ""

if [[ "$KEEP_WALLPAPERS" == true ]] || [[ "$KEEP_CONFIG" == true ]]; then
    echo "  Preserved files:"
    if [[ "$KEEP_WALLPAPERS" == true ]] && [[ -d "$PICTURES_DIR" ]]; then
        echo "    • Wallpapers: $PICTURES_DIR"
    fi
    if [[ "$KEEP_CONFIG" == true ]] && [[ -f "$CONFIG_FILE" ]]; then
        echo "    • Config: $CONFIG_FILE"
    fi
    echo ""
fi

echo "  To reinstall, run: ./setup.sh"
echo ""
