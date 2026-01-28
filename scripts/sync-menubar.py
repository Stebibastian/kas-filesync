#!/usr/bin/env python3
"""
Menubar app for multi-pair file sync.
- Shows sync status (active/stopped)
- Start/Stop the sync daemon
- Add new file pairs (source + target) via file picker
- Remove existing pairs
- View sync log
"""

import json
import os
import subprocess
import rumps

CONFIG = os.path.expanduser("~/Scripts/sync-config.json")
LOG_FILE = os.path.expanduser("~/Scripts/sync-files.log")
DAEMON_LABEL = "com.realview.sync-files"
DAEMON_PLIST = os.path.expanduser("~/Library/LaunchAgents/com.realview.sync-files.plist")

ICON_ACTIVE = "🔄"
ICON_STOPPED = "⏸️"


def load_config():
    try:
        with open(CONFIG, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pairs": []}


def save_config(data):
    with open(CONFIG, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    f.close()


def is_daemon_running():
    try:
        result = subprocess.run(
            ["launchctl", "list", DAEMON_LABEL],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def restart_daemon():
    """Unload and reload the daemon to pick up config changes."""
    subprocess.run(["launchctl", "unload", DAEMON_PLIST], capture_output=True)
    import time
    time.sleep(1)
    subprocess.run(["launchctl", "load", DAEMON_PLIST], capture_output=True)


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


def pick_file(prompt="Datei waehlen"):
    """Use AppleScript to open a native file picker dialog."""
    script = f'''
    set chosenFile to choose file with prompt "{prompt}"
    return POSIX path of chosenFile
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def input_dialog(prompt, default=""):
    """Use AppleScript for text input."""
    script = f'''
    set userInput to text returned of (display dialog "{prompt}" default answer "{default}")
    return userInput
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


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

        # Current pairs submenu
        config = load_config()
        pairs_menu = rumps.MenuItem("Sync-Paare")

        if not config["pairs"]:
            empty = rumps.MenuItem("(keine Paare konfiguriert)")
            empty.set_callback(None)
            pairs_menu.add(empty)
        else:
            for i, pair in enumerate(config["pairs"]):
                name = pair.get("name", f"Paar {i+1}")
                src_short = os.path.basename(pair["source"])
                tgt_dir = os.path.basename(os.path.dirname(pair["target"]))

                pair_submenu = rumps.MenuItem(f"{name}")

                info = rumps.MenuItem(f"  {src_short}  <->  .../{tgt_dir}/")
                info.set_callback(None)
                pair_submenu.add(info)

                src_item = rumps.MenuItem(f"  Quelle: {pair['source']}")
                src_item.set_callback(None)
                pair_submenu.add(src_item)

                tgt_item = rumps.MenuItem(f"  Ziel: {pair['target']}")
                tgt_item.set_callback(None)
                pair_submenu.add(tgt_item)

                pair_submenu.add(rumps.separator)

                remove_item = rumps.MenuItem(
                    f"  Entfernen",
                    callback=self.make_remove_callback(i, name)
                )
                pair_submenu.add(remove_item)

                pairs_menu.add(pair_submenu)

        self.menu.add(pairs_menu)

        # Open manager window
        manage_item = rumps.MenuItem("Verbindungen verwalten...", callback=self.open_manager)
        self.menu.add(manage_item)

        # Add new pair
        add_item = rumps.MenuItem("Neues Paar hinzufuegen...", callback=self.add_pair)
        self.menu.add(add_item)
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

    def add_pair(self, _):
        # Step 1: Name
        name = input_dialog("Name fuer das Sync-Paar (z.B. 'JF FIB'):", "Neues Paar")
        if not name:
            return

        # Step 2: Source file
        rumps.alert("Quelle waehlen", "Waehle die Quell-Datei (Original in deinem Vault)")
        source = pick_file("Quell-Datei waehlen (Original)")
        if not source:
            rumps.alert("Abgebrochen", "Kein Quell-Pfad gewaehlt.")
            return

        # Step 3: Target file
        rumps.alert("Ziel waehlen", "Waehle die Ziel-Datei (z.B. in Nextcloud)")
        target = pick_file("Ziel-Datei waehlen (z.B. Nextcloud)")
        if not target:
            rumps.alert("Abgebrochen", "Kein Ziel-Pfad gewaehlt.")
            return

        # Save
        config = load_config()
        config["pairs"].append({
            "name": name,
            "source": source,
            "target": target
        })
        save_config(config)

        # Restart daemon to pick up changes
        if is_daemon_running():
            restart_daemon()
            rumps.notification("KAS Filesync", "Paar hinzugefuegt",
                             f"'{name}' wird jetzt synchronisiert.", sound=False)
        else:
            rumps.notification("KAS Filesync", "Paar hinzugefuegt",
                             f"'{name}' gespeichert. Starte Sync um zu aktivieren.", sound=False)

        self.build_menu()

    def make_remove_callback(self, index, name):
        def callback(_):
            resp = rumps.alert(
                title=f"'{name}' entfernen?",
                message="Das Sync-Paar wird entfernt. Die Dateien selbst bleiben erhalten.",
                ok="Entfernen",
                cancel="Abbrechen"
            )
            if resp == 1:  # OK clicked
                config = load_config()
                if index < len(config["pairs"]):
                    config["pairs"].pop(index)
                    save_config(config)
                    if is_daemon_running():
                        restart_daemon()
                    rumps.notification("KAS Filesync", "Entfernt",
                                     f"'{name}' wurde entfernt.", sound=False)
                    self.build_menu()
        return callback

    def open_manager(self, _):
        """Open the sync manager window."""
        manager_script = os.path.expanduser("~/Scripts/sync-manager.py")
        subprocess.Popen(["python3", manager_script])

    def show_log(self, _):
        lines = get_last_log(12)
        rumps.alert(title="Sync Log", message=lines)

    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    SyncMenuBarApp().run()
