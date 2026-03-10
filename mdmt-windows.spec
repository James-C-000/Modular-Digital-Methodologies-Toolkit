# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# --- Tesseract bundling (Windows) ---
binaries = []
# Check common install locations
tesseract_candidates = [
    os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'Tesseract-OCR', 'tesseract.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
    shutil.which('tesseract') or '',
]
for candidate in tesseract_candidates:
    if candidate and os.path.isfile(candidate):
        tess_dir = os.path.dirname(candidate)
        binaries.append((candidate, 'tesseract_bin'))
        # Bundle DLLs from the same directory
        for dll in os.listdir(tess_dir):
            if dll.endswith('.dll'):
                binaries.append((os.path.join(tess_dir, dll), 'tesseract_bin'))
        # Bundle tessdata
        tessdata = os.path.join(tess_dir, 'tessdata')
        if os.path.isdir(tessdata):
            datas.append((tessdata, 'tessdata'))
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
    icon='MDMT_logo.ico',
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
