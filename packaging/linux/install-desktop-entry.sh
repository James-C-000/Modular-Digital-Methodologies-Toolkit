#!/bin/sh
# Add MDMT to your desktop's application menu (current user only).
# Run from the extracted mdmt folder:   ./install-desktop-entry.sh
# Remove with:                          ./install-desktop-entry.sh --uninstall
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
ENTRY="$APPS/net.jamescaldwell.mdmt.desktop"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$ENTRY" "$ICONS/net.jamescaldwell.mdmt.png"
  echo "Removed the MDMT menu entry."
  exit 0
fi

mkdir -p "$APPS" "$ICONS"
cp "$HERE/mdmt.png" "$ICONS/net.jamescaldwell.mdmt.png"
cat > "$ENTRY" <<DESKTOP
[Desktop Entry]
Type=Application
Name=MDMT
GenericName=Digital humanities toolkit
Comment=Modular Digital Methodologies Toolkit (opens in your web browser)
Exec="$HERE/mdmt"
Icon=net.jamescaldwell.mdmt
Terminal=false
Categories=Education;Science;Office;
DESKTOP
chmod 644 "$ENTRY"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "Added MDMT to your application menu ($ENTRY)."
