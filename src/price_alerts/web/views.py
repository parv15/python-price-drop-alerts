"""HTML for every page. Plain functions that return strings; everything dynamic goes through esc()."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape as esc

from ..models import Watchlist
from .assets import CSS, ICONS, TAG, mockup
from .charts import price_chart, sparkline
from .format import ago, fmt_datetime, fmt_delta, fmt_money, fmt_percent, parse_ts
from .model import FAILING, ItemView, Stats

REPO_URL = "https://github.com/manishgupta412/python-price-drop-alerts"

SCRIPT = """
(function () {
  var tabs = document.getElementById('tabs');
  if (tabs) {
    tabs.hidden = false;
    tabs.addEventListener('click', function (e) {
      var t = e.target.closest('.tab'); if (!t) return;
      tabs.querySelectorAll('.tab').forEach(function (b) { var on = b === t; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); });
      document.querySelectorAll('.pcard').forEach(function (c) { c.hidden = t.dataset.filter !== 'all' && c.dataset.status !== t.dataset.filter; });
    });
  }
  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); });
  });
  document.querySelectorAll('form').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return;
      var b = f.querySelector('button[data-busy]');
      if (b) { b.disabled = true; b.textContent = b.dataset.busy; }
    });
  });
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) document.querySelectorAll('button[data-busy][disabled]').forEach(function (b) { b.disabled = false; b.textContent = b.dataset.label; });
  });
})();
"""


@dataclass
class FormState:
    """What the Add / Edit form shows: the values to put back after an error, and the errors."""
    values: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _csrf(token: str) -> str:
    return f'<input type="hidden" name="csrf" value="{esc(token)}">'


def layout(title: str, body: str, *, nonce: str, flash: tuple[str, str] | None = None) -> str:
    flash_html = ""
    if flash:
        kind, text = flash
        flash_html = f'<p class="flash {esc(kind)}" role="status"><span class="wrap">{esc(text)}</span></p>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="logo" href="/">{TAG}<span>Price Alerts</span></a>
    <nav class="nav" aria-label="Main">
      <a href="/#products">Products</a>
      <a href="/#add">Add a product</a>
      <a href="/#how">How it works</a>
    </nav>
    <div class="top-actions">
      <a class="plain" href="{REPO_URL}">GitHub</a>
      <a class="btn sm" href="/#add">Add a product</a>
    </div>
  </div>
</header>
{flash_html}
{body}
<script nonce="{esc(nonce)}">{SCRIPT}</script>
</body>
</html>
"""


# ----------------------------------------------------------------------------- dashboard

def _delta_badge(v: ItemView) -> str:
    if len(v.points) < 2 or v.change is None or v.change_percent is None:
        return ""
    if v.change < 0:
        return f'<span class="delta down" title="Since the first price recorded">↓ {esc(fmt_percent(v.change_percent))}</span>'
    if v.change > 0:
        return f'<span class="delta up" title="Since the first price recorded">↑ {esc(fmt_percent(v.change_percent))}</span>'
    return '<span class="delta flat">No change</span>'


def product_card(v: ItemView, now: datetime) -> str:
    target = (f'Target <b>{esc(fmt_money(v.target, v.currency))}</b> · {esc(v.target_note)}'
              if v.target is not None else esc(v.target_note))
    return (
        f'<a class="pcard" href="/item/{esc(v.id)}" data-status="{esc(v.status)}">'
        f'<div class="top-row"><div><h3>{esc(v.name)}</h3><span class="dom">{esc(v.domain)}</span></div>'
        f'<span class="chip {esc(v.status)}">{esc(v.status_label)}</span></div>'
        f'<div class="price-row"><span class="price">{esc(fmt_money(v.price, v.currency))}</span>{_delta_badge(v)}</div>'
        f'{sparkline(v.points, now, width=300, height=46)}'
        f'<div class="meta"><span>{target}</span><span>{esc(ago(v.last_checked, now))}</span></div></a>'
    )


