#!/usr/bin/env bash
set -euo pipefail

# AI Status Bar — https://github.com/longbui99/AIStatusBar
# curl -fsSL https://raw.githubusercontent.com/longbui99/AIStatusBar/main/utils/setup.sh | bash

REPO="https://github.com/longbui99/AIStatusBar.git"
DIR="$HOME/.ai-status-bar"
BIN="$HOME/.local/bin"

# Clone or update
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" pull --ff-only origin main -q 2>/dev/null || {
        rm -rf "$DIR" && git clone --depth 1 -q "$REPO" "$DIR"
    }
else
    rm -rf "$DIR" 2>/dev/null; git clone --depth 1 -q "$REPO" "$DIR"
fi

# Link binary to PATH
mkdir -p "$BIN"
ln -sf "$DIR/bin/ai-status-bar" "$BIN/ai-status-bar"
chmod +x "$DIR/bin/ai-status-bar"

# Add to PATH if needed
if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    RC="$HOME/.zshrc"
    [ "$(basename "$SHELL")" = "bash" ] && RC="$HOME/.bashrc"
    echo '' >> "$RC"
    echo '# AI Status Bar' >> "$RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    export PATH="$BIN:$PATH"
fi

# Hand off to the real CLI — must use bash (not exec) so /dev/tty works after pipe
bash "$BIN/ai-status-bar" setup </dev/tty
