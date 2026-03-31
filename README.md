# AI Status Bar

SwiftBar plugins that show AI service usage and limits in your macOS menu bar. Each provider runs as an independent plugin with its own configurable refresh interval.

## Providers

| Provider | Default Refresh | What it shows |
|----------|----------------|---------------|
| **Claude** (Anthropic) | 3 min | 5h/7d usage windows, extra credits, spend (API key), plan tier |
| **Cursor** | 10 min | Premium request usage, billing period reset |
| **Antigravity** | 2 min | Per-model quota (Gemini Pro, Flash, etc.), plan info |

## Install

### Prerequisites

- macOS
- [Homebrew](https://brew.sh)
- Python 3 (ships with macOS or `brew install python3`)

### Quick Start

```bash
cd /path/to/AIStatusBar
# 1. Configure which providers to enable
vi config.json

# 2. Install
./install.sh
```

`install.sh` will:
1. Install [SwiftBar](https://github.com/swiftbar/SwiftBar) via Homebrew (if missing)
2. Read `config.json` and generate a plugin script for each **enabled** provider from `plugin.template.py`
3. Symlink generated plugins into SwiftBar's plugin directory
4. Launch SwiftBar

### Enabling / Disabling Providers

All providers are controlled via `config.json`. Set `"enabled": true` to install, `false` to skip:

```json
{
  "anthropic": {
    "enabled": true,
    "refresh_interval_minutes": 3
  },
  "cursor": {
    "enabled": false,
    "refresh_interval_minutes": 10
  },
  "antigravity": {
    "enabled": false,
    "refresh_interval_minutes": 2
  }
}
```

After changing `config.json`, re-run `./install.sh` to apply. Only enabled providers get a plugin script generated and symlinked — disabled providers are fully skipped (no process spawns).

### Changing Refresh Intervals

The `refresh_interval_minutes` value controls how often SwiftBar runs the plugin. It becomes part of the generated filename (e.g. `ai-anthropic.3m.py`), which is how SwiftBar determines the schedule. Re-run `./install.sh` after changing intervals.

### How It Works

```
config.json ──→ install.sh ──→ ai-anthropic.3m.py ──→ symlink ──→ SwiftBar
                    ↑
            plugin.template.py
```

`install.sh` reads each provider from `config.json`, renders `plugin.template.py` (replacing `{{PROVIDER_KEY}}` and `{{DESCRIPTION}}`), and writes the result as `ai-{provider}.{interval}m.py`. Generated plugin files are gitignored.

## Configuration

Edit `config.json` in the project root.

### Global Settings

| Key | Default | Description |
|-----|---------|-------------|
| `working_hours_per_day` | `24` | Active hours per day for forecast accuracy. Set to `8` if you only code during work hours. |
| `thresholds.yellow` | `80` | Usage % to turn yellow |
| `thresholds.orange` | `90` | Usage % to turn orange |
| `thresholds.red` | `150` | Usage % to turn red |
| `progress_bar.filled` | `█` | Filled character for menu bar |
| `progress_bar.empty` | `▒` | Empty character for menu bar |
| `progress_bar.width` | `4` | Bar width in characters |

### Claude (Anthropic)

Zero-config if you're logged into [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — reads your OAuth token from macOS Keychain automatically and refreshes it when expired.

| Key | Required | Description |
|-----|----------|-------------|
| `anthropic.enabled` | **Yes** | `true` or `false` |
| `anthropic.refresh_interval_minutes` | **Yes** | Refresh interval in minutes |
| `anthropic.api_key` | No | Standard API key — shows rate limits (RPM/TPM) and auto-detects tier |
| `anthropic.admin_key` | No | Admin key — enables spend tracking (today/week/month) |
| `anthropic.monthly_budget` | No | Budget cap for spend bar (e.g. `100`) |

### Cursor

Zero-config if Cursor IDE is installed — reads the access token from Cursor's local state database.

| Key | Required | Description |
|-----|----------|-------------|
| `cursor.enabled` | **Yes** | `true` or `false` |
| `cursor.refresh_interval_minutes` | **Yes** | Refresh interval in minutes |
| `cursor.session_token` | No | Manual override if auto-discovery fails |

### Antigravity

Zero-config if Antigravity IDE is running — connects to the local language server. Falls back to cloud API using credentials from Antigravity's state database when the IDE is closed.

| Key | Required | Description |
|-----|----------|-------------|
| `antigravity.enabled` | **Yes** | `true` or `false` |
| `antigravity.refresh_interval_minutes` | **Yes** | Refresh interval in minutes |

## Adding a Provider

1. Create `providers/my_provider.py`:

```python
PROVIDER_KEY = "my_provider"
DISPLAY_NAME = "MP"

def fetch_status(config: dict, global_config: dict | None = None) -> ProviderStatus:
    from providers import ProviderStatus
    # ... fetch and return status
```

2. Add a section to `config.json`:

```json
{
  "my_provider": {
    "enabled": true,
    "refresh_interval_minutes": 5
  }
}
```

3. Register the provider in `install.sh`'s `PROVIDERS` array and re-run `./install.sh`.

## Uninstall

```bash
./uninstall.sh
```

Removes plugin symlinks and optionally uninstalls SwiftBar.

## Testing

Generate plugins first with `./install.sh`, then run directly:

```bash
python3 ai-anthropic.3m.py
python3 ai-cursor.10m.py
python3 ai-antigravity.2m.py
```

Logs are written to `ai-status.log` in the project directory.
