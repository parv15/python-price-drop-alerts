"""Turn human-written price text ("1.299,00 €", "$1,299.99", "₹1,29,999") into a Decimal."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import NamedTuple


class ParsedPrice(NamedTuple):
    amount: Decimal
    currency: str | None


# Multi-character markers first so "US$" wins over "$" and "Rs." over nothing.
_SYMBOLS: list[tuple[str, str]] = [
    ("US$", "USD"),
    ("CA$", "CAD"),
    ("C$", "CAD"),
    ("AU$", "AUD"),
    ("A$", "AUD"),
    ("NZ$", "NZD"),
    ("R$", "BRL"),
    ("HK$", "HKD"),
    ("S$", "SGD"),
    ("Rs.", "INR"),
    ("Rs", "INR"),
    ("zł", "PLN"),
    ("Kč", "CZK"),
    ("€", "EUR"),
    ("£", "GBP"),
    ("₹", "INR"),
    ("¥", "JPY"),
    ("₩", "KRW"),
    ("₽", "RUB"),
    ("₺", "TRY"),
    ("₪", "ILS"),
    ("฿", "THB"),
    ("$", "USD"),
]

_ISO_CODES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CNY", "PLN", "CHF", "SEK", "NOK", "DKK",
    "CAD", "AUD", "NZD", "BRL", "MXN", "ZAR", "RUB", "TRY", "KRW", "SGD", "HKD",
    "CZK", "HUF", "RON", "BGN", "AED", "SAR", "ILS", "THB", "IDR", "MYR", "PHP",
    "VND", "UAH", "CLP", "COP", "ARS", "PEN", "TWD",
}

_ISO_RE = re.compile(r"(?<![A-Za-z])([A-Z]{3})(?![A-Za-z])")
# Digit groups joined by single separators: 1.299,00 / 1 299,00 / 1,29,999 / 1'299.00
_NUMBER_RE = re.compile(r"\d+(?:[.,' ’]\d+)*")
_SPACES_RE = re.compile(r"[\s\u00a0\u202f\u2009\u2007]+")


def parse_price(text: str | None) -> ParsedPrice | None:
    """Parse a price string. Returns None when no sensible number is found."""
    if not text:
        return None
    cleaned = _SPACES_RE.sub(" ", str(text)).strip()
    if not cleaned:
        return None

    match = _NUMBER_RE.search(cleaned)
    if not match:
        return None
    amount = _interpret_number(match.group(0))
    if amount is None:
        return None
    return ParsedPrice(amount, _guess_currency(cleaned))


def _guess_currency(text: str) -> str | None:
    for match in _ISO_RE.finditer(text):
        code = match.group(1)
        if code in _ISO_CODES:
            return code
    for symbol, code in _SYMBOLS:
        if symbol in text:
            return code
    return None


def _interpret_number(raw: str) -> Decimal | None:
    # Spaces and apostrophes are only ever thousands separators, and only when a
    # group of exactly three digits follows. Otherwise the number ends there
    # ("12 50" -> 12).
    parts = re.split(r"([ '’])", raw)
    number = parts[0]
    for i in range(1, len(parts) - 1, 2):
        group = parts[i + 1]
        if re.match(r"^\d{3}(?:[.,]|$)", group):
            number += group
        else:
            break

    dots, commas = number.count("."), number.count(",")
    if dots and commas:
        decimal_sep = "." if number.rfind(".") > number.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        integer, _, fraction = number.rpartition(decimal_sep)
        integer = integer.replace(thousands_sep, "")
        if not integer.isdigit() or not fraction.isdigit():
            return None
        normalized = f"{integer}.{fraction}"
    elif dots or commas:
        sep = "." if dots else ","
        integer, _, fraction = number.rpartition(sep)
        if number.count(sep) > 1:
            # 1.299.999 or 1,29,999 -> thousands separators only
            normalized = number.replace(sep, "")
        elif len(fraction) == 3 and integer.lstrip("0"):
            # 1,299 or 1.299 -> thousands. 0.999 stays a decimal.
            normalized = integer + fraction
        else:
            normalized = f"{integer}.{fraction}"
    else:
        normalized = number

    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0:
        return None
    return value
