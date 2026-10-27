"""Server-rendered SVG charts: a tiny sparkline for the cards and the full price graph.

Prices only change at the moments recorded in data/history.csv, so both charts are step
charts: the price holds until the next recorded change and the last price runs on to "now".
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from decimal import Decimal
from html import escape

from .format import fmt_datetime, fmt_money
from .model import Point

ACCENT = "#3a6b4d"
GREEN = "#2f7d4f"
TARGET = "#2563a8"
RED = "#b42318"
GRID = "#e4e8e3"
MUTED = "#68756c"

RANGES = {"7d": 7, "30d": 30, "90d": 90, "all": None}


def _num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def window(points: list[Point], now: datetime, range_key: str) -> list[Point]:
    """The points inside a range, starting with the price that was already in force at its start."""
    days = RANGES.get(range_key)
    if days is None or not points:
        return list(points)
    cutoff = now - timedelta(days=days)
    before = [p for p in points if p.when <= cutoff]
    inside = [p for p in points if p.when > cutoff]
    return ([Point(cutoff, before[-1].price)] if before else []) + inside


def _nice_step(span: float, parts: int) -> float:
    raw = span / parts
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _y_axis(values: list[Decimal]) -> tuple[float, float, list[float]]:
    lo, hi = float(min(values)), float(max(values))
    pad = (hi - lo) * 0.18 if hi > lo else max(hi * 0.08, 1.0)
    ylo, yhi = max(0.0, lo - pad), hi + pad
    step = _nice_step(yhi - ylo, 4)
    first = math.ceil(ylo / step) * step
    ticks = []
    value = first
    while value <= yhi + 1e-9:
        ticks.append(round(value, 6))
        value += step
    return ylo, yhi, ticks


def _x_labels(start: datetime, end: datetime, count: int = 5) -> list[tuple[datetime, str]]:
    span = end - start
    out = []
    for i in range(count):
        moment = start + span * (i / (count - 1))
        if span <= timedelta(days=2):
            label = moment.strftime("%H:%M")
        elif span <= timedelta(days=120):
            label = f"{moment.day} {moment.strftime('%b')}"
        else:
            label = moment.strftime("%b %Y")
        out.append((moment, label))
    return out


def _step_path(coords: list[tuple[float, float]], x_end: float) -> str:
    x, y = coords[0]
    parts = [f"M{_num(x)} {_num(y)}"]
    for nx, ny in coords[1:]:
        parts.append(f"H{_num(nx)} V{_num(ny)}")
    parts.append(f"H{_num(x_end)}")
    return " ".join(parts)


def sparkline(points: list[Point], now: datetime, *, width: int = 132, height: int = 40) -> str:
    """A tiny trend line. Green when the price fell since the first point, red when it rose."""
    pad = 4
    if not points:
        y = height / 2
        return (f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
                f'aria-hidden="true"><path d="M{pad} {y} H{width - pad}" stroke="{GRID}" stroke-width="2" '
                f'stroke-dasharray="3 4" fill="none"/></svg>')
    prices = [float(p.price) for p in points]
    lo, hi = min(prices), max(prices)
    t0, t1 = points[0].when, max(now, points[-1].when)
    if t1 - t0 < timedelta(days=1):
        t1 = t0 + timedelta(days=1)

    def x(moment: datetime) -> float:
        return pad + (width - 2 * pad) * ((moment - t0).total_seconds() / (t1 - t0).total_seconds())

    def y(price: float) -> float:
        if hi == lo:
            return height / 2
        return height - pad - (height - 2 * pad) * ((price - lo) / (hi - lo))

    coords = [(x(p.when), y(float(p.price))) for p in points]
    color = GREEN if prices[-1] < prices[0] else RED if prices[-1] > prices[0] else MUTED
    path = _step_path(coords, width - pad)
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{_num(width - pad)}" cy="{_num(coords[-1][1])}" r="3.2" fill="{color}"/></svg>')


def price_chart(points: list[Point], now: datetime, *, currency: str | None, target: Decimal | None,
                name: str, range_key: str = "all") -> str:
    """The full graph: grid, price steps with tooltips, a dashed target line and axis labels."""
    width, height = 760, 320
    left, right, top, bottom = 68, 28, 20, 38
    shown = window(points, now, range_key)

    if not shown:
        return (f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
                f'aria-label="No prices recorded yet for {escape(name)}">'
                f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="#fcfcfa" stroke="{GRID}"/>'
                f'<text x="{width / 2}" y="{height / 2 - 4}" text-anchor="middle" font-size="16" font-weight="600" '
                f'fill="#1d3226">No price recorded yet</text>'
                f'<text x="{width / 2}" y="{height / 2 + 20}" text-anchor="middle" font-size="13.5" fill="{MUTED}">'
                f'Run a check to start the graph.</text></svg>')

    values = [p.price for p in shown] + ([target] if target is not None else [])
    ylo, yhi, ticks = _y_axis(values)
    t0, t1 = shown[0].when, max(now, shown[-1].when)
    if t1 - t0 < timedelta(days=1):
        t1 = t0 + timedelta(days=1)  # a young series: start at the left edge and run a flat line across
    plot_w, plot_h = width - left - right, height - top - bottom

    def x(moment: datetime) -> float:
        return left + plot_w * ((moment - t0).total_seconds() / (t1 - t0).total_seconds())

    def y(price: float) -> float:
        return top + plot_h * (1 - (price - ylo) / (yhi - ylo))

    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1
    decimals = 0 if step >= 1 and all(abs(t - round(t)) < 1e-9 for t in ticks) else 2

    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Price history of {escape(name)}: {len(shown)} recorded price'
           f'{"s" if len(shown) != 1 else ""}, now {escape(fmt_money(shown[-1].price, currency))}">',
           '<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{ACCENT}" stop-opacity=".16"/>'
           f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient></defs>']

    for tick in ticks:
        ty = y(tick)
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{_num(ty)}" y2="{_num(ty)}" stroke="{GRID}"/>')
        out.append(f'<text x="{left - 10}" y="{_num(ty + 4)}" text-anchor="end" font-size="12" fill="{MUTED}">'
                   f'{escape(fmt_money(Decimal(str(tick)), currency, decimals=decimals))}</text>')
    for moment, label in _x_labels(t0, t1):
        if moment > max(now, shown[-1].when) + timedelta(minutes=1):
            continue  # never label a time that hasn't happened yet
        tx = x(moment)
        anchor = "start" if tx < left + 8 else "end" if tx > width - right - 8 else "middle"
        out.append(f'<text x="{_num(tx)}" y="{height - 12}" text-anchor="{anchor}" font-size="12" fill="{MUTED}">{escape(label)}</text>')

    coords = [(x(p.when), y(float(p.price))) for p in shown]
    line = _step_path(coords, x(t1))
    base = top + plot_h
    out.append(f'<path d="{line} V{_num(base)} H{_num(coords[0][0])} Z" fill="url(#area)"/>')

    if target is not None:
        ty = y(float(target))
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{_num(ty)}" y2="{_num(ty)}" stroke="{TARGET}" '
                   f'stroke-width="1.6" stroke-dasharray="6 5"/>')
        label_y = ty - 7 if ty - top > 18 else ty + 16
        out.append(f'<text x="{left + 8}" y="{_num(label_y)}" text-anchor="start" font-size="12" font-weight="600" '
                   f'fill="{TARGET}">Target {escape(fmt_money(target, currency))}</text>')

    out.append(f'<path d="{line}" fill="none" stroke="{ACCENT}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>')

    last = len(shown) - 1
    for i, (p, (cx, cy)) in enumerate(zip(shown, coords)):
        hit = target is not None and p.price <= target
        stroke = GREEN if hit else ACCENT
        fill = stroke if (i == last or hit) else "#fff"  # solid when it is the latest price or at/below the target
        radius = 5.5 if i == last else 4
        out.append(f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2.2">'
                   f'<title>{escape(fmt_money(p.price, currency))} · {escape(fmt_datetime(p.when))}</title></circle>')

    out.append('</svg>')
    return "".join(out)
