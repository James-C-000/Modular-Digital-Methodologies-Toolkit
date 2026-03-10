# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# --- Tesseract bundling (macOS / Homebrew) ---
binaries = []
tesseract_bin = shutil.which('tesseract')
if tesseract_bin:
    binaries.append((tesseract_bin, 'tesseract_bin'))
    # Bundle shared library dependencies discovered via otool
    try:
        otool_out = subprocess.check_output(['otool', '-L', tesseract_bin], text=True)
        for line in otool_out.splitlines()[1:]:  # skip first line (binary path)
            lib_path = line.strip().split(' (')[0].strip()
            # Bundle Homebrew libs, skip system frameworks
            if lib_path.startswith(('/opt/homebrew/', '/usr/local/')) and os.path.isfile(lib_path):
                binaries.append((lib_path, 'tesseract_bin'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

# Bundle eng.traineddata as baseline
tessdata_candidates = [
    '/opt/homebrew/share/tessdata',           # Apple Silicon Homebrew
    '/usr/local/share/tessdata',              # Intel Homebrew
    '/opt/homebrew/share/tesseract-ocr/5/tessdata',
    '/usr/local/share/tesseract-ocr/5/tessdata',
]
for td in tessdata_candidates:
    eng = os.path.join(td, 'eng.traineddata')
    if os.path.isfile(eng):
        datas.append((td, 'tessdata'))
        break

hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
    'ocrmypdf',
    'googletrans',
    'langchain',
    'langchain_community',
    'sentence_transformers',
    'transformers',
    'nltk',
    'networkx',
]

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
    upx=True,
    console=False,
    icon='MDMT_logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='mdmt',
)
