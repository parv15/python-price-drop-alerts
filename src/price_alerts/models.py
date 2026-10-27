"""Data models: watchlist config (validated with pydantic), fetch results and emails."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NotifyKind = Literal["price_below", "back_in_stock"]
AlertKind = Literal["price_below", "back_in_stock", "watcher_error"]
Source = Literal["json-ld", "selector"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def slugify(name: str) -> str:
    """Stable item id used as the key in data/state.json."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "item"


def _check_email(value: str) -> str:
    value = value.strip()
    if not _EMAIL_RE.match(value):
        raise ValueError(f"'{value}' is not a valid email address")
    return value


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_email: str
    from_name: str = "Price Alerts"
    default_recipients: list[str] = Field(default_factory=list)
    request_delay_seconds: float = Field(default=5, ge=0)
    timeout_seconds: float = Field(default=20, gt=0)
    respect_robots_txt: bool = True
    digest: bool = False

    @field_validator("from_email")
    @classmethod
    def _from_email(cls, value: str) -> str:
        return _check_email(value)

    @field_validator("default_recipients")
    @classmethod
    def _recipients(cls, value: list[str]) -> list[str]:
        return [_check_email(v) for v in value]


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    url: str
    selector: str | None = None
    stock_selector: str | None = None
    out_of_stock_text: list[str] = Field(default_factory=lambda: ["out of stock", "sold out"])
    target_price: Decimal | None = Field(default=None, gt=0)
    notify_on: list[NotifyKind] | None = None
    recipients: list[str] | None = None

    @property
    def id(self) -> str:
        return slugify(self.name)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"'{value}' must be an http(s) URL")
        return value

    @field_validator("recipients")
    @classmethod
    def _recipients(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else [_check_email(v) for v in value]

    @model_validator(mode="after")
    def _rules(self) -> Item:
        if self.notify_on is None:
            # Sensible default: a price alert if there's a target, plus stock alerts.
            self.notify_on = ["price_below", "back_in_stock"] if self.target_price is not None else ["back_in_stock"]
        if not self.notify_on:
            raise ValueError("notify_on: must list at least one of price_below, back_in_stock")
        self.notify_on = list(dict.fromkeys(self.notify_on))
        if "price_below" in self.notify_on and self.target_price is None:
            raise ValueError("target_price: required when notify_on includes price_below")
        return self


class Watchlist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: Settings
    items: list[Item] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_and_addressable(self) -> Watchlist:
        seen: dict[str, str] = {}
        for item in self.items:
            if item.id in seen:
                raise ValueError(
                    f"item names must be unique: '{item.name}' clashes with '{seen[item.id]}' "
                    f"(both become id '{item.id}')"
                )
            seen[item.id] = item.name
            if not (item.recipients or self.settings.default_recipients):
                raise ValueError(
                    f"item '{item.name}': recipients: no recipients and settings.default_recipients is empty"
                )
        return self

    def recipients_for(self, item: Item) -> list[str]:
        return item.recipients or self.settings.default_recipients

    def digest_recipients(self) -> list[str]:
        if self.settings.default_recipients:
            return self.settings.default_recipients
        return list(dict.fromkeys(r for item in self.items for r in self.recipients_for(item)))


@dataclass(frozen=True)
class FetchResult:
    """Outcome of fetching + extracting one product page."""

    ok: bool
    price: Decimal | None = None
    currency: str | None = None
    in_stock: bool | None = None
    source: Source | None = None
    error: str | None = None

    @classmethod
    def failure(cls, error: str) -> FetchResult:
        return cls(ok=False, error=error)


@dataclass(frozen=True)
class EmailMessage:
    to: list[str]
    subject: str
    text: str
    html: str
    category: str
    item_id: str
    kind: str
