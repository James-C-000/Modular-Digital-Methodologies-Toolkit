# tesseract_hook.py
import os
import sys
import tempfile


def setup_tesseract_environment():
    # Only run setup if we're in a PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        # Base directories
        meipass_dir = sys._MEIPASS
        tessdata_dir = os.path.join(meipass_dir, 'OCR', 'tessdata')

        # Set environment variables
        os.environ["TESSDATA_PREFIX"] = tessdata_dir

        # Create temporary config directory
        temp_dir = tempfile.mkdtemp(prefix='tesseract_')
        temp_configs = os.path.join(temp_dir, 'configs')
        os.makedirs(temp_configs, exist_ok=True)

        # Create essential config files
        config_files = {
            'hocr': 'tessedit_create_hocr 1\nhocr_font_info 0\n',
            'txt': 'tessedit_create_txt 1\n'
        }

        for name, content in config_files.items():
            with open(os.path.join(temp_configs, name), 'w') as f:
                f.write(content)

        # Set a custom environment variable with this path
        os.environ["TESSCONFIG_PATH"] = temp_configs
        print(f"Tesseract environment set up with TESSDATA_PREFIX={tessdata_dir}")


# Run setup when the hook is loaded
setup_tesseract_environment()