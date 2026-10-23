# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
import sys

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, os.path.join(SPECPATH, 'packaging'))
from spec_common import UPX, common_binaries, common_datas, common_hiddenimports  # noqa: E402

datas = common_datas()
binaries = common_binaries()

# --- Tesseract bundling (Linux) ---
# Core glibc libraries must come from the user's system; everything else
# tesseract links against is copied next to it (found via LD_LIBRARY_PATH,
# set in app._setup_frozen_env).
_SYSTEM_LIB_PREFIXES = ('libc.', 'libm.', 'libdl.', 'libpthread.', 'ld-linux', 'librt.', 'libgcc_s.')
tesseract_bin = shutil.which('tesseract')
if not tesseract_bin:
    raise SystemExit('tesseract not found: install tesseract-ocr before building')
binaries.append((tesseract_bin, 'tesseract_bin'))
ldd_out = subprocess.check_output(['ldd', tesseract_bin], text=True)
for line in ldd_out.splitlines():
    parts = line.strip().split()
    # Format: libfoo.so.1 => /usr/lib/libfoo.so.1 (0x...)
    if '=>' in line and len(parts) >= 3 and parts[2].startswith('/'):
        if not os.path.basename(parts[2]).startswith(_SYSTEM_LIB_PREFIXES):
            binaries.append((parts[2], 'tesseract_bin'))

# Seed tessdata (eng, osd, configs/); copied into the user's managed tessdata
# dir on first run by OCR.tessdata.
tessdata_candidates = [
    '/usr/share/tesseract-ocr/5/tessdata',
    '/usr/share/tesseract-ocr/4.00/tessdata',
    '/usr/share/tessdata',
]
for td in tessdata_candidates:
    if os.path.isfile(os.path.join(td, 'eng.traineddata')):
        for name in ('eng.traineddata', 'osd.traineddata', 'pdf.ttf'):
            if os.path.isfile(os.path.join(td, name)):
                datas.append((os.path.join(td, name), 'tessdata'))
        for sub in ('configs', 'tessconfigs'):
            if os.path.isdir(os.path.join(td, sub)):
                datas.append((os.path.join(td, sub), os.path.join('tessdata', sub)))
        break
else:
    raise SystemExit('eng.traineddata not found: install tesseract-ocr-eng before building')

# Hidden imports — PyInstaller can't discover these via static analysis
hiddenimports = common_hiddenimports() + collect_submodules('webview')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['readline'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mdmt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=UPX,
    console=False,
    icon='MDMT_logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=UPX,
    name='mdmt',
)
