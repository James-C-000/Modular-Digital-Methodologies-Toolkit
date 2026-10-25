"""Atomic file downloads.

Everything is written to ``<dest>.part`` and renamed into place only once the
transfer is complete, so an interrupted or failed download never leaves a
file that looks installed.  Downloads to the same destination run one at a
time (``destination_lock``): two at once would share, and delete, one
``.part``.
"""
import contextlib
import os
import shutil
import threading
import time
import urllib.request

# Partial downloads untouched for this long are leftovers of a crash; a live
# download writes to its .part every few seconds (a stall times out in 60 s).
STALE_PART_SECONDS = 3600

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


@contextlib.contextmanager
def destination_lock(dest: str):
    """Hold while downloading to *dest*, so one download to it runs at a time in this process."""
    key = os.path.normcase(os.path.abspath(dest))
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        yield


def user_agent() -> str:
    """Identify MDMT to servers; some (e.g. the Argos model host) refuse Python's default."""
    from version import __version__
    return f"MDMT/{__version__} (+https://github.com/James-C-000/Modular-Digital-Methodologies-Toolkit)"


def download_file(url: str, dest: str, on_progress=None, timeout: float = 60) -> str:
    """Download *url* to *dest* atomically and return *dest*.

    ``on_progress(done_bytes, total_bytes_or_None)`` is called as data
    arrives.  On any failure the partial file is removed and the exception
    propagates.
    """
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    part = dest + ".part"
    with destination_lock(dest):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": user_agent()})
            with urllib.request.urlopen(request, timeout=timeout) as response, open(part, "wb") as out:
                total = response.headers.get("Content-Length")
                total = int(total) if total and total.isdigit() else None
                done = 0
                while chunk := response.read(1 << 16):
                    out.write(chunk)
                    done += len(chunk)
                    if on_progress:
                        on_progress(done, total)
            if total is not None and done != total:
                raise IOError(f"incomplete download: got {done} of {total} bytes")
            os.replace(part, dest)
        except BaseException:
            try:
                os.remove(part)
            except OSError:
                pass
            raise
    return dest


def _last_modified(path: str) -> float:
    """Newest modification time of *path* or, for a folder, of anything in it."""
    newest = os.path.getmtime(path)
    for root, dirs, names in os.walk(path):
        for name in dirs + names:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
            except OSError:
                pass
    return newest


def remove_stale_parts(directory: str, min_age: float = STALE_PART_SECONDS):
    """Delete ``*.part`` and ``*.download`` leftovers (files or dirs) from an earlier crash.

    Only those untouched for *min_age* seconds: a newer one may belong to a
    download still running in another MDMT window.
    """
    try:
        names = os.listdir(directory)
    except OSError:
        return
    now = time.time()
    for name in names:
        if name.endswith((".part", ".download")):
            path = os.path.join(directory, name)
            try:
                if now - _last_modified(path) < min_age:
                    continue
            except OSError:
                continue
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass
