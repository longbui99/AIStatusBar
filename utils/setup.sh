#!/usr/bin/env bash
set -euo pipefail

# AI Radar — https://github.com/longbui99/AIRadar
# curl -fsSL https://raw.githubusercontent.com/longbui99/AIRadar/main/utils/setup.sh | bash

REPO="https://github.com/longbui99/AIRadar.git"
DIR="$HOME/.ai-radar"
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
ln -sf "$DIR/bin/ai-radar" "$BIN/ai-radar"
chmod +x "$DIR/bin/ai-radar"

# Add to PATH if needed
if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    RC="$HOME/.zshrc"
    [ "$(basename "$SHELL")" = "bash" ] && RC="$HOME/.bashrc"
    echo '' >> "$RC"
    echo '# AI Radar' >> "$RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$RC"
    export PATH="$BIN:$PATH"
fi

# Hand off to the real CLI — must use bash (not exec) so /dev/tty works after pipe
bash "$BIN/ai-radar" setup </dev/tty
