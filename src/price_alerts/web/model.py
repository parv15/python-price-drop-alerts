"""View models: everything the pages need about each watched product, computed in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from ..history import HistoryRow
from ..models import Item, Watchlist
from ..state import State, money
from .format import domain, fmt_money, parse_ts

# status keys
TARGET, WATCHING, OUT, FAILING, NEW = "target", "watching", "out", "failing", "new"
STATUS_LABELS = {
    TARGET: "At or below target",
    WATCHING: "Watching",
    OUT: "Out of stock",
    FAILING: "Check failing",
    NEW: "Not checked yet",
}


@dataclass(frozen=True)
class Point:
    when: datetime
    price: Decimal


@dataclass
class ItemView:
    item: Item
    currency: str | None
    price: Decimal | None
    in_stock: bool | None
    last_checked: datetime | None
    failures: int
    last_error: str | None
    points: list[Point] = field(default_factory=list)
    rows: list[HistoryRow] = field(default_factory=list)  # oldest first

    @property
    def id(self) -> str:
        return self.item.id

    @property
    def name(self) -> str:
        return self.item.name

    @property
    def url(self) -> str:
        return self.item.url

    @property
    def domain(self) -> str:
        return domain(self.item.url)

    @property
    def target(self) -> Decimal | None:
        return self.item.target_price

    @property
    def status(self) -> str:
        if self.failures:
            return FAILING
        if self.price is None and self.last_checked is None:
            return NEW
        if self.in_stock is False:
            return OUT
        if self.target is not None and self.price is not None and self.price <= self.target:
            return TARGET
        return WATCHING

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]

    @property
    def target_note(self) -> str:
        """How far the current price is from the target, in a few words."""
        if self.price is None:
            return "Waiting for the first check"
        if self.target is None:
            return "No price target set"
        gap = self.price - self.target
        if gap == 0:
            return "Target reached"
        if gap < 0:
            return f"{fmt_money(-gap, self.currency)} below target"
        return f"{fmt_money(gap, self.currency)} above target"

    @property
    def first_price(self) -> Decimal | None:
        return self.points[0].price if self.points else None

    @property
    def low(self) -> Decimal | None:
        return min((p.price for p in self.points), default=None)

    @property
    def high(self) -> Decimal | None:
        return max((p.price for p in self.points), default=None)

    @property
    def change(self) -> Decimal | None:
        """Current price minus the first price ever seen (negative = cheaper)."""
        if self.price is None or self.first_price is None:
            return None
        return money(self.price) - money(self.first_price)

    @property
    def change_percent(self) -> Decimal | None:
        if self.change is None or not self.first_price:
            return None
        return self.change / money(self.first_price) * 100


def build_views(watchlist: Watchlist, state: State, history: list[HistoryRow]) -> list[ItemView]:
    by_item: dict[str, list[HistoryRow]] = {}
    for row in history:
        by_item.setdefault(row.item_id, []).append(row)

    views = []
    for item in watchlist.items:
        s = state.get(item.id)
        rows = sorted(by_item.get(item.id, []), key=lambda r: r.timestamp)
        points = [Point(moment, row.price) for row in rows
                  if row.price is not None and (moment := parse_ts(row.timestamp)) is not None]
        price = s.last_price if s.last_price is not None else (points[-1].price if points else None)
        currency = s.last_currency or next((r.currency for r in reversed(rows) if r.currency), None)
        in_stock = s.last_in_stock
        if in_stock is None:
            in_stock = next((r.in_stock for r in reversed(rows) if r.in_stock is not None), None)
        last_checked = parse_ts(s.last_checked) or (points[-1].when if points else None)
        views.append(ItemView(item, currency, price, in_stock, last_checked,
                              s.consecutive_failures, s.last_error, points, rows))
    return views


@dataclass(frozen=True)
class Stats:
    products: int
    at_target: int
    out_of_stock: int
    failing: int
    last_checked: datetime | None


def build_stats(views: list[ItemView]) -> Stats:
    checked = [v.last_checked for v in views if v.last_checked]
    return Stats(
        products=len(views),
        at_target=sum(1 for v in views if v.status == TARGET),
        out_of_stock=sum(1 for v in views if v.status == OUT),
        failing=sum(1 for v in views if v.status == FAILING),
        last_checked=max(checked) if checked else None,
    )
