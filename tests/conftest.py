"""Shared test doubles: a fake fetcher (no network), a fake mailer and a fixed clock."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from price_alerts.fetch import FetchError
from price_alerts.mailer import MailerError
from price_alerts.models import EmailMessage, Watchlist

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def product_page(price: str | None, availability: str | None = "InStock", currency: str = "EUR") -> str:
    """A minimal page with schema.org Product JSON-LD."""
    offer: dict[str, Any] = {"@type": "Offer", "priceCurrency": currency}
    if price is not None:
        offer["price"] = price
    if availability is not None:
        offer["availability"] = f"https://schema.org/{availability}"
    data = {"@context": "https://schema.org", "@type": "Product", "name": "Thing", "offers": offer}
    return f'<html><head><script type="application/ld+json">{json.dumps(data)}</script></head><body></body></html>'


class FakeFetcher:
    """Maps URL -> HTML string, or an Exception instance to raise."""

    def __init__(self, pages: dict[str, str | Exception] | None = None) -> None:
        self.pages: dict[str, str | Exception] = dict(pages or {})
        self.calls: list[str] = []

    def get(self, url: str) -> str:
        self.calls.append(url)
        page = self.pages.get(url)
        if page is None:
            raise FetchError(f"HTTP 404 from {url}")
        if isinstance(page, Exception):
            raise page
        return page


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail = False

    def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise MailerError("APIError: simulated outage")
        self.sent.append(message)


class FixedClock:
    def __init__(self, start: datetime = datetime(2026, 10, 14, 6, 17, tzinfo=UTC)) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


def make_watchlist(*items: dict[str, Any], **settings: Any) -> Watchlist:
    base = {
        "from_email": "alerts@example.com",
        "default_recipients": ["me@example.com"],
        "request_delay_seconds": 0,
    }
    base.update(settings)
    return Watchlist.model_validate({"settings": base, "items": list(items)})


@pytest.fixture
def fetcher() -> FakeFetcher:
    return FakeFetcher()


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    (path / "state.json").write_text("{}\n", encoding="utf-8")
    (path / "history.csv").write_text("timestamp,item_id,name,price,currency,in_stock,source\n", encoding="utf-8")
    return path
