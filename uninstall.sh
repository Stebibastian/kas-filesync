#!/bin/bash
#
# KAS Filesync Uninstaller
# Completely removes KAS Filesync from the system
#

echo "╔════════════════════════════════════════╗"
echo "║       KAS Filesync Deinstallation      ║"
echo "╚════════════════════════════════════════╝"
echo ""

APP_PATH="/Applications/KAS Filesync.app"
SUPPORT_DIR="$HOME/Library/Application Support/KAS Filesync"

# Confirm
echo "Dies wird folgendes entfernen:"
echo "  - $APP_PATH"
echo "  - $SUPPORT_DIR (inkl. Konfiguration und Logs)"
echo ""
read -p "Fortfahren? (j/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[JjYy]$ ]]; then
    echo "Abgebrochen."
    exit 0
fi

echo ""

# Stop running processes
echo "→ Stoppe laufende Prozesse..."
pkill -f "sync-menubar.py" 2>/dev/null && echo "  ✓ Menubar-App gestoppt" || echo "  - Menubar-App war nicht aktiv"
pkill -f "sync-files.py" 2>/dev/null && echo "  ✓ Sync-Daemon gestoppt" || echo "  - Sync-Daemon war nicht aktiv"
sleep 1

# Remove app
echo "→ Entferne App..."
if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    echo "  ✓ App entfernt"
else
    echo "  - App war nicht installiert"
fi

# Remove support directory
echo "→ Entferne Konfiguration und Logs..."
if [ -d "$SUPPORT_DIR" ]; then
    rm -rf "$SUPPORT_DIR"
    echo "  ✓ Support-Verzeichnis entfernt"
else
    echo "  - Support-Verzeichnis existierte nicht"
fi

# Remove from Login Items (informational)
echo ""
echo "╔════════════════════════════════════════╗"
echo "║       Deinstallation abgeschlossen     ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Falls KAS Filesync in den Anmeldeobjekten war,"
echo "bitte manuell entfernen:"
echo "  Systemeinstellungen → Allgemein → Anmeldeobjekte"
echo ""
echo "Zur Neuinstallation:"
echo "  curl -fsSL https://raw.githubusercontent.com/Stebibastian/kas-filesync/main/install.sh | bash"
echo ""
