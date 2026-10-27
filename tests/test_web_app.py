"""The dashboard end to end, without a socket: WebApp.handle() with a fake fetcher and mailer."""

import re
from pathlib import Path

import pytest

from price_alerts.web.app import HeldMailer, Request, WebApp, parse_request

from .conftest import FakeFetcher, FixedClock, product_page

HOST = {"Host": "localhost:8765"}
SHOP = "https://shop.example"

WATCHLIST = """\
# kept as is
settings:
  from_email: alerts@example.com
  default_recipients: [me@example.com]
  request_delay_seconds: 0

items:
  - name: Kettle
    url: https://shop.example/kettle
    target_price: 30.00
    notify_on: [price_below, back_in_stock]
"""


class Env:
    def __init__(self, tmp_path: Path, mailer, can_email=True):
        self.path = tmp_path / "watchlist.yaml"
        self.path.write_text(WATCHLIST, encoding="utf-8")
        self.data = tmp_path / "data"
        self.data.mkdir()
        self.fetcher = FakeFetcher({f"{SHOP}/kettle": product_page("39.00", currency="GBP")})
        self.mailer = mailer
        self.clock = FixedClock()

        class Ctx:  # a context-manager wrapper, like HttpFetcher
            def __init__(ctx, f): ctx.f = f
            def __enter__(ctx): return ctx.f
            def __exit__(ctx, *a): return None

        def mailer_factory(_wl):
            if not can_email:
                from price_alerts.config import ConfigError
                raise ConfigError("no token")
            return mailer

        self.app = WebApp(self.path, self.data, fetcher_factory=lambda wl: Ctx(self.fetcher),
                          mailer_factory=mailer_factory, clock=self.clock, token="tok")

    def get(self, path, **query):
        return self.app.handle(Request("GET", path, {k: [v] for k, v in query.items()}, {}, HOST))

    def post(self, path, **form):
        form.setdefault("csrf", "tok")
        return self.app.handle(Request("POST", path, {}, {k: [v] for k, v in form.items()}, HOST))


@pytest.fixture
def env(tmp_path, mailer):
    return Env(tmp_path, mailer)


def test_dashboard_lists_products_and_the_add_form(env):
    page = env.get("/")
    assert page.status == 200
    for expected in ("Never miss a price drop again", "Kettle", "Not checked yet", 'action="/items/new"', 'name="csrf" value="tok"'):
        assert expected in page.body


def test_adding_a_product_writes_the_yaml_keeps_comments_and_records_the_first_price(env):
    env.fetcher.pages[f"{SHOP}/toaster"] = product_page("19.99", currency="GBP")
    response = env.post("/items/new", name="Toaster", url=f"{SHOP}/toaster", target_price="25",
                        notify_price="on", notify_stock="on")
    assert response.status == 303 and response.headers[0][1].startswith("/item/toaster?ok=")
    text = env.path.read_text(encoding="utf-8")
    assert "# kept as is" in text and "name: Toaster" in text and "target_price: 25.00" in text
    assert env.path.with_name("watchlist.yaml.bak").exists()
    history = (env.data / "history.csv").read_text()
    assert ",toaster,Toaster,19.99,GBP," in history
    assert "£19.99" in env.get("/item/toaster").body


def test_a_price_at_the_target_sends_the_alert_when_adding(env, mailer):
    env.fetcher.pages[f"{SHOP}/toaster"] = product_page("19.99")
    env.post("/items/new", name="Toaster", url=f"{SHOP}/toaster", target_price="25", notify_price="on")
    assert [m.kind for m in mailer.sent] == ["price_below"]


@pytest.mark.parametrize("form, message", [
    ({"name": "", "url": f"{SHOP}/x", "notify_stock": "on"}, "Product name"),
    ({"name": "X", "url": "not a url", "notify_stock": "on"}, "Product page link"),
    ({"name": "X", "url": f"{SHOP}/x", "target_price": "abc", "notify_price": "on"}, "Target price"),
    ({"name": "X", "url": f"{SHOP}/x", "target_price": "-5", "notify_price": "on"}, "Target price"),
    ({"name": "X", "url": f"{SHOP}/x"}, "choose at least one"),
    ({"name": "X", "url": f"{SHOP}/x", "notify_price": "on"}, "target_price"),
    ({"name": "Kettle", "url": f"{SHOP}/x", "notify_stock": "on"}, "unique"),
])
def test_invalid_input_is_explained_and_nothing_is_written(env, form, message):
    before = env.path.read_text(encoding="utf-8")
    response = env.post("/items/new", **form)
    assert response.status == 422 and message in response.body
    assert env.path.read_text(encoding="utf-8") == before


