# KAS Filesync

Bidirektionale Dateisynchronisation für macOS mit Menubar-Integration.

![KAS Filesync](docs/screenshot.png)

## Features

- **Bidirektionale Synchronisation** – Änderungen werden in beide Richtungen synchronisiert
- **Event-basiert** – Synct nur wenn sich eine Datei ändert (kein Polling)
- **Menubar-App** – Statusanzeige und Steuerung direkt in der Menüleiste
- **Verbindungs-Manager** – Natives macOS-Fenster zum Verwalten der Sync-Paare
- **Autostart** – Kann bei der Anmeldung automatisch starten

## Installation

### Automatisch (empfohlen)

```bash
curl -fsSL https://raw.githubusercontent.com/Stebibastian/kas-filesync/main/install.sh | bash
```

### Manuell

1. Repository klonen:
   ```bash
   git clone https://github.com/Stebibastian/kas-filesync.git
   cd kas-filesync
   ```

2. Install-Script ausführen:
   ```bash
   ./install.sh
   ```

## Verwendung

### App starten

Nach der Installation findest du **KAS Filesync** in `~/Applications/`.

- Doppelklick zum Starten
- Oder per Spotlight: "KAS Filesync" suchen

### Autostart einrichten

1. **Systemeinstellungen** → **Allgemein** → **Anmeldeobjekte**
2. Bei "Bei der Anmeldung öffnen" auf **+** klicken
3. `~/Applications/KAS Filesync.app` auswählen

### Sync-Verbindungen verwalten

1. Klick auf das 🔄 Symbol in der Menüleiste
2. **"Verbindungen verwalten..."** wählen
3. Im Fenster:
   - **+** Neue Verbindung hinzufügen
   - **−** Ausgewählte Verbindung entfernen

### Neue Verbindung hinzufügen

1. Klick auf **+**
2. Name für die Verbindung eingeben
3. **Quell-Datei** auswählen (z.B. in deinem Obsidian-Vault)
4. **Ziel-Ordner** auswählen (z.B. in Nextcloud)
5. Die Datei wird automatisch mit dem gleichen Namen im Zielordner angelegt

## Dateien

| Datei | Beschreibung |
|-------|--------------|
| `sync-files.py` | Sync-Daemon (event-basiert mit fswatch) |
| `sync-menubar.py` | Menubar-App |
| `sync-manager.py` | Verbindungs-Manager (natives Fenster) |
| `sync-config.json` | Konfiguration der Sync-Paare |

## Voraussetzungen

- macOS 10.13 oder neuer
- Python 3.8+
- fswatch (`brew install fswatch`)

Die Python-Pakete werden automatisch installiert.

## Deinstallation

```bash
# App entfernen
rm -rf ~/Applications/KAS\ Filesync.app

# Scripts entfernen
rm -f ~/Scripts/sync-files.py
rm -f ~/Scripts/sync-menubar.py
rm -f ~/Scripts/sync-manager.py
rm -f ~/Scripts/sync-config.json

# Logs entfernen (optional)
rm -f ~/Scripts/sync-files.log
rm -f ~/Scripts/kas-filesync-launcher.log
```

## Lizenz

MIT License
