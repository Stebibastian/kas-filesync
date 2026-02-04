#!/bin/bash
#
# KAS Filesync Diagnostic Script
# Run this to collect debug information when the app doesn't start
#

echo "======================================"
echo "KAS Filesync Diagnostic Report"
echo "======================================"
echo ""
echo "Date: $(date)"
echo "macOS Version: $(sw_vers -productVersion)"
echo ""

SUPPORT_DIR="$HOME/Library/Application Support/KAS Filesync"

echo "=== Python Installation ==="
echo ""
echo "Available Python installations:"
for p in /usr/local/bin/python3* /Library/Frameworks/Python.framework/Versions/*/bin/python3* /opt/homebrew/bin/python3* /usr/bin/python3; do
    if [ -x "$p" ] 2>/dev/null; then
        version=$("$p" --version 2>&1)
        echo "  $p -> $version"
    fi
done

echo ""
echo "=== rumps Module Check ==="
echo ""
for p in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ] 2>/dev/null; then
        echo -n "  $p: "
        if "$p" -c "import rumps; print('OK -', rumps.__file__)" 2>/dev/null; then
            :
        else
            echo "NOT FOUND"
        fi
    fi
done

echo ""
echo "=== App Installation ==="
echo ""
APP_PATH="/Applications/KAS Filesync.app"
if [ -d "$APP_PATH" ]; then
    echo "App found: $APP_PATH"
    echo "Launcher exists: $([ -x "$APP_PATH/Contents/MacOS/KAS Filesync" ] && echo 'YES' || echo 'NO')"
else
    echo "App NOT FOUND at $APP_PATH"
fi

echo ""
echo "=== Support Directory ==="
echo ""
echo "Path: $SUPPORT_DIR"
if [ -d "$SUPPORT_DIR" ]; then
    echo "Contents:"
    ls -la "$SUPPORT_DIR" 2>/dev/null
else
    echo "  Directory does not exist! (This is normal before first run)"
fi

echo ""
echo "=== Log Files ==="

for log in "kas-filesync-launcher.log" "sync-menubar.log" "sync-daemon-stderr.log" "sync-files.log"; do
    logfile="$SUPPORT_DIR/$log"
    echo ""
    echo "--- $log ---"
    if [ -f "$logfile" ]; then
        tail -30 "$logfile"
    else
        echo "  (not found)"
    fi
done

echo ""
echo "=== Running Processes ==="
echo ""
echo "Menubar app:"
pgrep -fl "sync-menubar" 2>/dev/null || echo "  Not running"
echo ""
echo "Sync daemon:"
pgrep -fl "sync-files" 2>/dev/null || echo "  Not running"

echo ""
echo "=== Manual Test ==="
echo ""
echo "Testing menubar script import..."
PYTHON3=""
for p in /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    if [ -x "$p" ] && "$p" -c "import rumps" 2>/dev/null; then
        PYTHON3="$p"
        break
    fi
done

if [ -n "$PYTHON3" ]; then
    echo "Using Python: $PYTHON3"
    cd "$SUPPORT_DIR" 2>/dev/null || cd "$(dirname "$0")/.."
    "$PYTHON3" -c "
import sys
sys.path.insert(0, '$SUPPORT_DIR')
print('Testing imports...')
try:
    import rumps
    print('  rumps: OK')
except ImportError as e:
    print(f'  rumps: FAILED - {e}')
try:
    import AppKit
    print('  AppKit: OK')
except ImportError as e:
    print(f'  AppKit: FAILED - {e}')
print('All imports OK!')
" 2>&1
else
    echo "No Python with rumps found!"
fi

echo ""
echo "======================================"
echo "End of Diagnostic Report"
echo "======================================"
echo ""
echo "Please share this output when reporting issues."
