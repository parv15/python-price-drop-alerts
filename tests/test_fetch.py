"""HttpFetcher against httpx.MockTransport: no network."""

import httpx
import pytest

from price_alerts.fetch import USER_AGENT, FetchError, HttpFetcher


def make(handler, **kwargs):
    sleeps: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})
    fetcher = HttpFetcher(client=client, sleep=sleeps.append, monotonic=lambda: 100.0, **kwargs)
    return fetcher, sleeps


def test_retries_once_on_5xx_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(503 if calls.count("/p") == 1 else 200, text="<html>ok</html>")

    fetcher, sleeps = make(handler, delay=5)
    assert fetcher.get("https://shop.example/p") == "<html>ok</html>"
    assert calls == ["/robots.txt", "/p", "/p"]
    assert sleeps == [5, 5]  # politeness delay between requests to the same host


def test_gives_up_after_one_retry_on_network_error():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectError("no route")

    fetcher, _ = make(handler, delay=0)
    with pytest.raises(FetchError, match="Network error"):
        fetcher.get("https://shop.example/p")


def test_4xx_is_a_failure_without_retry():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(404)

    fetcher, _ = make(handler, delay=0, respect_robots_txt=False)
    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.get("https://shop.example/p")
    assert calls == ["/p"]


def test_robots_txt_disallow_is_a_clear_failure():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200, text="page")

    fetcher, _ = make(handler, delay=0)
    with pytest.raises(FetchError, match="robots.txt"):
        fetcher.get("https://shop.example/private/item")
    assert fetcher.get("https://shop.example/public/item") == "page"


def test_user_agent_identifies_the_project():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(200, text="x")

    fetcher, _ = make(handler, delay=0, respect_robots_txt=False)
    fetcher.get("https://shop.example/p")
    assert seen["ua"].startswith("python-price-drop-alerts/1.0 (+https://github.com/")
