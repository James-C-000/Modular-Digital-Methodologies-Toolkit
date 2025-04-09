
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
