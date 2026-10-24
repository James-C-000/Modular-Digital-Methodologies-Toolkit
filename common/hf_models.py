"""Atomic downloads of pinned Hugging Face model files, with byte progress."""
import os
import shutil
import threading

POLL_SECONDS = 0.5


def is_snapshot_complete(dest: str, files) -> bool:
    return all(os.path.isfile(os.path.join(dest, f)) for f in files)


def remote_sizes(repo_id: str, revision: str, files) -> dict:
    """Byte size of each file at *revision* (one Hub API call); {} if unavailable."""
    try:
        from huggingface_hub import HfApi
        infos = HfApi().get_paths_info(repo_id, list(files), revision=revision)
        return {i.path: i.size for i in infos if getattr(i, "size", None)}
    except Exception:
        return {}


def _use_plain_http():
    """Download over plain HTTP instead of the Xet protocol.

    Xet assembles each file outside the target folder and keeps a chunk cache
    in ~/.cache/huggingface, so progress could not be shown and the space used
    would sit outside MDMT's folder (invisible to the Downloads page, never
    deleted).  Plain HTTP was as fast in testing.  The flag is read at download
    time, so setting it here works whatever imported huggingface_hub first.
    """
    try:
        from huggingface_hub import constants
        constants.HF_HUB_DISABLE_XET = True
    except ImportError:
        pass


def _bytes_under(folder: str) -> int:
    total = 0
    for root, _dirs, names in os.walk(folder):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def download_snapshot(repo_id: str, revision: str, files, dest: str, on_progress=None) -> str:
    """Download *files* of *repo_id* at a pinned *revision* into *dest*.

    Files go to ``<dest>.part`` first; the directory is renamed only after
    every file has arrived, so an interrupted download never looks installed.
    ``on_progress(done_bytes, total_bytes_or_None)`` is called while it runs
    (bytes on disk, including huggingface_hub's .incomplete files).
    Returns *dest*.  Already-complete downloads are left alone.
    """
    from huggingface_hub import snapshot_download

    if is_snapshot_complete(dest, files):
        return dest
    _use_plain_http()
    part = dest + ".part"
    shutil.rmtree(part, ignore_errors=True)
    finished = threading.Event()
    total = None
    if on_progress:
        sizes = remote_sizes(repo_id, revision, files)
        total = sum(sizes.values()) if len(sizes) == len(list(files)) else None

        def poll():
            while not finished.wait(POLL_SECONDS):
                on_progress(min(_bytes_under(part), total or 1 << 62), total)

        threading.Thread(target=poll, name="hf-progress", daemon=True).start()
    try:
        snapshot_download(repo_id=repo_id, revision=revision, allow_patterns=list(files), local_dir=part)
        shutil.rmtree(os.path.join(part, ".cache"), ignore_errors=True)
        if not is_snapshot_complete(part, files):
            missing = [f for f in files if not os.path.isfile(os.path.join(part, f))]
            raise FileNotFoundError(f"{repo_id}@{revision[:10]} is missing {missing}")
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        os.replace(part, dest)
    except BaseException:
        shutil.rmtree(part, ignore_errors=True)
        raise
    finally:
        finished.set()
    if on_progress:
        done = _bytes_under(dest)
        on_progress(done, total or done)
    return dest


def download_file(repo_id: str, revision: str, filename: str, target: str, on_progress=None) -> str:
    """Download one file of *repo_id* at *revision* to the path *target* (atomically)."""
    if os.path.isfile(target):
        return target
    staging = target + ".download"
    try:
        download_snapshot(repo_id, revision, [filename], staging, on_progress)
        os.replace(os.path.join(staging, filename), target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target
