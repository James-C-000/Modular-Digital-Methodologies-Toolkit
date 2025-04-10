# hook-ocrmypdf.py
import os
import sys
import shutil
import subprocess
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
from PyInstaller import compat

# Collect all package data
datas, binaries, hiddenimports = collect_all('ocrmypdf')

# Explicitly add the data module
hiddenimports.extend([
    'ocrmypdf.data',
    'ocrmypdf.hocrtransform',
    'ocrmypdf.hocrtransform._hocr',
    'ocrmypdf.hocrtransform._font',
    'ocrmypdf._concurrent',
    'ocrmypdf.subprocess',
    'ocrmypdf.helpers',
    'pikepdf',
    'reportlab',
    'img2pdf',
    'PIL'
])

# Copy the package metadata
datas.extend(copy_metadata('ocrmypdf'))

# Include Tesseract binary
def add_tesseract_binary():
    """Find and add the tesseract binary to the bundle"""
    tesseract_binary = None
    
    # Try to find tesseract binary
    try:
        # On Windows, tesseract.exe should be in PATH or in a well-known location
        if compat.is_win:
            # Try to find from PATH
            try:
                tesseract_binary = shutil.which('tesseract.exe')
            except Exception:
                pass
                
            # Try some common installation paths
            if not tesseract_binary:
                common_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
                ]
                for path in common_paths:
                    if os.path.exists(path):
                        tesseract_binary = path
                        break
                        
        # On macOS and Linux, we can use the 'which' command
        else:
            try:
                # Use the 'which' command to find tesseract
                result = subprocess.run(['which', 'tesseract'], 
                                        capture_output=True, text=True, check=True)
                tesseract_binary = result.stdout.strip()
            except Exception:
                pass
    
        if tesseract_binary:
            print(f"Found tesseract binary at: {tesseract_binary}")
            # Add the binary to PyInstaller binaries list
            binaries.append((tesseract_binary, '.'))
        else:
            print("Warning: Could not find tesseract binary. OCR functionality may be limited.")
        
    except Exception as e:
        print(f"Error locating tesseract binary: {e}")

# Try to add tesseract binary
add_tesseract_binary()

# Make sure required tessconfigs files are included
tessconfigs_files = [
    'hocr',
    'txt',
    'pdf'
]

tessdata_dir = os.path.join(os.getcwd(), 'OCR', 'tessdata')
for config_file in tessconfigs_files:
    config_path = os.path.join(tessdata_dir, 'tessconfigs', 'configs', config_file)
    if os.path.exists(config_path):
        datas.append((config_path, os.path.join('OCR', 'tessdata', 'tessconfigs', 'configs')))
    else:
        print(f"Warning: Config file {config_file} not found at {config_path}")