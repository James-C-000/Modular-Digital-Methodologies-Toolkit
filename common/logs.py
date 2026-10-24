"""Log file setup, including the windowed-build stdout/stderr fallback.

A PyInstaller app built with ``console=False`` (the Windows build) starts with
``sys.stdout`` and ``sys.stderr`` set to ``None``.  Anything that writes to
them -- tqdm progress bars during Hugging Face downloads, print(), uvicorn's
log handler -- then raises ``AttributeError: 'NoneType' object has no
attribute 'write'``.  ``setup_logging()`` replaces missing streams with
writers that feed a UTF-8 rotating log file, and routes ``logging`` there too.
"""
import io
import logging
import logging.handlers
import os
import sys
import threading

LOG_NAME = "mdmt.log"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUPS = 3

# Names of std streams that were None at startup (windowed builds); read by
# the self-test to prove the fallback path was exercised.
ORIGINALLY_MISSING_STREAMS: list[str] = []


def get_log_dir() -> str:
    from config import get_app_data_dir
    path = os.path.join(get_app_data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


class _LogStream(io.TextIOBase):
    """Minimal text stream that forwards complete lines to a logger.

    Carriage returns (tqdm redraws) are treated as line ends so a progress bar
    becomes a handful of log lines instead of one enormous one.
    """

    encoding = "utf-8"
    errors = "replace"

    def __init__(self, logger: logging.Logger, level: int):
        super().__init__()
        self._logger = logger
        self._level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise io.UnsupportedOperation("log stream has no file descriptor")

    def write(self, text) -> int:
        if not isinstance(text, str):
            text = text.decode("utf-8", "replace")
        with self._lock:
            self._buffer += text.replace("\r", "\n")
            *lines, self._buffer = self._buffer.split("\n")
        for line in lines:
            if line.strip():
                self._logger.log(self._level, line.rstrip())
        return len(text)

    def flush(self):
        with self._lock:
            line, self._buffer = self._buffer, ""
        if line.strip():
            self._logger.log(self._level, line.rstrip())


def setup_logging(log_dir: str | None = None, level: int = logging.INFO) -> str:
    """Send ``logging`` to a rotating file and patch any missing std streams.

    Safe to call more than once.  Returns the log file path.
    """
    log_dir = log_dir or get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, LOG_NAME)

    root = logging.getLogger()
    handler = next((h for h in root.handlers if getattr(h, "_mdmt", False)), None)
    if handler is None:
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8",
        )
        handler._mdmt = True
        handler.setFormatter(logging.Formatter("%(asctime)s %(process)d %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)

    # The stream loggers must not propagate: a StreamHandler created after the
    # redirect (uvicorn, logging.basicConfig) writes to these very streams, and
    # propagation would feed each record back into itself forever.
    for name, lvl in (("stdout", logging.INFO), ("stderr", logging.WARNING)):
        stream_logger = logging.getLogger(name)
        stream_logger.propagate = False
        stream_logger.setLevel(logging.INFO)
        if handler not in stream_logger.handlers:
            stream_logger.addHandler(handler)
        if getattr(sys, name) is None:
            ORIGINALLY_MISSING_STREAMS.append(name)
            setattr(sys, name, _LogStream(stream_logger, lvl))
    return path
