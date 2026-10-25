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


def test_a_log_file_that_cannot_be_rotated_keeps_logging(no_streams, monkeypatch):
    """On Windows the rename fails while another program has mdmt.log open.  logging then reported the
    error on stderr -- the log stream itself -- and every later log call raised RecursionError."""
    _setup(monkeypatch, no_streams)
    handler = next(h for h in logging.getLogger().handlers if getattr(h, "_mdmt", False))
    logging.getLogger("mdmt").info("x" * 100)
    calls = []

    def locked(source, dest):
        calls.append(source)
        raise PermissionError(32, "The process cannot access the file because it is being used")

    monkeypatch.setattr(handler, "rotate", locked)
    monkeypatch.setattr(handler, "maxBytes", 10)
    logging.getLogger("mdmt.jobs").info("job started")
    logging.getLogger("mdmt.jobs").info("job finished")
    assert len(calls) == 1                     # tried once, then again only minutes later
    text = _read(no_streams)
    assert "job started" in text and "job finished" in text


def test_text_written_to_stderr_while_logging_is_dropped_not_recursed(no_streams, monkeypatch):
    _setup(monkeypatch, no_streams)

    class Echo(logging.Handler):   # a handler that writes to stderr, which is our log stream
        def emit(self, record):
            sys.stderr.write(f"echo: {record.getMessage()}\n")

    echo = Echo()
    logging.getLogger("stderr").addHandler(echo)
    try:
        sys.stderr.write("from stderr\n")
    finally:
        logging.getLogger("stderr").removeHandler(echo)
    assert "from stderr" in _read(no_streams)
