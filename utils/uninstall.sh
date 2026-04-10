#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"

echo "=== AI Radar Uninstaller ==="

# 1. Stop SwiftBar
if pgrep -q SwiftBar; then
    echo "Stopping SwiftBar..."
    killall SwiftBar 2>/dev/null || true
    sleep 1
fi

# 2. Remove plugin symlinks
if [ -d "$PLUGIN_DIR" ]; then
    echo "Removing plugin symlinks..."
    rm -f "$PLUGIN_DIR"/ai-*.py 2>/dev/null || true
fi

# 3. Optionally uninstall SwiftBar
read -rp "Uninstall SwiftBar via Homebrew? [y/N] " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    echo "Uninstalling SwiftBar..."
    brew uninstall --cask swiftbar 2>/dev/null || true
    defaults delete com.ameba.SwiftBar 2>/dev/null || true
else
    echo "Kept SwiftBar installed."
fi

echo ""
echo "Done! AI Radar has been removed."
