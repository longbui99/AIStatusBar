"""Antigravity IDE provider for AI Status Bar."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import ssl
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from providers import MetricData, ProviderStatus

logger = logging.getLogger(__name__)

PROVIDER_KEY = "antigravity"
DISPLAY_NAME = "AG"
FULL_NAME = "Google Antigravity"

GRPC_PATH = "/exa.language_server_pb.LanguageServerService/GetUserStatus"
CLOUD_API_URL = (
    "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
)
STATE_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Antigravity"
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


# ── Local language server path ────────────────────────────────────────


def _find_language_server() -> tuple[int, str] | None:
    """Find Antigravity language server process.

    Returns (port, csrf_token) or None if not found.
    """
    try:
        result = subprocess.run(
            ["ps", "axo", "pid,command"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if (
                "language_server_macos" not in line
                or "--app_data_dir antigravity" not in line
            ):
                continue

            csrf_match = re.search(r"--csrf_token\s+(\S+)", line)
            if not csrf_match:
                continue
            csrf_token = csrf_match.group(1)
            pid = int(line.strip().split()[0])

            # Find listening port — filter lsof output by PID
            lsof = subprocess.run(
                ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pid_str = str(pid)
            for lsof_line in lsof.stdout.splitlines():
                parts = lsof_line.split()
                if len(parts) >= 2 and parts[1] == pid_str:
                    port_match = re.search(r":(\d+)\s+\(LISTEN\)", lsof_line)
                    if port_match:
                        return int(port_match.group(1)), csrf_token

    except Exception as e:
        logger.error(f"Failed to find Antigravity language server: {e}")
    return None


def _fetch_local(port: int, csrf_token: str) -> dict:
    """Fetch user status from local gRPC-Connect server.

    Returns normalized dict: {plan_name, email, models: [{label, remainingFraction, resetTime}]}
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        f"https://localhost:{port}{GRPC_PATH}",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Codeium-Csrf-Token": csrf_token,
            "Connect-Protocol-Version": "1",
        },
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        data = json.loads(resp.read())

    us = data.get("userStatus", {})
    plan_info = us.get("planStatus", {}).get("planInfo", {})
    models = []
    for m in us.get("cascadeModelConfigData", {}).get("clientModelConfigs", []):
        qi = m.get("quotaInfo", {})
        models.append(
            {
                "label": m.get("label", "Unknown"),
                "remainingFraction": qi.get("remainingFraction"),
                "resetTime": qi.get("resetTime", ""),
            }
        )

    return {
        "plan_name": plan_info.get("planName", ""),
        "email": us.get("email", ""),
        "models": models,
    }


# ── Cloud API fallback path ──────────────────────────────────────────


def _read_auth_from_db() -> dict:
    """Read auth credentials from Antigravity's state DB.

    Returns dict with api_key and email, or empty dict.
    """
    try:
        if not STATE_DB.exists():
            return {}
        conn = sqlite3.connect(str(STATE_DB))
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'antigravityAuthStatus'"
        ).fetchone()
        conn.close()
        if not row:
            return {}
        data = json.loads(row[0])
        return {
            "api_key": data.get("apiKey", ""),
            "email": data.get("email", ""),
            "name": data.get("name", ""),
        }
    except Exception as e:
        logger.error(f"Failed to read Antigravity state DB: {e}")
        return {}


def _read_plan_from_db() -> str:
    """Read plan name from the userStatus protobuf in state DB."""
    try:
        if not STATE_DB.exists():
            return ""
        conn = sqlite3.connect(str(STATE_DB))
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.userStatus'"
        ).fetchone()
        conn.close()
        if not row:
            return ""
        # The userStatusProtoBinaryBase64 in antigravityAuthStatus is easier
        # but planName is also in the JSON authStatus
        return ""
    except Exception:
        return ""


