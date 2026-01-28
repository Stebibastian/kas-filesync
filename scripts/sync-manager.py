#!/usr/bin/env python3
"""
Native macOS window for managing file sync pairs.
Reads/writes sync-config.json. The sync daemon auto-reloads on config changes.
"""

import fcntl
import json
import os
import sys

LOCK_FILE = "/tmp/sync-manager.lock"
CONFIG = os.path.expanduser("~/Scripts/sync-config.json")

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSApplication,
    NSBackingStoreBuffered,
    NSBezelStyleSmallSquare,
    NSButton,
    NSFont,
    NSLineBreakByTruncatingMiddle,
    NSObject,
    NSOpenPanel,
    NSScrollView,
    NSTableColumn,
    NSTableView,
    NSTableViewSelectionDidChangeNotification,
    NSTextField,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSViewMaxYMargin,
    NSViewMinYMargin,
)
from Foundation import (
    NSMakeRect,
    NSNotificationCenter,
)


def load_config():
    try:
        with open(CONFIG, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pairs": []}


def save_config(data):
    with open(CONFIG, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class SyncManagerDelegate(NSObject):
    """Main application and window delegate."""

    def init(self):
        self = objc.super(SyncManagerDelegate, self).init()
        if self is None:
            return None
        self.pairs = load_config().get("pairs", [])
        return self

    def buildWindow(self):
        """Create the main window with table, buttons, and detail area."""
        w, h = 620, 400

        # Window
        NSWindow = objc.lookUpClass("NSWindow")
        mask = 1 | 2 | 4 | 8  # titled, closable, miniaturizable, resizable
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, w, h), mask, 2, False  # 2 = NSBackingStoreBuffered
        )
        self.window.setTitle_("KAS Filesync – Verbindungen")
        self.window.setMinSize_((500, 350))
        self.window.setDelegate_(self)

        content = self.window.contentView()
        pad = 16

        # Calculate layout positions (bottom to top)
        detail_height = 50
        button_height = 24
        sep_height = 1
        header_height = 24

        detail_y = pad
        sep_y = detail_y + detail_height + 8
        button_y = sep_y + sep_height + 6
        table_y = button_y + button_height + 8
        header_y = h - pad - header_height
        table_height = header_y - table_y - 10

        # --- Header label ---
        header = NSTextField.labelWithString_("Sync-Verbindungen")
        header.setFont_(NSFont.boldSystemFontOfSize_(14))
        header.setFrame_(NSMakeRect(pad, header_y, w - 2*pad, header_height))
        header.setAutoresizingMask_(NSViewWidthSizable | NSViewMinYMargin)
        content.addSubview_(header)

        # --- Scroll view with table ---
        scrollView = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(pad, table_y, w - 2*pad, table_height)
        )
        scrollView.setHasVerticalScroller_(True)
        scrollView.setBorderType_(1)  # NSBezelBorder
        scrollView.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

        self.tableView = NSTableView.alloc().initWithFrame_(
            NSMakeRect(0, 0, w - 2*pad - 2, table_height - 2)
        )
        self.tableView.setUsesAlternatingRowBackgroundColors_(True)
        self.tableView.setAllowsMultipleSelection_(False)
        self.tableView.setRowHeight_(22)

        # Columns
        col_name = NSTableColumn.alloc().initWithIdentifier_("name")
        col_name.headerCell().setStringValue_("Name")
        col_name.setWidth_(120)
        col_name.setMinWidth_(80)
        self.tableView.addTableColumn_(col_name)

        col_file = NSTableColumn.alloc().initWithIdentifier_("file")
        col_file.headerCell().setStringValue_("Datei")
        col_file.setWidth_(200)
        col_file.setMinWidth_(100)
        self.tableView.addTableColumn_(col_file)

        col_target = NSTableColumn.alloc().initWithIdentifier_("target")
        col_target.headerCell().setStringValue_("Zielort")
        col_target.setWidth_(200)
        col_target.setMinWidth_(100)
        self.tableView.addTableColumn_(col_target)

        self.tableView.setDelegate_(self)
        self.tableView.setDataSource_(self)

        scrollView.setDocumentView_(self.tableView)
        content.addSubview_(scrollView)

        # --- Add / Remove buttons ---
        self.addButton = NSButton.alloc().initWithFrame_(NSMakeRect(pad, button_y, 24, 24))
        self.addButton.setBezelStyle_(NSBezelStyleSmallSquare)
        self.addButton.setTitle_("+")
        self.addButton.setTarget_(self)
        self.addButton.setAction_(objc.selector(self.addPair_, signature=b"v@:@"))
        self.addButton.setAutoresizingMask_(NSViewMaxYMargin)
        content.addSubview_(self.addButton)

        self.removeButton = NSButton.alloc().initWithFrame_(NSMakeRect(pad + 24, button_y, 24, 24))
        self.removeButton.setBezelStyle_(NSBezelStyleSmallSquare)
        self.removeButton.setTitle_("\u2212")  # minus sign
        self.removeButton.setTarget_(self)
        self.removeButton.setAction_(objc.selector(self.removePair_, signature=b"v@:@"))
        self.removeButton.setEnabled_(False)
        self.removeButton.setAutoresizingMask_(NSViewMaxYMargin)
        content.addSubview_(self.removeButton)

        # --- Separator ---
        NSBox = objc.lookUpClass("NSBox")
        sep = NSBox.alloc().initWithFrame_(NSMakeRect(pad, sep_y, w - 2*pad, sep_height))
        sep.setBoxType_(2)  # NSBoxSeparator
        sep.setAutoresizingMask_(NSViewWidthSizable | NSViewMaxYMargin)
        content.addSubview_(sep)

        # --- Detail area ---
        NSColor = objc.lookUpClass("NSColor")

        self.detailSourceLabel = NSTextField.labelWithString_("Quelle:")
        self.detailSourceLabel.setFont_(NSFont.systemFontOfSize_(11))
        self.detailSourceLabel.setTextColor_(NSColor.secondaryLabelColor())
        self.detailSourceLabel.setFrame_(NSMakeRect(pad, detail_y + 22, 50, 16))
        self.detailSourceLabel.setAutoresizingMask_(NSViewMaxYMargin)
        content.addSubview_(self.detailSourceLabel)

        self.detailSourcePath = NSTextField.labelWithString_("–")
        self.detailSourcePath.setFont_(NSFont.systemFontOfSize_(11))
        self.detailSourcePath.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
        self.detailSourcePath.setSelectable_(True)
        self.detailSourcePath.setFrame_(NSMakeRect(pad + 54, detail_y + 22, w - 2*pad - 54, 16))
        self.detailSourcePath.setAutoresizingMask_(NSViewWidthSizable | NSViewMaxYMargin)
        content.addSubview_(self.detailSourcePath)

        self.detailTargetLabel = NSTextField.labelWithString_("Ziel:")
        self.detailTargetLabel.setFont_(NSFont.systemFontOfSize_(11))
        self.detailTargetLabel.setTextColor_(NSColor.secondaryLabelColor())
        self.detailTargetLabel.setFrame_(NSMakeRect(pad, detail_y, 50, 16))
        self.detailTargetLabel.setAutoresizingMask_(NSViewMaxYMargin)
        content.addSubview_(self.detailTargetLabel)

        self.detailTargetPath = NSTextField.labelWithString_("–")
        self.detailTargetPath.setFont_(NSFont.systemFontOfSize_(11))
        self.detailTargetPath.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
        self.detailTargetPath.setSelectable_(True)
        self.detailTargetPath.setFrame_(NSMakeRect(pad + 54, detail_y, w - 2*pad - 54, 16))
        self.detailTargetPath.setAutoresizingMask_(NSViewWidthSizable | NSViewMaxYMargin)
        content.addSubview_(self.detailTargetPath)

        # Listen for selection changes
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self,
            objc.selector(self.tableSelectionChanged_, signature=b"v@:@"),
            NSTableViewSelectionDidChangeNotification,
            self.tableView,
        )

        # Reload table data
        self.tableView.reloadData()

        self.window.center()
        self.window.makeKeyAndOrderFront_(None)

    # ─── NSTableViewDataSource ───

    def numberOfRowsInTableView_(self, tableView):
        return len(self.pairs)

    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if row >= len(self.pairs):
            return ""
        pair = self.pairs[row]
        col_id = column.identifier()
        if col_id == "name":
            return pair.get("name", "")
        elif col_id == "file":
            return os.path.basename(pair.get("source", ""))
        elif col_id == "target":
            return os.path.basename(os.path.dirname(pair.get("target", "")))
        return ""

    # ─── NSTableViewDelegate ───

    def tableSelectionChanged_(self, notification):
        row = self.tableView.selectedRow()
        if row >= 0 and row < len(self.pairs):
            pair = self.pairs[row]
            self.detailSourcePath.setStringValue_(pair.get("source", "–"))
            self.detailTargetPath.setStringValue_(pair.get("target", "–"))
            self.removeButton.setEnabled_(True)
        else:
            self.detailSourcePath.setStringValue_("–")
            self.detailTargetPath.setStringValue_("–")
            self.removeButton.setEnabled_(False)

    # ─── Actions ───

    def addPair_(self, sender):
        """Add a new sync pair: name, source file, target folder."""

        # Step 1: Ask for name
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Neue Sync-Verbindung")
        alert.setInformativeText_("Name für die Verbindung:")
        alert.addButtonWithTitle_("Weiter")
        alert.addButtonWithTitle_("Abbrechen")

        nameField = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        nameField.setStringValue_("Neues Paar")
        alert.setAccessoryView_(nameField)
        alert.window().setInitialFirstResponder_(nameField)

        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        name = str(nameField.stringValue())
        if not name:
            return

        # Step 2: Pick source file
        panel = NSOpenPanel.openPanel()
        panel.setTitle_("Quell-Datei wählen")
        panel.setMessage_("Wähle die Datei, die synchronisiert werden soll")
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(False)

        if panel.runModal() != 1:  # NSOKButton
            return
        source = str(panel.URL().path())

        # Step 3: Pick target folder
        panel2 = NSOpenPanel.openPanel()
        panel2.setTitle_("Ziel-Ordner wählen")
        panel2.setMessage_("Wähle den Ordner, in den die Datei synchronisiert wird")
        panel2.setCanChooseFiles_(False)
        panel2.setCanChooseDirectories_(True)
        panel2.setAllowsMultipleSelection_(False)

        if panel2.runModal() != 1:
            return
        target_dir = str(panel2.URL().path())

        # Build target path: folder + source filename
        source_filename = os.path.basename(source)
        target = os.path.join(target_dir, source_filename)

        # Add to config
        self.pairs.append({
            "name": name,
            "source": source,
            "target": target,
        })
        self._saveAndReload()

    def removePair_(self, sender):
        """Remove the selected sync pair with confirmation."""
        row = self.tableView.selectedRow()
        if row < 0 or row >= len(self.pairs):
            return

        pair = self.pairs[row]
        name = pair.get("name", "?")

        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"'{name}' entfernen?")
        alert.setInformativeText_("Die Sync-Verbindung wird entfernt. Die Dateien selbst bleiben erhalten.")
        alert.addButtonWithTitle_("Entfernen")
        alert.addButtonWithTitle_("Abbrechen")
        alert.setAlertStyle_(2)  # NSAlertStyleCritical

        if alert.runModal() != NSAlertFirstButtonReturn:
            return

        self.pairs.pop(row)
        self._saveAndReload()

    def _saveAndReload(self):
        """Save config and refresh the table view."""
        save_config({"pairs": self.pairs})
        self.tableView.reloadData()
        self.tableView.deselectAll_(None)
        self.detailSourcePath.setStringValue_("–")
        self.detailTargetPath.setStringValue_("–")
        self.removeButton.setEnabled_(False)

    # ─── Window delegate ───

    def windowWillClose_(self, notification):
        NSApp.terminate_(None)


def main():
    # Single instance check using file lock
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Another instance is running - just exit quietly
        sys.exit(0)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(0)  # NSApplicationActivationPolicyRegular

    delegate = SyncManagerDelegate.alloc().init()
    delegate.buildWindow()

    app.activateIgnoringOtherApps_(True)
    app.run()


if __name__ == "__main__":
    main()
