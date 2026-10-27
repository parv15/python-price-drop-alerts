"""Email content: a plain-text and a simple inline-styled HTML version of every email."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from html import escape

from .models import EmailMessage, Item
from .rules import Alert
from .state import money

CATEGORIES = {
    "price_below": "price-alert",
    "back_in_stock": "stock-alert",
    "watcher_error": "watcher-error",
    "digest": "digest",
}

_FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


@dataclass(frozen=True)
class DigestRow:
    name: str
    url: str
    price: Decimal | None
    currency: str | None
    change: Decimal | None  # absolute change since 24h ago
    in_stock: bool | None
    status: str


def fmt_price(price: Decimal | None, currency: str | None = None) -> str:
    if price is None:
        return "n/a"
    text = f"{money(price):,}"
    return f"{text} {currency}" if currency else text


def fmt_percent(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral_value():
        rounded = rounded.quantize(Decimal("1"))
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded}%"


def fmt_stock(in_stock: bool | None) -> str:
    return {True: "In stock", False: "Out of stock"}.get(in_stock, "Unknown")


def fmt_time(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M UTC")


def build_alert_email(item: Item, alert: Alert, recipients: list[str], now: datetime) -> EmailMessage:
    subject, headline, facts = _alert_content(item, alert)
    facts.append(("Checked", fmt_time(now)))

    text_lines = [headline, ""]
    text_lines += [f"{label}: {value}" for label, value in facts]
    text_lines += ["", f"Product page: {item.url}"]
    if alert.kind == "watcher_error":
        text_lines += ["", _ERROR_HINT]
    text_lines += ["", _FOOTER]

    rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#6b7280">{escape(label)}</td>'
        f'<td style="padding:4px 0;font-weight:600">{escape(value)}</td></tr>'
        for label, value in facts
    )
    hint = (
        f'<p style="margin:16px 0;color:#92400e">{escape(_ERROR_HINT)}</p>'
        if alert.kind == "watcher_error" else ""
    )
    body = (
        f'<h1 style="font-size:20px;margin:0 0 16px">{escape(headline)}</h1>'
        f'<table style="border-collapse:collapse;font-size:15px">{rows}</table>'
        f"{hint}"
        f'<p style="margin:20px 0"><a href="{escape(item.url, quote=True)}" '
        f'style="background:#2563eb;color:#ffffff;padding:10px 16px;border-radius:6px;'
        f'text-decoration:none;display:inline-block">Open product page</a></p>'
    )
    return EmailMessage(
        to=list(recipients),
        subject=subject,
        text="\n".join(text_lines) + "\n",
        html=_wrap(subject, body),
        category=CATEGORIES[alert.kind],
        item_id=item.id,
        kind=alert.kind,
    )


def _unsigned(value: Decimal) -> str:
    text = fmt_percent(abs(value)).lstrip("+")
    # 51.77 vs a 51.78 target is 0.02%: say "<0.1%" rather than a misleading "0%".
    return "<0.1%" if text == "0%" and value != 0 else text


def drop_from_target(alert: Alert) -> str:
    """E.g. "0.5% (1.00 EUR below the 200.00 EUR target)"."""
    cur, pct = alert.currency, alert.target_percent
    target = fmt_price(alert.target_price, cur)
    diff = alert.price - alert.target_price
    if diff == 0:
        return f"0% (exactly at the {target} target)"
    if diff < 0:
        return f"{_unsigned(pct)} ({fmt_price(-diff, cur)} below the {target} target)"
    return f"none: {_unsigned(pct)} above the {target} target"


def drop_from_last(alert: Alert) -> str:
    """E.g. "20.1% (249.00 EUR → 199.00 EUR)"."""
    cur = alert.currency
    if alert.old_price is None:
        return "n/a (first check)"
    if alert.old_price == alert.price:
        return f"0% (unchanged at {fmt_price(alert.price, cur)})"
    moved = f"({fmt_price(alert.old_price, cur)} → {fmt_price(alert.price, cur)})"
    if alert.price < alert.old_price:
        return f"{_unsigned(alert.change_percent)} {moved}"
    return f"none: up {_unsigned(alert.change_percent)} {moved}"


def _price_facts(alert: Alert) -> list[tuple[str, str]]:
    facts = [("Price", fmt_price(alert.price, alert.currency))]
    if alert.target_price is not None:
        facts.append(("Target price", fmt_price(alert.target_price, alert.currency)))
        facts.append(("Drop from target", drop_from_target(alert)))
    facts.append(("Drop from last price", drop_from_last(alert)))
    return facts


def _alert_content(item: Item, alert: Alert) -> tuple[str, str, list[tuple[str, str]]]:
    name, cur = item.name, alert.currency
    facts: list[tuple[str, str]] = [("Product", name)]

    if alert.kind == "price_below":
        new, target = fmt_price(alert.price), fmt_price(alert.target_price)
        at_target = alert.price == alert.target_price
        vs_target = f"at target {target}" if at_target else f"{_unsigned(alert.target_percent)} below target {target}"
        if alert.old_price is not None and alert.price < alert.old_price:
            subject = (f"Price drop: {name} {fmt_price(alert.old_price)} → {new} "
                       f"({fmt_percent(alert.change_percent)}), {vs_target}")
        else:
            subject = f"Price alert: {name} is {new}, {vs_target}"
        headline = (f"{name} is at your target price" if at_target
                    else f"{name} is {_unsigned(alert.target_percent)} below your target price")
        facts += _price_facts(alert)
        facts.append(("Stock", fmt_stock(alert.in_stock)))
        return subject, headline, facts

    if alert.kind == "back_in_stock":
        facts.append(("Stock", "In stock"))
        if alert.price is not None:
            facts += _price_facts(alert)
        return f"Back in stock: {name}", f"{name} is back in stock", facts

    # watcher_error
    facts += [
        ("URL", item.url),
        ("Failed checks in a row", str(alert.failures)),
        ("Last error", alert.error or "unknown"),
    ]
    if alert.price is not None:
        facts.append(("Last known price", fmt_price(alert.price, cur)))
    return f"Watcher error: {name} failed {alert.failures} checks in a row", f"Can't check {name}", facts


def build_digest_email(rows: list[DigestRow], recipients: list[str], now: datetime) -> EmailMessage:
    day = now.strftime("%Y-%m-%d")
    subject = f"Price digest {day}: {len(rows)} item{'s' if len(rows) != 1 else ''}"

    def change_text(row: DigestRow) -> str:
        if row.change is None or row.price is None:
            return "–"
        if row.change == 0:
            return "no change"
        old = row.price - row.change
        pct = fmt_percent(row.change / old * 100) if old else ""
        sign = "+" if row.change > 0 else "-"
        return f"{sign}{fmt_price(abs(row.change))} ({pct})"

    text_lines = [f"Daily price digest for {day}", ""]
    for row in rows:
        text_lines.append(
            f"- {row.name}: {fmt_price(row.price, row.currency)} | change 24h: {change_text(row)} | "
            f"{fmt_stock(row.in_stock)} | {row.status}"
        )
        text_lines.append(f"  {row.url}")
    text_lines += ["", _FOOTER]

    th = 'style="text-align:left;padding:8px;border-bottom:2px solid #e5e7eb;font-size:13px;color:#6b7280"'
    td = 'style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:14px;vertical-align:top"'
    body_rows = "".join(
        f"<tr><td {td}><a href=\"{escape(row.url, quote=True)}\" style=\"color:#2563eb\">{escape(row.name)}</a></td>"
        f"<td {td}>{escape(fmt_price(row.price, row.currency))}</td>"
        f"<td {td}>{escape(change_text(row))}</td>"
        f"<td {td}>{escape(fmt_stock(row.in_stock))}</td>"
        f"<td {td}>{escape(row.status)}</td></tr>"
        for row in rows
    )
    body = (
        f'<h1 style="font-size:20px;margin:0 0 16px">Daily price digest for {escape(day)}</h1>'
        f'<table style="border-collapse:collapse;width:100%"><thead><tr>'
        f"<th {th}>Item</th><th {th}>Price</th><th {th}>Change (24h)</th>"
        f"<th {th}>Stock</th><th {th}>Status</th></tr></thead><tbody>{body_rows}</tbody></table>"
    )
    return EmailMessage(
        to=list(recipients),
        subject=subject,
        text="\n".join(text_lines) + "\n",
        html=_wrap(subject, body),
        category=CATEGORIES["digest"],
        item_id="digest",
        kind="digest",
    )


_ERROR_HINT = (
    "Check that the URL still opens the product page in a browser, and if the site "
    "changed its layout, update the item's CSS 'selector' in watchlist.yaml. You'll get "
    "this email once; checks continue and the warning resets after the next success."
)
_FOOTER = "Sent by python-price-drop-alerts. Edit watchlist.yaml to change what you're watching."


def _wrap(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{escape(title)}</title></head>"
        f'<body style="margin:0;padding:24px;background:#f3f4f6;{_FONT};color:#111827">'
        '<div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:8px;padding:24px">'
        f"{body}"
        f'<p style="margin:24px 0 0;font-size:12px;color:#9ca3af">{escape(_FOOTER)}</p>'
        "</div></body></html>"
    )
