# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import subprocess
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect data files for frameworks that bundle static assets
nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)
datas.extend(collect_data_files('ocrmypdf'))
datas.extend(collect_data_files('whisper'))

# Bundle certifi CA certificates so SSL works in the frozen app
try:
    import certifi
    datas.append((certifi.where(), 'certifi'))
except ImportError:
    pass

# --- llama-cpp-python native libraries ---
binaries = []
try:
    import llama_cpp
    _llama_pkg = os.path.dirname(llama_cpp.__file__)
    _llama_lib_dir = os.path.join(_llama_pkg, 'lib')
    if os.path.isdir(_llama_lib_dir):
        import glob as _glob
        for _so in _glob.glob(os.path.join(_llama_lib_dir, '*.so*')):
            binaries.append((_so, 'llama_cpp/lib'))
except ImportError:
    pass

# --- ffmpeg bundling (needed by Whisper for audio loading) ---
ffmpeg_bin = shutil.which('ffmpeg')
if ffmpeg_bin:
    binaries.append((ffmpeg_bin, '.'))

# --- Tesseract bundling (Linux) ---
tesseract_bin = shutil.which('tesseract')
if tesseract_bin:
    binaries.append((tesseract_bin, 'tesseract_bin'))
    # Bundle shared library dependencies discovered via ldd
    try:
        ldd_out = subprocess.check_output(['ldd', tesseract_bin], text=True)
        for line in ldd_out.splitlines():
            parts = line.strip().split()
            # Format: libfoo.so.1 => /usr/lib/libfoo.so.1 (0x...)
            if '=>' in line and len(parts) >= 3 and parts[2].startswith('/'):
                lib_path = parts[2]
                # Skip core system libs (libc, libm, libpthread, ld-linux, etc.)
                basename = os.path.basename(lib_path)
                if not any(basename.startswith(s) for s in ('libc.', 'libm.', 'libdl.', 'libpthread.', 'ld-linux', 'librt.', 'libgcc_s.')):
                    binaries.append((lib_path, 'tesseract_bin'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

# Bundle eng.traineddata as baseline
tessdata_candidates = [
    '/usr/share/tesseract-ocr/5/tessdata',
    '/usr/share/tesseract-ocr/4.00/tessdata',
    '/usr/share/tessdata',
]
for td in tessdata_candidates:
    eng = os.path.join(td, 'eng.traineddata')
    if os.path.isfile(eng):
        datas.append((td, 'tessdata'))
        break

# Hidden imports — PyInstaller can't discover these via static analysis
hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
    'ocrmypdf',
    'ocrmypdf.builtin_plugins.tesseract_ocr',
    'ocrmypdf.builtin_plugins.ghostscript',
    'ocrmypdf.builtin_plugins.concurrency',
    'ocrmypdf.builtin_plugins.default_filters',
    'ocrmypdf.builtin_plugins.null_ocr',
    'ocrmypdf.builtin_plugins.optimize',
    'ocrmypdf.builtin_plugins.pypdfium',
    'googletrans',
    'langchain',
    'langchain_community',
    'sentence_transformers',
    'transformers',
    'nltk',
    'networkx',
    'llama_cpp',
    'certifi',
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
