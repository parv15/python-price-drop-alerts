"""Connect WebApp to HTTP with the standard library. Meant for one person on their own machine."""

from __future__ import annotations

import logging
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .app import WebApp, parse_request

log = logging.getLogger("price_alerts.web")
MAX_BODY = 64 * 1024


def make_handler(app: WebApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PriceAlerts"
        sys_version = ""

        def _serve(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self.send_error(413, "Request too large")
                return
            body = self.rfile.read(length) if length else b""
            response = app.handle(parse_request(method, self.path, dict(self.headers.items()), body))
            data = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(data)))
            for name, value in response.headers:
                self.send_header(name, value)
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self._serve("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._serve("POST")

        def log_message(self, fmt: str, *args: object) -> None:
            log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def serve(watchlist: Path, data_dir: Path, *, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> int:
    loopback = host in ("127.0.0.1", "localhost", "::1")
    app = WebApp(watchlist, data_dir, allowed_hosts=None if loopback else set())
    try:
        httpd = ThreadingHTTPServer((host, port), make_handler(app))
    except OSError as exc:
        log.error("Could not listen on %s:%s: %s", host, port, exc)
        return 1
    url = f"http://{'localhost' if loopback else host}:{port}/"
    print(f"Price Alerts dashboard: {url}   (Ctrl+C to stop)")
    if not loopback:
        print("Warning: the dashboard has no login. Anyone who can reach this address can edit your watchlist.")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0
