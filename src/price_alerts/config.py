"""Load watchlist.yaml, the optional local .env file and environment flags."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models import Watchlist

TOKEN_ENV = "MAILTRAP_API_TOKEN"  # noqa: S105  (the name of the env var, not a secret)
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(Exception):
    """The watchlist or environment is invalid. Maps to exit code 1."""


def load_dotenv(path: Path | str = ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, optional quotes.

    Only runs if the file exists and never overrides variables that are already
    set in the real environment. Values are never printed.
    """
    path = Path(path)
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key and key not in os.environ:
            os.environ[key] = value


def env_bool(name: str) -> bool | None:
    """Read a boolean env var. Unset or empty -> None (so it doesn't override config)."""
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return None
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false, got '{value}'")


def get_api_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise ConfigError(
            f"{TOKEN_ENV} is not set. Add it as a repository secret (GitHub Actions) "
            "or to a local .env file. Use --dry-run to run without sending."
        )
    return token


def load_watchlist(path: Path | str) -> Watchlist:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Watchlist not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping with 'settings' and 'items'")
    try:
        return Watchlist.model_validate(raw)
    except ValidationError as exc:
        lines = [_describe(err, raw) for err in exc.errors()]
        raise ConfigError(f"{path} is invalid:\n" + "\n".join(f"  - {line}" for line in lines)) from None


def _describe(err: dict[str, Any], raw: dict[str, Any]) -> str:
    loc = list(err.get("loc", ()))
    msg = str(err.get("msg", "invalid value")).removeprefix("Value error, ")
    where = ""
    if len(loc) >= 2 and loc[0] == "items" and isinstance(loc[1], int):
        items = raw.get("items") or []
        name = None
        if loc[1] < len(items) and isinstance(items[loc[1]], dict):
            name = items[loc[1]].get("name")
        where = f"item '{name}'" if name else f"items[{loc[1]}]"
        rest = [str(p) for p in loc[2:] if not isinstance(p, int)]
        # Enum errors on list entries point at notify_on.<index>; keep the field name.
        if rest:
            where += f": {rest[0]}"
    elif loc:
        where = ".".join(str(p) for p in loc)
    return f"{where}: {msg}" if where else msg
