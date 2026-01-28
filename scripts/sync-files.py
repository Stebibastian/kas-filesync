#!/usr/bin/env python3
"""
Multi-pair bidirectional file sync daemon.
Reads file pairs from sync-config.json, watches them with fswatch,
and copies the newer file when changes are detected.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

CONFIG = os.path.expanduser("~/Scripts/sync-config.json")
LOG_FILE = os.path.expanduser("~/Scripts/sync-files.log")
LOCK_DIR = "/tmp/sync-files-locks"


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


def sync_file(changed, pair_map):
    """Sync a changed file to its partner if it's newer."""
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

        # Copy if changed is newer, or if partner doesn't exist
        if not os.path.exists(partner) or os.path.getmtime(changed) > os.path.getmtime(partner):
            shutil.copy2(changed, partner)
            src_name = os.path.basename(os.path.dirname(changed))
            tgt_name = os.path.basename(os.path.dirname(partner))
            log(f"Synced: .../{src_name}/{os.path.basename(changed)} -> .../{tgt_name}/")
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
            log(f"Initial ({name}): Created target from source")
        elif not os.path.exists(src):
            shutil.copy2(tgt, src)
            log(f"Initial ({name}): Created source from target")
        elif os.path.getmtime(src) > os.path.getmtime(tgt):
            shutil.copy2(src, tgt)
            log(f"Initial ({name}): Source -> Target")
        elif os.path.getmtime(tgt) > os.path.getmtime(src):
            shutil.copy2(tgt, src)
            log(f"Initial ({name}): Target -> Source")
        else:
            log(f"Initial ({name}): Already in sync")


def main():
    log("=== Sync daemon starting ===")

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
