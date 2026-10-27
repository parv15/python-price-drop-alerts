"""A made-up product for the /demo page, so the graph can be seen before real history exists.

Nothing here is read from or written to watchlist.yaml, state.json or history.csv.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from ..history import HistoryRow
from ..models import Item
from .format import TS_FORMAT
from .model import ItemView, Point

# (days ago, price): rises and falls around a target in the middle of the range
SERIES = [(58, "189.00"), (52, "176.00"), (46, "198.00"), (40, "184.00"), (34, "168.00"), (28, "176.00"),
          (22, "192.00"), (17, "181.00"), (11, "163.00"), (6, "158.00"), (3, "172.00"), (1, "166.00")]
TARGET = Decimal("170.00")


def demo_view(now: datetime) -> ItemView:
    item = Item(name="Sample: wireless headphones", url="https://shop.example.com/sample",
                target_price=TARGET, notify_on=["price_below", "back_in_stock"])
    moments = [(now - timedelta(days=days)).replace(hour=10, minute=8, second=0, microsecond=0) for days, _ in SERIES]
    points = [Point(moment, Decimal(price)) for moment, (_, price) in zip(moments, SERIES)]
    rows = [HistoryRow(moment.strftime(TS_FORMAT), item.id, item.name, point.price, "USD", True, "json-ld")
            for moment, point in zip(moments, points)]
    return ItemView(item=item, currency="USD", price=points[-1].price, in_stock=True, last_checked=now - timedelta(hours=3),
                    failures=0, last_error=None, points=points, rows=rows)
