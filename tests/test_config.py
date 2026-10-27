import os
from pathlib import Path

import pytest

from price_alerts.config import (
    ConfigError,
    env_bool,
    get_api_token,
    load_dotenv,
    load_watchlist,
)
from price_alerts.models import slugify

ROOT = Path(__file__).resolve().parent.parent

VALID = """
settings:
  from_email: alerts@example.com
  default_recipients: [me@example.com]
items:
  - name: Example Headphones
    url: https://example.com/p/1
    target_price: 199.99
    notify_on: [price_below, back_in_stock]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "watchlist.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def errors_for(tmp_path: Path, text: str) -> str:
    with pytest.raises(ConfigError) as exc:
        load_watchlist(write(tmp_path, text))
    return str(exc.value)


def test_valid_watchlist(tmp_path):
    wl = load_watchlist(write(tmp_path, VALID))
    item = wl.items[0]
    assert item.id == "example-headphones"
    assert str(item.target_price) == "199.99"
    assert wl.settings.request_delay_seconds == 5 and wl.settings.respect_robots_txt is True


def test_repo_example_watchlist_is_valid():
    assert load_watchlist(ROOT / "watchlist.yaml").items


def test_bad_url(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("https://example.com/p/1", "ftp://example.com/p/1"))
    assert "item 'Example Headphones': url:" in msg and "http(s)" in msg


def test_unknown_notify_on_value(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("back_in_stock]", "back_in_stok]"))
    assert "item 'Example Headphones': notify_on:" in msg


def test_price_below_requires_target_price(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("    target_price: 199.99\n", ""))
    assert "item 'Example Headphones'" in msg and "target_price: required" in msg


def test_unknown_notify_on_kind_is_rejected(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("[price_below, back_in_stock]", "[price_below, price_drop]"))
    assert "item 'Example Headphones': notify_on:" in msg


def test_duplicate_names(tmp_path):
    text = VALID + "  - name: example headphones!\n    url: https://example.com/p/2\n"
    assert "must be unique" in errors_for(tmp_path, text)


def test_unknown_field_is_reported(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("    target_price: 199.99\n", "    target_price: 199.99\n    selectr: .x\n"))
    assert "item 'Example Headphones': selectr:" in msg


def test_bad_from_email_and_missing_recipients(tmp_path):
    msg = errors_for(tmp_path, VALID.replace("alerts@example.com", "not-an-email"))
    assert "settings.from_email" in msg
    msg = errors_for(tmp_path, VALID.replace("[me@example.com]", "[]"))
    assert "recipients" in msg


def test_no_items_and_invalid_yaml(tmp_path):
    assert "items" in errors_for(tmp_path, "settings:\n  from_email: a@b.co\nitems: []\n")
    assert "invalid YAML" in errors_for(tmp_path, "settings: [\n")
    with pytest.raises(ConfigError, match="not found"):
        load_watchlist(tmp_path / "missing.yaml")


def test_notify_on_defaults_to_configured_rules(tmp_path):
    wl = load_watchlist(write(tmp_path, VALID.replace("    notify_on: [price_below, back_in_stock]\n", "")))
    assert wl.items[0].notify_on == ["price_below", "back_in_stock"]


def test_slugify():
    assert slugify("  Sony WH-1000XM5 (Black)! ") == "sony-wh-1000xm5-black"


def test_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nMAILTRAP_API_TOKEN="from-file"\nexport PA_TEST_OTHER=x # note\n\nBROKEN LINE\n')
    monkeypatch.setenv("MAILTRAP_API_TOKEN", "from-env")
    monkeypatch.delenv("PA_TEST_OTHER", raising=False)
    load_dotenv(env)
    assert os.environ["MAILTRAP_API_TOKEN"] == "from-env"
    assert os.environ["PA_TEST_OTHER"] == "x"
    monkeypatch.delenv("PA_TEST_OTHER")


def test_dotenv_missing_file_is_fine(tmp_path):
    load_dotenv(tmp_path / "nope.env")


def test_env_bool_and_token(monkeypatch):
    monkeypatch.setenv("DIGEST", "")
    assert env_bool("DIGEST") is None
    monkeypatch.setenv("DIGEST", "True")
    assert env_bool("DIGEST") is True
    monkeypatch.setenv("DIGEST", "maybe")
    with pytest.raises(ConfigError):
        env_bool("DIGEST")
    monkeypatch.delenv("MAILTRAP_API_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="MAILTRAP_API_TOKEN"):
        get_api_token()
