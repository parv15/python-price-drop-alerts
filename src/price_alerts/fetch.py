"""HTTP fetching with a clear User-Agent, per-host politeness delay, one retry and robots.txt."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from . import __version__

log = logging.getLogger(__name__)

USER_AGENT = (
    f"python-price-drop-alerts/{__version__} "
    "(+https://github.com/manishgupta412/python-price-drop-alerts)"
)


class FetchError(Exception):
    """The page could not be fetched (network, HTTP status, robots.txt)."""


class Fetcher(Protocol):
    def get(self, url: str) -> str:
        """Return the page HTML or raise FetchError."""
        ...


class HttpFetcher:
    def __init__(
        self,
        *,
        timeout: float = 20,
        delay: float = 5,
        respect_robots_txt: bool = True,
        user_agent: str = USER_AGENT,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.delay = delay
        self.respect_robots_txt = respect_robots_txt
        self.user_agent = user_agent
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en;q=0.9,*;q=0.5",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpFetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, url: str) -> str:
        if self.respect_robots_txt and not self._allowed(url):
            raise FetchError(
                "Blocked by robots.txt for our User-Agent. Respect the site's wishes, "
                "or set respect_robots_txt: false only if you have permission."
            )
        response = self._request(url)
        if response.status_code >= 400:
            raise FetchError(f"HTTP {response.status_code} from {url}")
        return response.text

    def _request(self, url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in (1, 2):
            self._wait_for_host(url)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                log.debug("Attempt %d for %s failed: %s", attempt, url, exc)
                continue
            if response.status_code >= 500 and attempt == 1:
                log.debug("Attempt %d for %s got HTTP %d, retrying", attempt, url, response.status_code)
                continue
            return response
        raise FetchError(f"Network error fetching {url}: {type(last_error).__name__}: {last_error}")

    def _wait_for_host(self, url: str) -> None:
        host = urlsplit(url).netloc.lower()
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.delay - (self._monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._monotonic()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = self._load_robots(origin)
            self._robots[origin] = parser
        return parser.can_fetch(self.user_agent, url)

    def _load_robots(self, origin: str) -> RobotFileParser:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser(robots_url)
        try:
            self._wait_for_host(robots_url)
            response = self._client.get(robots_url)
        except httpx.HTTPError as exc:
            # Same behaviour as most crawlers: unreachable robots.txt means no rules.
            log.warning("Could not fetch %s (%s); assuming allowed", robots_url, exc)
            parser.allow_all = True
            return parser
        if response.status_code in (401, 403):
            parser.disallow_all = True
        elif response.status_code >= 400:
            parser.allow_all = True
        else:
            parser.parse(response.text.splitlines())
        return parser
