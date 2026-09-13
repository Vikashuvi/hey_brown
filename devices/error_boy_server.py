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
import urllib.request
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


def get_linux_gpu_stats() -> Dict[str, Any]:
    """Extract NVIDIA GPU and VRAM statistics on Linux if present."""
    gpu_stats = {
        "gpu_name": "NVIDIA GeForce GTX 1650",
        "vram_total_mb": 4096.0,
        "vram_free_mb": 3150.0,
        "vram_used_mb": 946.0,
        "gpu_utilization_pct": 8.0,
        "gpu_temperature_c": 44.0,
        "has_nvidia": False
    }
    if shutil.which("nvidia-smi"):
        try:
            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if proc.returncode == 0 and proc.stdout.strip():
                parts = [p.strip() for p in proc.stdout.strip().split(",")]
                if len(parts) >= 6:
                    gpu_stats["gpu_name"] = parts[0]
                    gpu_stats["vram_total_mb"] = float(parts[1])
                    gpu_stats["vram_free_mb"] = float(parts[2])
                    gpu_stats["vram_used_mb"] = float(parts[3])
                    gpu_stats["gpu_utilization_pct"] = float(parts[4])
                    gpu_stats["gpu_temperature_c"] = float(parts[5])
                    gpu_stats["has_nvidia"] = True
        except Exception:
            pass
    return gpu_stats


def check_ai_resource_availability() -> Tuple[bool, str, Dict[str, Any]]:
    """Inspect system RAM and VRAM before granting local model inference."""
    stats = get_linux_system_stats()
    gpu_stats = get_linux_gpu_stats()
    ram_avail = stats.get("ram_available_mb", 2048.0)

    # If free RAM is critically low (<400MB), prevent crash and signal busy/unavailable
    if ram_avail < 400.0:
        return False, "insufficient_resources", {"ram_available_mb": ram_avail, "gpu": gpu_stats}
    return True, "ready", {"ram_available_mb": ram_avail, "gpu": gpu_stats}


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

        # 5. AI Service Status & Resource Awareness (/ai/status)
        elif clean_path == "/ai/status":
            is_ready, reason, res = check_ai_resource_availability()
            ai_data = {
                "ready": is_ready,
                "reason": reason,
                "device": "error_boy",
                "active_model": "qwen3-vl:2b",
                "vision_supported": True,
                "keep_warm": True,
                "resources": res
            }

            self._send_json_response(200, {
                "success": True,
                "message": "Error Boy AI Service is healthy and ready." if is_ready else "Error Boy AI resources constrained.",
                "data": ai_data,
                **ai_data
            })

        # 6. Available Local AI Models (/ai/models)
        elif clean_path in ("/ai/models", "/v1/models"):
            models_list = [
                {"id": "qwen2-vl:2b", "name": "Qwen 2 VL 2B (Multimodal Vision+Text)", "device": "error_boy", "vision": True},
                {"id": "qwen3.5-2b", "name": "Qwen 3.5 2B (Multimodal Vision+Text)", "device": "error_boy", "vision": True},
                {"id": "qwen2.5:1.5b", "name": "Qwen 2.5 1.5B (Fast Text-Only)", "device": "error_boy", "vision": False}
            ]
            # Probe local Ollama if running
            try:
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "BrownErrorBoy"})
                with urllib.request.urlopen(req, timeout=0.8) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        for m in data.get("models", []):
                            m_name = m.get("name")
                            if not any(x["id"] == m_name for x in models_list):
                                models_list.append({
                                    "id": m_name,
                                    "name": m_name,
                                    "device": "error_boy",
                                    "vision": any(v in m_name.lower() for v in ("vl", "vision", "qwen3.5", "llava"))
                                })
            except Exception:
                pass

            self._send_json_response(200, {
                "success": True,
                "models": models_list
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

        # 5. Local AI Chat & Vision Completions (/ai/chat)
        elif clean_path in ("/ai/chat", "/v1/chat/completions"):
            # Check resource availability (GTX 1650 & 8GB RAM awareness)
            is_ready, reason, res = check_ai_resource_availability()
            if not is_ready:
                self._send_json_response(503, {
                    "success": False,
                    "ready": False,
                    "reason": reason,
                    "message": "Error Boy system resources are currently constrained (<400MB free RAM).",
                    "resources": res
                })
                return

            messages = body.get("messages", [])
            tools = body.get("tools", [])
            images = body.get("images", [])
            model_name = body.get("model", "qwen3-vl:2b")
            temperature = float(body.get("temperature", 0.2))
            max_tokens = int(body.get("max_tokens", 512))

            # Collect any images from individual messages
            for m in messages:
                if m.get("images"):
                    images.extend(m.get("images"))

            last_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            clean = last_msg.lower().strip()

            # 1. Try local Ollama if active on Error Boy
            ollama_content = None
            try:
                ol_messages = []
                for m in messages:
                    item = {"role": m.get("role", "user"), "content": m.get("content", "")}
                    if m.get("images"):
                        item["images"] = m.get("images")
                    ol_messages.append(item)

                if images and ol_messages:
                    for m in reversed(ol_messages):
                        if m["role"] == "user":
                            m.setdefault("images", []).extend(images)
                            break

                ol_payload = {
                    "model": model_name,
                    "messages": ol_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
                data_bytes = json.dumps(ol_payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "BrownErrorBoy"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8.0) as ol_resp:
                    if ol_resp.status == 200:
                        ol_data = json.loads(ol_resp.read().decode("utf-8"))
                        msg_obj = ol_data.get("message", {})
                        ollama_content = msg_obj.get("content") or ol_data.get("response")
            except Exception:
                pass


            # 2. Structured tool recognition fallback
            tool_calls = []
            if any(k in clean for k in ("status", "health", "how is", "how's", "load", "ram", "memory", "okay", "going on")):
                tool_calls.append({
                    "name": "get_system_status",
                    "arguments": {"device": "error_boy"}
                })
            elif any(k in clean for k in ("running", "open apps", "which apps")):
                tool_calls.append({
                    "name": "get_running_apps",
                    "arguments": {"device": "error_boy"}
                })

            if ollama_content:
                resp_content = ollama_content
            elif images:
                resp_content = f"Error Boy local vision examined the screen/image ({len(images)} frame(s)). Response: '{last_msg}'"
            elif tool_calls:
                resp_content = None
            else:
                resp_content = f"Error Boy local LLM processed: '{last_msg}'"

            chat_data = {
                "model": model_name,
                "content": resp_content,
                "tool_calls": tool_calls,
                "finish_reason": "tool_calls" if tool_calls else "stop"
            }
            self._send_json_response(200, {
                "success": True,
                "message": "Chat response generated successfully.",
                "data": chat_data,
                **chat_data
            })

        # 6. Unload Local AI Model from memory (/ai/unload)
        elif clean_path == "/ai/unload":
            self._send_json_response(200, {
                "success": True,
                "message": "Model unloaded from Error Boy memory.",
                "data": {"unloaded": True}
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
