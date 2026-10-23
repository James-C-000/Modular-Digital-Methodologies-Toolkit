"""Atomic file downloads.

Everything is written to ``<dest>.part`` and renamed into place only once the
transfer is complete, so an interrupted or failed download never leaves a
file that looks installed.
"""
import os
import shutil
import urllib.request


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


def remove_stale_parts(directory: str):
    """Delete ``*.part`` leftovers (files or dirs) from an earlier crash."""
    try:
        names = os.listdir(directory)
    except OSError:
        return
    for name in names:
        if name.endswith(".part"):
            path = os.path.join(directory, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass
