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

# 2. Set up clean plugin directory with symlink
#    SwiftBar executes ALL files in its plugin dir, so we point it to a
#    dedicated folder containing only a symlink to our actual plugin script.
mkdir -p "$PLUGIN_DIR"

# Auto-detect the plugin file (matches ai-status.*.py pattern)
PLUGIN_FILE="$(ls "$SCRIPT_DIR"/ai-status.*.py 2>/dev/null | head -1)"
if [ -z "$PLUGIN_FILE" ]; then
    echo "Error: No ai-status.*.py plugin found in $SCRIPT_DIR"
    exit 1
fi
PLUGIN_NAME="$(basename "$PLUGIN_FILE")"

# Remove old symlinks
rm -f "$PLUGIN_DIR"/ai-status.*.py 2>/dev/null || true

# Create symlink to the actual plugin
ln -s "$PLUGIN_FILE" "$PLUGIN_DIR/$PLUGIN_NAME"
echo "Symlinked plugin to: $PLUGIN_DIR/$PLUGIN_NAME"

# 3. Point SwiftBar to the clean plugin directory (NOT the source dir)
defaults write com.ameba.SwiftBar PluginDirectory "$PLUGIN_DIR"
echo "Set SwiftBar plugin directory to: $PLUGIN_DIR"

# 4. Launch SwiftBar
killall SwiftBar 2>/dev/null || true
sleep 1
echo "Launching SwiftBar..."
open "$SWIFTBAR_APP"

echo ""
echo "Done! Look for 'CLD' in your menu bar."
