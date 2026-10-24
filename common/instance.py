"""Single-instance lock for browser mode.

The running instance records its pid, port and access token in a lock file in
the app data folder (readable only by the user).  A second launch finds it,
checks that the process is alive and the server answers, and opens a new
browser tab on the existing instance instead of starting another server.
"""
import json
import os
import urllib.request

LOCK_NAME = "instance.json"


def lock_path() -> str:
    from config import get_app_data_dir
    return os.path.join(get_app_data_dir(), LOCK_NAME)


def write_lock(path: str, port: int, token: str):
    data = json.dumps({"pid": os.getpid(), "port": port, "token": token})
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
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


def running_instance_url(path: str) -> str | None:
    """Launch URL (with token) of a live MDMT instance, or None."""
    data = read_lock(path)
    if data is None or not _alive(int(data["pid"])):
        return None
    base = f"http://127.0.0.1:{int(data['port'])}"
    request = urllib.request.Request(f"{base}/_mdmt/ping", headers={"X-MDMT-Token": data["token"]})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            if json.load(response).get("app") != "mdmt":
                return None
    except Exception:
        return None
    return f"{base}/?token={data['token']}"
