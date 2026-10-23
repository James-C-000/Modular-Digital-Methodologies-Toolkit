"""Windowed (console=False) builds start with sys.stdout/sys.stderr = None."""
import logging
import sys

import pytest

from common import logs


@pytest.fixture
def no_streams(monkeypatch, tmp_path):
    root = logging.getLogger()
    saved = list(root.handlers)
    yield tmp_path
    for h in list(root.handlers):
        if h not in saved:
            root.removeHandler(h)
            h.close()
    for name in ("stdout", "stderr"):
        lg = logging.getLogger(name)
        for h in list(lg.handlers):
            lg.removeHandler(h)


def _setup(monkeypatch, tmp_path):
    # Done in the test body: pytest's capture re-installs sys.stdout/stderr
    # between fixture setup and the call phase.
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    logs.setup_logging(str(tmp_path))


def _read(tmp_path):
    for h in logging.getLogger().handlers:
        h.flush()
    return (tmp_path / logs.LOG_NAME).read_text(encoding="utf-8")


def test_missing_streams_are_replaced_and_logged(no_streams, monkeypatch):
    _setup(monkeypatch, no_streams)
    assert sys.stdout is not None and sys.stderr is not None
    print("héllo wörld 日本語")
    sys.stderr.write("problem\n")
    assert "héllo wörld 日本語" in _read(no_streams)
    assert "problem" in _read(no_streams)


def test_tqdm_works_without_a_console(no_streams, monkeypatch):
    """The v2.0.7 crash: tqdm (used by Hugging Face downloads) writes to stderr."""
    _setup(monkeypatch, no_streams)
    from tqdm import tqdm
    for _ in tqdm(range(3), desc="downloading"):
        pass
    assert "downloading" in _read(no_streams)


def test_stream_handler_created_after_redirect_does_not_recurse(no_streams, monkeypatch):
    _setup(monkeypatch, no_streams)
    handler = logging.StreamHandler(sys.stderr)  # what uvicorn/basicConfig do
    logging.getLogger().addHandler(handler)
    try:
        logging.getLogger("x").warning("no infinite loop please")
    finally:
        logging.getLogger().removeHandler(handler)
    assert _read(no_streams).count("no infinite loop please") == 2  # direct + via the stream


def test_setup_is_idempotent(no_streams, monkeypatch):
    _setup(monkeypatch, no_streams)
    logs.setup_logging(str(no_streams))
    assert isinstance(sys.stderr, logs._LogStream)
    assert sum(getattr(h, "_mdmt", False) for h in logging.getLogger().handlers) == 1
