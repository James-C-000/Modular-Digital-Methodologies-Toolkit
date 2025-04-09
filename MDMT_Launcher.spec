# MDMT_Launcher.spec (Enhanced version)
import os
import sys
import glob
import ocrmypdf
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata, collect_data_files
import site
import os.path
from PyInstaller.utils.hooks import collect_dynamic_libs

# Base directory - use current working directory
base_dir = os.getcwd()
block_cipher = None

# Find llama shared libraries
llama_binaries = collect_dynamic_libs('llama_cpp')

# Platform detection
is_windows = sys.platform.startswith('win')
is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')

# Define executable name based on platform
if is_windows:
    exe_name = 'MDMT.exe'
    icon_file = os.path.join(base_dir, 'resources', 'mdmt_icon.ico')
elif is_mac:
    exe_name = 'MDMT'
    icon_file = os.path.join(base_dir, 'resources', 'mdmt_icon.icns')
else:
    exe_name = 'MDMT'
    icon_file = None

# Gather all UI files
ui_files = []
for ui_file in glob.glob(os.path.join(base_dir, '*.ui')):
    ui_files.append((ui_file, '.'))

# Define data files to include
datas = []
datas.extend(ui_files)

# Explicitly include images
for file in glob.glob(os.path.join(base_dir, '*.png')) + glob.glob(os.path.join(base_dir, '*.ico')):
    datas.append((file, '.'))

# Include directories with their contents
for directory in [
    'Advanced_Keyword_Search',
    'Audio_Transcription',
    'Bibliometrix',
    'NLP',
    'RAG',
    'Translation',
    'resources'
]:
    dir_path = os.path.join(base_dir, directory)
    if os.path.exists(dir_path):
        # Get all files in the directory and subdirectories
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate relative path for destination
                rel_path = os.path.relpath(os.path.dirname(file_path), base_dir)
                datas.append((file_path, rel_path))

# Special handling for OCR directory to ensure all tesseract components are included
ocr_dir = os.path.join(base_dir, 'OCR')
if os.path.exists(ocr_dir):
    # Handle all files in OCR directory except tessdata (which we'll handle separately)
    for root, dirs, files in os.walk(ocr_dir):
        # Skip the tessdata directory for now
        if os.path.basename(root) == 'tessdata':
            continue
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(os.path.dirname(file_path), base_dir)
            datas.append((file_path, rel_path))

