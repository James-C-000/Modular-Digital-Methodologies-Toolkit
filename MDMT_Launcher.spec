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

# Find and include ocrmypdf data files
ocrmypdf_data_dir = os.path.join(os.path.dirname(ocrmypdf.__file__), 'data')
if os.path.exists(ocrmypdf_data_dir):
    for root, dirs, files in os.walk(ocrmypdf_data_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.join('ocrmypdf', 'data', os.path.relpath(file_path, ocrmypdf_data_dir))
            datas.append((file_path, os.path.dirname(rel_path)))

# Explicitly include images
for file in glob.glob(os.path.join(base_dir, '*.png')) + glob.glob(os.path.join(base_dir, '*.ico')):
    datas.append((file, '.'))

# Include directories with their contents
for directory in [
    'OCR',
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

# Collect data from packages
binaries = []
package_data = []

# Core packages with data files
for package in ['nltk', 'transformers', 'whisper', 'torch']:
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

# Create a runtime hook to set up NLTK data path
with open('runtime_hook.py', 'w') as f:
    f.write("""
import os
import sys
import nltk

# Set the NLTK data path to be relative to the executable
nltk_data_dir = os.path.join(sys._MEIPASS, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.insert(0, nltk_data_dir)
""")

# Add platform-specific Tesseract binaries
tesseract_binaries = []
if is_windows:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'win_tesseract')
    if os.path.exists(tesseract_dir):
        for file in glob.glob(os.path.join(tesseract_dir, '*.exe')):
            tesseract_binaries.append((file, 'OCR'))
        for file in glob.glob(os.path.join(tesseract_dir, '*.dll')):
            tesseract_binaries.append((file, 'OCR'))
elif is_mac:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'mac_tesseract')
    if os.path.exists(tesseract_dir):
        for file in glob.glob(os.path.join(tesseract_dir, 'tesseract')):
            tesseract_binaries.append((file, 'OCR'))
        for file in glob.glob(os.path.join(tesseract_dir, '*.dylib')):
            tesseract_binaries.append((file, 'OCR'))
elif is_linux:
    tesseract_dir = os.path.join(base_dir, 'OCR', 'linux_tesseract')
    if os.path.exists(tesseract_dir):
        for file in glob.glob(os.path.join(tesseract_dir, 'tesseract')):
            tesseract_binaries.append((file, 'OCR'))
        for file in glob.glob(os.path.join(tesseract_dir, '*.so*')):
            tesseract_binaries.append((file, 'OCR'))

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