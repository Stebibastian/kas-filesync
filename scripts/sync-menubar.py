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

# Hide Python icon from Dock
try:
    import AppKit
    # NSApplicationActivationPolicyAccessory = 1 (no dock icon, but can have menu bar)
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
except Exception:
    pass

import rumps

LOG_FILE = os.path.expanduser("~/Library/Application Support/KAS Filesync/sync-files.log")
DAEMON_LABEL = "com.realview.sync-files"
DAEMON_PLIST = os.path.expanduser("~/Library/LaunchAgents/com.realview.sync-files.plist")

ICON_ACTIVE = "🔄"
ICON_STOPPED = "⏸️"


def is_daemon_running():
    try:
        result = subprocess.run(
            ["launchctl", "list", DAEMON_LABEL],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


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
        self.build_menu()

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
            subprocess.run(["launchctl", "unload", DAEMON_PLIST], capture_output=True)
            rumps.notification("KAS Filesync", "Gestoppt", "Sync-Daemon wurde gestoppt.", sound=False)
        else:
            subprocess.run(["launchctl", "load", DAEMON_PLIST], capture_output=True)
            rumps.notification("KAS Filesync", "Gestartet", "Sync-Daemon wurde gestartet.", sound=False)
        self.update_status()

    def open_manager(self, _):
        """Open the sync manager window."""
        manager_script = os.path.expanduser("~/Library/Application Support/KAS Filesync/sync-manager.py")
        subprocess.Popen(["python3", manager_script])

    def show_log(self, _):
        lines = get_last_log(12)
        rumps.alert(title="Sync Log", message=lines)

    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    SyncMenuBarApp().run()
