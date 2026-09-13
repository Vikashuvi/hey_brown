#!/usr/bin/env python3
"""Cross-Platform Desktop Launcher for Brown AI Assistant.
Runs seamlessly across macOS, Linux, and Windows.

Modes:
  - Native Webview: Borderless floating overlay via pywebview (if installed).
  - App-Mode Browser: Lightweight dedicated window via Chrome/Edge/Firefox or default browser.
"""

import sys
import os
import time
import subprocess
import webbrowser
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_INDEX = os.path.join(PROJECT_ROOT, "ui", "dist", "index.html")
DEV_URL = "http://localhost:5173"
PREVIEW_URL = "http://localhost:4173"


def launch_in_browser(url: str):
    """Open Brown UI in a dedicated app-mode window on Windows, Linux, or macOS."""
    print(f"[*] Opening Brown in App-Mode Browser: {url}")
    
    # Try Chrome or Edge app mode (frameless minimal window)
    app_args = [f"--app={url}", "--window-size=240,320", "--window-position=1400,60"]
    
    browsers = [
        # macOS
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] + app_args,
        ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"] + app_args,
        # Linux
        ["google-chrome"] + app_args,
        ["chromium-browser"] + app_args,
        ["microsoft-edge"] + app_args,
        # Windows
        ["chrome.exe"] + app_args,
        ["msedge.exe"] + app_args,
    ]
    
    for cmd in browsers:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return proc
        except (FileNotFoundError, PermissionError):
            continue
            
    # Fallback to standard default browser
    webbrowser.open(url)
    return None


class BrownDesktopApi:
    """JS Bridge exposed to webview for native window management on Windows & Linux."""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.settings_window = None

    def open_settings_window(self):
        import webview
        if self.settings_window is not None:
            try:
                self.settings_window.show()
                self.settings_window.restore()
                return
            except Exception:
                self.settings_window = None

        sep = "&" if "?" in self.base_url else "?"
        settings_url = f"{self.base_url}{sep}view=settings"
        self.settings_window = webview.create_window(
            title="Brown — Control Panel",
            url=settings_url,
            width=740,
            height=780,
            resizable=True,
            on_top=True
        )

    def close_settings_window(self):
        if self.settings_window is not None:
            try:
                self.settings_window.destroy()
            except Exception:
                pass
            self.settings_window = None


def run_pywebview(html_or_url: str):
    """Launch via pywebview with native floating mascot + separate settings window (Cross-OS)."""
    try:
        import webview
    except ImportError:
        print("[!] pywebview is not installed. To install: pip install pywebview")
        return False

    print("[*] Launching Brown via native pywebview window (Cross-OS)...")
    api = BrownDesktopApi(html_or_url)
    window = webview.create_window(
        title="Brown AI Assistant",
        url=html_or_url,
        width=240,
        height=320,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        background_color='#00000000',
        js_api=api
    )
    webview.start()
    return True



def main():
    parser = argparse.ArgumentParser(description="Run Brown Assistant Desktop Window (Cross-OS)")
    parser.add_argument("--browser", action="store_true", help="Force app-mode browser window")
    parser.add_argument("--dev", action="store_true", help="Connect to Vite dev server on port 5173")
    parser.add_argument("--url", default=None, help="Custom UI URL")
    args = parser.parse_args()

    # Determine target URL or dist file
    if args.url:
        target = args.url
    elif args.dev:
        target = DEV_URL
    elif os.path.exists(DIST_INDEX):
        target = f"file://{DIST_INDEX}"
    else:
        target = DEV_URL

    # On macOS, prioritize native Brown.app if available
    mac_app_path = os.path.join(PROJECT_ROOT, "macos", "build", "Brown.app")
    if sys.platform == "darwin" and os.path.exists(mac_app_path) and not args.browser:
        print(f"[*] Launching native macOS Brown.app...")
        subprocess.run(["open", mac_app_path])
        return

    if not args.browser:
        success = run_pywebview(target)
        if success:
            return

    # Fallback to App-Mode browser
    launch_in_browser(target)


if __name__ == "__main__":

    main()
