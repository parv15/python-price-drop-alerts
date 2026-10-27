"""Small formatting helpers shared by the views and the charts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

from ..state import money

SYMBOLS = {
    "GBP": "£", "USD": "$", "EUR": "€", "INR": "₹", "JPY": "¥", "CNY": "¥",
    "AUD": "A$", "CAD": "C$", "NZD": "NZ$", "CHF": "CHF ", "SEK": "kr ", "NOK": "kr ", "DKK": "kr ",
}

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, TS_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def fmt_money(price: Decimal | None, currency: str | None = None, *, decimals: int = 2) -> str:
    if price is None:
        return "–"
    quantum = Decimal(1).scaleb(-decimals)
    text = f"{price.quantize(quantum, rounding=ROUND_HALF_UP):,}" if decimals != 2 else f"{money(price):,}"
    symbol = SYMBOLS.get(currency or "")
    if symbol is not None:
        return f"{symbol}{text}"
    return f"{currency} {text}" if currency else text


def fmt_delta(value: Decimal, currency: str | None) -> str:
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}{fmt_money(abs(value), currency)}"


def fmt_percent(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral_value():
        rounded = rounded.quantize(Decimal("1"))
    return f"{abs(rounded)}%"


def fmt_date(moment: datetime) -> str:
    return f"{moment.day} {moment.strftime('%b %Y')}"


def fmt_datetime(moment: datetime) -> str:
    return f"{moment.day} {moment.strftime('%b %Y, %H:%M')} UTC"


def ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "never"
    seconds = int((now - moment).total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 45:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return fmt_date(moment)


def domain(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host.removeprefix("www.")
