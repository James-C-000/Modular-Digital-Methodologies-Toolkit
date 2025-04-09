# tesseract_hook.py
import os
import sys
import tempfile
import shutil
import atexit


def setup_tesseract_environment():
    """
    Set up Tesseract OCR environment for PyInstaller bundled applications.

    This function:
    1. Sets TESSDATA_PREFIX to the bundled tessdata directory
    2. Checks for and uses bundled tessconfigs if available
    3. Creates temporary configs only if bundled ones aren't available
    """
    # Only run setup if we're in a PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        # Base directories
        meipass_dir = sys._MEIPASS
        tessdata_dir = os.path.join(meipass_dir, 'OCR', 'tessdata')

        # Clean up any existing temp directories that might be left over from crashes
        temp_dir = tempfile.gettempdir()
        for item in os.listdir(temp_dir):
            if item.startswith('mdmt_tesseract_'):
                try:
                    path = os.path.join(temp_dir, item)
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                except Exception:
                    pass

        # Set the TESSDATA_PREFIX environment variable
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        print(f"Set TESSDATA_PREFIX to {tessdata_dir}")

        # Check if bundled tessconfigs/configs directory exists and has files
        bundled_configs_path = os.path.join(tessdata_dir, 'tessconfigs', 'configs')
        has_bundled_configs = os.path.exists(bundled_configs_path) and len(os.listdir(bundled_configs_path)) > 0

        if has_bundled_configs:
            # Use bundled configs directly
            os.environ["TESSCONFIG_PATH"] = bundled_configs_path
            print(f"Using bundled Tesseract config files from: {bundled_configs_path}")

            # Check for specific required config files
            for required_config in ['hocr', 'txt', 'pdf']:
                config_path = os.path.join(bundled_configs_path, required_config)
                if not os.path.exists(config_path):
                    print(f"Warning: Required config '{required_config}' not found in bundled configs")
        else:
            # Create a new temporary directory for configs
            temp_dir = tempfile.mkdtemp(prefix='mdmt_tesseract_')
            temp_configs = os.path.join(temp_dir, 'configs')
            os.makedirs(temp_configs, exist_ok=True)

            # Define essential config files
            config_files = {
                'hocr': 'tessedit_create_hocr 1\nhocr_font_info 0\n',
                'txt': 'tessedit_create_txt 1\n',
                'pdf': 'tessedit_create_pdf 1\n',
                'alto': 'tessedit_create_alto 1\n',
                'tsv': 'tessedit_create_tsv 1\n'
            }

            # Create the config files
            for name, content in config_files.items():
                with open(os.path.join(temp_configs, name), 'w') as f:
                    f.write(content)

            # Set the path to our temporary config files
            os.environ["TESSCONFIG_PATH"] = temp_configs
            print(f"Created temporary Tesseract config files at: {temp_configs}")

            # Register cleanup function to run on exit
            atexit.register(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        # Double check if critical environment variables are set
        if "TESSDATA_PREFIX" not in os.environ:
            print("Warning: TESSDATA_PREFIX not set")
        if "TESSCONFIG_PATH" not in os.environ:
            print("Warning: TESSCONFIG_PATH not set")

        # Print the final configuration
        print(f"Tesseract environment successfully initialized:")
        print(f"  - TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX', 'Not set')}")
        print(f"  - TESSCONFIG_PATH: {os.environ.get('TESSCONFIG_PATH', 'Not set')}")


# Run setup when the hook is loaded
setup_tesseract_environment()