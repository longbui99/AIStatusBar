#!/usr/bin/env python3
# <xbar.title>AI Status Bar</xbar.title>
# <xbar.version>v2.0</xbar.version>
# <xbar.author>Glacis</xbar.author>
# <xbar.desc>Show AI API usage and rate limits in the menu bar</xbar.desc>
# <xbar.dependencies>python3</xbar.dependencies>
"""AI Status Bar — SwiftBar plugin showing AI API usage at a glance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from providers import ProviderStatus, load_providers
from providers.rendering import (
    COLORS,
    Metric,
    SpendRow,
    configure_bar,
    render_footer,
    render_metric_section,
    render_plan_badge,
    render_rate_limit_section,
    render_separator,
    render_spend_section,
    render_title_cycling,
)

# Shorter refresh interval when not authenticated (2 minutes instead of 30)
RETRY_INTERVAL_SECS = 120


def load_config() -> dict:
    config_path = SCRIPT_DIR / "config.json"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return json.load(f)


def _needs_login(statuses: list[ProviderStatus]) -> bool:
    """Check if any provider has an auth error suggesting login is needed."""
    for s in statuses:
        if s.error and ("No API key" in s.error or "401" in s.error or "Unauthorized" in s.error):
            return True
    if not statuses:
        return False
    return all(s.summary in ("--", "err") for s in statuses)


def render(statuses: list[ProviderStatus]) -> None:
    needs_login = _needs_login(statuses)

    if not statuses:
        print(f"Setup | sfimage=sparkle color=#FF9500 size=13")
        print("---")
        config_example = SCRIPT_DIR / "config.example.json"
        print(f"Copy config.example.json to config.json | bash=cp param1={config_example} param2={SCRIPT_DIR / 'config.json'} terminal=false refresh=true")
        print(f"Open Plugin Folder | bash=open param1={SCRIPT_DIR} terminal=false")
        return

    # ── Menu bar title (cycling lines) ───────────────────────────────────
    title_lines = render_title_cycling(statuses)
    for line in title_lines:
        print(line)

    print("---")

    # ── Dropdown body ────────────────────────────────────────────────────
    for s in statuses:
        # Provider header
        print(f"{s.name} | size=15 font=SF-Pro-Display-Bold sfimage=sparkles sfcolor={COLORS['blue']}")
        print("---")

        # Metrics sections
        for i, md in enumerate(s.metrics):
            m = Metric(
                label=md.label,
                pct=md.pct,
                forecast_pct=md.forecast_pct,
                color=md.color,
                reset_label=md.reset_label,
                extra=md.extra,
            )
            for line in render_metric_section(m):
                print(line)
            if i < len(s.metrics) - 1:
                print(render_separator())

        # Spend section
        if s.spend_rows:
            print(render_separator())
            rows = [SpendRow(label=sr.label, amount=sr.amount) for sr in s.spend_rows]
            for line in render_spend_section(
                "Spend", rows,
                bar_pct=s.spend_pct,
                bar_color=s.spend_color,
                forecast_line=s.spend_forecast,
            ):
                print(line)

        # Rate limits
        if s.rate_limits:
            print(render_separator())
            for line in render_rate_limit_section(s.rate_limits):
                print(line)

        # Plan badge
        if s.plan_label:
            print(render_separator())
            for line in render_plan_badge(s.plan_label):
                print(line)

        # Error
        if s.error:
            print(render_separator())
            print(f"  {s.error} | sfimage=exclamationmark.triangle color=#FF3B30 size=11")

    # Footer
    for line in render_footer(str(SCRIPT_DIR), show_login=needs_login):
        print(line)


def main() -> None:
    try:
        config = load_config()
        configure_bar(config)
        providers = load_providers()

        statuses: list[ProviderStatus] = []
        for key, mod in sorted(providers.items()):
            provider_config = config.get(key, {})
            try:
                status = mod.fetch_status(provider_config, global_config=config)
                statuses.append(status)
            except Exception as e:
                statuses.append(ProviderStatus(
                    name=getattr(mod, "DISPLAY_NAME", key),
                    short_name=getattr(mod, "DISPLAY_NAME", key),
                    summary="err",
                    error=str(e),
                ))

        render(statuses)
    except Exception as e:
        print(f"err | sfimage=exclamationmark.triangle color=#FF3B30 size=13")
        print("---")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
