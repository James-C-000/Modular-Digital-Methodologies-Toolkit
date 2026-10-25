"""Partial downloads must never masquerade as installed assets."""
import http.server
import os
import threading
import time

import pytest

from common.downloads import STALE_PART_SECONDS, download_file, remove_stale_parts


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if not self.headers.get("User-Agent", "").startswith("MDMT/"):
            self.send_response(403)
            self.end_headers()
        elif self.path == "/ok":
            body = b"x" * 200_000
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", "200000")
            self.end_headers()
            self.wfile.write(b"x" * 1000)  # then hang up
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="module")
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_successful_download_lands_atomically(server, tmp_path):
    dest = tmp_path / "fra.traineddata"
    seen = []
    download_file(f"{server}/ok", str(dest), on_progress=lambda d, t: seen.append((d, t)))
    assert dest.stat().st_size == 200_000
    assert not (tmp_path / "fra.traineddata.part").exists()
    assert seen[-1] == (200_000, 200_000)


@pytest.mark.parametrize("path", ["/truncated", "/missing"])
def test_failed_download_leaves_nothing_behind(server, tmp_path, path):
    dest = tmp_path / "fra.traineddata"
    with pytest.raises(Exception):
        download_file(f"{server}{path}", str(dest))
    assert os.listdir(tmp_path) == []


def test_remove_stale_parts(tmp_path):
    (tmp_path / "a.traineddata.part").write_bytes(b"x")
    (tmp_path / "tiny.part").mkdir()
    (tmp_path / "eng.traineddata").write_bytes(b"x")
    old = time.time() - 2 * STALE_PART_SECONDS
    for name in ("a.traineddata.part", "tiny.part"):
        os.utime(tmp_path / name, (old, old))
    remove_stale_parts(str(tmp_path))
    assert os.listdir(tmp_path) == ["eng.traineddata"]


def test_remove_stale_parts_keeps_a_download_still_running(tmp_path):
    """Another MDMT window may be downloading: a .part written to recently stays."""
    (tmp_path / "fra.traineddata.part").write_bytes(b"x")
    snapshot = tmp_path / "Qwen.gguf.download"
    (snapshot / "Qwen.gguf.part" / ".cache").mkdir(parents=True)
    old = time.time() - 2 * STALE_PART_SECONDS
    os.utime(snapshot, (old, old))   # the folder is old, but a file inside is being written
    (snapshot / "Qwen.gguf.part" / ".cache" / "x.incomplete").write_bytes(b"x")
    remove_stale_parts(str(tmp_path))
    assert sorted(os.listdir(tmp_path)) == ["Qwen.gguf.download", "fra.traineddata.part"]


def test_downloads_to_one_destination_run_one_at_a_time(tmp_path):
    from common.downloads import destination_lock
    order, inside = [], threading.Event()

    def first():
        with destination_lock(str(tmp_path / "a")):
            inside.set()
            time.sleep(0.2)
            order.append("first done")

    t = threading.Thread(target=first)
    t.start()
    inside.wait(5)
    with destination_lock(str(tmp_path / "a")):
        order.append("second")
    t.join()
    assert order == ["first done", "second"]
