#!/bin/bash
# =============================================================================
# This script downloads and installs FFmpeg on macOS using the Evermeet.cx
# download API and adds the installation directory to the user's PATH.
#
# It performs the following steps:
#   1. Checks that curl and unzip are installed.
#   2. Downloads the latest FFmpeg release as a zip file from:
#      https://evermeet.cx/ffmpeg/getrelease/zip
#   3. Extracts the zip file into ~/bin (creating it if necessary).
#   4. Makes sure the ffmpeg binary is executable.
#   5. Adds ~/bin to the user's PATH (in ~/.zshrc or ~/.bash_profile) if not already present.
# =============================================================================

# Check for required commands
if ! command -v curl &>/dev/null; then
    echo "Error: curl is not installed. Please install curl and try again."
    exit 1
fi

if ! command -v unzip &>/dev/null; then
    echo "Error: unzip is not installed. Please install unzip and try again."
    exit 1
fi

# Create a temporary directory for download
TMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TMP_DIR"

# Set download URL for the latest FFmpeg release from Evermeet.cx API
FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/zip"
ZIP_FILE="$TMP_DIR/ffmpeg.zip"

echo "Downloading FFmpeg from $FFMPEG_URL ..."
curl -L "$FFMPEG_URL" -o "$ZIP_FILE"
if [ $? -ne 0 ]; then
    echo "Error: Failed to download FFmpeg."
    exit 1
fi
echo "Downloaded FFmpeg zip to $ZIP_FILE"

# Define target installation directory (using ~/bin in this example)
INSTALL_DIR="$HOME/bin"
mkdir -p "$INSTALL_DIR"
echo "Installation directory: $INSTALL_DIR"

# Extract the downloaded zip file into the installation directory
echo "Extracting FFmpeg..."
unzip -q "$ZIP_FILE" -d "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to extract FFmpeg."
    exit 1
fi

# Clean up temporary directory
rm -rf "$TMP_DIR"
echo "Temporary files cleaned up."

# Ensure the ffmpeg binary is executable
chmod +x "$INSTALL_DIR/ffmpeg"

# Check if the installation directory is already in the PATH
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
    echo "The directory $INSTALL_DIR is not in your PATH."
    # Determine user's shell and choose the appropriate profile file
    SHELL_NAME=$(basename "$SHELL")
    if [ "$SHELL_NAME" = "zsh" ]; then
        PROFILE_FILE="$HOME/.zshrc"
    else
        PROFILE_FILE="$HOME/.bash_profile"
    fi
    echo "Adding $INSTALL_DIR to your PATH in $PROFILE_FILE..."
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$PROFILE_FILE"
    echo "PATH updated. Please restart your terminal or run: source $PROFILE_FILE"
else
    echo "$INSTALL_DIR is already in your PATH."
fi

echo "FFmpeg installation complete. You can now run 'ffmpeg' from the command line."
