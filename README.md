# AI Status Bar

SwiftBar plugin showing AI API usage/limits in the macOS menu bar.

## Setup

1. Install [SwiftBar](https://github.com/swiftbar/SwiftBar) (e.g. `brew install --cask swiftbar`)
2. Copy config: `cp config.example.json config.json`
3. Edit `config.json` with your API keys
4. Symlink the plugin into your SwiftBar plugins folder:
   ```bash
   ln -s "$(pwd)/ai-status.30m.py" ~/Library/Application\ Support/SwiftBar/Plugins/
   ```

## Configuration

| Key | Required | Description |
|-----|----------|-------------|
| `anthropic.api_key` | Yes* | Standard API key — shows rate limits (RPM/TPM) |
| `anthropic.admin_key` | No | Admin key — enables spend tracking ($/day/week/month) |
| `anthropic.monthly_budget` | No | Budget cap for display (e.g. 100.00) |

*At least one of `api_key` or `admin_key` needed.

## Adding Providers

Drop a new file in `providers/` (e.g. `openai.py`) with:
```python
PROVIDER_KEY = "openai"
DISPLAY_NAME = "GPT"

def fetch_status(config: dict) -> ProviderStatus:
    from providers import ProviderStatus
    # ... fetch and return status
```

Add matching section to `config.json`. Auto-discovered on next refresh.

## Testing

```bash
python3 ai-status.30m.py
```
