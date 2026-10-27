"""Orchestration: fetch every item, evaluate rules, send emails, persist state and history.

Fetcher, mailer and clock are injected so tests run without network or real email.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .config import ConfigError
from .extract import extract
from .fetch import Fetcher, FetchError
from .history import (
    HistoryRow,
    append_history,
    has_changed,
    last_rows,
    price_at,
    read_history,
)
from .mailer import Mailer
from .models import EmailMessage, FetchResult, Item, Watchlist
from .rules import apply_sent, evaluate
from .state import State, load_state, save_state
from .templates import DigestRow, build_alert_email, build_digest_email

log = logging.getLogger(__name__)

Clock = Callable[[], datetime]

STATE_FILE = "state.json"
HISTORY_FILE = "history.csv"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RunSummary:
    dry_run: bool = False
    checked: int = 0
    ok: int = 0
    failed: int = 0
    alerts_sent: int = 0
    alerts_would_send: int = 0
    send_failures: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    saved_files: list[Path] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 2 if self.send_failures else 0

    def format(self) -> str:
        lines = [
            "",
            "Summary" + (" (dry run: nothing sent, data/ untouched)" if self.dry_run else ""),
            f"  Items checked: {self.checked}",
            f"  OK:            {self.ok}",
            f"  Failed:        {self.failed}",
        ]
        if self.dry_run:
            lines.append(f"  Alerts that would be sent: {self.alerts_would_send}")
            if self.saved_files:
                lines.append(f"  Email previews: {self.saved_files[0].parent}/")
        else:
            lines.append(f"  Alerts sent:   {self.alerts_sent}")
            if self.send_failures:
                lines.append(f"  Send failures: {self.send_failures} (will retry next run)")
        for name, error in self.errors:
            lines.append(f"  ! {name}: {error}")
        return "\n".join(lines)


def run(
    watchlist: Watchlist,
    *,
    data_dir: Path,
    fetcher: Fetcher,
    mailer: Mailer | None,
    clock: Clock = utc_now,
    dry_run: bool = False,
    out_dir: Path = Path("out"),
    only: str | None = None,
    digest: bool = False,
) -> RunSummary:
    if mailer is None and not dry_run:
        raise ValueError("a mailer is required unless dry_run=True")

    now = clock().astimezone(UTC).replace(microsecond=0)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path, history_path = data_dir / STATE_FILE, data_dir / HISTORY_FILE
    try:
        state = load_state(state_path)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    history = read_history(history_path)
    latest = last_rows(history)
    new_rows: list[HistoryRow] = []

    summary = RunSummary(dry_run=dry_run)
    items = _select(watchlist.items, only)

    def deliver(message: EmailMessage) -> bool:
        if dry_run:
            path = _save_preview(out_dir, now, message)
            summary.saved_files.append(path)
            summary.alerts_would_send += 1
            log.info("[dry-run] WOULD SEND %-13s to %s: %s -> %s",
                     message.category, ", ".join(message.to), message.subject, path)
            return True
        try:
            mailer.send(message)
        except Exception as exc:
            summary.send_failures += 1
            log.error("Sending %s email for %s failed: %s", message.category, message.item_id, exc)
            return False
        summary.alerts_sent += 1
        log.info("Sent %s email to %s: %s", message.category, ", ".join(message.to), message.subject)
        return True

    for item in items:
        summary.checked += 1
        prev = state.get(item.id)
        result = _check(fetcher, item)
        if result.ok:
            summary.ok += 1
            log.info("%s: %s, %s (via %s)", item.name, _price_text(result), _stock_text(result.in_stock),
                     result.source)
        else:
            summary.failed += 1
            summary.errors.append((item.name, result.error or "unknown error"))
            log.warning("%s: FAILED (%d in a row): %s", item.name, prev.consecutive_failures + 1, result.error)

        evaluation = evaluate(item, prev, result)
        new_state = evaluation.state
        for alert in evaluation.alerts:
            message = build_alert_email(item, alert, watchlist.recipients_for(item), now)
            if deliver(message):
                new_state = apply_sent(new_state, alert)

        if new_state != prev:
            new_state = new_state.updated(last_checked=now_iso)
        state.items[item.id] = new_state

        if result.ok and has_changed(latest.get(item.id), result.price, result.in_stock):
            row = HistoryRow(now_iso, item.id, item.name, result.price, result.currency,
                             result.in_stock, result.source)
            new_rows.append(row)
            latest[item.id] = row

    if only is None:
        # Forget items that were removed from the watchlist.
        ids = {item.id for item in watchlist.items}
        state.items = {key: value for key, value in state.items.items() if key in ids}

    today = now.strftime("%Y-%m-%d")
    if digest and state.last_digest_date != today:
        message = build_digest_email(
            _digest_rows(watchlist, state, history + new_rows, now), watchlist.digest_recipients(), now
        )
        if deliver(message):
            state.last_digest_date = today

    if not dry_run:
        save_state(state_path, state)
        append_history(history_path, new_rows)
    return summary


def _select(items: list[Item], only: str | None) -> list[Item]:
    if only is None:
        return items
    wanted = only.strip().lower()
    selected = [item for item in items if item.name.lower() == wanted or item.id == wanted]
    if not selected:
        names = ", ".join(f"'{item.name}'" for item in items)
        raise ConfigError(f"--only '{only}' matches no item. Items: {names}")
    return selected


def _check(fetcher: Fetcher, item: Item) -> FetchResult:
    try:
        html = fetcher.get(item.url)
    except FetchError as exc:
        return FetchResult.failure(str(exc))
    except Exception as exc:  # never let one item break the whole run
        log.exception("Unexpected error fetching %s", item.url)
        return FetchResult.failure(f"Unexpected error: {type(exc).__name__}: {exc}")
    try:
        return extract(html, item)
    except Exception as exc:
        log.exception("Unexpected error parsing %s", item.url)
        return FetchResult.failure(f"Could not parse page: {type(exc).__name__}: {exc}")


def _digest_rows(watchlist: Watchlist, state: State, history: list[HistoryRow], now: datetime) -> list[DigestRow]:
    rows = []
    yesterday = now - timedelta(days=1)
    for item in watchlist.items:
        s = state.get(item.id)
        before = price_at(history, item.id, yesterday)
        change = s.last_price - before if (s.last_price is not None and before is not None) else None
        if s.consecutive_failures:
            status = f"failing ({s.consecutive_failures}x): {s.last_error or 'unknown error'}"
        elif s.last_checked is None:
            status = "not checked yet"
        else:
            status = "ok"
        rows.append(DigestRow(item.name, item.url, s.last_price, s.last_currency, change, s.last_in_stock, status))
    return rows


def _save_preview(out_dir: Path, now: datetime, message: EmailMessage) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{stamp}_{message.item_id}_{message.kind}.html"
    path.write_text(message.html, encoding="utf-8")
    return path


def _price_text(result: FetchResult) -> str:
    if result.price is None:
        return "no price"
    return f"{result.price} {result.currency or ''}".strip()


def _stock_text(in_stock: bool | None) -> str:
    return {True: "in stock", False: "out of stock"}.get(in_stock, "stock unknown")
