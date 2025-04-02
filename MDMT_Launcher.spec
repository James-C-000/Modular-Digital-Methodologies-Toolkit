# MDMT_Launcher.spec
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# Base directory - use current working directory
base_dir = os.getcwd()

# Define a block cipher (None in this case)
block_cipher = None

# Define executable name based on platform
if sys.platform.startswith('win'):
    exe_name = 'MDMT.exe'
elif sys.platform.startswith('darwin'):
    exe_name = 'MDMT'
else:
    exe_name = 'MDMT'

# Explicitly list all UI files with their full paths
ui_files = []
for ui_file in [
    'aksWindow.ui',
    'audioTranscriptionWindow.ui',
    'coWordAnalysisWindow.ui',
    'defaultWindow.ui',
    'nerWindow.ui',
    'ocrWindow.ui',
    'ragWindow.ui',
    'relationshipExtractionWindow.ui',
    'translationWindow.ui'
]:
    full_path = os.path.join(base_dir, ui_file)
    if os.path.exists(full_path):
        ui_files.append((full_path, '.'))
    else:
        print(f"Warning: UI file not found: {full_path}")

# Define data files to include
datas = []
datas.extend(ui_files)

# Include required directories
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
        datas.append((dir_path, directory))
    else:
        print(f"Warning: Directory not found: {dir_path}")

# Find all image files in the base directory
for file in os.listdir(base_dir):
    if file.endswith('.png') or file.endswith('.ico'):
        datas.append((os.path.join(base_dir, file), '.'))

# Collect all necessary modules
for module_name in ['whisper', 'torch', 'ocrmypdf', 'pygubu', 'nltk']:
    try:
        module_datas, module_binaries, module_hiddenimports = collect_all(module_name)
        datas.extend(module_datas)
        binaries = module_binaries  # We'll accumulate all binaries
        # Also collect metadata
        datas.extend(copy_metadata(module_name))
    except Exception as e:
        print(f"Warning: Could not collect {module_name} module: {e}")

# Define hidden imports
hidden_imports = [
    # GUI framework
    'pygubu',
    'pygubu.builder',
    'pygubu.builder.tkstdwidgets',
    'pygubu.builder.widgets.dialog',
    'pygubu.builder.widgets.tkinterscrolledtext',
    'pygubu.builder.widgets.pathchooserinput',
    'tkinter',
    'tkinter.ttk',

    # Data processing
    'pandas',
    'matplotlib',
    'matplotlib.backends.backend_tkagg',

    # NLP
    'nltk',
    'nltk.tokenize',
    'nltk.corpus',
    'nltk.data',
    'transformers',

    # OCR processing
    'ocrmypdf',
    'ocrmypdf.data',

    # Audio processing
    'whisper',
    'torch',

    # Others
    'glob',
    'json',
    're',
    'collections',
    'time',
    'asyncio',
    'threading',
]

# Add all submodules
for module_name in ['pygubu', 'nltk', 'ocrmypdf']:
    hidden_imports.extend(collect_submodules(module_name))

# Create a runtime hook to set up NLTK data path
runtime_hook = """
import os
import sys
import nltk

# Set the NLTK data path to be relative to the executable
nltk_data_dir = os.path.join(sys._MEIPASS, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.insert(0, nltk_data_dir)
"""

with open('runtime_hook.py', 'w') as f:
    f.write(runtime_hook)

# Define the Analysis object
a = Analysis(
    ['MDMT_Launcher.py'],
    pathex=[base_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
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
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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