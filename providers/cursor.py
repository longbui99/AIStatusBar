"""Cursor IDE provider for AI Radar."""

from __future__ import annotations

import json
import logging
import sqlite3 as sqlite
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from providers import MetricData, ProviderStatus

logger = logging.getLogger(__name__)

PROVIDER_KEY = "cursor"
DISPLAY_NAME = "CUR"
FULL_NAME = "Cursor"

USAGE_URL = "https://api2.cursor.sh/auth/usage"
PROFILE_URL = "https://api2.cursor.sh/auth/full_stripe_profile"
CURSOR_STATE_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "state.vscdb"
)

# Default thresholds — overridden by config.json
_THRESHOLDS = {"yellow": 60, "orange": 80, "red": 100}
_WORKING_HOURS: float = 0


def _estimate_active_hours(wall_hours: float, working_hours_per_day: float) -> float:
    """Estimate active hours within a wall-clock duration."""
    if working_hours_per_day <= 0 or working_hours_per_day >= 24:
        return wall_hours
    full_days = wall_hours / 24
    return full_days * working_hours_per_day


def _set_thresholds(cfg: dict) -> None:
    global _THRESHOLDS, _WORKING_HOURS
    t = cfg.get("thresholds", {})
    if t:
        _THRESHOLDS = {
            "yellow": t.get("yellow", 60),
            "orange": t.get("orange", 80),
            "red": t.get("red", 100),
        }
    _WORKING_HOURS = cfg.get("working_hours_per_day", 0)


def _pct_color(pct: float) -> str:
    if pct >= _THRESHOLDS["red"]:
        return "red"
    if pct >= _THRESHOLDS["orange"]:
        return "orange"
    if pct >= _THRESHOLDS["yellow"]:
        return "yellow"
    return "green"


_COLOR_RANK = {"white": 0, "green": 0, "yellow": 1, "orange": 2, "red": 3}


def _worst(a: str, b: str) -> str:
    return a if _COLOR_RANK.get(a, 0) >= _COLOR_RANK.get(b, 0) else b


def _to_bar_color(color: str) -> str:
    return "white" if color == "green" else color


def _read_state_db(key: str) -> str:
    """Read a value from Cursor's local state DB."""
    try:
        if not CURSOR_STATE_DB.exists():
            return ""
        conn = sqlite.connect(str(CURSOR_STATE_DB))
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def _read_membership_type() -> str:
    return _read_state_db("cursorAuth/stripeMembershipType")


def _read_access_token() -> str:
    """Read the access token directly from Cursor's state DB."""
    return _read_state_db("cursorAuth/accessToken")


