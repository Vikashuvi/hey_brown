"""Error Boy Remote Agent Daemon for Arch Linux / Linux systems.
Runs on the secondary machine (HP Victus / Arch Linux) to receive commands from Brown.
Zero external dependencies (uses Python standard library only).

Usage on Error Boy (Arch Linux):
    python3 devices/error_boy_server.py --port 8765
Or run as a systemd user service via brown-error-boy.service.
"""

import os
import re
import sys
import json
import shutil
import socket
import argparse
import subprocess
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, List


SAFE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_\.]+$")

# Map colloquial or cross-platform names to typical Linux / Arch binaries
LINUX_APP_MAP = {
    "visual studio code": "code",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
    "vscodium": "codium",
    "chrome": "google-chrome-stable",
    "google chrome": "google-chrome-stable",
    "chromium": "chromium",
    "firefox": "firefox",
    "browser": "firefox",
    "discord": "discord",
    "spotify": "spotify",
    "slack": "slack",
    "steam": "steam",
    "telegram": "telegram-desktop",
    "vlc": "vlc",
    "obs": "obs",
    "calculator": "gnome-calculator",
    "calc": "kcalc",
    "gimp": "gimp",
    "htop": "htop",
    "btop": "btop",
}

# Preferred Linux terminal emulators in order of discovery
TERMINAL_CANDIDATES = ["alacritty", "kitty", "foot", "wezterm", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"]


def resolve_linux_binary(app_name: str) -> str:
    """Resolve a friendly app name to an installed executable on Arch Linux."""
    raw = app_name.strip().lower()

    # Special handling for terminal requests
    if raw in ("terminal", "console", "iterm", "iterm2"):
        for term in TERMINAL_CANDIDATES:
            if shutil.which(term):
                return term
        return "xterm"

    # Map aliases
    mapped = LINUX_APP_MAP.get(raw, raw)

    # 1. Direct binary check
    if shutil.which(mapped):
        return mapped

    # 2. Check if original lowercase exists in PATH
    if shutil.which(raw):
        return raw

    # 3. Try hyphenated variant (e.g. "google chrome" -> "google-chrome")
    hyphenated = raw.replace(" ", "-")
    if shutil.which(hyphenated):
        return hyphenated

    return mapped


def get_linux_system_stats() -> Dict[str, Any]:
    """Extract CPU, Memory, and Host statistics on Linux."""
    stats = {
        "hostname": socket.gethostname(),
        "platform": sys.platform,
        "cpu_count": os.cpu_count() or 1,
    }

    # Load averages
    try:
        load1, load5, load15 = os.getloadavg()
        stats["load1"] = round(load1, 2)
        stats["load5"] = round(load5, 2)
        stats["load15"] = round(load15, 2)
    except Exception:
        stats["load1"] = stats["load5"] = stats["load15"] = 0.0

    # Memory info from /proc/meminfo
    try:
        mem_info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    if val.isdigit():
                        mem_info[key] = int(val)

        total_kb = mem_info.get("MemTotal", 0)
        avail_kb = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
        used_kb = total_kb - avail_kb

        stats["ram_total_mb"] = round(total_kb / 1024, 1)
        stats["ram_used_mb"] = round(used_kb / 1024, 1)
        stats["ram_available_mb"] = round(avail_kb / 1024, 1)
        if total_kb > 0:
            stats["ram_usage_pct"] = round((used_kb / total_kb) * 100, 1)
    except Exception:
        pass

    # OS Release info
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        stats["os"] = line.split("=", 1)[1].strip().strip('"')
                        break
    except Exception:
        pass

    return stats


def get_running_linux_apps() -> List[str]:
    """Inspect currently running user applications without elevated privileges."""
    running = set()
    try:
        proc = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True, timeout=2)
        if proc.returncode == 0:
            lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
            known_binaries = set(LINUX_APP_MAP.values()) | set(TERMINAL_CANDIDATES) | {"python", "python3", "bash", "zsh"}
            for line in lines:
                if line in known_binaries:
                    running.add(line)
    except Exception:
        pass
    return sorted(list(running))


