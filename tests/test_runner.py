import json
from pathlib import Path

import pytest

from price_alerts.config import ConfigError
from price_alerts.fetch import FetchError
from price_alerts.runner import run
from price_alerts.templates import CATEGORIES

from .conftest import fixture_html, make_watchlist, product_page

URL = "https://shop.example/headphones"
URL2 = "https://shop.example/kettle"


def headphones(**kwargs):
    data = {
        "name": "Example Headphones",
        "url": URL,
        "target_price": 200,
        "notify_on": ["price_below", "back_in_stock"],
    }
    data.update(kwargs)
    return data


def go(watchlist, data_dir, fetcher, mailer, clock, **kwargs):
    return run(watchlist, data_dir=data_dir, fetcher=fetcher, mailer=mailer, clock=clock,
               out_dir=data_dir.parent / "out", **kwargs)


def snapshot(data_dir: Path) -> tuple[bytes, bytes]:
    return (data_dir / "state.json").read_bytes(), (data_dir / "history.csv").read_bytes()


def test_acceptance_unchanged_prices_send_nothing_and_change_nothing(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(), {"name": "Kettle", "url": URL2, "notify_on": ["back_in_stock"]})
    fetcher.pages = {URL: product_page("249.00"), URL2: fixture_html("jsonld_out_of_stock.html")}

    first = go(wl, data_dir, fetcher, mailer, clock)
    assert first.ok == 2 and first.alerts_sent == 0  # first run only records baselines
    before = snapshot(data_dir)
    history_lines = before[1].decode().splitlines()
    assert len(history_lines) == 3  # header + one row per item

    clock.advance(hours=6)
    second = go(wl, data_dir, fetcher, mailer, clock)
    assert second.alerts_sent == 0
    assert mailer.sent == []
    assert snapshot(data_dir) == before


def test_price_below_dedup_across_runs(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["price_below"]))
    prices = ["249.00", "199.00", "199.00", "189.00", "249.00", "199.00"]
    sent_per_run = []
    for price in prices:
        fetcher.pages[URL] = product_page(price)
        before = len(mailer.sent)
        go(wl, data_dir, fetcher, mailer, clock)
        sent_per_run.append(len(mailer.sent) - before)
        clock.advance(hours=6)
    assert sent_per_run == [0, 1, 0, 0, 0, 1]
    assert mailer.sent[0].subject == (
        "Price drop: Example Headphones 249.00 → 199.00 (-20.1%), 0.5% below target 200.00"
    )
    assert "Drop from target: 0.5% (1.00 EUR below the 200.00 EUR target)" in mailer.sent[0].text
    assert "Drop from last price: 20.1% (249.00 EUR → 199.00 EUR)" in mailer.sent[0].text


def test_back_in_stock_email(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["back_in_stock"]))
    for availability in ("OutOfStock", "OutOfStock", "InStock", "InStock"):
        fetcher.pages[URL] = product_page("249.00", availability)
        go(wl, data_dir, fetcher, mailer, clock)
    assert [m.subject for m in mailer.sent] == ["Back in stock: Example Headphones"]
    assert mailer.sent[0].category == "stock-alert"


def test_failure_counter_and_single_watcher_error(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones())
    fetcher.pages[URL] = product_page("249.00")
    go(wl, data_dir, fetcher, mailer, clock)

    fetcher.pages[URL] = FetchError("HTTP 503 from shop")
    counts = []
    for _ in range(4):
        before = len(mailer.sent)
        summary = go(wl, data_dir, fetcher, mailer, clock)
        counts.append(len(mailer.sent) - before)
        assert summary.failed == 1 and summary.exit_code == 0
    assert counts == [0, 0, 1, 0]
    err = mailer.sent[0]
    assert err.category == "watcher-error"
    assert "HTTP 503" in err.text and URL in err.text and "selector" in err.text

    state = json.loads((data_dir / "state.json").read_text())["items"]["example-headphones"]
    assert state["last_price"] == "249.00"  # untouched by failures
    assert state["consecutive_failures"] == 4 and state["error_alert_sent"] is True

    fetcher.pages[URL] = product_page("249.00")
    go(wl, data_dir, fetcher, mailer, clock)
    state = json.loads((data_dir / "state.json").read_text())["items"]["example-headphones"]
    assert state["consecutive_failures"] == 0 and state["error_alert_sent"] is False