def _fetch_cloud(api_key: str) -> list[dict]:
    """Fetch model quota from Antigravity cloud API.

    Returns list of {label, remainingFraction, resetTime}.
    """
    req = urllib.request.Request(
        CLOUD_API_URL,
        data=b"{}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity-cockpit/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    models = []
    for key, info in data.get("models", {}).items():
        qi = info.get("quotaInfo", {})
        remaining = qi.get("remainingFraction")
        reset_time = qi.get("resetTime", "")
        if remaining is None and not reset_time:
            continue  # Skip models with no quota info at all
        # Skip internal/non-user-facing models (tab completion, chat variants)
        display = info.get("displayName", key)
        if key.startswith("tab_") or key.startswith("chat_"):
            continue
        models.append(
            {
                "label": info.get("displayName", key),
                "remainingFraction": remaining,
                "resetTime": reset_time,
            }
        )

    return models


# ── Shared rendering ─────────────────────────────────────────────────


def _parse_reset(iso_str: str) -> str:
    """Parse ISO reset time to relative + absolute label."""
    try:
        clean = iso_str.replace("+00:00", "").replace("Z", "")
        reset_utc = datetime.fromisoformat(clean)
        now = datetime.utcnow()
        delta = reset_utc - now
        total_min = int(delta.total_seconds() / 60)

        reset_aware = reset_utc.replace(tzinfo=timezone.utc)
        reset_local = reset_aware.astimezone()
        now_local = datetime.now().astimezone()

        if total_min < 0:
            return "now"
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

        return f"{relative} ({time_str})"
    except Exception:
        return iso_str


def _forecast_pct(pct_used: float, resets_at: str) -> float:
    """Project usage at end of reset window using linear extrapolation."""
    try:
        clean = resets_at.replace("+00:00", "").replace("Z", "")
        reset_dt = datetime.fromisoformat(clean)
        now = datetime.utcnow()
        remaining_secs = (reset_dt - now).total_seconds()
        if remaining_secs <= 0:
            return pct_used
        # Antigravity doesn't expose window start, so estimate from reset intervals:
        # Most models reset weekly (168h), Flash resets weekly too
        # Use 7 days as default window
        total_secs = 7 * 24 * 3600
        elapsed_secs = total_secs - remaining_secs
        if elapsed_secs <= 0:
            return pct_used

        elapsed_h = elapsed_secs / 3600
        remaining_h = remaining_secs / 3600
        active_elapsed = _estimate_active_hours(elapsed_h, _WORKING_HOURS)
        active_remaining = _estimate_active_hours(remaining_h, _WORKING_HOURS)
        if active_elapsed <= 0:
            return pct_used
        rate = pct_used / active_elapsed
        return pct_used + rate * active_remaining
    except Exception:
        return pct_used


def _forecast_color(pct_used: float, resets_at: str) -> str:
    """Return color based on forecasted usage at reset."""
    return _pct_color(_forecast_pct(pct_used, resets_at))


# Models to show in the quick bar (not detail_only)
_BAR_MODELS = {"gemini-3.1-pro", "gemini-3-flash", "gemini 3.1 pro", "gemini 3 flash"}


def _short_label(label: str) -> str:
    """Generate a distinct short label for the menu bar."""
    lower = label.lower()
    if "pro" in lower and "high" in lower:
        return "Pro+"
    if "pro" in lower and "low" in lower:
        return "Pro"
    if "flash" in lower:
        return "Flash"
    if "opus" in lower:
        return "Opus"
    if "sonnet" in lower:
        return "Son"
    if "gpt" in lower:
        return "GPT"
    return label.split()[0][:4]


def _is_bar_model(label: str) -> bool:
    """Check if model should appear in the top menu bar."""
    lower = label.lower()
    return "gemini 3.1 pro" in lower or "gemini 3 flash" in lower


def _build_metrics(models: list[dict], email: str) -> tuple[list[MetricData], str, str]:
    """Build metrics from model list.

    Returns (metrics, summary, worst_color).
    """
    metrics: list[MetricData] = []
    worst_color = "green"
    bar_parts = []

    for m in models:
        label = m.get("label", "Unknown")
        remaining = m.get("remainingFraction")
        reset_time = m.get("resetTime", "")

        if remaining is None:
            pct_used = 100.0
        else:
            pct_used = (1.0 - float(remaining)) * 100

        reset_label = _parse_reset(reset_time) if reset_time else "unknown"
        short = _short_label(label)

        # Forecast and color based on projected usage at reset
        if reset_time and remaining is not None:
            fp = _forecast_pct(pct_used, reset_time)
            fc_color = _forecast_color(pct_used, reset_time)
        else:
            fp = pct_used
            fc_color = _pct_color(pct_used)

        worst_color = _worst(worst_color, fc_color)
        extra = (
            f"{remaining * 100:.0f}% remaining" if remaining is not None else "depleted"
        )

        show_in_bar = _is_bar_model(label)

        metrics.append(
            MetricData(
                label=label,
                short_label=short,
                pct=pct_used,
                forecast_pct=fp,
                color=fc_color,
                reset_label=reset_label,
                extra=extra,
                detail_only=not show_in_bar,
            )
        )
        if remaining is not None and show_in_bar:
            bar_parts.append(f"{short}:{pct_used:.0f}%")

    summary = " ".join(bar_parts[:3]) if bar_parts else "OK"

    # Append email to last metric
    if email and metrics:
        last = metrics[-1]
        metrics[-1] = MetricData(
            label=last.label,
            short_label=last.short_label,
            pct=last.pct,
            forecast_pct=last.forecast_pct,
            color=last.color,
            reset_label=last.reset_label,
            extra=f"{last.extra} · {email}",
            detail_only=last.detail_only,
        )

    return metrics, summary, worst_color


# ── Main entry point ─────────────────────────────────────────────────


def fetch_status(config: dict, global_config: dict | None = None) -> ProviderStatus:
    """Fetch Antigravity usage status.

    Tries local language server first (fast, no auth), then falls back
    to cloud API using OAuth token from state DB (works when IDE is closed).
    """
    if global_config:
        _set_thresholds(global_config)

    plan_label = ""
    email = ""
    models: list[dict] = []
    error = None

    # Path 1: Local language server (Antigravity is running)
    server = _find_language_server()
    if server:
        try:
            port, csrf_token = server
            result = _fetch_local(port, csrf_token)
            plan_label = result["plan_name"]
            email = result["email"]
            models = result["models"]
            logger.info(f"Antigravity local: {len(models)} models, plan={plan_label}")
        except Exception as e:
            logger.warning(f"Local fetch failed, trying cloud: {e}")
            server = None  # fall through to cloud path

    # Path 2: Cloud API fallback (Antigravity is closed)
    if not server or not models:
        auth = _read_auth_from_db()
        api_key = auth.get("api_key", "")
        if api_key:
            email = email or auth.get("email", "")
            try:
                models = _fetch_cloud(api_key)
                logger.info(f"Antigravity cloud: {len(models)} models")
            except Exception as e:
                error = f"Antigravity API: {e}"
                logger.error(f"Antigravity cloud fetch error: {e}", exc_info=True)
        elif not models:
            return ProviderStatus(
                name="Antigravity",
                short_name=DISPLAY_NAME,
                summary="--",
                error="Not logged in to Antigravity",
            )

    if error and not models:
        return ProviderStatus(
            name="Antigravity",
            short_name=DISPLAY_NAME,
            summary="err",
            error=error,
        )

    metrics, summary, worst_color = _build_metrics(models, email)

    return ProviderStatus(
        name="Antigravity",
        short_name=DISPLAY_NAME,
        summary=summary or "--",
        color=_to_bar_color(worst_color),
        error=error,
        metrics=metrics,
        plan_label=plan_label,
    )
