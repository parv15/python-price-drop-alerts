"""Edit watchlist.yaml as text, so comments and the other products are left exactly as they are.

Each product is a block that starts with `- name:` under `items:`. Adding, replacing and
removing work on those blocks only. Every change is validated with the real loader before
the file is replaced, and the previous version is kept as watchlist.yaml.bak.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import yaml

from ..config import ConfigError, load_watchlist
from ..models import Item, slugify
from ..state import money

_ITEMS = re.compile(r"^items:\s*(#.*)?$")
_START = re.compile(r"^(\s*)- name:\s*(.*)$")
_PLAIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()+-]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "y", "n"}
DEFAULT_OUT_OF_STOCK = ["out of stock", "sold out"]


class EditError(Exception):
    """The change could not be made. The message is safe to show to the user."""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(text: str) -> str:
    """A YAML scalar: plain when that is unambiguous, otherwise a double-quoted string."""
    looks_numeric = re.fullmatch(r"[0-9.+\-eE_]+", text) is not None
    if _PLAIN.match(text) and text.lower() not in _RESERVED and not looks_numeric and not text.endswith(" "):
        return text
    return json.dumps(text, ensure_ascii=False)


def render_item(item: Item, *, indent: str = "  ") -> list[str]:
    pad = indent + "  "
    lines = [f"{indent}- name: {_scalar(item.name)}", f"{pad}url: {json.dumps(item.url)}"]
    if item.selector:
        lines.append(f"{pad}selector: {json.dumps(item.selector, ensure_ascii=False)}")
    if item.stock_selector:
        lines.append(f"{pad}stock_selector: {json.dumps(item.stock_selector, ensure_ascii=False)}")
    if item.out_of_stock_text != DEFAULT_OUT_OF_STOCK:
        lines.append(f"{pad}out_of_stock_text: [{', '.join(json.dumps(t, ensure_ascii=False) for t in item.out_of_stock_text)}]")
    if item.target_price is not None:
        lines.append(f"{pad}target_price: {money(item.target_price)}")
    lines.append(f"{pad}notify_on: [{', '.join(item.notify_on or [])}]")
    if item.recipients:
        lines.append(f"{pad}recipients: [{', '.join(json.dumps(r) for r in item.recipients)}]")
    return lines


def _blocks(lines: list[str]) -> tuple[int, list[tuple[int, int, str]]]:
    """Return the index of `items:` and the (start, end, id) of each active product block."""
    items_at = next((i for i, line in enumerate(lines) if _ITEMS.match(line)), None)
    if items_at is None:
        raise EditError("watchlist.yaml has no 'items:' section")
    blocks: list[tuple[int, int, str]] = []
    i = items_at + 1
    while i < len(lines):
        match = _START.match(lines[i])
        if not match:
            i += 1
            continue
        start, base = i, len(match.group(1))
        end = start + 1
        while end < len(lines):
            line = lines[end]
            if not line.strip() or line.lstrip().startswith("#") or _indent(line) <= base:
                break
            end += 1
        try:
            name = yaml.safe_load(f"name: {match.group(2)}")["name"]
        except Exception:
            name = match.group(2)
        blocks.append((start, end, slugify(str(name))))
        i = end
    return items_at, blocks


def add_item(text: str, item: Item) -> str:
    lines = text.split("\n")
    items_at, blocks = _blocks(lines)
    indent = " " * (len(_START.match(lines[blocks[-1][0]]).group(1)) if blocks else 2)
    insert_at = blocks[-1][1] if blocks else items_at + 1
    new = ([""] if blocks else []) + render_item(item, indent=indent)
    return "\n".join(lines[:insert_at] + new + lines[insert_at:])


def replace_item(text: str, item_id: str, item: Item) -> str:
    lines = text.split("\n")
    _, blocks = _blocks(lines)
    for start, end, found in blocks:
        if found == item_id:
            indent = _START.match(lines[start]).group(1)
            return "\n".join(lines[:start] + render_item(item, indent=indent) + lines[end:])
    raise EditError(f"'{item_id}' is not in watchlist.yaml")


def remove_item(text: str, item_id: str) -> str:
    lines = text.split("\n")
    _, blocks = _blocks(lines)
    if len(blocks) <= 1:
        raise EditError("A watchlist needs at least one product, so the last one can't be removed.")
    for start, end, found in blocks:
        if found == item_id:
            if start > 0 and not lines[start - 1].strip():
                start -= 1  # take the blank separator line with it
            return "\n".join(lines[:start] + lines[end:])
    raise EditError(f"'{item_id}' is not in watchlist.yaml")


def write_validated(path: Path, new_text: str) -> None:
    """Validate with the real loader, keep a .bak of the old file, then replace it atomically."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(new_text)
        try:
            load_watchlist(tmp)
        except ConfigError as exc:
            raise EditError(_clean(str(exc), tmp)) from None
        if path.is_file():
            path.with_name(path.name + ".bak").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _clean(message: str, tmp: str) -> str:
    lines = [line.strip().lstrip("- ").strip() for line in message.splitlines()[1:]] or [message]
    return "; ".join(line for line in lines if line)
