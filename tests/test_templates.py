from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from price_alerts.models import Item
from price_alerts.rules import Alert
from price_alerts.templates import build_alert_email, drop_from_last, drop_from_target

NOW = datetime(2026, 10, 14, 6, 17, tzinfo=UTC)
ITEM = Item(name="Example Headphones", url="https://shop.example/h", target_price=D("200"))


def alert(price, old=None, kind="price_below", target="200"):
    return Alert(kind=kind, price=D(price), old_price=None if old is None else D(old), currency="EUR",
                 target_price=D(target), in_stock=True)


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        ("199.00", "0.5% (1.00 EUR below the 200.00 EUR target)"),
        ("150.00", "25% (50.00 EUR below the 200.00 EUR target)"),
        ("200.00", "0% (exactly at the 200.00 EUR target)"),
        ("199.99", "<0.1% (0.01 EUR below the 200.00 EUR target)"),
        ("210.00", "none: 5% above the 200.00 EUR target"),
    ],
)
def test_drop_from_target(price, expected):
    assert drop_from_target(alert(price)) == expected


@pytest.mark.parametrize(
    ("old", "price", "expected"),
    [
        ("249.00", "199.00", "20.1% (249.00 EUR → 199.00 EUR)"),
        (None, "199.00", "n/a (first check)"),
        ("199.00", "199.00", "0% (unchanged at 199.00 EUR)"),
        ("190.00", "199.50", "none: up 5% (190.00 EUR → 199.50 EUR)"),
    ],
)
def test_drop_from_last(old, price, expected):
    assert drop_from_last(alert(price, old)) == expected


def test_price_alert_email_on_first_check():
    msg = build_alert_email(ITEM, alert("150.00"), ["me@example.com"], NOW)
    assert msg.subject == "Price alert: Example Headphones is 150.00, 25% below target 200.00"
    assert "Example Headphones is 25% below your target price" in msg.text
    assert "Drop from last price: n/a (first check)" in msg.text


def test_price_alert_email_at_target():
    msg = build_alert_email(ITEM, alert("200.00", "230.00"), ["me@example.com"], NOW)
    assert msg.subject == "Price drop: Example Headphones 230.00 → 200.00 (-13%), at target 200.00"


def test_back_in_stock_email_shows_both_drops():
    msg = build_alert_email(ITEM, alert("190.00", "220.00", kind="back_in_stock"), ["me@example.com"], NOW)
    assert msg.subject == "Back in stock: Example Headphones"
    assert "Drop from target: 5% (10.00 EUR below the 200.00 EUR target)" in msg.text
    assert "Drop from last price: 13.6% (220.00 EUR → 190.00 EUR)" in msg.text
    assert "Drop from target" in msg.html and "Drop from last price" in msg.html