def get_desktop_environment() -> Dict[str, str]:
    """Auto-detect user's active GUI desktop environment (Wayland/X11)."""
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        uid = os.getuid()
        runtime_path = f"/run/user/{uid}"
        if os.path.exists(runtime_path):
            env["XDG_RUNTIME_DIR"] = runtime_path

    if "WAYLAND_DISPLAY" not in env and "XDG_RUNTIME_DIR" in env:
        try:
            for item in os.listdir(env["XDG_RUNTIME_DIR"]):
                if item.startswith("wayland-") and not item.endswith(".lock"):
                    env["WAYLAND_DISPLAY"] = item
                    break
        except Exception:
            pass

    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    return env


class ErrorBoyRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing Error Boy's strict typed REST API."""

    auth_token: Optional[str] = None

    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        if not self.auth_token:
            return True
        auth_header = self.headers.get("Authorization", "")
        expected = f"Bearer {self.auth_token}"
        return auth_header == expected

    def _parse_json_body(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                return True, {}
            raw_body = self.rfile.read(content_len).decode("utf-8")
            return True, json.loads(raw_body)
        except Exception as e:
            return False, {"error": f"Invalid JSON payload: {str(e)}"}

    def do_GET(self):
        if not self._check_auth():
            self._send_json_response(401, {"success": False, "message": "Unauthorized: invalid or missing bearer token."})
            return

        clean_path = self.path.split("?")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        # 1. Health Ping
        if clean_path in ("/health", "/"):
            self._send_json_response(200, {
                "success": True,
                "status": "ok",
                "device": "error_boy",
                "message": "Error Boy (Arch Linux) is online and reachable."
            })

        # 2. System Status (get_device_status)
        elif clean_path in ("/system/status", "/status"):
            stats = get_linux_system_stats()
            load_str = f"Load: {stats.get('load1', 0.0):.2f}"
            ram_str = f"RAM: {stats.get('ram_used_mb', 0)}MB/{stats.get('ram_total_mb', 0)}MB"
            self._send_json_response(200, {
                "success": True,
                "message": f"Error Boy is healthy. {load_str}, {ram_str}.",
                "data": stats
            })

        # 3. Running Applications (get_running_apps)
        elif clean_path == "/apps/running":
            running = get_running_linux_apps()
            self._send_json_response(200, {
                "success": True,
                "message": f"Error Boy is currently running: {', '.join(running) if running else 'no major applications'}." if running else "No targeted applications currently running.",
                "data": {"running_apps": running}
            })

        # 4. Device Capabilities (get_device_capabilities)
        elif clean_path == "/capabilities":
            self._send_json_response(200, {
                "success": True,
                "message": "Error Boy device capabilities retrieved.",
                "data": {
                    "device": "error_boy",
                    "os": "Arch Linux",
                    "version": "1.0.0",
                    "capabilities": [
                        "get_device_status",
                        "get_running_apps",
                        "open_application",
                        "close_application",
                        "open_url",
                        "get_device_capabilities"
                    ]
                }
            })

        else:
            self._send_json_response(404, {"success": False, "message": f"Endpoint not found: {self.path}"})

    def do_POST(self):
        if not self._check_auth():
            self._send_json_response(401, {"success": False, "message": "Unauthorized: invalid or missing bearer token."})
            return

        ok, body = self._parse_json_body()
        if not ok:
            self._send_json_response(400, {"success": False, "message": body.get("error", "Bad Request")})
            return

        clean_path = self.path.split("?")[0].rstrip("/")

        # 1. Open Application (open_application)
        if clean_path == "/apps/open":
            app_name = body.get("application", "").strip()
            if not app_name or len(app_name) > 64 or not SAFE_NAME_PATTERN.match(app_name):
                self._send_json_response(400, {
                    "success": False,
                    "message": f"Invalid or unsafe application name: '{app_name}'"
                })
                return

            binary = resolve_linux_binary(app_name)
            executable = shutil.which(binary) or shutil.which(app_name.lower())
            if not executable:
                self._send_json_response(200, {
                    "success": False,
                    "message": f"Application '{app_name}' (binary '{binary}') is not installed or not found in PATH on Error Boy."
                })
                return

            try:
                env = get_desktop_environment()
                subprocess.Popen(
                    [executable],
                    env=env,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._send_json_response(200, {
                    "success": True,
                    "message": f"Launched {app_name} on Error Boy (Arch Linux).",
                    "data": {"binary": executable}
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to launch {app_name} on Error Boy: {str(e)}"
                })

        # 2. Close Application (close_application)
        elif clean_path == "/apps/close":
            app_name = body.get("application", "").strip()
            if not app_name or len(app_name) > 64 or not SAFE_NAME_PATTERN.match(app_name):
                self._send_json_response(400, {
                    "success": False,
                    "message": f"Invalid application name: '{app_name}'"
                })
                return

            binary = resolve_linux_binary(app_name)
            try:
                proc = subprocess.run(["pkill", "-f", binary], capture_output=True, text=True, timeout=5)
                self._send_json_response(200, {
                    "success": True,
                    "message": f"Closed {app_name} on Error Boy.",
                    "data": {"returncode": proc.returncode}
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to close {app_name}: {str(e)}"
                })

        # 3. Open URL (open_url)
        elif clean_path == "/browser/open":
            raw_url = body.get("url", "").strip()
            if not raw_url:
                self._send_json_response(400, {"success": False, "message": "URL cannot be empty."})
                return

            if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
                raw_url = "https://" + raw_url

            parsed = urllib.parse.urlparse(raw_url)
            if not parsed.netloc or len(raw_url) > 2048 or " " in raw_url:
                self._send_json_response(400, {"success": False, "message": f"Invalid URL: '{raw_url}'"})
                return

            try:
                env = get_desktop_environment()
                launcher = shutil.which("xdg-open") or shutil.which("open")
                if launcher:
                    subprocess.Popen(
                        [launcher, raw_url],
                        env=env,
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    import webbrowser
                    webbrowser.open(raw_url)

                self._send_json_response(200, {
                    "success": True,
                    "message": f"Opened {raw_url} in browser on Error Boy."
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to open URL on Error Boy: {str(e)}"
                })

        # 4. Fallback for system/status if sent via POST
        elif clean_path in ("/system/status", "/status"):
            stats = get_linux_system_stats()
            load_str = f"Load: {stats.get('load1', 0.0):.2f}"
            ram_str = f"RAM: {stats.get('ram_used_mb', 0)}MB/{stats.get('ram_total_mb', 0)}MB"
            self._send_json_response(200, {
                "success": True,
                "message": f"Error Boy is healthy. {load_str}, {ram_str}.",
                "data": stats
            })

        else:
            self._send_json_response(404, {"success": False, "message": f"Endpoint not found: {self.path}"})

    def log_message(self, format, *args):
        print(f"[ErrorBoyDaemon] {self.address_string()} - {format % args}")


def run_server(host: str = "0.0.0.0", port: int = 8765, auth_token: Optional[str] = None):
    """Start Error Boy daemon HTTP server."""
    ErrorBoyRequestHandler.auth_token = auth_token
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, ErrorBoyRequestHandler)
    print(f"==================================================")
    print(f"  Error Boy Agent Daemon (Arch Linux)")
    print(f"  Listening on: http://{host}:{port}")
    print(f"  Auth Token  : {'Configured' if auth_token else 'Disabled (Open LAN)'}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ErrorBoyDaemon] Shutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Error Boy Agent Daemon for Arch Linux")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    parser.add_argument("--auth-token", default=os.environ.get("ERROR_BOY_AUTH_TOKEN"), help="Optional authentication bearer token")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, auth_token=args.auth_token)
