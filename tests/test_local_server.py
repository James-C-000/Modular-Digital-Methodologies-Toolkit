"""Browser mode (Linux): token + Host checks and the single-instance lock."""
import json
import os
import sys

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from common import instance
from common.local_server import COOKIE, LocalAccessMiddleware

TOKEN = "s3cret-token"
PORT = 8765


def _app(token=TOKEN):
    async def home(request):
        return PlainTextResponse("the page")

    async def ws(websocket):
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    app = Starlette(routes=[Route("/", home), Route("/ocr", home), WebSocketRoute("/ws", ws)])
    app.add_middleware(LocalAccessMiddleware, port=PORT, token=token)
    return app


def _client(token=TOKEN, host=f"127.0.0.1:{PORT}"):
    return TestClient(_app(token), base_url=f"http://{host}", follow_redirects=False)


def test_request_without_token_is_rejected():
    r = _client().get("/")
    assert r.status_code == 403 and "the page" not in r.text


def test_token_link_sets_an_httponly_cookie_and_redirects_without_the_token():
    c = _client()
    r = c.get(f"/ocr?token={TOKEN}")
    assert r.status_code == 302 and r.headers["location"] == "/ocr"
    cookie = r.headers["set-cookie"]
    assert f"{COOKIE}={TOKEN}" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict")
    assert c.get("/ocr").text == "the page"  # cookie now carried


def test_wrong_token_is_rejected():
    assert _client().get("/?token=nope").status_code == 403


def test_header_token_works_for_the_second_instance():
    assert _client().get("/", headers={"X-MDMT-Token": TOKEN}).text == "the page"


@pytest.mark.parametrize("host", ["evil.example:8765", "127.0.0.1:9999", "192.168.1.5:8765", "localhost.evil:8765"])
def test_foreign_host_headers_are_rejected_even_with_the_token(host):
    """DNS rebinding: a web page can make the browser send our cookie to a renamed host."""
    r = _client(host=host).get(f"/?token={TOKEN}")
    assert r.status_code == 400


def test_localhost_name_is_accepted():
    assert _client(host=f"localhost:{PORT}").get(f"/?token={TOKEN}").status_code == 302


def test_websocket_requires_the_cookie():
    # TestClient sends "Host: testserver" and no cookies on websockets, so both
    # are given explicitly (browsers send them automatically).
    c = _client()
    host = {"host": f"127.0.0.1:{PORT}"}
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers=host) as ws:
            ws.receive_text()
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={**host, "cookie": f"{COOKIE}=wrong"}) as ws:
            ws.receive_text()
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"host": "evil.example:8765", "cookie": f"{COOKIE}={TOKEN}"}) as ws:
            ws.receive_text()
    with c.websocket_connect("/ws", headers={**host, "cookie": f"other=1; {COOKIE}={TOKEN}"}) as ws:
        assert ws.receive_text() == "hello"


def test_without_a_token_only_the_host_is_checked():
    """Native-window mode: pywebview loads the page directly; Host checks still apply."""
    assert _client(token=None).get("/").text == "the page"
    assert _client(token=None, host="evil.example:8765").get("/").status_code == 400


class TestInstanceLock:
    def test_write_read_and_clear(self, tmp_path):
        path = str(tmp_path / "instance.json")
        instance.write_lock(path, port=PORT, token=TOKEN)
        data = instance.read_lock(path)
        assert data["port"] == PORT and data["token"] == TOKEN and data["pid"] == os.getpid()
        if sys.platform != "win32":
            assert oct(os.stat(path).st_mode & 0o777) == "0o600"
        instance.clear_lock(path)
        assert instance.read_lock(path) is None

    def test_stale_lock_from_a_dead_process_is_ignored(self, tmp_path):
        path = tmp_path / "instance.json"
        path.write_text(json.dumps({"pid": 999_999_999, "port": PORT, "token": TOKEN}), encoding="utf-8")
        assert instance.running_instance_url(str(path)) is None

    def test_live_lock_whose_server_does_not_answer_is_ignored(self, tmp_path):
        path = str(tmp_path / "instance.json")
        instance.write_lock(path, port=1, token=TOKEN)  # our own pid, but nothing on port 1
        assert instance.running_instance_url(path) is None

    def test_corrupt_lock(self, tmp_path):
        path = tmp_path / "instance.json"
        path.write_text("{not json", encoding="utf-8")
        assert instance.read_lock(str(path)) is None
