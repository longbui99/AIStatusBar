#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$HOME/Library/Application Support/SwiftBar/Plugins"
CONFIG="$SCRIPT_DIR/config.json"
TEMPLATE="$SCRIPT_DIR/plugin.template.py"

echo "=== AI Status Bar Installer ==="

# 0. Check config exists
if [ ! -f "$CONFIG" ]; then
    echo "Error: config.json not found. Copy config.example.json to config.json first."
    exit 1
fi
if [ ! -f "$TEMPLATE" ]; then
    echo "Error: plugin.template.py not found."
    exit 1
fi

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

# 2. Set up clean plugin directory
mkdir -p "$PLUGIN_DIR"

# Remove old plugin symlinks/files (both in SwiftBar dir and generated source files)
rm -f "$PLUGIN_DIR"/ai-status.*.py "$PLUGIN_DIR"/ai-*.py 2>/dev/null || true
rm -f "$SCRIPT_DIR"/ai-*.py 2>/dev/null || true

# 3. Generate plugin scripts from config.json
#    Each enabled provider gets a file named ai-{provider}.{interval}m.py
#    SwiftBar uses the filename to determine refresh interval.
PROVIDERS=("anthropic:anthropic:Claude (Anthropic)" "cursor:cursor:Cursor IDE" "antigravity:antigravity:Antigravity IDE")

COUNT=0
for entry in "${PROVIDERS[@]}"; do
    IFS=':' read -r config_key provider_key description <<< "$entry"

    enabled=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c.get('$config_key',{}).get('enabled',False))" 2>/dev/null || echo "False")
    if [ "$enabled" != "True" ]; then
        echo "Skipped: $config_key (disabled)"
        continue
    fi

    interval=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c.get('$config_key',{}).get('refresh_interval_minutes',5))" 2>/dev/null || echo "5")

    plugin_file="$SCRIPT_DIR/ai-${provider_key}.${interval}m.py"

    # Generate the plugin script from template
    sed -e "s/{{DESCRIPTION}}/${description}/g" \
        -e "s/{{PROVIDER_KEY}}/${provider_key}/g" \
        "$TEMPLATE" > "$plugin_file"
    chmod +x "$plugin_file"

    # Symlink into SwiftBar plugin dir
    ln -s "$plugin_file" "$PLUGIN_DIR/$(basename "$plugin_file")"
    echo "Installed: ai-${provider_key}.${interval}m.py (every ${interval}min)"
    COUNT=$((COUNT + 1))
done

if [ "$COUNT" -eq 0 ]; then
    echo "Warning: No providers enabled in config.json"
    exit 0
fi

# 4. Point SwiftBar to the plugin directory
defaults write com.ameba.SwiftBar PluginDirectory "$PLUGIN_DIR"
echo "Set SwiftBar plugin directory to: $PLUGIN_DIR"

# 5. Launch SwiftBar
killall SwiftBar 2>/dev/null || true
sleep 1
echo "Launching SwiftBar..."
open "$SWIFTBAR_APP"

echo ""
echo "Done! $COUNT plugins installed — check your menu bar."
