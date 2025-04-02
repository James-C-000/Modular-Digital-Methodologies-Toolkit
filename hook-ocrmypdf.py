# hook-ocrmypdf.py
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# Collect all package data
datas, binaries, hiddenimports = collect_all('ocrmypdf')

# Explicitly add the data module
hiddenimports.extend([
    'ocrmypdf.data',
    'ocrmypdf.hocrtransform',
    'ocrmypdf.hocrtransform._hocr',
    'ocrmypdf.hocrtransform._font'
])

# Copy the package metadata
datas.extend(copy_metadata('ocrmypdf'))