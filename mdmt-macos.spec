# -*- mode: python ; coding: utf-8 -*-
# Builds dist/MDMT.app (Apple Silicon / arm64 only).
import os
import shutil
import sys

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, os.path.join(SPECPATH, 'packaging'))
from spec_common import LGPL_SOURCE_MODULES, UPX, VERSION, common_binaries, common_datas, common_hiddenimports  # noqa: E402

datas = common_datas()
binaries = common_binaries()

# --- Tesseract bundling (macOS / Homebrew) ---
# PyInstaller collects the binary's non-system dylib dependencies (recursively),
# rewrites their /opt/homebrew install names to @rpath and ad-hoc signs them.
# packaging/check_bundle_libs.py verifies nothing still points outside the app.
tesseract_bin = shutil.which('tesseract')
if not tesseract_bin:
    raise SystemExit('tesseract not found: brew install tesseract before building')
binaries.append((os.path.realpath(tesseract_bin), 'tesseract_bin'))

# Seed tessdata (eng, osd, configs/); copied into the user's managed tessdata
# dir on first run by OCR.tessdata.
tessdata_candidates = [
    '/opt/homebrew/share/tessdata',           # Apple Silicon Homebrew
    '/usr/local/share/tessdata',              # Intel Homebrew
    '/opt/homebrew/share/tesseract-ocr/5/tessdata',
    '/usr/local/share/tesseract-ocr/5/tessdata',
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
    raise SystemExit('eng.traineddata not found in Homebrew tessdata')

# --- App icon: .icns generated from the PNG logo at build time ---
icns_path = os.path.join(workpath, 'MDMT.icns')
from PIL import Image  # noqa: E402  (Pillow is a matplotlib/ocrmypdf dependency)
Image.open(os.path.join(SPECPATH, 'MDMT_logo.png')).convert('RGBA').save(
    icns_path, sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])

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
    excludes=[],
    noarchive=False,
    module_collection_mode=LGPL_SOURCE_MODULES,
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
    target_arch='arm64',
    icon=icns_path,
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

app = BUNDLE(
    coll,
    name='MDMT.app',
    icon=icns_path,
    bundle_identifier='net.jamescaldwell.mdmt',
    version=VERSION,
    info_plist={
        'CFBundleName': 'MDMT',
        'CFBundleDisplayName': 'MDMT',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '15.0',  # locked wheels (pikepdf) need macOS 15+
        'NSHumanReadableCopyright': 'Copyright (c) 2026 James C. Caldwell. MIT License.',
    },
)
