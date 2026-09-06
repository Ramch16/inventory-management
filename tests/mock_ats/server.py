"""A local HTTP server that imitates the DOM shape of real ATS application forms.

Browser tests run only against this. Submitting test applications to real employers is
prohibited, and nothing here talks to a real ATS.

The server also implements a working submit: a POST records what was sent and returns
either the confirmation page or the no-confirmation page, so the confirmation-capture
path is exercised for real rather than mocked out.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SITES = Path(__file__).parent / "sites"

ROUTES: dict[str, str] = {
    "/greenhouse": "greenhouse.html",
    "/lever": "lever.html",
    "/workday": "workday.html",
    "/generic": "generic.html",
    "/generic-ambiguous": "generic_ambiguous.html",
    "/captcha": "captcha.html",
    "/otp": "otp.html",
    "/confirmation": "confirmation.html",
}


@dataclass
class Submission:
    path: str
    fields: dict[str, list[str]] = field(default_factory=dict)


class MockAtsServer:
    """Serves the mock sites on an ephemeral port."""

    def __init__(self) -> None:
        self.submissions: list[Submission] = []
        #: When set, a submission returns a page with no confirmation text, so the
        #: runner has to report SUBMISSION_UNCONFIRMED.
        self.suppress_confirmation = False
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None, "server is not running"
        host, port = self._server.server_address[:2]
        return f"http://127.0.0.1:{port}"

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def start(self) -> MockAtsServer:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: A003 - silence the default stderr log
                return

            def _send(self, body: bytes, status: int = 200) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                path = urlparse(self.path).path.rstrip("/") or "/"
                filename = ROUTES.get(path)
                if filename is None:
                    self._send(b"<html><body>Not found</body></html>", 404)
                    return
                self._send((SITES / filename).read_bytes())

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                content_type = self.headers.get("Content-Type", "")
                fields: dict[str, list[str]] = {}
                if content_type.startswith("application/x-www-form-urlencoded"):
                    fields = parse_qs(raw)
                elif "multipart/form-data" in content_type:
                    # Enough parsing to assert which fields were sent.
                    for chunk in raw.split("\r\n\r\n"):
                        if 'name="' in chunk:
                            name = chunk.split('name="', 1)[1].split('"', 1)[0]
                            fields.setdefault(name, [])
                outer.submissions.append(Submission(path=urlparse(self.path).path, fields=fields))
                page = (
                    "no_confirmation.html" if outer.suppress_confirmation else "confirmation.html"
                )
                self._send((SITES / page).read_bytes())

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> MockAtsServer:
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()
