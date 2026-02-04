#!/usr/bin/env python3
"""
Menubar app for KAS Filesync.
- Shows sync status (active/stopped)
- Start/Stop the sync daemon
- Open connection manager
- View sync log
"""

import os
import subprocess
import sys
from datetime import datetime

SUPPORT_DIR = os.path.expanduser("~/Library/Application Support/KAS Filesync")
MENUBAR_LOG = os.path.join(SUPPORT_DIR, "sync-menubar.log")

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

# Import rumps first
try:
    import rumps
    debug_log(f"rumps loaded successfully from {rumps.__file__}")
except ImportError as e:
    debug_log(f"FATAL: Cannot import rumps: {e}")
    raise

# Hide Python icon from Dock AFTER rumps import
try:
    import AppKit
    # NSApplicationActivationPolicyAccessory = 1 (no dock icon, but can have menu bar)
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
    debug_log("AppKit: dock icon hidden")
except Exception as e:
    debug_log(f"AppKit error (non-fatal): {e}")

DAEMON_SCRIPT = os.path.join(SUPPORT_DIR, "sync-files.py")
LOG_FILE = os.path.join(SUPPORT_DIR, "sync-files.log")
PID_FILE = os.path.join(SUPPORT_DIR, "sync-daemon.pid")

# Simple text icons (emojis can cause issues on some systems)
ICON_ACTIVE = "KAS"
ICON_STOPPED = "kas"


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
        debug_log("SyncMenuBarApp.__init__ starting")
        super().__init__("KAS", quit_button=None)  # Start with simple title
        debug_log("rumps.App.__init__ completed")
        self.build_menu()
        debug_log("build_menu() completed")

    def build_menu(self):
        """Rebuild the entire menu from current config."""
        self.menu.clear()

        # Status
        self.status_item = rumps.MenuItem("Status: ...")
        self.status_item.set_callback(None)
        self.menu.add(self.status_item)
        self.menu.add(rumps.separator)

        # Toggle
        self.toggle_item = rumps.MenuItem("Sync stoppen", callback=self.toggle_sync)
        self.menu.add(self.toggle_item)
        self.menu.add(rumps.separator)

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
        if running:
            self.title = ICON_ACTIVE
            self.status_item.title = "Status: Aktiv"
            self.toggle_item.title = "Sync stoppen"
        else:
            self.title = ICON_STOPPED
            self.status_item.title = "Status: Gestoppt"
            self.toggle_item.title = "Sync starten"

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