def test_the_form_keeps_what_was_typed_after_an_error(env):
    response = env.post("/items/new", name="Toaster", url="nope", target_price="25", notify_price="on")
    assert 'value="Toaster"' in response.body and 'value="25"' in response.body


def test_item_page_has_the_graph_the_tiles_and_the_history_table(env):
    env.post("/item/kettle/check")
    env.fetcher.pages[f"{SHOP}/kettle"] = product_page("28.00", currency="GBP")
    env.clock.advance(days=3)
    env.post("/item/kettle/check")
    page = env.get("/item/kettle", range="30d").body
    for expected in ('<svg class="chart"', "Target £30.00", "£28.00", "£39.00", "−£11.00", "At or below target",
                     'aria-current="true">30 days'):
        assert expected in page


def test_unknown_product_and_unknown_page_are_404(env):
    assert env.get("/item/nope").status == 404
    assert env.get("/nothing-here").status == 404


def test_check_now_updates_the_history_and_reports_the_price(env):
    response = env.post("/item/kettle/check")
    assert response.status == 303 and "Checked" in response.headers[0][1].replace("%20", " ")
    assert "39.00" in (env.data / "history.csv").read_text()


def test_a_failing_page_is_reported_not_raised(env):
    env.fetcher.pages[f"{SHOP}/kettle"] = Exception("boom")
    response = env.post("/item/kettle/check")
    assert response.headers[0][1].startswith("/item/kettle?warn=")


def test_without_a_token_alerts_are_held_back_but_prices_are_still_recorded(tmp_path, mailer):
    env = Env(tmp_path, mailer, can_email=False)
    env.fetcher.pages[f"{SHOP}/kettle"] = product_page("20.00")
    response = env.post("/item/kettle/check")
    assert "held back" in response.headers[0][1].replace("%20", " ")
    assert mailer.sent == [] and "20.00" in (env.data / "history.csv").read_text()
    assert "price_below_active" in (env.data / "state.json").read_text()
    assert '"price_below_active": false' in (env.data / "state.json").read_text()  # so the real run still alerts


def test_held_mailer_refuses_every_message():
    from price_alerts.mailer import MailerError
    with pytest.raises(MailerError):
        HeldMailer().send(None)


def test_the_form_has_no_advanced_fields(env):
    body = env.get("/").body
    assert "Advanced" not in body and 'name="selector"' not in body and 'name="recipients"' not in body


def test_editing_keeps_selectors_and_recipients_that_are_not_on_the_form(env):
    env.path.write_text(WATCHLIST.replace("    notify_on: [price_below, back_in_stock]",
                                          '    selector: ".price"\n    stock_selector: ".stock"\n    recipients: [other@example.com]\n    notify_on: [price_below, back_in_stock]'),
                        encoding="utf-8")
    env.post("/item/kettle/edit", url=f"{SHOP}/kettle", target_price="22", notify_price="on", notify_stock="on")
    text = env.path.read_text(encoding="utf-8")
    assert 'selector: ".price"' in text and 'stock_selector: ".stock"' in text and 'recipients: ["other@example.com"]' in text
    assert "target_price: 22.00" in text


def test_edit_changes_the_target_but_not_the_name(env):
    assert 'name="name" value="Kettle"' in env.get("/item/kettle/edit").body
    response = env.post("/item/kettle/edit", name="Hacked", url=f"{SHOP}/kettle", target_price="22.5", notify_price="on")
    assert response.status == 303
    text = env.path.read_text(encoding="utf-8")
    assert "name: Kettle" in text and "Hacked" not in text and "target_price: 22.50" in text and "# kept as is" in text


