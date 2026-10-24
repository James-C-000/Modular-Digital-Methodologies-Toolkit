import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_banned_dependencies_in_the_lock_files():
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "packaging", "check_banned_deps.py")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
