from decimal import Decimal

import pytest

from price_alerts.extract import extract
from price_alerts.models import Item

from .conftest import fixture_html, product_page


def item(**kwargs) -> Item:
    data = {"name": "Thing", "url": "https://shop.example/p/1", "notify_on": ["back_in_stock"]}
    data.update(kwargs)
    return Item.model_validate(data)


def test_simple_product():
    result = extract(fixture_html("jsonld_simple.html"), item())
    assert result.ok
    assert (result.price, result.currency, result.in_stock, result.source) == (
        Decimal("249.00"), "EUR", True, "json-ld",
    )


def test_graph_and_type_list():
    result = extract(fixture_html("jsonld_graph.html"), item())
    assert (result.price, result.currency, result.in_stock, result.source) == (
        Decimal("1299.99"), "USD", True, "json-ld",
    )


def test_top_level_list_and_offer_list_picks_lowest_in_stock_offer():
    result = extract(fixture_html("jsonld_offers_list.html"), item())
    assert (result.price, result.currency, result.in_stock) == (Decimal("89.00"), "GBP", True)


def test_aggregate_offer_uses_low_price():
    result = extract(fixture_html("jsonld_aggregate.html"), item())
    assert (result.price, result.currency, result.in_stock) == (Decimal("129999"), "INR", True)


def test_out_of_stock():
    result = extract(fixture_html("jsonld_out_of_stock.html"), item())
    assert result.ok
    assert (result.price, result.in_stock) == (Decimal("59.99"), False)


def test_selector_only_page():
    it = item(selector=".price", stock_selector=".availability")
    result = extract(fixture_html("selector_only.html"), it)
    assert result.ok
    assert (result.price, result.currency, result.in_stock, result.source) == (
        Decimal("1299.00"), "EUR", False, "selector",
    )


def test_broken_json_ld_falls_back_to_selector():
    it = item(selector=".price", stock_selector=".availability")
    result = extract(fixture_html("broken_jsonld.html"), it)
    assert result.ok
    assert (result.price, result.currency, result.in_stock, result.source) == (
        Decimal("1299.99"), "USD", True, "selector",
    )


def test_selector_without_stock_selector_gives_unknown_stock():
    result = extract(fixture_html("selector_only.html"), item(selector=".price"))
    assert result.ok and result.in_stock is None


def test_nothing_parseable_is_a_failure_with_reason():
    result = extract(fixture_html("nothing.html"), item(selector=".price"))
    assert not result.ok
    assert "No price found" in result.error and "'.price'" in result.error


def test_nothing_parseable_without_selector_hints_to_add_one():
    result = extract(fixture_html("nothing.html"), item())
    assert not result.ok and "add a CSS 'selector'" in result.error


def test_json_ld_wins_over_selector():
    result = extract(fixture_html("jsonld_simple.html"), item(selector=".price"))
    assert result.source == "json-ld"


def test_meta_content_attribute_selector():
    html = '<html><body><meta itemprop="price" content="12.99"><span>£12.99</span></body></html>'
    result = extract(html, item(selector='[itemprop="price"]'))
    assert result.price == Decimal("12.99")


@pytest.mark.parametrize(
    ("availability", "expected"),
    [
        ("https://schema.org/InStock", True),
        ("http://schema.org/InStock", True),
        ("InStock", True),
        ("schema:InStock", True),
        ("https://schema.org/LimitedAvailability", True),
        ("https://schema.org/OnlineOnly", True),
        ("https://schema.org/OutOfStock", False),
        ("OutOfStock", False),
        ("https://schema.org/SoldOut", False),
        ("https://schema.org/Discontinued", False),
        ("https://schema.org/PreOrder", False),
        ("https://schema.org/BackOrder", False),
        ("SomethingElse", None),
    ],
)
def test_availability_mapping(availability, expected):
    html = product_page("10.00", availability=None).replace(
        '"priceCurrency"', f'"availability": "{availability}", "priceCurrency"'
    )
    assert extract(html, item()).in_stock is expected


def test_stock_only_page_is_ok_without_price():
    result = extract(product_page(None, "OutOfStock"), item())
    assert result.ok and result.price is None and result.in_stock is False


def test_price_specification_and_numeric_price():
    html = (
        '<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer",'
        '"priceSpecification":{"price":19.5,"priceCurrency":"USD"}}}</script>'
    )
    result = extract(html, item())
    assert (result.price, result.currency) == (Decimal("19.5"), "USD")
