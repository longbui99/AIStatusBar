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

# 2. Set up clean plugin directory with symlinks
#    SwiftBar executes ALL files in its plugin dir, so we point it to a
#    dedicated folder containing only symlinks to our actual plugin scripts.
mkdir -p "$PLUGIN_DIR"

# Remove old symlinks (both legacy combined and per-provider)
rm -f "$PLUGIN_DIR"/ai-status.*.py "$PLUGIN_DIR"/ai-*.py 2>/dev/null || true

# Symlink each per-provider plugin
COUNT=0
for plugin in "$SCRIPT_DIR"/ai-*.py; do
    [ -f "$plugin" ] || continue
    name="$(basename "$plugin")"
    ln -s "$plugin" "$PLUGIN_DIR/$name"
    echo "Symlinked: $name"
    COUNT=$((COUNT + 1))
done

if [ "$COUNT" -eq 0 ]; then
    echo "Error: No ai-*.py plugins found in $SCRIPT_DIR"
    exit 1
fi

# 3. Point SwiftBar to the clean plugin directory (NOT the source dir)
defaults write com.ameba.SwiftBar PluginDirectory "$PLUGIN_DIR"
echo "Set SwiftBar plugin directory to: $PLUGIN_DIR"

# 4. Launch SwiftBar
killall SwiftBar 2>/dev/null || true
sleep 1
echo "Launching SwiftBar..."
open "$SWIFTBAR_APP"

echo ""
echo "Done! $COUNT plugins installed — check your menu bar."
