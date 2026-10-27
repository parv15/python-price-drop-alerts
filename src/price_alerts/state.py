"""data/state.json: what we last saw and which alerts were already sent, per item id."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

_TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Normalize a price so 199, 199.0 and 199.00 are stored identically ("199.00")."""
    normalized = value.normalize()
    if normalized.as_tuple().exponent >= -2:
        return value.quantize(_TWO_PLACES)
    return normalized


@dataclass(frozen=True)
class ItemState:
    last_price: Decimal | None = None
    last_currency: str | None = None
    last_in_stock: bool | None = None
    # Time of the last check that changed anything for this item. Not bumped on
    # every run on purpose: unchanged runs must leave state.json byte-identical.
    last_checked: str | None = None
    consecutive_failures: int = 0
    error_alert_sent: bool = False
    last_error: str | None = None
    price_below_active: bool = False

    def updated(self, **changes: Any) -> ItemState:
        return replace(self, **changes)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        if data["last_price"] is not None:
            data["last_price"] = str(money(data["last_price"]))
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ItemState:
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        if values.get("last_price") is not None:
            values["last_price"] = money(Decimal(str(values["last_price"])))
        return cls(**values)


@dataclass
class State:
    items: dict[str, ItemState] = field(default_factory=dict)
    last_digest_date: str | None = None

    def get(self, item_id: str) -> ItemState:
        return self.items.get(item_id, ItemState())

    def to_json(self) -> dict[str, Any]:
        return {
            "items": {key: value.to_json() for key, value in self.items.items()},
            "last_digest_date": self.last_digest_date,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> State:
        items = {key: ItemState.from_json(value) for key, value in (data.get("items") or {}).items()}
        return cls(items=items, last_digest_date=data.get("last_digest_date"))


def load_state(path: Path) -> State:
    if not path.is_file():
        return State()
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return State()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    return State.from_json(data if isinstance(data, dict) else {})


def dump_state(state: State) -> str:
    return json.dumps(state.to_json(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def save_state(path: Path, state: State) -> bool:
    """Atomically write state.json. Returns False (and doesn't touch the file) if unchanged."""
    content = dump_state(state)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return True