def test_remove_deletes_the_block_but_the_last_product_stays(env):
    env.fetcher.pages[f"{SHOP}/toaster"] = product_page("5")
    env.post("/items/new", name="Toaster", url=f"{SHOP}/toaster", notify_stock="on")
    assert env.post("/item/toaster/delete").headers[0][1].startswith("/?ok=")
    assert "Toaster" not in env.path.read_text(encoding="utf-8")
    blocked = env.post("/item/kettle/delete")
    assert blocked.headers[0][1].startswith("/item/kettle?err=") and "name: Kettle" in env.path.read_text(encoding="utf-8")


def test_every_post_needs_the_csrf_token(env):
    before = env.path.read_text(encoding="utf-8")
    assert env.post("/item/kettle/delete", csrf="wrong").status == 403
    assert env.post("/items/new", csrf="", name="X", url=f"{SHOP}/x", notify_stock="on").status == 403
    assert env.path.read_text(encoding="utf-8") == before


def test_other_hosts_are_refused(env):
    assert env.app.handle(Request("GET", "/", {}, {}, {"Host": "evil.example"})).status == 403
    assert env.app.handle(Request("GET", "/", {}, {}, {"Host": "127.0.0.1:8765"})).status == 200
    assert env.app.handle(Request("GET", "/", {}, {}, {"Host": "[::1]:8765"})).status == 200


def test_security_headers_and_escaping(env, tmp_path):
    response = env.get("/")
    headers = dict(response.headers)
    assert "script-src 'nonce-" in headers["Content-Security-Policy"] and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY" and headers["Cache-Control"] == "no-store"
    nonce = headers["Content-Security-Policy"].split("'nonce-")[1].split("'")[0]
    assert f'<script nonce="{nonce}">' in response.body
    assert "<b>x</b>" not in env.post("/items/new", name="<b>x</b>", url="nope", notify_stock="on").body


def test_flash_messages_are_escaped(env):
    assert "<script>" not in env.get("/", ok="<script>alert(1)</script>").body


def test_a_broken_watchlist_shows_a_helpful_page(env):
    env.path.write_text("items: []\n", encoding="utf-8")
    page = env.get("/")
    assert page.status == 500 and "watchlist" in page.body.lower()


def test_only_get_and_post(env):
    assert env.app.handle(Request("DELETE", "/", {}, {}, HOST)).status == 405


def test_parse_request_reads_query_and_form():
    req = parse_request("POST", "/x?a=1", {"Host": "h"}, b"name=Kettle&csrf=t")
    assert req.query == {"a": ["1"]} and req.form == {"name": ["Kettle"], "csrf": ["t"]}


def test_demo_page_shows_a_full_up_and_down_graph_with_the_target_in_the_middle(env):
    page = env.get("/demo")
    assert page.status == 200
    body = page.body
    chart = re.search(r'<svg class="chart".*?</svg>', body, re.S).group(0)
    assert "Demo data" in body and "This is sample data" in body and "Sample: wireless headphones" in body
    assert '<svg class="chart"' in body and "Target $170.00" in body
    assert chart.count("<circle") == 12                     # every sample price is a marker
    assert chart.count('fill="#2f7d4f"') >= 3               # prices at or below the target are solid green
    assert chart.count('fill="#fff"') >= 3                  # prices above it are hollow
    assert "$198.00" in body and "$158.00" in body          # the series really rises and falls


def test_demo_is_read_only_and_writes_nothing(env):
    before = env.path.read_text(encoding="utf-8")
    body = env.get("/demo").body
    assert "/check" not in body and "/delete" not in body and 'action="/item' not in body
    assert env.path.read_text(encoding="utf-8") == before
    assert list(env.data.iterdir()) == []
    assert not env.path.with_name("watchlist.yaml.bak").exists()


def test_demo_ranges_narrow_the_graph(env):
    def markers(**query):
        return re.search(r'<svg class="chart".*?</svg>', env.get("/demo", **query).body, re.S).group(0).count("<circle")

    assert markers(range="30d") < markers()
    assert markers(range="bogus") == markers() == 12  # an unknown range falls back to all time


def test_the_dashboard_and_young_products_point_to_the_demo(env):
    assert 'href="/demo"' in env.get("/").body
    env.post("/item/kettle/check")
    page = env.get("/item/kettle").body
    assert "1 price recorded so far" in page and 'href="/demo"' in page
