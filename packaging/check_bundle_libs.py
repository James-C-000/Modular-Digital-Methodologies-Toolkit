"""Fail if any binary in a frozen MDMT bundle depends on a library outside it.

    python packaging/check_bundle_libs.py dist/mdmt          # Linux (ldd)
    python packaging/check_bundle_libs.py dist/MDMT.app      # macOS (otool -L)

A dependency may live outside the bundle only if it is a system library that
PyInstaller itself refuses to bundle (``PyInstaller.depend.dylib.include_library``
returns False: glibc, libGL, ... on Linux; /usr/lib and /System on macOS).
Anything else -- e.g. Tesseract's Homebrew libraries referenced by absolute
/opt/homebrew paths -- works on the build machine and breaks on users' machines.

Run it in the build environment (it imports PyInstaller).
"""
import os
import re
import subprocess
import sys

from PyInstaller.depend.dylib import include_library

ELF_MAGIC = b"\x7fELF"
MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",  # fat binaries
}


def _magic(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(4)
    except OSError:
        return b""


def _walk_binaries(root: str, magics) -> list[str]:
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            if not os.path.islink(path) and _magic(path) in magics:
                found.append(path)
    return sorted(found)


# The glibc core is always provided by the user's system (PyInstaller's own
# exclude patterns miss the x86-64 ELF interpreter name).
_GLIBC_CORE = re.compile(
    r"^(ld-linux.*|libc|libm|libdl|libpthread|librt|libutil|libresolv|libanl|libnsl|libmvec)\.so"
)


def _system_lib(path: str) -> bool:
    return bool(_GLIBC_CORE.match(os.path.basename(path))) or not include_library(path)


def _inside(path: str, root: str) -> bool:
    return os.path.realpath(path).startswith(os.path.realpath(root) + os.sep)


# ---------------------------------------------------------------- Linux ----

def check_linux(bundle: str) -> list[str]:
    internal = os.path.join(bundle, "_internal")
    # What the PyInstaller bootloader and app._setup_frozen_env provide at runtime.
    env = dict(os.environ, LD_LIBRARY_PATH=os.pathsep.join(
        [internal, os.path.join(internal, "tesseract_bin")]))
    problems = []
    for path in _walk_binaries(bundle, {ELF_MAGIC}):
        out = subprocess.run(["ldd", path], capture_output=True, text=True, env=env)
        if "not a dynamic executable" in out.stdout + out.stderr:
            continue
        for line in out.stdout.splitlines():
            line = line.strip()
            m = re.match(r"(\S+) => (not found|(\S+) \(0x[0-9a-f]+\))", line)
            if not m:
                continue
            soname, target = m.group(1), m.group(3)
            rel = os.path.relpath(path, bundle)
            if target is None:
                if not _system_lib(soname):
                    problems.append(f"{rel}: {soname} not found")
            elif not _inside(target, bundle) and not _system_lib(target):
                problems.append(f"{rel}: {soname} resolves outside the bundle to {target}")
    return problems


# ---------------------------------------------------------------- macOS ----

def _otool(args, path) -> str:
    return subprocess.run(["otool", *args, path], capture_output=True, text=True).stdout


def _rpaths(path: str) -> list[str]:
    rpaths, lines = [], _otool(["-l"], path).splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "cmd LC_RPATH":
            for follow in lines[i + 1:i + 4]:
                follow = follow.strip()
                if follow.startswith("path "):
                    rpaths.append(follow.split()[1])
    return rpaths


def check_macos(bundle: str) -> list[str]:
    macos_dir = os.path.join(bundle, "Contents", "MacOS")
    problems = []
    for path in _walk_binaries(bundle, MACHO_MAGICS):
        rel = os.path.relpath(path, bundle)
        loader_dir = os.path.dirname(path)
        rpaths = [r.replace("@loader_path", loader_dir).replace("@executable_path", macos_dir)
                  for r in _rpaths(path)]
        # A dylib's own install name (LC_ID_DYLIB) is listed by otool -L too;
        # it is an identity, not a dependency.
        own_id = (_otool(["-D"], path).splitlines()[1:] or [""])[0].strip()
        lines = _otool(["-L"], path).splitlines()[1:]
        for line in lines:
            dep = line.strip().split(" (")[0]
            if not dep or dep == own_id:
                continue
            if dep.startswith("@rpath/"):
                candidates = [os.path.join(r, dep[len("@rpath/"):]) for r in rpaths]
                if not any(os.path.exists(c) for c in candidates):
                    problems.append(f"{rel}: {dep} not found via rpaths {rpaths}")
                elif not any(os.path.exists(c) and _inside(c, bundle) for c in candidates):
                    problems.append(f"{rel}: {dep} resolves outside the bundle")
            elif dep.startswith(("@loader_path/", "@executable_path/")):
                target = dep.replace("@loader_path", loader_dir).replace("@executable_path", macos_dir)
                if not os.path.exists(target):
                    problems.append(f"{rel}: {dep} does not exist in the bundle")
            elif dep.startswith(("/usr/lib/", "/System/")):
                continue
            else:
                problems.append(f"{rel}: absolute dependency outside the bundle: {dep}")
    return problems


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    bundle = argv[1]
    if sys.platform == "darwin":
        problems = check_macos(bundle)
    elif sys.platform.startswith("linux"):
        problems = check_linux(bundle)
    else:
        print("Only Linux and macOS bundles are checked.")
        return 0
    for p in problems:
        print("ERROR:", p)
    print(f"{len(problems)} problem(s) in {bundle}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
