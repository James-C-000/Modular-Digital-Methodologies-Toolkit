"""Access control for MDMT's local web server.

On Linux MDMT runs in the user's browser rather than a native window.  A
localhost port is reachable by every local user and, through DNS rebinding, by
web pages, and MDMT can read and write files, so the server:

- binds 127.0.0.1 only;
- rejects requests whose Host header is not 127.0.0.1/localhost on our port
  (DNS rebinding sends the victim's cookies to an attacker-named host);
- requires a random per-launch token.  The launch URL carries it once
  (``?token=...``); MDMT swaps it for an HttpOnly, SameSite=Strict cookie and
  redirects to the same URL without the token.  A second MDMT launch talks to
  the first with an ``X-MDMT-Token`` header.

The Host check also applies in native-window mode (no token there: pywebview
loads the page itself).
"""
import secrets
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode

COOKIE = "mdmt_token"
HEADER = b"x-mdmt-token"

_FORBIDDEN_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>MDMT</title>"
    "<p style='font-family:sans-serif'>This MDMT window has expired or was opened without its "
    "access link. Start MDMT again from its launcher; it will open a new tab.</p>"
).encode("utf-8")


def new_token() -> str:
    return secrets.token_urlsafe(32)


class LocalAccessMiddleware:
    """Pure ASGI middleware guarding HTTP and websocket traffic."""

    def __init__(self, app, port: int, token: str | None):
        self.app = app
        self.token = token
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        if headers.get(b"host", b"").decode("latin-1").lower() not in self.allowed_hosts:
            return await self._reject(scope, receive, send, 400, b"Bad Host header")
        if self.token is None:
            return await self.app(scope, receive, send)

        if headers.get(HEADER, b"").decode("latin-1") == self.token or self._cookie_ok(headers):
            return await self.app(scope, receive, send)

        query = dict(parse_qsl(scope.get("query_string", b"").decode("latin-1")))
        if scope["type"] == "http" and secrets.compare_digest(query.get("token", ""), self.token):
            rest = urlencode({k: v for k, v in query.items() if k != "token"})
            location = scope.get("path", "/") + (f"?{rest}" if rest else "")
            cookie = f"{COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict"
            await send({"type": "http.response.start", "status": 302,
                        "headers": [(b"location", location.encode("latin-1")),
                                    (b"set-cookie", cookie.encode("latin-1")),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b""})
            return
        return await self._reject(scope, receive, send, 403, _FORBIDDEN_PAGE)

    def _cookie_ok(self, headers) -> bool:
        raw = headers.get(b"cookie", b"").decode("latin-1")
        if not raw:
            return False
        try:
            morsel = SimpleCookie(raw).get(COOKIE)
        except Exception:
            return False
        return morsel is not None and secrets.compare_digest(morsel.value, self.token)

    @staticmethod
    async def _reject(scope, receive, send, status: int, body: bytes):
        if scope["type"] == "websocket":
            await receive()  # websocket.connect
            await send({"type": "websocket.close", "code": 1008})
            return
        content_type = b"text/html; charset=utf-8" if body.startswith(b"<!doctype") else b"text/plain"
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", content_type), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})
