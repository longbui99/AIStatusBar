#!/usr/bin/env python3
# <xbar.title>AI Radar — Manager</xbar.title>
# <xbar.desc>Configure AI Radar providers</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>

import json
import pkgutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from providers.rendering import COLORS

CONFIG_PATH = SCRIPT_DIR / "config.json"
PROVIDERS_DIR = SCRIPT_DIR / "providers"
TOGGLE_SCRIPT = SCRIPT_DIR / "bin" / "ai-toggle-provider"

DEFAULT_CONFIG = {
    "working_hours_per_day": 24,
    "thresholds": {"yellow": 80, "orange": 90, "red": 100},
    "progress_bar": {"filled": "\u2588", "empty": "\u2592", "width": 4},
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return dict(DEFAULT_CONFIG)


def discover_providers() -> list[tuple[str, str]]:
    """Auto-discover providers from providers/*.py, return [(key, full_name)]."""
    providers = []
    for _, name, _ in pkgutil.iter_modules([str(PROVIDERS_DIR)]):
        if name.startswith("_"):
            continue
        src = (PROVIDERS_DIR / f"{name}.py").read_text()
        pk = fn = ""
        for line in src.splitlines():
            if line.startswith("PROVIDER_KEY"):
                pk = line.split("=", 1)[1].strip().strip("\"'")
            if line.startswith("FULL_NAME"):
                fn = line.split("=", 1)[1].strip().strip("\"'")
        if pk and fn:
            providers.append((pk, fn))
    return providers


def main() -> None:
    config = load_config()
    providers = discover_providers()

    # Title — small sparkle icon
    print(f"\u2726 | sfimage=sparkles size=13 color={COLORS['blue']}")
    print("---")
    print(f"AI Radar | size=13 font=SF-Pro-Text-Semibold color={COLORS['white']}")
    print("---")

    # Provider toggles
    for key, full_name in providers:
        enabled = config.get(key, {}).get("enabled", False)
        if enabled:
            icon = "checkmark.circle.fill"
            color = COLORS["green"]
            prefix = "\u2713"
        else:
            icon = "circle"
            color = COLORS["gray"]
            prefix = "\u2717"

        print(
            f"{prefix} {full_name} | "
            f"bash={TOGGLE_SCRIPT} param1={key} "
            f"terminal=false refresh=true "
            f"sfimage={icon} color={color} size=13"
        )

    # Footer
    print("---")
    print(
        f"Open Config | "
        f"bash=open param1={CONFIG_PATH} "
        f"terminal=false sfimage=gearshape size=13 color={COLORS['dim']}"
    )
    print(f"Refresh | refresh=true sfimage=arrow.clockwise size=13 color={COLORS['dim']}")


if __name__ == "__main__":
    main()