def _form_fields(state: FormState, *, edit: bool) -> str:
    v = state.values

    def val(key: str, default: str = "") -> str:
        return esc(v.get(key, default))

    price_checked = "checked" if v.get("notify_price", "on") else ""
    stock_checked = "checked" if v.get("notify_stock", "on") else ""
    if state.values and "csrf" in state.values:  # a re-rendered form: unchecked boxes stay unchecked
        price_checked = "checked" if v.get("notify_price") else ""
        stock_checked = "checked" if v.get("notify_stock") else ""
    readonly = " readonly" if edit else ""
    name_help = ("The name is this product's id, so it can't be changed. Remove it and add it again to rename."
                 if edit else "Used as the product's id. Keep it short and unique.")
    return f"""
        <div class="fields">
          <div class="field full">
            <label for="f-name">Product name</label>
            <input type="text" id="f-name" name="name" value="{val('name')}" placeholder="Wireless headphones" maxlength="120" required{readonly}>
            <small>{esc(name_help)}</small>
          </div>
          <div class="field full">
            <label for="f-url">Product page link</label>
            <input type="url" id="f-url" name="url" value="{val('url')}" placeholder="https://shop.example.com/product/123" required>
          </div>
          <div class="field full">
            <label for="f-target">Alert me when the price is at or below</label>
            <input type="number" id="f-target" name="target_price" value="{val('target_price')}" placeholder="149.99" step="0.01" min="0.01" inputmode="decimal">
            <small>In the shop's own currency. Leave it empty for stock alerts only.</small>
          </div>
          <label class="check full"><input type="checkbox" name="notify_price" value="on" {price_checked}>
            <span>Price drops to my target<small>One email when it first reaches the target, and again after it has gone back above it.</small></span></label>
          <label class="check full"><input type="checkbox" name="notify_stock" value="on" {stock_checked}>
            <span>Back in stock<small>One email when an out-of-stock product becomes available.</small></span></label>
        </div>"""


def _errors(state: FormState) -> str:
    if not state.errors:
        return ""
    items = "".join(f"<li>{esc(e)}</li>" for e in state.errors)
    return f'<div class="errors" role="alert"><strong>Please fix this:</strong><ul>{items}</ul></div>'


