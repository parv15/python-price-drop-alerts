from decimal import Decimal

import pytest

from price_alerts.parse_price import parse_price


@pytest.mark.parametrize(
    ("text", "amount", "currency"),
    [
        ("1.299,00 €", "1299.00", "EUR"),
        ("$1,299.99", "1299.99", "USD"),
        ("1 299,00 zł", "1299.00", "PLN"),
        ("1 299,00 zł", "1299.00", "PLN"),
        ("₹1,29,999", "129999", "INR"),
        ("£12.50", "12.50", "GBP"),
        ("12,50 €", "12.50", "EUR"),
        ("1,299", "1299", None),
        ("EUR 49", "49", "EUR"),
        ("Rs. 2,499.00", "2499.00", "INR"),
        ("49.99 USD", "49.99", "USD"),
        ("CHF 1'299.50", "1299.50", "CHF"),
        ("  Now only $5  ", "5", "USD"),
        ("0.999", "0.999", None),
        ("1.299.999 Kč", "1299999", "CZK"),
        ("US$ 19.99", "19.99", "USD"),
    ],
)
def test_parses_formats(text, amount, currency):
    parsed = parse_price(text)
    assert parsed is not None
    assert parsed.amount == Decimal(amount)
    assert parsed.currency == currency


@pytest.mark.parametrize("text", ["", "   ", None, "Call for price", "N/A", "€", "free shipping"])
def test_garbage_returns_none(text):
    assert parse_price(text) is None
