"""Collect the licence texts of everything a frozen build bundles, verbatim.

THIRD_PARTY_LICENSES gives each licence once, with the families' standard
texts; but BSD, MIT-CMU, PSF, FreeType, libjpeg and other licences require
each component's own copyright notice to accompany binaries, and the wheels
MDMT bundles carry native libraries (OpenBLAS, libgfortran, FreeType, qpdf,
PDFium ...) whose notices only the wheels themselves hold.  At build time the
specs call collect_licenses(), which copies into the bundle's ``licenses/``
folder:

- for every package in the platform's runtime lock (plus llama-cpp-python),
  the licence files its wheel ships (its METADATA ``License-File`` entries,
  everything in ``.dist-info/licenses/``, and LICENSE/COPYING/NOTICE files in
  its package folder): ``licenses/python/<package>/...``;
- CPython's own LICENSE.txt (the interpreter and standard library):
  ``licenses/python/CPython/LICENSE.txt``;
- the copyright files of the system libraries bundled with Tesseract: on
  Linux from their Debian packages (``/usr/share/doc/<package>/copyright``),
  on macOS from their Homebrew kegs, on Windows whatever licence files the
  Tesseract-OCR installation holds: ``licenses/system/<package>/...``;

and writes ``licenses/README.txt``, an index of what came from where and of
anything for which no licence file was found.

    python packaging/collect_licenses.py OUT_DIR --platform linux [--library PATH ...]
"""
import argparse
import importlib.metadata as metadata
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA_DISTRIBUTIONS = ("llama-cpp-python",)   # installed from source, outside the lock
_LICENSE_NAME = re.compile(r"^(LICEN[CS]E|COPYING|COPYRIGHT|NOTICE|AUTHORS|THIRDPARTYNOTICES|THIRD_PARTY)", re.I)
_SKIP_SUFFIXES = (".py", ".pyc", ".pyi", ".so", ".dll", ".dylib", ".pyd")