def test_every_email_has_the_right_category(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(
        headphones(),
        {"name": "Broken", "url": URL2, "notify_on": ["back_in_stock"]},
    )
    fetcher.pages = {URL: product_page("300.00", "OutOfStock")}
    for _ in range(3):  # Broken fails 3 times -> watcher-error
        go(wl, data_dir, fetcher, mailer, clock)
    fetcher.pages[URL] = product_page("180.00", "InStock")  # price_below + back_in_stock
    go(wl, data_dir, fetcher, mailer, clock, digest=True)

    by_kind = {m.kind: m.category for m in mailer.sent}
    assert by_kind == {
        "watcher_error": "watcher-error",
        "price_below": "price-alert",
        "back_in_stock": "stock-alert",
        "digest": "digest",
    }
    assert all(m.category == CATEGORIES[m.kind] for m in mailer.sent)
    assert all(m.to == ["me@example.com"] for m in mailer.sent)


def test_emails_escape_values(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(name="<b>Evil</b> & Co", notify_on=["price_below"]))
    fetcher.pages[URL] = product_page("150.00")
    go(wl, data_dir, fetcher, mailer, clock)
    html = mailer.sent[0].html
    assert "<b>Evil</b>" not in html and "&lt;b&gt;Evil&lt;/b&gt; &amp; Co" in html


def test_dry_run_sends_nothing_writes_previews_and_keeps_data(data_dir, fetcher, clock):
    wl = make_watchlist(headphones(notify_on=["price_below"]))
    fetcher.pages[URL] = product_page("150.00")
    before = snapshot(data_dir)

    summary = go(wl, data_dir, fetcher, None, clock, dry_run=True)

    assert summary.alerts_would_send == 1 and summary.alerts_sent == 0
    assert snapshot(data_dir) == before
    previews = list((data_dir.parent / "out").glob("*.html"))
    assert [p.name for p in previews] == ["20261014T061700Z_example-headphones_price_below.html"]
    assert "Example Headphones" in previews[0].read_text()


def test_send_failure_is_retried_next_run(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["price_below"]), {"name": "Kettle", "url": URL2,
                                                                 "target_price": 100,
                                                                 "notify_on": ["price_below"]})
    fetcher.pages = {URL: product_page("150.00"), URL2: product_page("50.00")}
    mailer.fail = True
    summary = go(wl, data_dir, fetcher, mailer, clock)
    assert summary.send_failures == 2 and summary.exit_code == 2 and summary.checked == 2
    state = json.loads((data_dir / "state.json").read_text())["items"]
    assert state["example-headphones"]["price_below_active"] is False

    mailer.fail = False
    summary = go(wl, data_dir, fetcher, mailer, clock)
    assert summary.alerts_sent == 2 and summary.exit_code == 0
    summary = go(wl, data_dir, fetcher, mailer, clock)
    assert summary.alerts_sent == 0


def test_digest_once_per_day(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["back_in_stock"]))
    fetcher.pages[URL] = product_page("249.00")
    go(wl, data_dir, fetcher, mailer, clock, digest=True)
    clock.advance(hours=6)
    go(wl, data_dir, fetcher, mailer, clock, digest=True)
    assert [m.kind for m in mailer.sent] == ["digest"]

    clock.advance(hours=18)  # next UTC day
    fetcher.pages[URL] = product_page("229.00")
    go(wl, data_dir, fetcher, mailer, clock, digest=True)
    assert [m.kind for m in mailer.sent] == ["digest", "digest"]
    assert "-20.00 (-8%)" in mailer.sent[1].text


def test_digest_disabled_sends_nothing(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["back_in_stock"]))
    fetcher.pages[URL] = product_page("249.00")
    go(wl, data_dir, fetcher, mailer, clock, digest=False)
    assert mailer.sent == []


def test_history_only_appends_on_change(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["back_in_stock"]))
    for price in ("249.00", "249", "249.00", "239.00"):
        fetcher.pages[URL] = product_page(price)
        go(wl, data_dir, fetcher, mailer, clock)
        clock.advance(hours=6)
    lines = (data_dir / "history.csv").read_text().splitlines()
    assert lines[1:] == [
        "2026-10-14T06:17:00Z,example-headphones,Example Headphones,249.00,EUR,true,json-ld",
        "2026-10-15T00:17:00Z,example-headphones,Example Headphones,239.00,EUR,true,json-ld",
    ]


def test_only_filter(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(), {"name": "Kettle", "url": URL2, "notify_on": ["back_in_stock"]})
    fetcher.pages = {URL: product_page("249.00"), URL2: product_page("20.00")}
    summary = go(wl, data_dir, fetcher, mailer, clock, only="kettle")
    assert summary.checked == 1 and fetcher.calls == [URL2]
    with pytest.raises(ConfigError, match="matches no item"):
        go(wl, data_dir, fetcher, mailer, clock, only="nope")


def test_one_broken_item_does_not_stop_others(data_dir, fetcher, mailer, clock):
    wl = make_watchlist(headphones(notify_on=["price_below"]), {"name": "Kettle", "url": URL2,
                                                                 "notify_on": ["back_in_stock"]})
    fetcher.pages = {URL: product_page("150.00"), URL2: RuntimeError("weird")}
    summary = go(wl, data_dir, fetcher, mailer, clock)
    assert (summary.ok, summary.failed, summary.alerts_sent) == (1, 1, 1)
