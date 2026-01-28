#!/bin/bash
#
# KAS Filesync Installer
#

set -e

echo "╔════════════════════════════════════════╗"
echo "║       KAS Filesync Installer           ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Installation directories
APP_DIR="/Applications"
SUPPORT_DIR="$HOME/Library/Application Support/KAS Filesync"
REPO_URL="https://github.com/Stebibastian/kas-filesync"

# Create temporary directory for download
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Download repository
echo "→ Lade Repository herunter..."
if command -v git &> /dev/null; then
    git clone --depth 1 "$REPO_URL" "$TEMP_DIR/kas-filesync" 2>/dev/null
else
    curl -sL "$REPO_URL/archive/main.tar.gz" | tar xz -C "$TEMP_DIR"
    mv "$TEMP_DIR/kas-filesync-main" "$TEMP_DIR/kas-filesync"
fi
REPO_DIR="$TEMP_DIR/kas-filesync"
echo "  ✓ Repository heruntergeladen"

# Create support directory
echo "→ Erstelle Verzeichnisse..."
mkdir -p "$SUPPORT_DIR"

# Check for fswatch
echo "→ Prüfe Abhängigkeiten..."
if ! command -v fswatch &> /dev/null; then
    echo "  ⚠ fswatch nicht gefunden."
    if command -v brew &> /dev/null; then
        echo "  → Installiere fswatch mit Homebrew..."
        brew install fswatch
    else
        echo "  ✗ Bitte fswatch manuell installieren:"
        echo "    brew install fswatch"
        exit 1
    fi
else
    echo "  ✓ fswatch gefunden"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 nicht gefunden. Bitte installieren."
    exit 1
else
    echo "  ✓ Python 3 gefunden"
fi

# Install Python packages
echo "→ Installiere Python-Pakete..."
pip3 install --user rumps 2>/dev/null || pip3 install rumps
echo "  ✓ rumps installiert"

# Copy scripts to Application Support
echo "→ Kopiere Scripts..."
cp "$REPO_DIR/scripts/sync-files.py" "$SUPPORT_DIR/"
cp "$REPO_DIR/scripts/sync-menubar.py" "$SUPPORT_DIR/"
cp "$REPO_DIR/scripts/sync-manager.py" "$SUPPORT_DIR/"
echo "  ✓ Scripts kopiert nach $SUPPORT_DIR"

# Create config if not exists
if [ ! -f "$SUPPORT_DIR/sync-config.json" ]; then
    echo '{"pairs": []}' > "$SUPPORT_DIR/sync-config.json"
    echo "  ✓ Konfiguration erstellt"
fi

# Create app bundle
echo "→ Erstelle App..."
APP_PATH="$APP_DIR/KAS Filesync.app"
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Copy launcher
cp "$REPO_DIR/app/KAS Filesync" "$APP_PATH/Contents/MacOS/"
chmod +x "$APP_PATH/Contents/MacOS/KAS Filesync"

# Copy Info.plist
cp "$REPO_DIR/app/Info.plist" "$APP_PATH/Contents/"

# Copy icon
cp "$REPO_DIR/app/AppIcon.icns" "$APP_PATH/Contents/Resources/"

# Register app
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH"

echo "  ✓ App erstellt: $APP_PATH"

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         Installation abgeschlossen     ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Starte die App:"
echo "  open \"$APP_PATH\""
echo ""
echo "Oder suche 'KAS Filesync' in Spotlight."
echo ""
echo "Für Autostart: Systemeinstellungen → Anmeldeobjekte"
echo ""
