# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys

from PyInstaller.utils.hooks import collect_submodules

sys.path.insert(0, os.path.join(SPECPATH, 'packaging'))
from spec_common import UPX, VERSION, common_binaries, common_datas, common_hiddenimports  # noqa: E402

datas = common_datas()
binaries = common_binaries()

# --- Tesseract bundling (Windows) ---
# The UB Mannheim build keeps its DLLs next to tesseract.exe; Windows loads
# DLLs from the executable's own directory first.
tesseract_candidates = [
    os.path.join(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'Tesseract-OCR', 'tesseract.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
]
tess_exe = next((c for c in tesseract_candidates if c and os.path.isfile(c)), None)
if tess_exe is None:
    raise SystemExit('Tesseract-OCR not found in Program Files: choco install tesseract before building')
tess_dir = os.path.dirname(tess_exe)
binaries.append((tess_exe, 'tesseract_bin'))
for dll in os.listdir(tess_dir):
    if dll.lower().endswith('.dll'):
        binaries.append((os.path.join(tess_dir, dll), 'tesseract_bin'))

# Seed tessdata (eng, osd, configs/); copied into the user's managed tessdata
# dir on first run by OCR.tessdata.
tessdata = os.path.join(tess_dir, 'tessdata')
for name in ('eng.traineddata', 'osd.traineddata', 'pdf.ttf'):
    if os.path.isfile(os.path.join(tessdata, name)):
        datas.append((os.path.join(tessdata, name), 'tessdata'))
for sub in ('configs', 'tessconfigs'):
    if os.path.isdir(os.path.join(tessdata, sub)):
        datas.append((os.path.join(tessdata, sub), os.path.join('tessdata', sub)))

# --- Windows version resource (Explorer > Properties > Details) ---
_v = tuple(int(p) for p in VERSION.split('.')) + (0,) * (4 - len(VERSION.split('.')))
version_file = os.path.join(workpath, 'mdmt_version_info.txt')
os.makedirs(workpath, exist_ok=True)
with open(version_file, 'w', encoding='utf-8') as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={_v}, prodvers={_v}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'James C. Caldwell'),
      StringStruct('FileDescription', 'MDMT - Modular Digital Methodologies Toolkit'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'mdmt'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'mdmt.exe'),
      StringStruct('ProductName', 'MDMT'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

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
    icon='MDMT_logo.ico',
    version=version_file,
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
