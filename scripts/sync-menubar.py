#!/usr/bin/env python3
"""
Menubar app for KAS Filesync.
- Shows sync status (active/stopped)
- Shows conflict status
- Start/Stop the sync daemon
- Open connection manager
- Open conflict resolver
- View sync log
"""

import json
import os
import subprocess
import sys
from datetime import datetime

SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/KAS Filesync")
MENUBAR_LOG = os.path.join(SUPPORT_DIR, "sync-menubar.log")
CONFLICTS_FILE = os.path.join(SUPPORT_DIR, "conflicts.json")

def debug_log(msg):
    """Log debug messages to menubar log file."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(MENUBAR_LOG, "a") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass

debug_log("=== Menubar app starting ===")
debug_log(f"Python: {sys.executable}")
debug_log(f"Python version: {sys.version}")
debug_log(f"sys.path: {sys.path}")

# Hide Python icon from Dock
try:
    import AppKit
    # NSApplicationActivationPolicyAccessory = 1 (no dock icon, but can have menu bar)
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
    debug_log("AppKit loaded, dock icon hidden")
except Exception as e:
    debug_log(f"AppKit error (non-fatal): {e}")

try:
    import rumps
    debug_log(f"rumps loaded successfully from {rumps.__file__}")
except ImportError as e:
    debug_log(f"FATAL: Cannot import rumps: {e}")
    raise

DAEMON_SCRIPT = os.path.join(SUPPORT_DIR, "sync-files.py")
LOG_FILE = os.path.join(SUPPORT_DIR, "sync-files.log")
PID_FILE = os.path.join(SUPPORT_DIR, "sync-daemon.pid")

ICON_ACTIVE = "🔄"
ICON_STOPPED = "⏸️"
ICON_CONFLICT = "⚠️"


def is_daemon_running():
    """Check if the sync daemon is running."""
    # First check PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # Check if process is still running
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            # PID file exists but process is dead
            try:
                os.remove(PID_FILE)
            except OSError:
                pass

    # Fallback: check with pgrep
    try:
        result = subprocess.run(
            ["pgrep", "-f", "sync-files.py"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_conflicts():
    """Load and return active conflicts."""
    if os.path.exists(CONFLICTS_FILE):
        try:
            with open(CONFLICTS_FILE, "r") as f:
                data = json.load(f)
                return data if data else {}
        except:
            pass
    return {}


def get_conflict_count():
    """Return the number of active conflicts."""
    conflicts = get_conflicts()
    return len(conflicts)


def start_daemon():
    """Start the sync daemon."""
    debug_log("start_daemon() called")
    if is_daemon_running():
        debug_log("Daemon already running, skipping start")
        return True

    try:
        # Use the same Python that's running this script
        python_path = sys.executable
        debug_log(f"Starting daemon with Python: {python_path}")
        debug_log(f"Daemon script: {DAEMON_SCRIPT}")

        if not os.path.exists(DAEMON_SCRIPT):
            debug_log(f"ERROR: Daemon script not found: {DAEMON_SCRIPT}")
            rumps.alert("Fehler", f"Daemon-Script nicht gefunden: {DAEMON_SCRIPT}")
            return False

        stdout_log = os.path.join(SUPPORT_DIR, "sync-daemon-stdout.log")
        stderr_log = os.path.join(SUPPORT_DIR, "sync-daemon-stderr.log")
        debug_log(f"stdout -> {stdout_log}")
        debug_log(f"stderr -> {stderr_log}")

        proc = subprocess.Popen(
            [python_path, DAEMON_SCRIPT],
            stdout=open(stdout_log, "a"),
            stderr=open(stderr_log, "a"),
            start_new_session=True
        )
        # Save PID
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
        debug_log(f"Daemon started with PID {proc.pid}")
        return True
    except Exception as e:
        debug_log(f"ERROR starting daemon: {e}")
        rumps.alert("Fehler", f"Konnte Daemon nicht starten: {e}")
        return False


def stop_daemon():
    """Stop the sync daemon."""
    stopped = False

    # Try PID file first
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 15)  # SIGTERM
            stopped = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        try:
            os.remove(PID_FILE)
        except OSError:
            pass

    # Also try pkill as fallback
    try:
        subprocess.run(["pkill", "-f", "sync-files.py"], capture_output=True)
        stopped = True
    except Exception:
        pass

    return stopped


def get_last_log(n=10):
    try:
        if not os.path.exists(LOG_FILE):
            return "Kein Log vorhanden"
        result = subprocess.run(
            ["tail", "-n", str(n), LOG_FILE],
            capture_output=True, text=True
        )
        return result.stdout.strip() or "Log leer"
    except Exception:
        return "Fehler beim Lesen"


class SyncMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("KAS Filesync", quit_button=None)
        self.conflict_count = 0
        self.build_menu()

    def build_menu(self):
        """Rebuild the entire menu from current config."""
        self.menu.clear()

        # Status
        self.status_item = rumps.MenuItem("Status: ...")
        self.status_item.set_callback(None)
        self.menu.add(self.status_item)

        # Conflict status
        self.conflict_item = rumps.MenuItem("Konflikte: 0")
        self.conflict_item.set_callback(None)
        self.menu.add(self.conflict_item)
        self.menu.add(rumps.separator)

        # Toggle
        self.toggle_item = rumps.MenuItem("Sync stoppen", callback=self.toggle_sync)
        self.menu.add(self.toggle_item)
        self.menu.add(rumps.separator)

        # Conflict resolver (only shown when conflicts exist)
        self.resolve_item = rumps.MenuItem("Konflikte auflösen...", callback=self.open_resolver)
        self.menu.add(self.resolve_item)

        # Open manager window
        manage_item = rumps.MenuItem("Verbindungen verwalten...", callback=self.open_manager)
        self.menu.add(manage_item)
        self.menu.add(rumps.separator)

        # Log
        log_item = rumps.MenuItem("Log anzeigen", callback=self.show_log)
        self.menu.add(log_item)
        self.menu.add(rumps.separator)

        # Quit
        quit_item = rumps.MenuItem("Beenden", callback=self.quit_app)
        self.menu.add(quit_item)

        self.update_status()

    def update_status(self):
        running = is_daemon_running()
        self.conflict_count = get_conflict_count()

        # Update icon based on status
        if self.conflict_count > 0:
            self.title = ICON_CONFLICT
        elif running:
            self.title = ICON_ACTIVE
        else:
            self.title = ICON_STOPPED

        # Update status text
        if running:
            self.status_item.title = "Status: Aktiv"
            self.toggle_item.title = "Sync stoppen"
        else:
            self.status_item.title = "Status: Gestoppt"
            self.toggle_item.title = "Sync starten"

        # Update conflict display
        if self.conflict_count > 0:
            self.conflict_item.title = f"⚠️ {self.conflict_count} Konflikt{'e' if self.conflict_count != 1 else ''}"
            self.resolve_item.hidden = False
        else:
            self.conflict_item.title = "Konflikte: Keine"
            self.resolve_item.hidden = True

    @rumps.timer(5)
    def periodic_check(self, _):
        self.update_status()

    def toggle_sync(self, _):
        if is_daemon_running():
            stop_daemon()
            rumps.notification("KAS Filesync", "Gestoppt", "Sync-Daemon wurde gestoppt.", sound=False)
        else:
            if start_daemon():
                rumps.notification("KAS Filesync", "Gestartet", "Sync-Daemon wurde gestartet.", sound=False)
        self.update_status()

    def open_manager(self, _):
        """Open the sync manager window."""
        manager_script = os.path.join(SUPPORT_DIR, "sync-manager.py")
        subprocess.Popen([sys.executable, manager_script])

    def open_resolver(self, _):
        """Open the conflict resolver window."""
        conflicts = get_conflicts()
        if not conflicts:
            rumps.alert("Keine Konflikte", "Es gibt keine ungelösten Konflikte.")
            return

        # Show conflict summary and options
        conflict_list = []
        for key, info in conflicts.items():
            filename = os.path.basename(info.get("source", "?"))
            count = info.get("conflict_count", 0)
            conflict_list.append(f"• {filename}: {count} Konflikt{'e' if count != 1 else ''}")

        message = "Folgende Dateien haben Konflikte:\n\n" + "\n".join(conflict_list)
        message += "\n\nÖffne die Dateien in einem Texteditor und suche nach den Konflikt-Markern:\n"
        message += "<<<<<<< SOURCE\n=======\n>>>>>>> TARGET\n\n"
        message += "Nach dem Bearbeiten wird der Konflikt automatisch aufgelöst."

        response = rumps.alert(
            title="Konflikte auflösen",
            message=message,
            ok="Dateien öffnen",
            cancel="Schließen"
        )

        if response == 1:  # OK clicked
            # Open conflicted files in default editor
            for key, info in conflicts.items():
                source = info.get("source")
                if source and os.path.exists(source):
                    subprocess.Popen(["open", source])

    def show_log(self, _):
        lines = get_last_log(12)
        rumps.alert(title="Sync Log", message=lines)

    def quit_app(self, _):
        # Stop daemon when quitting
        stop_daemon()
        rumps.quit_application()


if __name__ == "__main__":
    debug_log("Creating SyncMenuBarApp instance...")
    try:
        app = SyncMenuBarApp()
        debug_log("SyncMenuBarApp created, calling run()")
        app.run()
    except Exception as e:
        debug_log(f"FATAL ERROR in menubar app: {e}")
        import traceback
        debug_log(traceback.format_exc())
        raise
