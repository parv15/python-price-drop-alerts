"""The dashboard's request handling. `WebApp.handle()` turns a Request into a Response with no
sockets involved, so it is tested directly; `server.py` only connects it to HTTP."""

from __future__ import annotations

import hmac
import logging
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, quote

from pydantic import ValidationError

from ..config import ConfigError, get_api_token, load_watchlist
from ..fetch import HttpFetcher
from ..history import read_history
from ..mailer import MailerError, MailtrapMailer
from ..models import EmailMessage, Item, Watchlist
from ..runner import HISTORY_FILE, STATE_FILE, RunSummary, run, utc_now
from ..state import load_state, money
from . import editor, views
from .charts import RANGES
from .demo import demo_view
from .format import fmt_money
from .model import ItemView, build_stats, build_views

log = logging.getLogger(__name__)

LOOPBACK = {"127.0.0.1", "localhost", "[::1]", "::1"}
FIELD_LABELS = {"name": "Product name", "url": "Product page link", "target_price": "Target price",
                "notify_on": "Alerts"}


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]] = field(default_factory=dict)
    form: dict[str, list[str]] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def first(self, source: dict[str, list[str]], key: str, default: str = "") -> str:
        values = source.get(key)
        return values[0] if values else default


@dataclass
class Response:
    status: int = 200
    body: str = ""
    content_type: str = "text/html; charset=utf-8"
    headers: list[tuple[str, str]] = field(default_factory=list)


class HeldMailer:
    """Used when there is no Mailtrap token: every alert is held back, so the next real run still sends it."""

    def send(self, message: EmailMessage) -> None:
        raise MailerError("held: MAILTRAP_API_TOKEN is not set")


FetcherFactory = Callable[[Watchlist], "HttpFetcher"]
MailerFactory = Callable[[Watchlist], object]


def default_fetcher(watchlist: Watchlist) -> HttpFetcher:
    s = watchlist.settings
    return HttpFetcher(timeout=s.timeout_seconds, delay=s.request_delay_seconds, respect_robots_txt=s.respect_robots_txt)


def default_mailer(watchlist: Watchlist) -> object:
    s = watchlist.settings
    return MailtrapMailer(get_api_token(), s.from_email, s.from_name)


