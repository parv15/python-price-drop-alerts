"""Alert rules. Pure functions: (item, previous state, fetch result) -> new state + alerts.

Every alert fires once when its condition *becomes* true and stays quiet until the
condition resets. The state change that marks an alert as sent lives in
`Alert.on_sent` and is only applied after the email went out, so a failed send is
retried on the next run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .models import AlertKind, FetchResult, Item
from .state import ItemState, money

FAILURE_THRESHOLD = 3


@dataclass(frozen=True)
class Alert:
    kind: AlertKind
    price: Decimal | None = None
    old_price: Decimal | None = None
    currency: str | None = None
    target_price: Decimal | None = None
    in_stock: bool | None = None
    error: str | None = None
    failures: int = 0
    on_sent: dict[str, Any] = field(default_factory=dict)

    @property
    def change_percent(self) -> Decimal | None:
        """Change from the last checked price, in percent (negative = cheaper)."""
        if self.price is None or not self.old_price:
            return None
        return (self.price - self.old_price) / self.old_price * 100

    @property
    def target_percent(self) -> Decimal | None:
        """Price relative to the target, in percent (negative = below target)."""
        if self.price is None or not self.target_price:
            return None
        return (self.price - self.target_price) / self.target_price * 100


@dataclass(frozen=True)
class Evaluation:
    state: ItemState
    alerts: list[Alert]


def evaluate(item: Item, prev: ItemState, result: FetchResult) -> Evaluation:
    if not result.ok:
        return _evaluate_failure(prev, result)

    alerts: list[Alert] = []
    changes: dict[str, Any] = {
        "consecutive_failures": 0,
        "error_alert_sent": False,
        "last_error": None,
    }
    currency = result.currency or prev.last_currency
    in_stock = result.in_stock if result.in_stock is not None else prev.last_in_stock

    if result.price is not None:
        price = money(result.price)
        changes["last_price"] = price
        changes["last_currency"] = currency

        if "price_below" in item.notify_on and item.target_price is not None:
            alert, reset = check_price_below(price, item.target_price, prev.price_below_active)
            if alert:
                alerts.append(Alert(
                    kind="price_below", price=price, old_price=prev.last_price, currency=currency,
                    target_price=item.target_price, in_stock=in_stock,
                    on_sent={"price_below_active": True},
                ))
            elif reset:
                changes["price_below_active"] = False


    if result.in_stock is not None:
        if "back_in_stock" in item.notify_on and check_back_in_stock(result.in_stock, prev.last_in_stock):
            # last_in_stock stays False until the email is sent, so a failed send retries.
            alerts.append(Alert(
                kind="back_in_stock", price=changes.get("last_price", prev.last_price),
                old_price=prev.last_price, currency=currency, target_price=item.target_price, in_stock=True,
                on_sent={"last_in_stock": True},
            ))
        else:
            changes["last_in_stock"] = result.in_stock

    return Evaluation(prev.updated(**changes), alerts)


def _evaluate_failure(prev: ItemState, result: FetchResult) -> Evaluation:
    # Keep the last known price/stock untouched; only count the failure.
    failures = prev.consecutive_failures + 1
    state = prev.updated(consecutive_failures=failures, last_error=result.error)
    alerts = []
    if failures >= FAILURE_THRESHOLD and not prev.error_alert_sent:
        alerts.append(Alert(
            kind="watcher_error", price=prev.last_price, currency=prev.last_currency,
            error=result.error, failures=failures, on_sent={"error_alert_sent": True},
        ))
    return Evaluation(state, alerts)


def check_price_below(price: Decimal, target: Decimal, active: bool) -> tuple[bool, bool]:
    """Returns (fire, reset). Fires once when price <= target; resets when price > target."""
    if price <= target:
        return (not active, False)
    return (False, active)


def check_back_in_stock(in_stock: bool, last_in_stock: bool | None) -> bool:
    """Only an observed False -> True transition counts (not first sight, not None -> True)."""
    return in_stock is True and last_in_stock is False


def apply_sent(state: ItemState, alert: Alert) -> ItemState:
    return state.updated(**alert.on_sent)