def locked_distributions(platform: str) -> list[str]:
    with open(os.path.join(ROOT, "requirements", f"lock-{platform}.txt"), encoding="utf-8") as f:
        names = re.findall(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==", f.read(), re.M)
    return names + [n for n in EXTRA_DISTRIBUTIONS if n not in names]


def _license_files(dist) -> list[tuple[str, str]]:
    """(source path, path to copy it to) for each licence file of an installed distribution."""
    found = {}
    dist_info = None
    for f in dist.files or []:
        parts = f.parts
        if not parts or str(f).endswith(_SKIP_SUFFIXES):
            continue
        if parts[0].endswith(".dist-info"):
            dist_info = parts[0]
            inner = parts[1:]
            if inner[:1] == ("licenses",) and len(inner) > 1:
                found[str(f)] = os.path.join(*inner[1:])
            elif len(inner) == 1 and _LICENSE_NAME.match(inner[0]):
                found[str(f)] = inner[0]
        elif len(parts) == 2 and _LICENSE_NAME.match(parts[1]):
            found[str(f)] = os.path.join(parts[0], parts[1])   # e.g. onnxruntime/ThirdPartyNotices.txt
    for name in dist.metadata.get_all("License-File") or []:
        for base in ("licenses", ""):
            rel = os.path.join(dist_info or "", base, name)
            if os.path.isfile(dist.locate_file(rel)):
                found.setdefault(rel, name)
                break
    return [(str(dist.locate_file(src)), dest) for src, dest in sorted(found.items())]


def _license_label(dist) -> str:
    meta = dist.metadata
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    license_field = (meta.get("License") or "").strip()
    if license_field and "\n" not in license_field and len(license_field) <= 60:
        return license_field
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return "; ".join(classifiers) or "see the files"


def python_licenses(dest: str, names) -> list[str]:
    """Copy each distribution's licence files to dest/python/<name>/; returns index lines."""
    lines = []
    for name in names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            raise SystemExit(f"collect_licenses: {name} is in the lock file but not installed")
        files = _license_files(dist)
        folder = os.path.join(dest, "python", dist.metadata["Name"])
        for src, rel in files:
            os.makedirs(os.path.dirname(os.path.join(folder, rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(folder, rel))
        label = f"{dist.metadata['Name']} {dist.version} ({_license_label(dist)})"
        if files:
            lines.append(f"{label}: python/{dist.metadata['Name']}/ ({len(files)} file(s))")
        else:
            lines.append(f"{label}: its wheel ships no licence file; the licence's standard text is in"
                         " THIRD_PARTY_LICENSES")
    return lines


def python_runtime_license(dest: str) -> str:
    """Copy CPython's LICENSE.txt (interpreter and standard library, bundled by PyInstaller)."""
    stdlib = os.path.dirname(os.__file__)
    for candidate in (os.path.join(stdlib, "LICENSE.txt"), os.path.join(sys.base_prefix, "LICENSE.txt"),
                      os.path.join(sys.base_prefix, "share", "doc", "python3", "copyright")):
        if os.path.isfile(candidate):
            os.makedirs(os.path.join(dest, "python", "CPython"), exist_ok=True)
            shutil.copyfile(candidate, os.path.join(dest, "python", "CPython", "LICENSE.txt"))
            return f"CPython {sys.version.split()[0]} (PSF-2.0): python/CPython/LICENSE.txt"
    raise SystemExit("collect_licenses: CPython's LICENSE.txt was not found")


# ------------------------------------------------------------ system libraries ----

def _run(args) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _path_variants(path: str):
    """The path as given and resolved, with and without /usr (Debian's merged /usr)."""
    seen = []
    for p in (path, os.path.realpath(path)):
        for v in (p, p[len("/usr"):] if p.startswith("/usr/") else "/usr" + p):
            if v not in seen:
                seen.append(v)
    return seen


def _debian_package(path: str) -> str | None:
    for variant in _path_variants(path):
        out = _run(["dpkg", "-S", variant])
        for line in out.splitlines():
            if ": " in line and not line.startswith("diversion"):
                return line.split(": ", 1)[0].split(":")[0].split(",")[0].strip()
    return None


def _linux_license_files(path: str) -> tuple[str | None, list[str]]:
    if shutil.which("dpkg"):
        package = _debian_package(path)
        if package:
            copyright_file = f"/usr/share/doc/{package}/copyright"
            return package, [copyright_file] if os.path.isfile(copyright_file) else []
    if shutil.which("pacman"):   # a build on Arch-like systems (developers' machines)
        package = _run(["pacman", "-Qqo", os.path.realpath(path)]).strip() or None
        if package:
            folder = f"/usr/share/licenses/{package}"
            files = [os.path.join(folder, f) for f in sorted(os.listdir(folder))] if os.path.isdir(folder) else []
            return package, files
    return None, []


def _homebrew_keg(path: str) -> str | None:
    m = re.match(r"^(.*/Cellar/[^/]+/[^/]+)/", os.path.realpath(path))
    return m.group(1) if m else None


def _macos_dependencies(binary: str) -> list[str]:
    """*binary* and the Homebrew libraries it loads, recursively (otool -L)."""
    todo, seen = [os.path.realpath(binary)], []
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.append(current)
        for line in _run(["otool", "-L", current]).splitlines()[1:]:
            lib = line.strip().split(" (", 1)[0]
            if lib.startswith(("/opt/homebrew/", "/usr/local/")) and os.path.exists(lib):
                todo.append(os.path.realpath(lib))
    return seen


def system_licenses(dest: str, platform: str, libraries=(), tesseract_dir: str | None = None) -> list[str]:
    """Copy the licence files of Tesseract and the libraries bundled with it; returns index lines."""
    lines, done = [], {}
    if platform == "windows":
        files = []
        for root, _dirs, names in os.walk(tesseract_dir or ""):
            if root[len(tesseract_dir):].count(os.sep) > 2:
                continue
            files += [os.path.join(root, n) for n in names if _LICENSE_NAME.match(n)]
        for src in files:
            rel = os.path.relpath(src, tesseract_dir)
            os.makedirs(os.path.dirname(os.path.join(dest, "system", "Tesseract-OCR", rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(dest, "system", "Tesseract-OCR", rel))
        lines.append(f"Tesseract-OCR and its DLLs: {len(files)} licence file(s) from its installation folder in"
                     " system/Tesseract-OCR/" if files else
                     "Tesseract-OCR and its DLLs: the installation folder holds no licence files (NOT FOUND)")
        return lines
    if platform == "macos":
        libraries = [d for lib in libraries for d in _macos_dependencies(lib)]
    for lib in libraries:   # grouped by the package each library comes from
        if platform == "macos":
            keg = _homebrew_keg(lib)
            package = os.path.basename(os.path.dirname(keg)) if keg else None
            files = ([os.path.join(keg, n) for n in sorted(os.listdir(keg)) if _LICENSE_NAME.match(n)]
                     if keg else [])
        else:
            package, files = _linux_license_files(lib)
        key = package or os.path.basename(lib)
        if key not in done:
            done[key] = (package, files, [])
        if os.path.basename(lib) not in done[key][2]:
            done[key][2].append(os.path.basename(lib))
    for key, (package, files, names) in done.items():
        if not files:
            print(f"collect_licenses: WARNING: no licence file found for {', '.join(names)} (package {package})",
                  file=sys.stderr)
            lines.append(f"{key} ({', '.join(names)}): NO LICENCE FILE FOUND")
            continue
        for src in files:
            target = os.path.join(dest, "system", package, os.path.basename(src))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)
        lines.append(f"{package} ({', '.join(names)}): system/{package}/")
    return lines


def collect_licenses(dest: str, platform: str, libraries=(), tesseract_dir: str | None = None) -> str:
    """Fill *dest* (emptied first) with the bundle's licence files; returns *dest*."""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    index = ["Licence files of the components bundled with MDMT, copied from the components themselves",
             "when this build was made.  The standard licence texts, the FFmpeg libraries and the models",
             "MDMT downloads are covered in THIRD_PARTY_LICENSES.", "",
             "Python packages", "---------------"]
    index += python_licenses(dest, locked_distributions(platform))
    index += [python_runtime_license(dest), "", "Tesseract and the libraries bundled with it", "-" * 43]
    index += system_licenses(dest, platform, libraries, tesseract_dir)
    with open(os.path.join(dest, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dest")
    parser.add_argument("--platform", choices=("linux", "macos", "windows"), required=True)
    parser.add_argument("--library", action="append", default=[], help="a bundled system library (repeatable)")
    parser.add_argument("--tesseract-dir", help="Windows: the Tesseract-OCR installation folder")
    args = parser.parse_args(argv)
    collect_licenses(args.dest, args.platform, args.library, args.tesseract_dir)
    print(open(os.path.join(args.dest, "README.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