class WebApp:
    def __init__(self, watchlist_path: Path, data_dir: Path, *, fetcher_factory: FetcherFactory = default_fetcher,
                 mailer_factory: MailerFactory = default_mailer, clock: Callable[[], datetime] = utc_now,
                 allowed_hosts: set[str] | None = None, token: str | None = None) -> None:
        self.watchlist_path = Path(watchlist_path)
        self.data_dir = Path(data_dir)
        self.fetcher_factory = fetcher_factory
        self.mailer_factory = mailer_factory
        self.clock = clock
        self.allowed_hosts = LOOPBACK if allowed_hosts is None else allowed_hosts
        self.token = token or secrets.token_hex(16)
        self._lock = threading.Lock()  # one check at a time, and no edit in the middle of one

    # ------------------------------------------------------------------ plumbing

    def handle(self, req: Request) -> Response:
        nonce = secrets.token_urlsafe(12)
        try:
            response = self._route(req, nonce)
        except ConfigError as exc:
            response = self._page(500, "The watchlist has a problem", str(exc), nonce)
        except Exception:  # never show a traceback in the browser
            log.exception("Unhandled error for %s %s", req.method, req.path)
            response = self._page(500, "Something went wrong", "The error was logged in the terminal running the dashboard.", nonce)
        response.headers += [
            ("Content-Security-Policy", f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; "
                                        "img-src data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"),
            ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"), ("Cache-Control", "no-store"),
        ]
        return response

    def _page(self, status: int, title: str, message: str, nonce: str) -> Response:
        return Response(status, views.error_page(status, title, message, nonce=nonce))

    def _redirect(self, location: str, kind: str | None = None, text: str | None = None) -> Response:
        if kind and text:
            sep = "&" if "?" in location else "?"
            location = f"{location}{sep}{kind}={quote(text[:400])}"
        return Response(303, "", headers=[("Location", location)])

    def _route(self, req: Request, nonce: str) -> Response:
        if self.allowed_hosts and _hostname(req.headers.get("Host", "")) not in self.allowed_hosts:
            return self._page(403, "Unknown host", "This dashboard only answers on localhost.", nonce)
        if req.method == "POST":
            sent = req.first(req.form, "csrf")
            if not hmac.compare_digest(sent.encode(), self.token.encode()):
                return self._page(403, "Form expired", "Reload the page and try again.", nonce)
        elif req.method != "GET":
            return self._page(405, "Method not allowed", f"{req.method} is not supported.", nonce)

        path = req.path.rstrip("/") or "/"
        if req.method == "GET":
            if path == "/":
                return self._dashboard(req, nonce)
            if path == "/demo":
                return self._demo(req, nonce)
            if m := re.fullmatch(r"/item/([a-z0-9-]+)", path):
                return self._item(req, m.group(1), nonce)
            if m := re.fullmatch(r"/item/([a-z0-9-]+)/edit", path):
                return self._edit_form(m.group(1), nonce)
        else:
            if path == "/items/new":
                return self._add(req, nonce)
            if path == "/check":
                return self._check(None, "/")
            if m := re.fullmatch(r"/item/([a-z0-9-]+)/check", path):
                return self._check(m.group(1), f"/item/{m.group(1)}")
            if m := re.fullmatch(r"/item/([a-z0-9-]+)/edit", path):
                return self._edit(req, m.group(1), nonce)
            if m := re.fullmatch(r"/item/([a-z0-9-]+)/delete", path):
                return self._delete(m.group(1))
        return self._page(404, "Page not found", "There is nothing at this address.", nonce)

    # ------------------------------------------------------------------ data

    def _load(self) -> tuple[Watchlist, list[ItemView]]:
        watchlist = load_watchlist(self.watchlist_path)
        try:
            state = load_state(self.data_dir / STATE_FILE)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        history = read_history(self.data_dir / HISTORY_FILE)
        return watchlist, build_views(watchlist, state, history)

    def _flash(self, req: Request) -> tuple[str, str] | None:
        for kind in ("ok", "warn", "err"):
            text = req.first(req.query, kind)
            if text:
                return kind, text[:400]
        return None

    @staticmethod
    def _can_email() -> bool:
        try:
            get_api_token()
            return True
        except ConfigError:
            return False

    # ------------------------------------------------------------------ pages

    def _dashboard(self, req: Request, nonce: str, form: views.FormState | None = None, status: int = 200) -> Response:
        _, items = self._load()
        now = self.clock()
        html = views.dashboard(items, build_stats(items), now, token=self.token, nonce=nonce, form=form,
                               flash=self._flash(req), can_email=self._can_email())
        return Response(status, html)

    def _find(self, items: list[ItemView], item_id: str) -> ItemView | None:
        return next((v for v in items if v.id == item_id), None)

    def _item(self, req: Request, item_id: str, nonce: str) -> Response:
        watchlist, items = self._load()
        view = self._find(items, item_id)
        if view is None:
            return self._page(404, "Product not found", "It may have been removed from the watchlist.", nonce)
        range_key = req.first(req.query, "range", "all")
        if range_key not in RANGES:
            range_key = "all"
        html = views.item_page(view, watchlist, self.clock(), range_key=range_key, token=self.token, nonce=nonce,
                               flash=self._flash(req))
        return Response(200, html)

    def _demo(self, req: Request, nonce: str) -> Response:
        now = self.clock()
        range_key = req.first(req.query, "range", "all")
        if range_key not in RANGES:
            range_key = "all"
        html = views.item_page(demo_view(now), None, now, range_key=range_key, token=self.token, nonce=nonce, demo=True)
        return Response(200, html)

    def _edit_form(self, item_id: str, nonce: str, state: views.FormState | None = None, status: int = 200) -> Response:
        _, items = self._load()
        view = self._find(items, item_id)
        if view is None:
            return self._page(404, "Product not found", "It may have been removed from the watchlist.", nonce)
        if state is None:
            item = view.item
            state = views.FormState({
                "name": item.name, "url": item.url,
                "target_price": "" if item.target_price is None else str(money(item.target_price)),
                "notify_price": "on" if "price_below" in (item.notify_on or []) else "",
                "notify_stock": "on" if "back_in_stock" in (item.notify_on or []) else "",
            })
        return Response(status, views.edit_page(view, state, token=self.token, nonce=nonce))

    # ------------------------------------------------------------------ actions

    def _form_item(self, req: Request, *, keep: Item | None = None) -> tuple[Item | None, views.FormState]:
        f = req.form
        state = views.FormState({k: req.first(f, k) for k in
                                 ("name", "url", "target_price", "notify_price", "notify_stock", "csrf")})
        if keep is not None:
            state.values["name"] = keep.name  # the name is the id, so it never changes
        target_text = state.values["target_price"].strip()
        data: dict[str, object] = {
            "name": state.values["name"].strip(), "url": state.values["url"].strip(),
            "notify_on": [k for k, on in (("price_below", state.values["notify_price"]), ("back_in_stock", state.values["notify_stock"])) if on],
        }
        if keep is not None:
            # Not on the form, so an edit leaves them exactly as they are in watchlist.yaml.
            data.update(selector=keep.selector, stock_selector=keep.stock_selector,
                        out_of_stock_text=keep.out_of_stock_text, recipients=keep.recipients)
        if target_text:
            try:
                data["target_price"] = Decimal(target_text)
            except InvalidOperation:
                state.errors.append("Target price: enter a number such as 149.99")
        if not data["notify_on"]:
            state.errors.append("Alerts: choose at least one of price drop or back in stock")
        try:
            item = Item.model_validate(data)
        except ValidationError as exc:
            for err in exc.errors():
                loc = str(err["loc"][0]) if err["loc"] else ""
                if loc == "notify_on" and not data["notify_on"]:
                    continue
                state.errors.append(f"{FIELD_LABELS.get(loc, loc)}: {str(err['msg']).removeprefix('Value error, ')}")
            return None, state
        return (None if state.errors else item), state

    def _write(self, new_text: str, state: views.FormState) -> bool:
        try:
            editor.write_validated(self.watchlist_path, new_text)
        except editor.EditError as exc:
            state.errors.append(str(exc))
            return False
        return True

    def _add(self, req: Request, nonce: str) -> Response:
        item, state = self._form_item(req)
        if item is not None:
            with self._lock:
                try:
                    text = self.watchlist_path.read_text(encoding="utf-8")
                    ok = self._write(editor.add_item(text, item), state)
                except editor.EditError as exc:
                    state.errors.append(str(exc))
                    ok = False
            if ok:
                kind, message = self._run(item.id)
                return self._redirect(f"/item/{item.id}", kind, f"Added {item.name}. {message}")
        return self._dashboard(req, nonce, form=state, status=422)

    def _edit(self, req: Request, item_id: str, nonce: str) -> Response:
        _, items = self._load()
        view = self._find(items, item_id)
        if view is None:
            return self._page(404, "Product not found", "It may have been removed from the watchlist.", nonce)
        item, state = self._form_item(req, keep=view.item)
        if item is not None:
            with self._lock:
                try:
                    text = self.watchlist_path.read_text(encoding="utf-8")
                    ok = self._write(editor.replace_item(text, item_id, item), state)
                except editor.EditError as exc:
                    state.errors.append(str(exc))
                    ok = False
            if ok:
                return self._redirect(f"/item/{item_id}", "ok", f"Saved changes to {item.name}.")
        return self._edit_form(item_id, nonce, state, 422)

    def _delete(self, item_id: str) -> Response:
        with self._lock:
            try:
                text = self.watchlist_path.read_text(encoding="utf-8")
                editor.write_validated(self.watchlist_path, editor.remove_item(text, item_id))
            except editor.EditError as exc:
                return self._redirect(f"/item/{item_id}", "err", str(exc))
        return self._redirect("/", "ok", "Removed from the watchlist. Its recorded history stays in data/history.csv.")

    def _check(self, item_id: str | None, back: str) -> Response:
        kind, message = self._run(item_id)
        return self._redirect(back, kind, message)

    def _run(self, item_id: str | None) -> tuple[str, str]:
        """Run the real checker for one product or all of them, and describe the outcome."""
        with self._lock:
            watchlist = load_watchlist(self.watchlist_path)
            held = False
            try:
                mailer = self.mailer_factory(watchlist)
            except ConfigError:
                mailer, held = HeldMailer(), True
            try:
                with self.fetcher_factory(watchlist) as fetcher:
                    summary = run(watchlist, data_dir=self.data_dir, fetcher=fetcher, mailer=mailer,  # type: ignore[arg-type]
                                  clock=self.clock, only=item_id, digest=False)
            except ConfigError as exc:
                return "err", str(exc)
        return self._describe(summary, watchlist, item_id, held)

    def _describe(self, summary: RunSummary, watchlist: Watchlist, item_id: str | None, held: bool) -> tuple[str, str]:
        if summary.failed:
            first = summary.errors[0] if summary.errors else ("", "unknown error")
            more = f" (and {summary.failed - 1} more)" if summary.failed > 1 else ""
            return "warn", f"Could not read {first[0]}: {first[1]}{more}"
        state = load_state(self.data_dir / STATE_FILE)
        parts = []
        if item_id:
            s = state.get(item_id)
            parts.append(f"Checked: now {fmt_money(s.last_price, s.last_currency)}.")
        else:
            parts.append(f"Checked {summary.ok} product{'s' if summary.ok != 1 else ''}.")
        if summary.alerts_sent:
            parts.append(f"{summary.alerts_sent} alert email{'s' if summary.alerts_sent != 1 else ''} sent.")
        if summary.send_failures:
            reason = "no Mailtrap token is set" if held else "the email service rejected it"
            parts.append(f"{summary.send_failures} alert{'s' if summary.send_failures != 1 else ''} held back because {reason}; "
                         "the next run will send them.")
            return "warn", " ".join(parts)
        return "ok", " ".join(parts)


def _hostname(header: str) -> str:
    """The host part of a Host header, without the port: 'localhost:8765' -> 'localhost', '[::1]:80' -> '[::1]'."""
    if header.startswith("["):
        return header.split("]", 1)[0] + "]"
    return header.rsplit(":", 1)[0] if ":" in header else header


def parse_request(method: str, target: str, headers: dict[str, str], body: bytes) -> Request:
    path, _, query = target.partition("?")
    form = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True) if method == "POST" else {}
    return Request(method, path, parse_qs(query), form, headers)
