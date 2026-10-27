"""Extract price and stock from a product page: schema.org JSON-LD first, CSS selectors second."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .models import FetchResult, Item
from .parse_price import parse_price

log = logging.getLogger(__name__)

_PRODUCT_TYPES = {"product", "productgroup", "individualproduct", "productmodel"}
_IN_STOCK = {"instock", "limitedavailability", "onlineonly", "instoreonly"}
# PreOrder/BackOrder can be ordered but can't ship now, so they count as "not in stock":
# the back-in-stock alert fires when the item really becomes available.
_OUT_OF_STOCK = {
    "outofstock", "soldout", "discontinued", "preorder", "presale", "backorder",
    "madetoorder", "reserved",
}


@dataclass
class _Offer:
    price: Decimal | None = None
    currency: str | None = None
    in_stock: bool | None = None


def extract(html: str, item: Item) -> FetchResult:
    tree = HTMLParser(html)
    ld_offer = _from_json_ld(tree)

    price, currency, in_stock, source = None, None, None, None
    if ld_offer is not None:
        price, currency, in_stock = ld_offer.price, ld_offer.currency, ld_offer.in_stock
        if price is not None:
            source = "json-ld"

    selector_note = ""
    if price is None and item.selector:
        parsed = _price_from_selector(tree, item.selector)
        if parsed is not None:
            price, currency, source = parsed.amount, parsed.currency or currency, "selector"
        else:
            selector_note = f"; selector '{item.selector}' matched no parseable price"

    if in_stock is None and item.stock_selector:
        in_stock = _stock_from_selector(tree, item.stock_selector, item.out_of_stock_text)
        if source is None and in_stock is not None:
            source = "selector"

    if price is None and in_stock is None:
        hint = "" if item.selector else "; add a CSS 'selector' for this site"
        return FetchResult.failure(
            "No price found: no schema.org Product price in JSON-LD" + selector_note + hint
        )
    # A page without a price but with known stock (typical for sold-out pages) still
    # counts as a successful check.
    return FetchResult(ok=True, price=price, currency=currency, in_stock=in_stock, source=source)


# --- JSON-LD -------------------------------------------------------------------------------


def _from_json_ld(tree: HTMLParser) -> _Offer | None:
    best: _Offer | None = None
    for node in tree.css("script"):
        script_type = (node.attributes.get("type") or "").lower()
        if not script_type.startswith("application/ld+json"):
            continue
        data = _load_json(node.text(deep=True))
        if data is None:
            continue
        for product in _products(data):
            offer = _offer_from_product(product)
            if offer.price is not None:
                return offer
            if best is None and offer.in_stock is not None:
                best = offer
    return best


def _load_json(text: str) -> Any:
    text = text.strip()
    for wrapper in (("<!--", "-->"), ("/*<![CDATA[*/", "/*]]>*/"), ("<![CDATA[", "]]>")):
        if text.startswith(wrapper[0]) and text.endswith(wrapper[1]):
            text = text[len(wrapper[0]):-len(wrapper[1])].strip()
    try:
        return json.loads(text, strict=False)
    except ValueError:
        log.debug("Skipping invalid JSON-LD block")
        return None


def _type_names(obj: dict[str, Any]) -> set[str]:
    raw = obj.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    # "Product", "schema:Product" and "https://schema.org/Product" are all Product.
    return {str(v).rsplit("/", 1)[-1].rsplit(":", 1)[-1].lower() for v in values if v}


def _products(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, list):
        for entry in data:
            yield from _products(entry)
        return
    if not isinstance(data, dict):
        return
    if _type_names(data) & _PRODUCT_TYPES:
        yield data
    for key in ("@graph", "mainEntity", "mainEntityOfPage"):
        if key in data:
            yield from _products(data[key])


def _offer_from_product(product: dict[str, Any]) -> _Offer:
    offers = list(_offers(product.get("offers")))
    if not offers and product.get("hasVariant"):
        # ProductGroup: look through the variants' offers.
        for variant in _as_list(product["hasVariant"]):
            if isinstance(variant, dict):
                offers.extend(_offers(variant.get("offers")))
    if not offers:
        return _Offer()

    priced = [o for o in offers if o.price is not None]
    in_stock_priced = [o for o in priced if o.in_stock is True]
    pool = in_stock_priced or priced
    chosen = min(pool, key=lambda o: o.price) if pool else _Offer()

    stocks = [o.in_stock for o in offers if o.in_stock is not None]
    in_stock = None if not stocks else any(stocks)
    currency = chosen.currency or next((o.currency for o in offers if o.currency), None)
    return _Offer(price=chosen.price, currency=currency, in_stock=in_stock)


def _offers(raw: Any) -> Iterator[_Offer]:
    for offer in _as_list(raw):
        if not isinstance(offer, dict):
            continue
        types = _type_names(offer)
        price = None
        if "aggregateoffer" in types:
            price = _to_decimal(offer.get("lowPrice"))
            if price is None:
                price = _to_decimal(offer.get("price"))
            nested = list(_offers(offer.get("offers")))
            if price is None and nested:
                prices = [o.price for o in nested if o.price is not None]
                price = min(prices) if prices else None
            availability = _availability(offer.get("availability"))
            if availability is None:
                stocks = [o.in_stock for o in nested if o.in_stock is not None]
                availability = any(stocks) if stocks else None
            currency = offer.get("priceCurrency") or next((o.currency for o in nested if o.currency), None)
            yield _Offer(price, _str_or_none(currency), availability)
            continue

        price = _to_decimal(offer.get("price"))
        currency = offer.get("priceCurrency")
        if price is None:
            for spec in _as_list(offer.get("priceSpecification")):
                if isinstance(spec, dict) and _to_decimal(spec.get("price")) is not None:
                    price = _to_decimal(spec.get("price"))
                    currency = currency or spec.get("priceCurrency")
                    break
        yield _Offer(price, _str_or_none(currency), _availability(offer.get("availability")))


def _availability(value: Any) -> bool | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("@id") or value.get("name")
    if not value:
        return None
    key = str(value).strip().rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1].lower()
    key = key.replace(" ", "").replace("_", "")
    if key in _IN_STOCK:
        return True
    if key in _OUT_OF_STOCK:
        return False
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        # schema.org prices should use "." as decimal separator: "1299.00"
        result = Decimal(text)
        return result if result.is_finite() and result >= 0 else None
    except InvalidOperation:
        parsed = parse_price(text)
        return parsed.amount if parsed else None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _str_or_none(value: Any) -> str | None:
    return str(value).strip() or None if value else None


# --- CSS selector fallback ------------------------------------------------------------------


def _price_from_selector(tree: HTMLParser, selector: str):
    try:
        nodes = tree.css(selector)
    except Exception as exc:  # selectolax raises on invalid selectors
        log.warning("Invalid CSS selector %r: %s", selector, exc)
        return None
    for node in nodes:
        # <meta itemprop="price" content="12.99"> and data attributes hold clean values.
        for attr in ("content", "data-price", "value"):
            parsed = parse_price(node.attributes.get(attr))
            if parsed is not None:
                text_parsed = parse_price(node.text(deep=True, separator=" "))
                currency = parsed.currency or (text_parsed.currency if text_parsed else None)
                return parsed._replace(currency=currency)
        parsed = parse_price(node.text(deep=True, separator=" "))
        if parsed is not None:
            return parsed
    return None


def _stock_from_selector(tree: HTMLParser, selector: str, out_of_stock_text: list[str]) -> bool | None:
    try:
        node = tree.css_first(selector)
    except Exception as exc:
        log.warning("Invalid CSS stock_selector %r: %s", selector, exc)
        return None
    if node is None:
        return None
    text = " ".join(node.text(deep=True, separator=" ").split()).lower()
    if not text:
        return None
    return not any(marker.lower() in text for marker in out_of_stock_text)
