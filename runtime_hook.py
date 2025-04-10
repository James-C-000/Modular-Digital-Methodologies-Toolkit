
import os
import sys
import nltk

# Set the NLTK data path to be relative to the executable
nltk_data_dir = os.path.join(sys._MEIPASS, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.insert(0, nltk_data_dir)

# Add tesseract runtime configuration
def configure_tesseract():
    if hasattr(sys, '_MEIPASS'):
        # We're running in a PyInstaller bundle
        bundle_dir = sys._MEIPASS
        
        # Set TESSDATA_PREFIX to point to the bundled tessdata directory
        os.environ['TESSDATA_PREFIX'] = os.path.join(bundle_dir, 'OCR', 'tessdata')
        
        # For ocrmypdf, ensure it can find the tesseract binary
        if 'TESSERACT_PATH' not in os.environ:
            tesseract_bin = os.path.join(bundle_dir, 'tesseract')
            if os.name == 'nt':  # Windows
                tesseract_bin += '.exe'
            if os.path.exists(tesseract_bin):
                os.environ['TESSERACT_PATH'] = tesseract_bin
                print(f"Using bundled tesseract binary at: {tesseract_bin}")
            else:
                print(f"Warning: Expected tesseract binary at {tesseract_bin} not found!")

# Configure tesseract at startup
configure_tesseract()
