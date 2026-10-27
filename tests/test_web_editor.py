"""watchlist.yaml text edits: comments and other products stay exactly as they were."""

from decimal import Decimal

import pytest

from price_alerts.config import load_watchlist
from price_alerts.models import Item
from price_alerts.web import editor

SAMPLE = """\
# my notes at the top
settings:
  from_email: alerts@example.com
  default_recipients: [me@example.com]  # who gets the emails

items:
  # the first product
  - name: Kettle
    url: https://shop.example/kettle
    target_price: 30.00
    notify_on: [price_below]

  - name: Toaster
    url: https://shop.example/toaster
    selector: ".price"
    notify_on: [back_in_stock]

  # Full example with every option.
  # - name: Example
"""


def item(**kwargs):
    data = {"name": "Headphones", "url": "https://shop.example/h", "target_price": Decimal("149.5")}
    data.update(kwargs)
    return Item.model_validate(data)


def test_add_appends_after_the_last_product_and_keeps_every_comment():
    new = editor.add_item(SAMPLE, item())
    assert new.index("name: Headphones") > new.index("name: Toaster")
    assert new.index("name: Headphones") < new.index("# Full example")
    for kept in ("# my notes at the top", "# who gets the emails", "# the first product", "# - name: Example"):
        assert kept in new
    assert "target_price: 149.50" in new and "notify_on: [price_below, back_in_stock]" in new


def test_remove_is_the_exact_inverse_of_add():
    assert editor.remove_item(editor.add_item(SAMPLE, item()), "headphones") == SAMPLE


def test_replace_swaps_only_that_block():
    new = editor.replace_item(SAMPLE, "kettle", item(name="Kettle", url="https://shop.example/kettle", target_price=Decimal("25")))
    assert "target_price: 25.00" in new and "target_price: 30.00" not in new
    assert new.count("name: Toaster") == 1 and "# the first product" in new


def test_the_last_product_cannot_be_removed():
    only = SAMPLE[: SAMPLE.index("  - name: Toaster")]
    with pytest.raises(editor.EditError, match="at least one product"):
        editor.remove_item(only, "kettle")


def test_unknown_product_is_an_error():
    with pytest.raises(editor.EditError, match="not in watchlist.yaml"):
        editor.replace_item(SAMPLE, "nope", item())


@pytest.mark.parametrize("name", ["Plain Name", "Name, with comma", 'Quote "inside"', "Café ☕", "yes", "123", "a: b"])
def test_awkward_names_survive_a_round_trip(tmp_path, name):
    path = tmp_path / "watchlist.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    editor.write_validated(path, editor.add_item(SAMPLE, item(name=name)))
    assert name in [i.name for i in load_watchlist(path).items]


def test_write_keeps_a_backup_and_never_writes_an_invalid_file(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    editor.write_validated(path, editor.add_item(SAMPLE, item()))
    assert path.with_name("watchlist.yaml.bak").read_text(encoding="utf-8") == SAMPLE

    before = path.read_text(encoding="utf-8")
    duplicate = editor.add_item(before, item(name="Kettle"))  # same name as an existing product
    with pytest.raises(editor.EditError, match="unique"):
        editor.write_validated(path, duplicate)
    assert path.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob(".watchlist.yaml.*.tmp"))