def _fetch_usage(access_token: str) -> dict:
    """Fetch usage data from Cursor's API."""
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _fetch_profile(access_token: str) -> dict:
    """Fetch subscription profile from Cursor's API."""
    req = urllib.request.Request(
        PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _parse_reset_period(start_of_period: str) -> tuple[str, str]:
    """Parse the start of billing period to compute reset info.

    Returns (relative_label, absolute_time_str).
    Cursor resets monthly from the start of the billing period.
    """
    try:
        # Parse the period start and compute next reset (1 month later)
        clean = start_of_period.replace("+00:00", "").replace("Z", "")
        start = datetime.fromisoformat(clean)
        # Approximate next month
        if start.month == 12:
            reset = start.replace(year=start.year + 1, month=1)
        else:
            reset = start.replace(month=start.month + 1)

        now = datetime.utcnow()
        delta = reset - now
        total_min = int(delta.total_seconds() / 60)

        reset_aware = reset.replace(tzinfo=timezone.utc)
        reset_local = reset_aware.astimezone()
        now_local = datetime.now().astimezone()

        if total_min < 0:
            return "now", ""
        if total_min < 60:
            relative = f"{total_min}m"
        elif total_min < 24 * 60:
            hours = total_min // 60
            mins = total_min % 60
            relative = f"{hours}h {mins}m"
        else:
            hours = total_min // 60
            days = hours // 24
            relative = f"{days}d {hours % 24}h"

        if reset_local.date() != now_local.date():
            time_str = reset_local.strftime("%b %-d %-I:%M %p")
        else:
            time_str = reset_local.strftime("%-I:%M %p")

        return f"{relative} ({time_str})", ""
    except Exception:
        return "month end", ""


def fetch_status(config: dict, global_config: dict | None = None) -> ProviderStatus:
    """Fetch Cursor usage status."""
    if global_config:
        _set_thresholds(global_config)

    # Auto-discover token from Cursor's state DB, fall back to config
    access_token = config.get("session_token", "") or _read_access_token()
    membership = _read_membership_type()

    if not access_token:
        return ProviderStatus(
            name="Cursor",
            short_name=DISPLAY_NAME,
            summary="--",
            error="Not logged in to Cursor IDE.",
        )

    metrics: list[MetricData] = []
    worst_color = "green"
    summary = ""
    error = None
    plan_label = membership.title() if membership else ""

    # Fetch profile for accurate plan info
    try:
        profile = _fetch_profile(access_token)
        plan_label = (profile.get("membershipType") or membership or "").title()
    except Exception:
        pass

    try:
        usage = _fetch_usage(access_token)
        logger.info(f"Cursor usage response: {usage}")

        start_period = usage.get("startOfMonth", "")

        # Response format: {"gpt-4": {"numRequests": N, "maxRequestUsage": M, ...}, "startOfMonth": "..."}
        # Aggregate across all models
        total_used = 0
        total_max = 0
        for key, val in usage.items():
            if not isinstance(val, dict):
                continue
            total_used += val.get("numRequests", 0) or 0
            mx = val.get("maxRequestUsage")
            if mx:
                total_max += mx

        if total_max > 0:
            pct = total_used / total_max * 100
            # Forecast based on days elapsed in billing period
            now = datetime.utcnow()
            try:
                period_start = datetime.fromisoformat(start_period.replace("Z", ""))
                days_elapsed = max((now - period_start).days, 1)
            except Exception:
                days_elapsed = now.day
            elapsed_active = _estimate_active_hours(days_elapsed * 24, _WORKING_HOURS)
            remaining_active = _estimate_active_hours((30 - days_elapsed) * 24, _WORKING_HOURS)
            if elapsed_active > 0:
                rate = pct / elapsed_active
                projected = pct + rate * remaining_active
            else:
                projected = pct
            fc_color = _pct_color(projected)
            worst_color = _worst(worst_color, fc_color)

            reset_label, _ = _parse_reset_period(start_period) if start_period else ("month end", "")

            metrics.append(
                MetricData(
                    label="Premium Requests",
                    short_label="Req",
                    pct=pct,
                    forecast_pct=projected,
                    color=fc_color,
                    reset_label=reset_label,
                    extra=f"{total_used} / {total_max} requests",
                )
            )
            summary = f"{pct:.0f}%"
        else:
            # Enterprise/unlimited — no cap, show request count as info metric
            total_reqs = sum(
                v.get("numRequests", 0) or 0
                for v in usage.values() if isinstance(v, dict)
            )
            reset_label, _ = _parse_reset_period(start_period) if start_period else ("month end", "")
            metrics.append(
                MetricData(
                    label="Requests",
                    short_label="∞",
                    pct=-1,  # signals unlimited — no bar/forecast to render
                    forecast_pct=-1,
                    color="green",
                    reset_label=reset_label,
                    extra=f"{total_reqs} requests this period · Unlimited",
                )
            )
            summary = f"{total_reqs} reqs"

    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            error = "Access token expired. Re-login to Cursor IDE."
        else:
            error = f"Cursor API error: {e.code}"
        summary = "err"
    except Exception as e:
        error = f"Cursor API: {e}"
        summary = "err"

    return ProviderStatus(
        name="Cursor",
        short_name=DISPLAY_NAME,
        summary=summary or "--",
        color=_to_bar_color(worst_color),
        error=error,
        metrics=metrics,
        plan_label=plan_label,
    )
