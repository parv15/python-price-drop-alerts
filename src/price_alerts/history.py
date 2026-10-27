"""data/history.csv: one row per observed change in price or stock (not one per run)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .state import money

HEADER = ["timestamp", "item_id", "name", "price", "currency", "in_stock", "source"]


@dataclass(frozen=True)
class HistoryRow:
    timestamp: str
    item_id: str
    name: str
    price: Decimal | None
    currency: str | None
    in_stock: bool | None
    source: str | None

    def to_csv(self) -> list[str]:
        return [
            self.timestamp,
            self.item_id,
            self.name,
            "" if self.price is None else str(money(self.price)),
            self.currency or "",
            "" if self.in_stock is None else str(self.in_stock).lower(),
            self.source or "",
        ]

    @classmethod
    def from_csv(cls, row: dict[str, str]) -> HistoryRow:
        try:
            price = Decimal(row["price"]) if row.get("price") else None
        except InvalidOperation:
            price = None
        stock = (row.get("in_stock") or "").lower()
        return cls(
            timestamp=row.get("timestamp", ""),
            item_id=row.get("item_id", ""),
            name=row.get("name", ""),
            price=price,
            currency=row.get("currency") or None,
            in_stock=True if stock == "true" else False if stock == "false" else None,
            source=row.get("source") or None,
        )


def read_history(path: Path) -> list[HistoryRow]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [HistoryRow.from_csv(row) for row in csv.DictReader(handle)]


def last_rows(rows: list[HistoryRow]) -> dict[str, HistoryRow]:
    latest: dict[str, HistoryRow] = {}
    for row in rows:
        latest[row.item_id] = row
    return latest


def has_changed(last: HistoryRow | None, price: Decimal | None, in_stock: bool | None) -> bool:
    """A new row is only worth writing if a known value differs from the last row."""
    if last is None:
        return price is not None or in_stock is not None
    if price is not None and (last.price is None or money(price) != money(last.price)):
        return True
    return in_stock is not None and in_stock != last.in_stock


def price_at(rows: list[HistoryRow], item_id: str, moment: datetime) -> Decimal | None:
    """Last known price for an item at or before `moment` (rows are in time order)."""
    cutoff = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    price = None
    for row in rows:
        if row.item_id == item_id and row.timestamp <= cutoff and row.price is not None:
            price = row.price
    return price


def append_history(path: Path, rows: list[HistoryRow]) -> None:
    if not rows:
        return
    new_file = not path.is_file() or path.stat().st_size == 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if new_file:
            writer.writerow(HEADER)
        writer.writerows(row.to_csv() for row in rows)
