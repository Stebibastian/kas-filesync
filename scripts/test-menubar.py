#!/usr/bin/env python3
"""
Minimal menubar test - run this to debug menubar issues.
"""
import sys
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")

print("\n1. Testing rumps import...")
try:
    import rumps
    print(f"   OK: rumps from {rumps.__file__}")
except ImportError as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

print("\n2. Testing AppKit import...")
try:
    import AppKit
    print(f"   OK: AppKit loaded")
except ImportError as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

print("\n3. Creating minimal menubar app...")
print("   (You should see 'TEST' in your menubar)")
print("   Press Ctrl+C to quit\n")

class TestApp(rumps.App):
    def __init__(self):
        super().__init__("TEST")
        self.menu = ["Item 1", "Item 2", None, "Quit"]

    @rumps.clicked("Quit")
    def quit_app(self, _):
        rumps.quit_application()

if __name__ == "__main__":
    try:
        app = TestApp()
        print("4. App created, calling run()...")
        app.run()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