# Special handling for tesseract data and configs - we need to be explicit
tessdata_dir = os.path.join(base_dir, 'OCR', 'tessdata')
if os.path.exists(tessdata_dir):
    # Include all files in the tessdata directory
    for file in glob.glob(os.path.join(tessdata_dir, '*.*')):
        if os.path.isfile(file):
            datas.append((file, os.path.join('OCR', 'tessdata')))

    # Explicitly handle tessconfigs directory
    tessconfigs_dir = os.path.join(tessdata_dir, 'tessconfigs')
    if os.path.exists(tessconfigs_dir):
        # Include the tessconfigs directory and all its subdirectories
        for root, dirs, files in os.walk(tessconfigs_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate path relative to OCR directory for proper structure preservation
                rel_path = os.path.join('OCR', 'tessdata', os.path.relpath(os.path.dirname(file_path), tessdata_dir))
                datas.append((file_path, rel_path))

        # Specifically check the configs directory inside tessconfigs
        configs_dir = os.path.join(tessconfigs_dir, 'configs')
        if os.path.exists(configs_dir):
            for file in os.listdir(configs_dir):
                file_path = os.path.join(configs_dir, file)
                if os.path.isfile(file_path):
                    # Explicitly put configs in the right place
                    datas.append((file_path, os.path.join('OCR', 'tessdata', 'tessconfigs', 'configs')))

# Find and include ocrmypdf data files - be comprehensive
ocrmypdf_data_dir = os.path.join(os.path.dirname(ocrmypdf.__file__), 'data')
if os.path.exists(ocrmypdf_data_dir):
    for root, dirs, files in os.walk(ocrmypdf_data_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.join('ocrmypdf', 'data', os.path.relpath(file_path, ocrmypdf_data_dir))
            datas.append((file_path, os.path.dirname(rel_path)))

# Collect data from packages
binaries = []
package_data = []

# Core packages with data files
for package in ['nltk', 'transformers', 'whisper', 'torch', 'ocrmypdf']:
    try:
        pkg_data, pkg_binaries, pkg_hidden = collect_all(package)
        datas.extend(pkg_data)
        binaries.extend(pkg_binaries)
        package_data.extend(copy_metadata(package))
    except Exception as e:
        print(f"Warning: Error collecting {package}: {e}")

# NLTK data
nltk_data_path = os.path.join(os.path.expanduser('~'), 'nltk_data')
if os.path.exists(nltk_data_path):
    for item in os.listdir(nltk_data_path):
        item_path = os.path.join(nltk_data_path, item)
        if os.path.isdir(item_path):
            datas.append((item_path, os.path.join('nltk_data', item)))

# Hidden imports
hidden_imports = [
    # Core
    'tkinter',
    'tkinter.ttk',
    'pandas',
    'numpy',
    'matplotlib',
    'PIL',

    # NLP
    'nltk',
    'nltk.tokenize',
    'nltk.corpus',
    'transformers',

    # Audio
    'whisper',
    'torch',

    # PDF
    'pypdf',
    'ocrmypdf',
    'ocrmypdf.api',
    'ocrmypdf.helpers',
    'ocrmypdf.exec',
    'ocrmypdf.pdfa',
    'ocrmypdf.pdfinfo',
    'ocrmypdf.quality',
    'ocrmypdf.optimize',
    'ocrmypdf.leptonica',
    'ocrmypdf.subprocess',
    'ocrmypdf.exceptions',
    'ocrmypdf._concurrent',

    # Specific modules
    'pygubu',
    'pygubu.builder',
    'pygubu.builder.widgets',
    'threading',
    'webbrowser',
    'glob',
    'asyncio',
    'collections',
    'csv',
    're',

    # Add these Pydantic-related imports
    'pydantic',
    'pydantic.deprecated.decorator',
    'pydantic.deprecated.class_validators',
    'pydantic.deprecated.config',
    'pydantic.deprecated.tools',
    'pydantic.alias_generators',
    'pydantic.networks',
    'pydantic.color',
    'pydantic.dataclasses',
    'pydantic.datetime_parse',

    # LangChain-related imports
    'langchain',
    'langchain_community',
    'langchain_core',
    'langchain_huggingface',

    # Add llama-cpp-python related imports
    'llama_cpp',
    'llama_cpp.llama',
    'llama_cpp.llama_types',
]

# Create a runtime hook to set up NLTK data path and clean up tesseract temp dirs
with open('runtime_hook.py', 'w') as f:
    f.write("""
import os
import sys
import nltk
import shutil
import tempfile

# Set the NLTK data path to be relative to the executable
nltk_data_dir = os.path.join(sys._MEIPASS, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.insert(0, nltk_data_dir)

# Clean up any temporary directories from previous runs
temp_dir = tempfile.gettempdir()
for item in os.listdir(temp_dir):
    if item.startswith('mdmt_tesseract_'):
        try:
            path = os.path.join(temp_dir, item)
            if os.path.isdir(path):
                shutil.rmtree(path)
        except Exception:
            pass
""")

# Add platform-specific Tesseract binaries - improved method
tesseract_binaries = []
if is_windows:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'win_tesseract')
    if os.path.exists(tesseract_dir):
        # Add all executable files
        for file in glob.glob(os.path.join(tesseract_dir, '*.exe')):
            tesseract_binaries.append((file, 'OCR'))
        # Add all DLLs
        for file in glob.glob(os.path.join(tesseract_dir, '*.dll')):
            tesseract_binaries.append((file, 'OCR'))
        # Also look for DLLs in subdirectories
        for root, dirs, files in os.walk(tesseract_dir):
            for file in files:
                if file.lower().endswith('.dll'):
                    file_path = os.path.join(root, file)
                    # Calculate destination path
                    rel_path = os.path.relpath(os.path.dirname(file_path), tesseract_dir)
                    if rel_path == '.':
                        dest_path = 'OCR'
                    else:
                        dest_path = os.path.join('OCR', rel_path)
                    tesseract_binaries.append((file_path, dest_path))

# Create the Analysis object
a = Analysis(
    ['MDMT_Launcher.py'],
    pathex=[base_dir],
    binaries=binaries + llama_binaries + tesseract_binaries,  # Keep your existing binaries
    datas=datas + package_data,          # Keep your existing data
    hiddenimports=hidden_imports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py', 'tesseract_hook.py'],  # Add the new hook
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Print some information during the build process for debugging
print(f"\n{'='*50}")
print(f"PyInstaller Build Information:")
print(f"{'='*50}")
print(f"Building MDMT with:")
print(f"  - Base directory: {base_dir}")
print(f"  - Platform: {'Windows' if is_windows else 'macOS' if is_mac else 'Linux'}")
print(f"  - Binaries count: {len(binaries + llama_binaries + tesseract_binaries)}")
print(f"  - Data files count: {len(datas + package_data)}")
print(f"  - Hidden imports count: {len(hidden_imports)}")
print(f"  - Using tesseract hook: {os.path.exists('tesseract_hook.py')}")
if os.path.exists(os.path.join(base_dir, 'OCR', 'tessdata', 'tessconfigs', 'configs')):
    config_files = os.listdir(os.path.join(base_dir, 'OCR', 'tessdata', 'tessconfigs', 'configs'))
    print(f"  - Bundled tessconfigs/configs directory contains: {config_files}")
print(f"{'='*50}\n")

# Create the PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=icon_file if icon_file and os.path.exists(icon_file) else None,
)

# Create the collection
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MDMT',
)

