#!/usr/bin/env python3
"""
Multi-pair bidirectional file sync daemon with 3-way merge support.
Reads file pairs from sync-config.json, watches them with fswatch,
and merges changes intelligently when both files have been modified.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Import merge module
from sync_merge import three_way_merge, is_text_file, has_conflict_markers, resolve_conflict_with_source

CONFIG = os.path.expanduser("~/Library/Application Support/KAS Filesync/sync-config.json")
LOG_FILE = os.path.expanduser("~/Library/Application Support/KAS Filesync/sync-files.log")
LOCK_DIR = "/tmp/sync-files-locks"
BASES_DIR = os.path.expanduser("~/Library/Application Support/KAS Filesync/bases")
CONFLICTS_FILE = os.path.expanduser("~/Library/Application Support/KAS Filesync/conflicts.json")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line.strip(), flush=True)


def load_config():
    try:
        with open(CONFIG, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log(f"Config error: {e}")
        return {"pairs": []}


def build_pair_map(config):
    """Build a dict mapping each file path to its partner."""
    pair_map = {}
    for pair in config.get("pairs", []):
        src = pair["source"]
        tgt = pair["target"]
        pair_map[src] = tgt
        pair_map[tgt] = src
    return pair_map


def lock_path(filepath):
    """Return a lock file path for a given file."""
    os.makedirs(LOCK_DIR, exist_ok=True)
    name = filepath.replace("/", "_")
    return os.path.join(LOCK_DIR, name + ".lock")


# ============= Base Version Management =============

def get_base_path(source, target):
    """Generiert Pfad für Base-Version basierend auf Paar-Hash."""
    os.makedirs(BASES_DIR, exist_ok=True)
    # Sortiere um konsistenten Hash zu bekommen, egal welche Datei sich ändert
    paths = sorted([source, target])
    pair_hash = hashlib.md5(f"{paths[0]}:{paths[1]}".encode()).hexdigest()[:12]
    return os.path.join(BASES_DIR, f"{pair_hash}.base")


def save_base_version(content, source, target):
    """Speichert den gemergten Inhalt als neue Base-Version."""
    base_path = get_base_path(source, target)
    with open(base_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"Base version saved: {os.path.basename(base_path)}")


def load_base_version(source, target):
    """Lädt die Base-Version falls vorhanden."""
    base_path = get_base_path(source, target)
    if os.path.exists(base_path):
        with open(base_path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def read_file(filepath):
    """Liest eine Datei als Text."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_file(filepath, content):
    """Schreibt Inhalt in eine Datei."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ============= Conflict Management =============

def load_conflicts():
    """Lädt bestehende Konflikte."""
    if os.path.exists(CONFLICTS_FILE):
        try:
            with open(CONFLICTS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_conflict(source, target, conflicts):
    """Speichert Konflikt-Info für UI."""
    data = load_conflicts()
    key = get_conflict_key(source, target)
    data[key] = {
        "source": source,
        "target": target,
        "conflict_count": len(conflicts),
        "conflicts": [
            {
                "line": c.line_number,
                "base": c.base_lines,
                "source": c.source_lines,
                "target": c.target_lines
            }
            for c in conflicts
        ],
        "timestamp": datetime.now().isoformat()
    }
    with open(CONFLICTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Conflict saved: {len(conflicts)} conflicts")


def remove_conflict(source, target):
    """Entfernt einen aufgelösten Konflikt."""
    data = load_conflicts()
    key = get_conflict_key(source, target)
    if key in data:
        del data[key]
        with open(CONFLICTS_FILE, "w") as f:
            json.dump(data, f, indent=2)


def get_conflict_key(source, target):
    """Generiert einen eindeutigen Key für ein Paar."""
    paths = sorted([source, target])
    return f"{paths[0]}:{paths[1]}"


def notify_conflict(source, target, conflict_count):
    """Sendet macOS Notification bei Konflikt."""
    filename = os.path.basename(source)
    msg = f"{conflict_count} Konflikt{'e' if conflict_count > 1 else ''} in {filename}"
    try:
        subprocess.run([
            'osascript', '-e',
            f'display notification "{msg}" with title "KAS Filesync" sound name "Basso"'
        ], check=False)
    except:
        pass


# ============= Sync Logic =============

def check_conflict_resolved(source, target):
    """Check if a conflict has been manually resolved (markers removed)."""
    key = get_conflict_key(source, target)
    conflicts = load_conflicts()

    if key not in conflicts:
        return False

    # Check if either file still has conflict markers
    try:
        source_content = read_file(source)
        target_content = read_file(target)

        source_has_markers = has_conflict_markers(source_content)
        target_has_markers = has_conflict_markers(target_content)

        if not source_has_markers and not target_has_markers:
            # Both files have been edited to remove markers
            # Sync them and update base
            if source_content == target_content:
                # Already identical - just update base and remove conflict
                save_base_version(source_content, source, target)
                remove_conflict(source, target)
                log(f"Conflict resolved (identical): {os.path.basename(source)}")
                return True
            else:
                # Files differ but no markers - use the newer one
                if os.path.getmtime(source) > os.path.getmtime(target):
                    write_file(target, source_content)
                    save_base_version(source_content, source, target)
                else:
                    write_file(source, target_content)
                    save_base_version(target_content, source, target)
                remove_conflict(source, target)
                log(f"Conflict resolved (newer wins): {os.path.basename(source)}")
                return True
        elif not source_has_markers:
            # Source was edited, sync to target
            write_file(target, source_content)
            save_base_version(source_content, source, target)
            remove_conflict(source, target)
            log(f"Conflict resolved (from source): {os.path.basename(source)}")
            return True
        elif not target_has_markers:
            # Target was edited, sync to source
            write_file(source, target_content)
            save_base_version(target_content, source, target)
            remove_conflict(source, target)
            log(f"Conflict resolved (from target): {os.path.basename(source)}")
            return True

    except Exception as e:
        log(f"Error checking conflict resolution: {e}")

    return False


def sync_file(changed, pair_map):
    """Sync a changed file to its partner with merge support."""
    partner = pair_map.get(changed)
    if not partner:
        return

    lp = lock_path(changed)
    if os.path.exists(lp):
        return

    try:
        # Create lock
        Path(lp).touch()

        if not os.path.exists(changed):
            log(f"Source missing: {changed}")
            return

        # Check if this resolves a conflict
        if check_conflict_resolved(changed, partner):
            return

        # Wenn Partner nicht existiert, einfach kopieren
        if not os.path.exists(partner):
            shutil.copy2(changed, partner)
            content = read_file(changed) if is_text_file(changed) else None
            if content:
                save_base_version(content, changed, partner)
            src_name = os.path.basename(os.path.dirname(changed))
            tgt_name = os.path.basename(os.path.dirname(partner))
            log(f"Created: .../{src_name}/{os.path.basename(changed)} -> .../{tgt_name}/")
            return

        # Prüfe ob es eine Textdatei ist
        if not is_text_file(changed):
            # Binärdatei: Einfach neuere kopieren (altes Verhalten)
            if os.path.getmtime(changed) > os.path.getmtime(partner):
                shutil.copy2(changed, partner)
                src_name = os.path.basename(os.path.dirname(changed))
                tgt_name = os.path.basename(os.path.dirname(partner))
                log(f"Binary synced: .../{src_name}/{os.path.basename(changed)} -> .../{tgt_name}/")
            return

        # Textdatei: 3-Wege-Merge
        source_content = read_file(changed)
        target_content = read_file(partner)

        # Wenn beide gleich sind, nichts tun
        if source_content == target_content:
            return

        # Base-Version laden
        base_content = load_base_version(changed, partner)

        if base_content is None:
            # Keine Base-Version: Erste Synchronisation
            # Neuere Datei gewinnt, speichere als Base
            if os.path.getmtime(changed) > os.path.getmtime(partner):
                shutil.copy2(changed, partner)
                save_base_version(source_content, changed, partner)
                log(f"Initial sync (source newer): {os.path.basename(changed)}")
            else:
                shutil.copy2(partner, changed)
                save_base_version(target_content, changed, partner)
                log(f"Initial sync (target newer): {os.path.basename(changed)}")
            return

        # Base existiert: Prüfe was sich geändert hat
        if source_content == base_content:
            # Source unverändert, Target hat Änderungen
            shutil.copy2(partner, changed)
            save_base_version(target_content, changed, partner)
            log(f"Synced from target: {os.path.basename(changed)}")
            return

        if target_content == base_content:
            # Target unverändert, Source hat Änderungen
            shutil.copy2(changed, partner)
            save_base_version(source_content, changed, partner)
            log(f"Synced from source: {os.path.basename(changed)}")
            return

        # Beide haben Änderungen: 3-Wege-Merge versuchen
        log(f"Attempting 3-way merge: {os.path.basename(changed)}")
        result = three_way_merge(base_content, source_content, target_content)

        if result.success:
            # Merge erfolgreich - beide Dateien aktualisieren
            write_file(changed, result.content)
            write_file(partner, result.content)
            save_base_version(result.content, changed, partner)
            remove_conflict(changed, partner)
            log(f"Auto-merged successfully: {os.path.basename(changed)}")
        else:
            # Konflikte - speichern und benachrichtigen
            # Schreibe Datei mit Konflikt-Markern
            write_file(changed, result.content)
            write_file(partner, result.content)
            save_conflict(changed, partner, result.conflicts)
            notify_conflict(changed, partner, len(result.conflicts))
            log(f"Merge conflict ({len(result.conflicts)} conflicts): {os.path.basename(changed)}")

    except Exception as e:
        log(f"Sync error: {e}")
    finally:
        # Hold lock briefly to prevent re-entrant trigger from the copy
        time.sleep(1)
        try:
            os.remove(lp)
        except OSError:
            pass


def initial_sync(config):
    """Ensure all pairs are in sync at startup."""
    for pair in config.get("pairs", []):
        name = pair.get("name", "?")
        src = pair["source"]
        tgt = pair["target"]

        if not os.path.exists(src) and not os.path.exists(tgt):
            log(f"Initial ({name}): Both files missing!")
            continue

        if not os.path.exists(tgt):
            shutil.copy2(src, tgt)
            if is_text_file(src):
                save_base_version(read_file(src), src, tgt)
            log(f"Initial ({name}): Created target from source")
        elif not os.path.exists(src):
            shutil.copy2(tgt, src)
            if is_text_file(tgt):
                save_base_version(read_file(tgt), src, tgt)
            log(f"Initial ({name}): Created source from target")
        else:
            # Beide existieren - prüfe auf Konflikte
            if is_text_file(src):
                source_content = read_file(src)
                target_content = read_file(tgt)
                base_content = load_base_version(src, tgt)

                if source_content == target_content:
                    if base_content is None:
                        save_base_version(source_content, src, tgt)
                    log(f"Initial ({name}): Already in sync")
                elif base_content is None:
                    # Keine Base, neuere gewinnt
                    if os.path.getmtime(src) > os.path.getmtime(tgt):
                        shutil.copy2(src, tgt)
                        save_base_version(source_content, src, tgt)
                        log(f"Initial ({name}): Source -> Target (newer)")
                    else:
                        shutil.copy2(tgt, src)
                        save_base_version(target_content, src, tgt)
                        log(f"Initial ({name}): Target -> Source (newer)")
                else:
                    # Base existiert - versuche Merge
                    result = three_way_merge(base_content, source_content, target_content)
                    if result.success:
                        write_file(src, result.content)
                        write_file(tgt, result.content)
                        save_base_version(result.content, src, tgt)
                        remove_conflict(src, tgt)
                        log(f"Initial ({name}): Auto-merged")
                    else:
                        write_file(src, result.content)
                        write_file(tgt, result.content)
                        save_conflict(src, tgt, result.conflicts)
                        log(f"Initial ({name}): Merge conflict ({len(result.conflicts)})")
            else:
                # Binärdatei
                if os.path.getmtime(src) > os.path.getmtime(tgt):
                    shutil.copy2(src, tgt)
                    log(f"Initial ({name}): Source -> Target")
                elif os.path.getmtime(tgt) > os.path.getmtime(src):
                    shutil.copy2(tgt, src)
                    log(f"Initial ({name}): Target -> Source")
                else:
                    log(f"Initial ({name}): Already in sync")


def main():
    log("=== Sync daemon starting (with merge support) ===")

    # Ensure bases directory exists
    os.makedirs(BASES_DIR, exist_ok=True)

    config = load_config()
    pair_map = build_pair_map(config)

    if not pair_map:
        log("No file pairs configured. Waiting for config changes...")
        # Watch the config file so we restart when pairs are added
        subprocess.run(["fswatch", "-1", CONFIG])
        log("Config changed, restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    initial_sync(config)

    # Collect all files to watch (+ the config file for live reload)
    watch_files = list(pair_map.keys()) + [CONFIG]
    log(f"Watching {len(pair_map)} files + config...")

    # Start fswatch
    proc = subprocess.Popen(
        ["fswatch", "-0"] + watch_files,
        stdout=subprocess.PIPE
    )

    try:
        buf = b""
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                break
            if chunk == b"\x00":
                changed = buf.decode("utf-8").strip()
                buf = b""

                if changed == CONFIG:
                    log("Config changed, reloading...")
                    proc.terminate()
                    proc.wait()
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                    return

                sync_file(changed, pair_map)
            else:
                buf += chunk
    except KeyboardInterrupt:
        log("Daemon stopped by signal")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
