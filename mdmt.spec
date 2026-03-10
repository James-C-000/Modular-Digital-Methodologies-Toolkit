# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect data files for frameworks that bundle static assets
nicegui_datas = collect_data_files('nicegui')

datas = [
    ('Assets', 'Assets'),
    ('Advanced_Keyword_Search/*.txt', 'Advanced_Keyword_Search'),
]
datas.extend(nicegui_datas)

# Hidden imports — PyInstaller can't discover these via static analysis
hiddenimports = collect_submodules('nicegui')
hiddenimports += collect_submodules('webview')
hiddenimports += [
    'engineio.async_drivers.threading',
    # ML/NLP deps that use dynamic imports
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
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

# Use --onedir mode (COLLECT) for large ML apps — avoids multi-GB extraction on each launch.
# Switch to single-file EXE if the dependency footprint is reduced later.
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
    icon='Assets/starNymph.png',
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
