"""Pinned Hugging Face downloads: atomic, with byte progress (no network)."""
import os
import sys
import time
import types

import pytest

from common import hf_models


@pytest.fixture
def fake_hub(monkeypatch):
    """snapshot_download that writes each file in pieces, slowly enough to be polled."""
    calls = []

    def snapshot_download(repo_id, revision, allow_patterns, local_dir):
        calls.append((repo_id, revision, tuple(allow_patterns)))
        for name in allow_patterns:
            path = os.path.join(local_dir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                for _ in range(4):
                    f.write(b"x" * 250)
                    f.flush()
                    time.sleep(0.06)
        return local_dir

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=snapshot_download))
    monkeypatch.setattr(hf_models, "remote_sizes", lambda repo, rev, files: {f: 1000 for f in files})
    monkeypatch.setattr(hf_models, "POLL_SECONDS", 0.02)
    return calls


def test_snapshot_reports_bytes_and_lands_atomically(tmp_path, fake_hub):
    seen = []
    dest = tmp_path / "model"
    hf_models.download_snapshot("org/m", "abc123", ["a.bin", "onnx/b.onnx"], str(dest),
                                on_progress=lambda done, total: seen.append((done, total)))
    assert sorted(os.listdir(dest)) == ["a.bin", "onnx"] and not os.path.exists(str(dest) + ".part")
    assert seen[-1] == (2000, 2000)
    assert any(0 < done < 2000 for done, _t in seen)          # intermediate progress was seen
    assert all(t == 2000 for _d, t in seen)


def test_complete_snapshot_is_not_downloaded_again(tmp_path, fake_hub):
    dest = tmp_path / "model"
    hf_models.download_snapshot("org/m", "abc123", ["a.bin"], str(dest))
    hf_models.download_snapshot("org/m", "abc123", ["a.bin"], str(dest))
    assert len(fake_hub) == 1


def test_single_file_goes_next_to_other_models(tmp_path, fake_hub):
    target = tmp_path / "models" / "Model-Q4.gguf"
    hf_models.download_file("org/gguf", "def456", "Model-Q4.gguf", str(target))
    assert target.stat().st_size == 1000
    assert os.listdir(tmp_path / "models") == ["Model-Q4.gguf"]   # no staging folder left behind


def test_failed_download_leaves_nothing(tmp_path, monkeypatch, fake_hub):
    def broken(**kwargs):
        os.makedirs(kwargs["local_dir"], exist_ok=True)
        open(os.path.join(kwargs["local_dir"], "a.bin"), "wb").write(b"half")
        raise ConnectionError("offline")

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=broken))
    with pytest.raises(ConnectionError):
        hf_models.download_file("org/gguf", "def456", "a.bin", str(tmp_path / "a.bin"))
    assert os.listdir(tmp_path) == []


def test_downloads_avoid_the_xet_cache(tmp_path, monkeypatch, fake_hub):
    constants = types.SimpleNamespace(HF_HUB_DISABLE_XET=False)
    sys.modules["huggingface_hub"].constants = constants
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    hf_models.download_snapshot("org/m", "abc123", ["a.bin"], str(tmp_path / "m"))
    assert constants.HF_HUB_DISABLE_XET is True


class FakeRateLimit(Exception):
    """Shaped like huggingface_hub's HfHubHTTPError for a 429."""

    def __init__(self, retry_after="2"):
        super().__init__("429 Too Many Requests")
        self.response = types.SimpleNamespace(status_code=429, headers={"Retry-After": retry_after})


def test_rate_limits_are_waited_out(tmp_path, monkeypatch, fake_hub):
    real = sys.modules["huggingface_hub"].snapshot_download
    failures = [FakeRateLimit("3"), FakeRateLimit()]

    def flaky(**kwargs):
        if failures:
            raise failures.pop(0)
        return real(**kwargs)

    sys.modules["huggingface_hub"].snapshot_download = flaky
    waits = []
    monkeypatch.setattr(hf_models.time, "sleep", waits.append)
    hf_models.download_snapshot("org/m", "abc123", ["a.bin"], str(tmp_path / "m"))
    assert (tmp_path / "m" / "a.bin").exists() and waits[:2] == [3, 2]   # then the fake hub's own pauses


def test_rate_limits_give_up_eventually(tmp_path, monkeypatch, fake_hub):
    def always(**kwargs):
        raise FakeRateLimit()

    sys.modules["huggingface_hub"].snapshot_download = always
    monkeypatch.setattr(hf_models.time, "sleep", lambda s: None)
    with pytest.raises(FakeRateLimit):
        hf_models.download_snapshot("org/m", "abc123", ["a.bin"], str(tmp_path / "m"))
    assert not (tmp_path / "m").exists() and not (tmp_path / "m.part").exists()