# For macOS, create a .app bundle
if is_mac:
    app = BUNDLE(
        coll,
        name='MDMT.app',
        icon=icon_file if icon_file and os.path.exists(icon_file) else None,
        bundle_identifier='com.jamescaldwell.mdmt',
    )
elif is_mac:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'mac_tesseract')
    if os.path.exists(tesseract_dir):
        # Add the main tesseract executable
        for file in glob.glob(os.path.join(tesseract_dir, 'tesseract')):
            tesseract_binaries.append((file, 'OCR'))
        # Add all dylib files
        for file in glob.glob(os.path.join(tesseract_dir, '*.dylib')):
            tesseract_binaries.append((file, 'OCR'))
        # Also look for dylibs in subdirectories
        for root, dirs, files in os.walk(tesseract_dir):
            for file in files:
                if file.lower().endswith('.dylib'):
                    file_path = os.path.join(root, file)
                    # Calculate destination path
                    rel_path = os.path.relpath(os.path.dirname(file_path), tesseract_dir)
                    if rel_path == '.':
                        dest_path = 'OCR'
                    else:
                        dest_path = os.path.join('OCR', rel_path)
                    tesseract_binaries.append((file_path, dest_path))
elif is_linux:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'linux_tesseract')
    if os.path.exists(tesseract_dir):
        # Add the main tesseract executable
        for file in glob.glob(os.path.join(tesseract_dir, 'tesseract')):
            tesseract_binaries.append((file, 'OCR'))
        # Add all shared object files
        for pattern in ['*.so', '*.so.*']:
            for file in glob.glob(os.path.join(tesseract_dir, pattern)):
                tesseract_binaries.append((file, 'OCR'))
        # Also look for shared objects in subdirectories
        for root, dirs, files in os.walk(tesseract_dir):
            for file in files:
                if file.lower().endswith(('.so', '.so.1', '.so.2', '.so.3', '.so.4')):
                    file_path = os.path.join(root, file)
                    # Calculate destination path
                    rel_path = os.path.relpath(os.path.dirname(file_path), tesseract_dir)
                    if rel_path == '.':
                        dest_path = 'OCR'
                    else:
                        dest_path = os.path.join('OCR', rel_path)
                    tesseract_binaries.append((file_path, dest_path))