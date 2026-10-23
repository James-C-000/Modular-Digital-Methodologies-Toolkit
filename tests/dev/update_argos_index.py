"""Regenerate Translation/argos_index.json from the Argos package index (dev-only).

    python tests/dev/update_argos_index.py

Pins the index to the current commit of argosopentech/argospm-index and records
each package's download size (HTTP HEAD), so the app can list translation
pairs and sizes without a network round trip. Review the diff before committing.
"""
import concurrent.futures
import json
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from common.downloads import user_agent  # noqa: E402

REPO = "argosopentech/argospm-index"
OUT = os.path.join(ROOT, "Translation", "argos_index.json")


def _get(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": user_agent()})
    return urllib.request.urlopen(req, timeout=60)


def main():
    with _get(f"https://api.github.com/repos/{REPO}/commits/main") as r:
        sha = json.load(r)["sha"]
    with _get(f"https://raw.githubusercontent.com/{REPO}/{sha}/index.json") as r:
        index = json.load(r)

    def entry(pkg):
        url = next(u for u in pkg["links"] if u.startswith("https://"))
        with _get(url, "HEAD") as r:
            size = int(r.headers["Content-Length"])
        return {k: pkg[k] for k in ("code", "from_code", "from_name", "to_code", "to_name", "package_version")} | {
            "url": url, "size": size}

    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        packages = sorted(ex.map(entry, index), key=lambda p: (p["from_name"], p["to_name"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": f"https://github.com/{REPO}/blob/{sha}/index.json", "packages": packages},
                  f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"{len(packages)} packages, {sum(p['size'] for p in packages) / 1e9:.1f} GB -> {OUT}")


if __name__ == "__main__":
    main()
