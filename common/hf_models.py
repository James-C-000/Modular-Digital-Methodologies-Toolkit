"""Atomic downloads of pinned Hugging Face model files."""
import os
import shutil


def is_snapshot_complete(dest: str, files) -> bool:
    return all(os.path.isfile(os.path.join(dest, f)) for f in files)


def download_snapshot(repo_id: str, revision: str, files, dest: str) -> str:
    """Download *files* of *repo_id* at a pinned *revision* into *dest*.

    Files go to ``<dest>.part`` first; the directory is renamed only after
    every file has arrived, so an interrupted download never looks installed.
    Returns *dest*.  Already-complete downloads are left alone.
    """
    from huggingface_hub import snapshot_download

    if is_snapshot_complete(dest, files):
        return dest
    part = dest + ".part"
    shutil.rmtree(part, ignore_errors=True)
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
    return dest
