#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"

echo "=== AI Status Bar Installer ==="

# 1. Install SwiftBar if missing
if ! brew list --cask swiftbar &>/dev/null; then
    echo "Installing SwiftBar..."
    brew install --cask swiftbar
else
    echo "SwiftBar already installed."
fi

# Find SwiftBar app path
SWIFTBAR_APP="$(find /opt/homebrew/Caskroom/swiftbar /Applications -name 'SwiftBar.app' -maxdepth 3 2>/dev/null | head -1)"
if [ -z "$SWIFTBAR_APP" ]; then
    echo "Error: Could not find SwiftBar.app"
    exit 1
fi
echo "Found SwiftBar at: $SWIFTBAR_APP"

# 3. Use our project folder as the SwiftBar plugin directory directly
#    Rename non-plugin files so SwiftBar ignores them (it only runs *.{sh,py,rb,etc} with intervals)
defaults write com.ameba.SwiftBar PluginDirectory "$SCRIPT_DIR"
echo "Set SwiftBar plugin directory to: $SCRIPT_DIR"

# 5. Launch SwiftBar
killall SwiftBar 2>/dev/null || true
sleep 1
echo "Launching SwiftBar..."
open "$SWIFTBAR_APP"

echo ""
echo "Done! Look for 'CLD' in your menu bar."
