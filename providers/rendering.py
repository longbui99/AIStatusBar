"""Rendering engine for AI Status Bar — beautiful SwiftBar output."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass

# ── Color palette (macOS system colors) ──────────────────────────────────────
COLORS = {
    "green": "#34C759",
    "yellow": "#FFD60A",
    "orange": "#FF9500",
    "red": "#FF3B30",
    "blue": "#007AFF",
    "gray": "#8E8E93",
    "dim": "#636366",
    "label": "#AEAEB2",
    "white": "#F5F5F7",
}

# ── SF Symbol helpers ────────────────────────────────────────────────────────

def _sfconfig(colors: list[str], rendering: str = "Palette", weight: str = "medium") -> str:
    """Encode SF Symbol config as base64 for sfconfig= parameter."""
    cfg = {"renderingMode": rendering, "colors": colors, "weight": weight}
    return base64.b64encode(json.dumps(cfg).encode()).decode()


def _color_hex(color: str) -> str:
    """Map status color name to hex."""
    return COLORS.get(color, color)


def _status_symbol(color: str) -> str:
    """Pick an SF Symbol name based on status severity."""
    if color == "red":
        return "exclamationmark.triangle.fill"
    if color == "orange":
        return "flame.fill"
    return "sparkles"


# ── Compact bar for menu bar title ───────────────────────────────────────────

# Defaults — overridden by config.json "progress_bar" section
_BAR_FILLED = "\u25A0"
_BAR_EMPTY = "\u25A1"
_BAR_WIDTH = 4


# Defaults — overridden by config.json "thresholds" section
_THRESHOLDS = {"yellow": 60, "orange": 80, "red": 100}


def configure_bar(cfg: dict) -> None:
    """Load progress bar and threshold settings from config."""
    global _BAR_FILLED, _BAR_EMPTY, _BAR_WIDTH, _THRESHOLDS
    bar_cfg = cfg.get("progress_bar", {})
    if bar_cfg:
        _BAR_FILLED = bar_cfg.get("filled", _BAR_FILLED)
        _BAR_EMPTY = bar_cfg.get("empty", _BAR_EMPTY)
        _BAR_WIDTH = bar_cfg.get("width", _BAR_WIDTH)
    t = cfg.get("thresholds", {})
    if t:
        _THRESHOLDS = {
            "yellow": t.get("yellow", 60),
            "orange": t.get("orange", 80),
            "red": t.get("red", 100),
        }


def _pct_color(pct: float) -> str:
    """Return color based on configured thresholds."""
    if pct >= _THRESHOLDS["red"]:
        return "red"
    if pct >= _THRESHOLDS["orange"]:
        return "orange"
    if pct >= _THRESHOLDS["yellow"]:
        return "yellow"
    return "green"


def _mini_bar(pct: float, width: int | None = None) -> str:
    """A compact progress bar using configurable filled/empty characters."""
    w = width if width is not None else _BAR_WIDTH
    pct = max(0.0, min(100.0, pct))
    filled = round(pct / 100.0 * w)
    return _BAR_FILLED * filled + _BAR_EMPTY * (w - filled)


# ── Menu bar title builders ──────────────────────────────────────────────────

def render_title_cycling(statuses: list) -> list[str]:
    """Generate a single compact title line with all key metrics.

    Format: 5h ▁▂ 7%  7d █▅ 56%  $2.1k/$5k
    """
    if not statuses:
        return ["AI | sfimage=gear color=#FF9500 size=13"]

    lines = []
    for s in statuses:
        worst = s.color or "green"
        hex_c = _color_hex(worst)
        symbol = _status_symbol(worst)
        sf_cfg = _sfconfig([hex_c], weight="semibold")

        if not hasattr(s, "metrics") or not s.metrics:
            lines.append(
                f" {s.summary} | sfimage={symbol} sfconfig={sf_cfg} sfsize=14 "
                f"size=12 font=SF-Mono-Medium"
            )
            continue

        # Single line with non-detail-only metrics, using · as separator
        parts = []
        for m in s.metrics:
            if getattr(m, "detail_only", False):
                continue
            if m.short_label == "$":
                parts.append(f"{m.extra or f'${m.pct:.0f}%'}")
            else:
                bar = _mini_bar(m.pct)
                parts.append(f"{m.short_label} {bar} {m.pct:.0f}%")

        # Anthropic "A" logo as 16x16 template image
        logo = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAAALklEQVR4nGP4z4AfEpDGVAAClCiAAZopgEmhKKGmAnRAngIsbFwhCOcTrQAnBAD5KzbYyX/0zQAAAABJRU5ErkJggg=="
        lines.append(
            f" {' · '.join(parts)} "
            f"| templateImage={logo} "
            f"size=11 font=SF-Mono-Medium color={hex_c}"
        )

    return lines


# ── Dropdown section builders ────────────────────────────────────────────────

@dataclass
class Metric:
    """A single usage metric for structured rendering."""
    label: str
    pct: float
    forecast_pct: float
    color: str
    reset_label: str
    extra: str = ""


@dataclass
class SpendRow:
    """A spend breakdown row."""
    label: str
    amount: str


def _smooth_bar(pct: float, width: int = 20) -> str:
    """Create a smooth gradient progress bar using Unicode blocks."""
    blocks = [" ", "\u258f", "\u258e", "\u258d", "\u258c", "\u258b", "\u258a", "\u2589", "\u2588"]
    pct = max(0.0, min(100.0, pct))
    fill = pct / 100.0 * width
    result = []
    for i in range(width):
        if fill >= i + 1:
            result.append("\u2588")
        elif fill > i:
            frac = fill - i
            idx = int(round(frac * 8))
            result.append(blocks[max(0, min(8, idx))])
        else:
            result.append("\u2005")  # thin space
    return "".join(result)


def _forecast_arrow(forecast_pct: float) -> str:
    """Return a directional indicator based on configured thresholds."""
    if forecast_pct >= _THRESHOLDS["red"]:
        return "\u2191\u2191"  # double up arrow
    if forecast_pct >= _THRESHOLDS["orange"]:
        return "\u2197"   # up-right
    if forecast_pct >= _THRESHOLDS["yellow"]:
        return "\u2192"   # right
    return "\u2192"       # right (safe/low)


def render_metric_section(m: Metric) -> list[str]:
    """Render a single metric as a beautiful dropdown section."""
    lines = []
    hex_c = _color_hex(m.color)

    if m.color == "red":
        header_icon = "exclamationmark.circle.fill"
    elif m.color == "orange":
        header_icon = "chart.line.uptrend.xyaxis"
    else:
        header_icon = "checkmark.circle.fill"

    header_cfg = _sfconfig([hex_c], weight="semibold")
    lines.append(
        f"  {m.label} | sfimage={header_icon} "
        f"sfconfig={header_cfg} sfsize=14 size=13 font=SF-Pro-Text-Semibold"
    )

    bar = _smooth_bar(m.pct)
    lines.append(
        f"  {bar}  {m.pct:5.1f}% | font=SF-Mono-Regular size=12 color={hex_c} trim=false"
    )

    arrow = _forecast_arrow(m.forecast_pct)
    lines.append(
        f"  {arrow} Forecast {m.forecast_pct:.0f}% at reset | "
        f"font=SF-Pro-Text-Regular size=11 color={hex_c}"
    )

    lines.append(
        f"  Resets in {m.reset_label} | "
        f"sfimage=clock size=11 color={COLORS['dim']}"
    )

    if m.extra:
        lines.append(f"  {m.extra} | size=11 color={COLORS['label']}")

    return lines


def render_spend_section(title: str, rows: list[SpendRow], bar_pct: float | None = None,
                         bar_color: str = "green", forecast_line: str = "") -> list[str]:
    """Render a spending section with optional progress bar."""
    lines = []
    hex_c = _color_hex(bar_color)
    cfg = _sfconfig([hex_c], weight="semibold")
    lines.append(
        f"  {title} | sfimage=creditcard.fill "
        f"sfconfig={cfg} sfsize=14 size=13 font=SF-Pro-Text-Semibold"
    )
    if bar_pct is not None:
        bar = _smooth_bar(bar_pct)
        lines.append(
            f"  {bar}  {bar_pct:5.1f}% | font=SF-Mono-Regular size=12 color={hex_c} trim=false"
        )
    if forecast_line:
        lines.append(f"  {forecast_line} | size=11 color={hex_c}")
    for row in rows:
        lines.append(
            f"  {row.label}  {row.amount} | font=SF-Mono-Regular size=12 color={COLORS['white']}"
        )
    return lines


def render_plan_badge(plan_label: str) -> list[str]:
    """Render the subscription plan as a styled footer."""
    cfg = _sfconfig([COLORS["blue"]], weight="medium")
    return [
        f"  {plan_label} | sfimage=person.crop.circle.badge.checkmark "
        f"sfconfig={cfg} size=12 color={COLORS['label']}"
    ]


def render_rate_limit_section(limits_details: list[tuple[str, float, str]]) -> list[str]:
    """Render rate limits section."""
    lines = []
    cfg = _sfconfig([COLORS["blue"]], weight="semibold")
    lines.append(
        f"  Rate Limits | sfimage=gauge.with.dots.needle.33percent "
        f"sfconfig={cfg} sfsize=14 size=13 font=SF-Pro-Text-Semibold"
    )
    for label, pct, text in limits_details:
        hex_c = _color_hex(_pct_color(pct))
        bar = _smooth_bar(pct, 12)
        lines.append(
            f"  {bar} {text} | font=SF-Mono-Regular size=11 color={hex_c} trim=false"
        )
    return lines


def render_separator() -> str:
    return "---"


def render_footer(script_dir: str) -> list[str]:
    return [
        "---",
        f"Open Config | bash=open param1={script_dir}/config.json terminal=false "
        f"sfimage=gearshape size=13 color={COLORS['dim']}",
        f"Refresh | refresh=true sfimage=arrow.clockwise size=13 color={COLORS['dim']}",
    ]
