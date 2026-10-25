"""Single-instance lock for browser mode.

The running instance records its pid, port and access token in a lock file in
the app data folder (readable only by the user).  A second launch finds it,
checks that the process is alive and the server answers, and opens a new
browser tab on the existing instance instead of starting another server.
The file is created exclusively (claim_lock), so of two launches at once
only one starts a server; the other waits for it to answer.
"""
import json
import os
import time
import urllib.request

LOCK_NAME = "instance.json"


def lock_path() -> str:
    from config import get_app_data_dir
    return os.path.join(get_app_data_dir(), LOCK_NAME)


def claim_lock(path: str, port: int, token: str) -> bool:
    """Create the lock file for this process; False if it exists (another instance, or a stale file)."""
    try:
        write_lock(path, port, token, exclusive=True)
    except FileExistsError:
        return False
    return True


def remove_lock(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


def write_lock(path: str, port: int, token: str, exclusive: bool = False):
    data = json.dumps({"pid": os.getpid(), "port": port, "token": token})
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_lock(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if {"pid", "port", "token"} <= set(data) else None
    except (OSError, ValueError):
        return None


def clear_lock(path: str):
    data = read_lock(path)
    if data is None or data.get("pid") == os.getpid():
        try:
            os.remove(path)
        except OSError:
            pass


def _alive(pid: int) -> bool:
    import psutil
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False


def running_instance_url(path: str, wait: float = 0.0) -> str | None:
    """Launch URL (with token) of a live MDMT instance, or None.

    With *wait*, keeps trying that long while the instance is alive but its
    server does not answer yet (it is starting), or its lock file is still
    being written.
    """
    deadline = time.monotonic() + wait
    while True:
        data = read_lock(path)
        if data is not None and _alive(int(data["pid"])):
            url = _answering_url(data)
            if url:
                return url
        elif data is not None or not os.path.exists(path):
            return None   # the process is gone, or there is no lock
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.25)


def _answering_url(data: dict) -> str | None:
    base = f"http://127.0.0.1:{int(data['port'])}"
    request = urllib.request.Request(f"{base}/_mdmt/ping", headers={"X-MDMT-Token": data["token"]})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if json.load(response).get("app") != "mdmt":
                return None
    except Exception:
        return None
    return f"{base}/?token={data['token']}"