def dashboard(views: list[ItemView], stats: Stats, now: datetime, *, token: str, nonce: str,
              form: FormState | None = None, flash: tuple[str, str] | None = None, can_email: bool = True) -> str:
    form = form or FormState()
    tabs = [("all", "All", len(views))]
    for key, label in (("target", "At or below target"), ("watching", "Watching"), ("out", "Out of stock"), ("failing", "Needs attention")):
        count = sum(1 for v in views if v.status == key) if key != "failing" else sum(1 for v in views if v.status in (FAILING, "new"))
        if count:
            tabs.append((key, label, count))
    tab_html = "".join(
        f'<button type="button" class="tab{" on" if k == "all" else ""}" data-filter="{k}" role="tab" '
        f'aria-selected="{"true" if k == "all" else "false"}">{esc(label)}<span>{n}</span></button>' for k, label, n in tabs)
    cards = "".join(product_card(v, now) for v in views)
    # "Needs attention" groups failing and never-checked products
    cards = cards.replace('data-status="new"', 'data-status="failing"')

    notice = ("" if can_email else
              '<p class="hint">No MAILTRAP_API_TOKEN is set, so Check now records prices and holds any alert back until a run that has the token.</p>')
    body = f"""
<section class="hero">
  <div class="wrap">
    <div>
      <span class="pill">Track prices. Buy smarter.</span>
      <h1>Never miss a price drop again</h1>
      <p class="lead">Add the products you are watching and a target price. Every price is recorded on a graph, and you get an email the moment one reaches your target or comes back in stock.</p>
      <a class="btn lg" href="#add">Add a product {ICONS['arrow']}</a>
      <div class="assure">
        <span>{ICONS['bell']}Instant email alerts</span>
        <span>{ICONS['shield']}Your data stays in your repo</span>
        <span>{ICONS['bars']}Price history graphs</span>
      </div>
    </div>
    {mockup()}
  </div>
</section>

<section class="section" id="products">
  <div class="wrap">
    <div class="section-head"><h2>Your products</h2>
      <p>{stats.products} product{'s' if stats.products != 1 else ''} on the watchlist. Open one to see its full price graph, or <a href="/demo">see a demo graph</a>.</p></div>
    <div class="stats">
      <div class="stat"><small>Products</small><b>{stats.products}</b></div>
      <div class="stat"><small>At or below target</small><b>{stats.at_target}</b></div>
      <div class="stat"><small>Out of stock</small><b>{stats.out_of_stock}</b></div>
      <div class="stat"><small>Last checked</small><b class="sm">{esc(ago(stats.last_checked, now))}</b></div>
    </div>
    <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-start">
      <div class="tabs" id="tabs" hidden role="tablist" aria-label="Filter products">{tab_html}</div>
      <form method="post" action="/check">{_csrf(token)}
        <button class="btn ghost sm" type="submit" data-busy="Checking…" data-label="Check all now">{ICONS['refresh']} Check all now</button></form>
    </div>
    {notice}
    <div class="grid">{cards}</div>
  </div>
</section>

<section class="section alt" id="add">
  <div class="wrap split">
    <div>
      <h2>Add a product</h2>
      <p style="font-size:18px;margin-top:10px">Paste the link and a target price. The first price is read right away, so it shows up on the graph.</p>
      <ol class="steps">
        <li><b>1</b><div><strong>Paste the product link</strong><span>Any product page that publishes its price, which most shops do.</span></div></li>
        <li><b>2</b><div><strong>Set a target price</strong><span>You are emailed once when the price reaches it.</span></div></li>
        <li><b>3</b><div><strong>Watch the graph</strong><span>Every change is recorded and plotted on the product's page.</span></div></li>
      </ol>
    </div>
    <form class="card" method="post" action="/items/new">
      {_csrf(token)}
      {_errors(form)}
      {_form_fields(form, edit=False)}
      <button class="btn lg block" type="submit" data-busy="Adding and checking…" data-label="Add product" style="margin-top:24px">Add product</button>
      <p class="hint">It is saved to watchlist.yaml, your comments are kept, and the previous file is backed up as watchlist.yaml.bak.</p>
    </form>
  </div>
</section>

{how_it_works()}
"""
    return layout("Price Alerts", body, nonce=nonce, flash=flash)


def how_it_works() -> str:
    def card(cls: str, icon: str, title: str, text: str) -> str:
        return f'<div class="feature"><span class="ico {cls}">{ICONS[icon]}</span><h3>{title}</h3><p>{text}</p></div>'
    return f"""
<section class="section" id="how">
  <div class="wrap">
    <div class="section-head center"><h2>A simpler way to save</h2>
      <p>Everything you need to watch prices and get the best deals, all in one place.</p></div>
    <div class="features">
      {card('i-green', 'search', 'Track any product', 'Add a product page link. The price and stock are read from the schema.org data most shops publish.')}
      {card('i-blue', 'bell', 'Get email alerts', 'Price-drop, back-in-stock and error alerts are sent through the Mailtrap Email API.')}
      {card('i-amber', 'bars', 'See the price history', 'Every change is one row in data/history.csv and one step on the graph, with your target line.')}
      {card('i-purple', 'gear', 'Stay in control', 'Checked on a schedule by GitHub Actions. Edit a target or remove a product here at any time.')}
    </div>
  </div>
</section>"""


# ----------------------------------------------------------------------------- product page

def _tile(label: str, value: str, note: str = "", note_cls: str = "") -> str:
    note_html = f'<span class="{note_cls}">{esc(note)}</span>' if note else ""
    return f'<div class="tile"><small>{esc(label)}</small><b>{esc(value)}</b>{note_html}</div>'


def item_page(v: ItemView, watchlist: Watchlist | None, now: datetime, *, range_key: str, token: str, nonce: str,
              flash: tuple[str, str] | None = None, demo: bool = False) -> str:
    cur = v.currency
    change_note, change_cls = "", ""
    if v.change is not None and len(v.points) > 1:
        if v.change == 0:
            change_note = "No change since first seen"
        else:
            change_note = f"{fmt_delta(v.change, cur)} ({fmt_percent(v.change_percent)}) since first seen"
            change_cls = "pos" if v.change < 0 else "neg"
    target_note = v.target_note if v.target is not None else "No price target"
    tiles = "".join([
        _tile("Current price", fmt_money(v.price, cur), change_note, change_cls),
        _tile("Target price", fmt_money(v.target, cur) if v.target is not None else "–", target_note if v.target is not None else ""),
        _tile("Lowest seen", fmt_money(v.low, cur)),
        _tile("Highest seen", fmt_money(v.high, cur)),
        _tile("Stock", {True: "In stock", False: "Out of stock"}.get(v.in_stock, "Unknown"), f"Checked {ago(v.last_checked, now)}"),
    ])
    ranges = "".join(
        f'<a href="{"/demo" if demo else "/item/" + esc(v.id)}?range={k}"{" aria-current=\"true\"" if k == range_key else ""}>{label}</a>'
        for k, label in (("7d", "7 days"), ("30d", "30 days"), ("90d", "90 days"), ("all", "All time")))
    chart = price_chart(v.points, now, currency=cur, target=v.target, name=v.name, range_key=range_key)
    legend = ('<div class="legend"><span><i></i>Price</span>'
              + ('<span><i class="t"></i>Target</span>' if v.target is not None else "")
              + '<span>Hover a point for the exact price and time.</span></div>')
    if not demo and len(v.points) < 3:
        recorded = len(v.points)
        legend += (f'<p class="hint">{recorded} price{"s" if recorded != 1 else ""} recorded so far. The graph fills in as the '
                   'price changes. <a href="/demo">See a demo graph</a> to preview it.</p>')

    error = ""
    if v.status == FAILING:
        error = (f'<p class="callout" role="alert"><strong>The last {v.failures} check{"s" if v.failures != 1 else ""} failed.</strong> '
                 f'{esc((v.last_error or "").rstrip(".") + ".") if v.last_error else ""} The last known price is shown. A failure alert goes out after 3 checks in a row.</p>')

    rows_html = _history_rows(v)
    alerts = []
    if "price_below" in (v.item.notify_on or []):
        alerts.append("Price at or below the target")
    if "back_in_stock" in (v.item.notify_on or []):
        alerts.append("Back in stock")
    count = len(watchlist.recipients_for(v.item)) if watchlist else 0

    demo_tag = '<span class="chip new">Demo data</span>'
    demo_note = ('<p class="callout info" role="note"><strong>This is sample data.</strong> It is a made-up product, so you can see what '
                 'the graph looks like after a few weeks of price changes. Nothing here is saved or sent.</p>') if demo else ""
    if demo:
        actions = '<a class="btn sm" href="/#add">Add a product</a><a class="btn ghost sm" href="/#products">Your products</a>'
    else:
        actions = (f'''<form method="post" action="/item/{esc(v.id)}/check">{_csrf(token)}
        <button class="btn sm" type="submit" data-busy="Checking…" data-label="Check now">{ICONS['refresh']} Check now</button></form>
      <a class="btn ghost sm" href="/item/{esc(v.id)}/edit">Edit</a>
      <form method="post" action="/item/{esc(v.id)}/delete" data-confirm="Remove {esc(v.name)} from the watchlist? Its recorded history stays in data/history.csv.">{_csrf(token)}
        <button class="btn danger sm" type="submit">Remove</button></form>''')
    settings_panel = "" if demo else f'''<section class="panel"><div class="panel-head"><h2>Alert settings</h2></div>
      <dl class="facts">
        <dt>Alerts for</dt><dd>{esc(' · '.join(alerts) or 'None')}</dd>
        <dt>Sent to</dt><dd>{count} recipient{'s' if count != 1 else ''}</dd>
        <dt>Page</dt><dd><a href="{esc(v.url)}" rel="noopener noreferrer" target="_blank">{esc(v.url)}</a></dd>
      </dl>
    </section>'''

    body = f"""
<div class="wrap">
  <div class="crumbs"><a href="/#products">← All products</a></div>
  <div class="p-head">
    <div>
      <h1>{esc(v.name)}</h1>
      <div class="sub"><span class="chip {esc(v.status)}">{esc(v.status_label)}</span>
        {demo_tag if demo else f'<a href="{esc(v.url)}" rel="noopener noreferrer" target="_blank">{esc(v.domain)} ↗</a>'}</div>
    </div>
    <div class="actions">{actions}</div>
  </div>
  {demo_note}{error}
  <div class="tiles">{tiles}</div>
  <section class="panel" aria-labelledby="graph">
    <div class="panel-head"><h2 id="graph">Price history</h2><div class="ranges" aria-label="Time range">{ranges}</div></div>
    {chart}
    {legend}
  </section>
  <div class="{'' if demo else 'two'}">
    {settings_panel}
    <section class="panel"><div class="panel-head"><h2>Recorded changes</h2></div>
      {rows_html}
    </section>
  </div>
</div>
<div style="height:48px"></div>
"""
    return layout(f"{v.name} · Price Alerts", body, nonce=nonce, flash=flash)


def _history_rows(v: ItemView) -> str:
    if not v.rows:
        return '<p class="empty">Nothing recorded yet. Press Check now to take the first price.</p>'
    body = []
    prev = None
    for row in v.rows:  # oldest first, so each row can be compared with the one before it
        change = ""
        if row.price is not None and prev is not None:
            diff = row.price - prev
            if diff:
                change = f'<span class="{"down" if diff < 0 else "up"}">{esc(fmt_delta(diff, row.currency))}</span>'
        if row.price is not None:
            prev = row.price
        moment = parse_ts(row.timestamp)
        stock = {True: "In stock", False: "Out of stock"}.get(row.in_stock, "–")
        body.append(
            f'<tr><td>{esc(fmt_datetime(moment) if moment else row.timestamp)}</td>'
            f'<td class="num">{esc(fmt_money(row.price, row.currency))}</td><td class="num">{change or "–"}</td>'
            f'<td class="hide-sm">{stock}</td></tr>')
    rows = "".join(reversed(body))
    return ('<table class="hist"><thead><tr><th>When</th><th class="num">Price</th><th class="num">Change</th>'
            f'<th class="hide-sm">Stock</th></tr></thead><tbody>{rows}</tbody></table>')


def edit_page(v: ItemView, state: FormState, *, token: str, nonce: str) -> str:
    body = f"""
<div class="wrap narrow">
  <div class="crumbs"><a href="/item/{esc(v.id)}">← {esc(v.name)}</a></div>
  <div class="p-head"><div><h1>Edit {esc(v.name)}</h1><div class="sub">Change the page link, the target price or which alerts you get.</div></div></div>
  <form class="card" method="post" action="/item/{esc(v.id)}/edit">
    {_csrf(token)}
    {_errors(state)}
    {_form_fields(state, edit=True)}
    <div class="actions" style="margin-top:24px">
      <button class="btn lg" type="submit" data-busy="Saving…" data-label="Save changes">Save changes</button>
      <a class="btn ghost lg" href="/item/{esc(v.id)}">Cancel</a>
    </div>
  </form>
</div>
<div style="height:64px"></div>
"""
    return layout(f"Edit {v.name} · Price Alerts", body, nonce=nonce)


def error_page(status: int, title: str, message: str, *, nonce: str) -> str:
    body = f"""
<section class="section"><div class="wrap narrow center">
  <p class="muted" style="font-weight:600">Error {status}</p>
  <h2>{esc(title)}</h2>
  <p style="font-size:18px;margin-top:12px">{esc(message)}</p>
  <p style="margin-top:26px"><a class="btn" href="/">Back to the dashboard</a></p>
</div></section>"""
    return layout(f"{title} · Price Alerts", body, nonce=nonce)
