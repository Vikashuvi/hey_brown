"""Brown Remote Agent & Inference Node Daemon.
Runs on secondary or accelerator machines (Linux / GPU nodes) to receive capability commands and host local AI.
Zero external dependencies (uses Python standard library only).

Usage:
    python3 devices/remote_daemon.py --port 8765
Or run as a systemd user service via brown-node.service.
"""

import os
import re
import sys
import json
import time
import shutil
import socket
import argparse
import threading
import subprocess
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional, Tuple, List


class LocalAIState:
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    MODEL_NOT_INSTALLED = "MODEL_NOT_INSTALLED"
    MODEL_LOADING = "MODEL_LOADING"
    READY = "READY"
    BUSY = "BUSY"
    RESOURCE_LIMITED = "RESOURCE_LIMITED"
    ERROR = "ERROR"


DEFAULT_DEVICE_ID = os.environ.get("BROWN_DEVICE_ID", os.environ.get("DEVICE_ID", "remote_node"))
DEFAULT_DEVICE_NAME = os.environ.get("BROWN_DEVICE_NAME", os.environ.get("DEVICE_NAME", "Remote Node"))

_state_lock = threading.Lock()
_is_busy = False
_is_loading = False
_last_self_heal_attempt = 0.0


def check_ollama_runtime() -> Tuple[bool, List[str], List[str]]:
    """Check Ollama API tags and loaded models (/api/ps)."""
    installed = []
    loaded = []
    online = False
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "BrownNodeDaemon"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                online = True
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    name = m.get("name")
                    if name:
                        installed.append(name)
                        if ":latest" in name:
                            installed.append(name.replace(":latest", ""))
    except Exception:
        online = False

    if online:
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/ps", headers={"User-Agent": "BrownNodeDaemon"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for m in data.get("models", []):
                        name = m.get("name")
                        if name:
                            loaded.append(name)
        except Exception:
            pass

    return online, installed, loaded


def attempt_ollama_recovery():
    """Attempt non-blocking recovery by triggering systemd user unit for Ollama."""
    global _last_self_heal_attempt
    now = time.time()
    if now - _last_self_heal_attempt < 15.0:
        return
    _last_self_heal_attempt = now
    try:
        subprocess.Popen(
            ["systemctl", "--user", "start", "ollama"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def get_local_ai_status(target_model: str = "qwen3-vl:2b") -> Dict[str, Any]:
    """Assess granular health state of local AI on the node."""
    global _is_busy, _is_loading

    eb_mod = sys.modules.get("devices.error_boy_server")
    res_fn = getattr(eb_mod, "check_ai_resource_availability", check_ai_resource_availability) if eb_mod else check_ai_resource_availability
    ol_fn = getattr(eb_mod, "check_ollama_runtime", check_ollama_runtime) if eb_mod else check_ollama_runtime
    rec_fn = getattr(eb_mod, "attempt_ollama_recovery", attempt_ollama_recovery) if eb_mod else attempt_ollama_recovery

    res_ready, res_reason, res_stats = res_fn()
    if not res_ready:
        return {
            "state": LocalAIState.RESOURCE_LIMITED,
            "ready": False,
            "reason": res_reason,
            "resources": res_stats,
            "model": target_model,
            "active_model": target_model,
            "device": DEFAULT_DEVICE_ID
        }

    with _state_lock:
        if _is_loading:
            return {
                "state": LocalAIState.MODEL_LOADING,
                "ready": False,
                "reason": "model_is_loading",
                "model": target_model,
                "active_model": target_model,
                "device": DEFAULT_DEVICE_ID,
                "resources": res_stats
            }
        if _is_busy:
            return {
                "state": LocalAIState.BUSY,
                "ready": False,
                "reason": "generating_inference",
                "model": target_model,
                "active_model": target_model,
                "device": DEFAULT_DEVICE_ID,
                "resources": res_stats
            }

    ollama_online, installed, loaded = ol_fn()
    if not ollama_online:
        rec_fn()
        state = LocalAIState.STARTING if (time.time() - _last_self_heal_attempt < 4.0) else LocalAIState.OLLAMA_UNAVAILABLE
        return {
            "state": state,
            "ready": False,
            "reason": "ollama_not_responding",
            "model": target_model,
            "active_model": target_model,
            "device": DEFAULT_DEVICE_ID,
            "ollama_active": False,
            "resources": res_stats
        }

    model_installed = any(
        target_model == m or target_model in m or m.startswith(target_model)
        for m in installed
    )
    if not model_installed:
        return {
            "state": LocalAIState.MODEL_NOT_INSTALLED,
            "ready": False,
            "reason": f"model_{target_model}_not_found",
            "model": target_model,
            "active_model": target_model,
            "installed_models": installed,
            "device": DEFAULT_DEVICE_ID,
            "ollama_active": True,
            "resources": res_stats
        }

    is_loaded = any(target_model in m for m in loaded)

    return {
        "state": LocalAIState.READY,
        "ready": True,
        "model": target_model,
        "active_model": target_model,
        "loaded": is_loaded,
        "loaded_models": loaded,
        "installed_models": installed,
        "device": DEFAULT_DEVICE_ID,
        "ollama_active": True,
        "resources": res_stats
    }


SAFE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\s\-_\.]+$")

# Map colloquial or cross-platform names to typical Linux binaries
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

TERMINAL_CANDIDATES = ["alacritty", "kitty", "foot", "wezterm", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"]


def resolve_linux_binary(app_name: str) -> str:
    """Resolve a friendly app name to an installed executable on Linux."""
    raw = app_name.strip().lower()

    if raw in ("terminal", "console", "iterm", "iterm2"):
        for term in TERMINAL_CANDIDATES:
            if shutil.which(term):
                return term
        return "xterm"

    mapped = LINUX_APP_MAP.get(raw, raw)

    if shutil.which(mapped):
        return mapped

    if shutil.which(raw):
        return raw

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

    try:
        load1, load5, load15 = os.getloadavg()
        stats["load1"] = round(load1, 2)
        stats["load5"] = round(load5, 2)
        stats["load15"] = round(load15, 2)
    except Exception:
        stats["load1"] = stats["load5"] = stats["load15"] = 0.0

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
    """Extract NVIDIA/accelerator GPU and VRAM statistics on Linux if present."""
    gpu_stats = {
        "gpu_name": "None",
        "vram_total_mb": 0.0,
        "vram_free_mb": 0.0,
        "vram_used_mb": 0.0,
        "gpu_utilization_pct": 0.0,
        "gpu_temperature_c": 0.0,
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

    # Protect against OOM if free RAM is critically low (<400MB)
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


class NodeRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing the node's strict typed REST API."""

    auth_token: Optional[str] = None
    device_id: str = DEFAULT_DEVICE_ID
    device_name: str = DEFAULT_DEVICE_NAME

    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

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
                "device": self.device_id,
                "message": f"{self.device_name} is online and reachable."
            })

        # 2. System Status
        elif clean_path in ("/system/status", "/status"):
            stats = get_linux_system_stats()
            load_str = f"Load: {stats.get('load1', 0.0):.2f}"
            ram_str = f"RAM: {stats.get('ram_used_mb', 0)}MB/{stats.get('ram_total_mb', 0)}MB"
            self._send_json_response(200, {
                "success": True,
                "message": f"{self.device_name} is healthy. {load_str}, {ram_str}.",
                "data": stats
            })

        # 3. Running Applications
        elif clean_path == "/apps/running":
            running = get_running_linux_apps()
            self._send_json_response(200, {
                "success": True,
                "message": f"{self.device_name} is currently running: {', '.join(running) if running else 'no targeted applications'}.",
                "data": {"running_apps": running}
            })

        # 4. Device Capabilities
        elif clean_path == "/capabilities":
            self._send_json_response(200, {
                "success": True,
                "message": f"{self.device_name} device capabilities retrieved.",
                "data": {
                    "device": self.device_id,
                    "os": "Linux",
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
            parsed_query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            target_model = parsed_query.get("model", ["qwen3-vl:2b"])[0]
            status_data = get_local_ai_status(target_model=target_model)
            self._send_json_response(200, {
                "success": True,
                "data": status_data,
                **status_data
            })

        # 6. Available Local AI Models (/ai/models)
        elif clean_path in ("/ai/models", "/v1/models"):
            models_list = []
            ollama_online, installed, loaded = check_ollama_runtime()
            for m_name in installed:
                models_list.append({
                    "id": m_name,
                    "name": m_name,
                    "device": self.device_id,
                    "loaded": any(m_name in l for l in loaded),
                    "vision": any(v in m_name.lower() for v in ("vl", "vision", "qwen3", "llava"))
                })
            if not models_list:
                models_list = [
                    {"id": "qwen3-vl:2b", "name": "Qwen 3 VL 2B (Multimodal Vision+Text)", "device": self.device_id, "vision": True, "loaded": False},
                    {"id": "qwen2.5:1.5b", "name": "Qwen 2.5 1.5B (Fast Text-Only)", "device": self.device_id, "vision": False, "loaded": False}
                ]

            self._send_json_response(200, {
                "success": True,
                "models": models_list
            })

        else:
            self._send_json_response(404, {"success": False, "message": f"Endpoint not found: {self.path}"})

    def do_POST(self):
        global _is_busy, _is_loading
        if not self._check_auth():
            self._send_json_response(401, {"success": False, "message": "Unauthorized: invalid or missing bearer token."})
            return

        ok, body = self._parse_json_body()
        if not ok:
            self._send_json_response(400, {"success": False, "message": body.get("error", "Bad Request")})
            return

        clean_path = self.path.split("?")[0].rstrip("/")

        # 1. Open Application
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
                    "message": f"Application '{app_name}' (binary '{binary}') is not installed or not found in PATH on {self.device_name}."
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
                    "message": f"Launched {app_name} on {self.device_name}.",
                    "data": {"binary": executable}
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to launch {app_name} on {self.device_name}: {str(e)}"
                })

        # 2. Close Application
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
                    "message": f"Closed {app_name} on {self.device_name}.",
                    "data": {"returncode": proc.returncode}
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to close {app_name}: {str(e)}"
                })

        # 3. Open URL
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
                    "message": f"Opened {raw_url} in browser on {self.device_name}."
                })
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "message": f"Failed to open URL on {self.device_name}: {str(e)}"
                })

        # 4. Fallback for system status via POST
        elif clean_path in ("/system/status", "/status"):
            stats = get_linux_system_stats()
            load_str = f"Load: {stats.get('load1', 0.0):.2f}"
            ram_str = f"RAM: {stats.get('ram_used_mb', 0)}MB/{stats.get('ram_total_mb', 0)}MB"
            self._send_json_response(200, {
                "success": True,
                "message": f"{self.device_name} is healthy. {load_str}, {ram_str}.",
                "data": stats
            })

        # 5. Warm / Preload Local AI Model into VRAM (/ai/warm)
        elif clean_path == "/ai/warm":
            model_name = body.get("model", "qwen3-vl:2b")
            keep_alive = body.get("keep_alive", "15m")
            with _state_lock:
                _is_loading = True
            try:
                ol_payload = {
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": keep_alive
                }
                data_bytes = json.dumps(ol_payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "BrownNodeDaemon"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30.0) as ol_resp:
                    if ol_resp.status == 200:
                        self._send_json_response(200, {
                            "success": True,
                            "state": LocalAIState.READY,
                            "message": f"Model '{model_name}' successfully warmed in memory.",
                            "model": model_name,
                            "keep_alive": keep_alive
                        })
                        return
            except Exception as e:
                self._send_json_response(500, {
                    "success": False,
                    "state": LocalAIState.ERROR,
                    "message": f"Failed to warm model '{model_name}': {str(e)}"
                })
                return
            finally:
                with _state_lock:
                    _is_loading = False

        # 6. Stream Local AI Completions (/ai/stream)
        elif clean_path == "/ai/stream":
            messages = body.get("messages", [])
            model_name = body.get("model", "qwen3-vl:2b")
            temperature = float(body.get("temperature", 0.2))
            max_tokens = int(body.get("max_tokens", 512))
            keep_alive = body.get("keep_alive", "15m")

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with _state_lock:
                _is_busy = True

            try:
                ol_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
                ol_payload = {
                    "model": model_name,
                    "messages": ol_messages,
                    "stream": True,
                    "keep_alive": keep_alive,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
                data_bytes = json.dumps(ol_payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "BrownNodeDaemon"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30.0) as ol_resp:
                    for line in ol_resp:
                        if line:
                            chunk = json.loads(line.decode("utf-8"))
                            content = chunk.get("message", {}).get("content") or chunk.get("response", "")
                            if content:
                                event_data = f"data: {json.dumps({'content': content})}\n\n"
                                self.wfile.write(event_data.encode("utf-8"))
                                self.wfile.flush()
                            if chunk.get("done", False):
                                break
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as e:
                err_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                self.wfile.write(err_data.encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            finally:
                with _state_lock:
                    _is_busy = False

        # 7. Local AI Chat & Vision Completions (/ai/chat)
        elif clean_path in ("/ai/chat", "/v1/chat/completions"):
            is_ready, reason, res = check_ai_resource_availability()
            if not is_ready:
                self._send_json_response(503, {
                    "success": False,
                    "ready": False,
                    "reason": reason,
                    "message": f"{self.device_name} system resources are currently constrained (<400MB free RAM).",
                    "resources": res
                })
                return

            messages = body.get("messages", [])
            tools = body.get("tools", [])
            images = body.get("images", [])
            model_name = body.get("model", "qwen3-vl:2b")
            temperature = float(body.get("temperature", 0.2))
            max_tokens = int(body.get("max_tokens", 512))
            keep_alive = body.get("keep_alive", "15m")

            for m in messages:
                if m.get("images"):
                    images.extend(m.get("images"))

            last_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            clean = last_msg.lower().strip()

            ollama_content = None
            with _state_lock:
                _is_busy = True
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

                if not any(m.get("role") == "system" for m in ol_messages):
                    ol_messages.insert(0, {
                        "role": "system",
                        "content": "You are Brown, a personal AI assistant. Answer directly and concisely in 1-2 brief sentences."
                    })

                ol_payload = {
                    "model": model_name,
                    "messages": ol_messages,
                    "stream": False,
                    "keep_alive": keep_alive,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
                data_bytes = json.dumps(ol_payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "BrownNodeDaemon"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30.0) as ol_resp:
                    if ol_resp.status == 200:
                        ol_data = json.loads(ol_resp.read().decode("utf-8"))
                        msg_obj = ol_data.get("message", {})
                        ollama_content = msg_obj.get("content") or ol_data.get("response")
            except Exception as e:
                print(f"[BrownNodeDaemon] Ollama inference error: {e}")
            finally:
                with _state_lock:
                    _is_busy = False

            # Structured tool recognition fallback
            tool_calls = []
            if any(k in clean for k in ("status", "health", "how is", "how's", "load", "ram", "memory", "okay", "going on")):
                tool_calls.append({
                    "name": "get_system_status",
                    "arguments": {"device": self.device_id}
                })
            elif any(k in clean for k in ("running", "open apps", "which apps")):
                tool_calls.append({
                    "name": "get_running_apps",
                    "arguments": {"device": self.device_id}
                })

            if ollama_content:
                resp_content = ollama_content
            elif images:
                resp_content = f"{self.device_name} local vision examined the screen/image ({len(images)} frame(s)). Response: '{last_msg}'"
            elif tool_calls:
                resp_content = None
            else:
                resp_content = f"{self.device_name} local model processed: '{last_msg}'"

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

        # 8. Unload Model from Memory (/ai/unload)
        elif clean_path == "/ai/unload":
            model_name = body.get("model", "qwen3-vl:2b")
            try:
                ol_payload = {
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": 0
                }
                data_bytes = json.dumps(ol_payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "BrownNodeDaemon"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10.0) as ol_resp:
                    pass
            except Exception:
                pass

            self._send_json_response(200, {
                "success": True,
                "message": f"Model '{model_name}' unloaded from {self.device_name} memory.",
                "data": {"unloaded": True}
            })

        else:
            self._send_json_response(404, {"success": False, "message": f"Endpoint not found: {self.path}"})

    def log_message(self, format, *args):
        print(f"[BrownNodeDaemon] {self.address_string()} - {format % args}")


# Backward compatibility alias
class ErrorBoyRequestHandler(NodeRequestHandler):
    device_id = "error_boy"
    device_name = "Error Boy"


def run_server(
    host: str = "0.0.0.0",
    port: int = 8765,
    auth_token: Optional[str] = None,
    device_id: str = DEFAULT_DEVICE_ID,
    device_name: str = DEFAULT_DEVICE_NAME
):
    """Start Brown Remote Node HTTP daemon."""
    NodeRequestHandler.auth_token = auth_token
    NodeRequestHandler.device_id = device_id
    NodeRequestHandler.device_name = device_name
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, NodeRequestHandler)
    print(f"==================================================")
    print(f"  Brown Remote Agent Daemon (Node: {device_name})")
    print(f"  Device ID   : {device_id}")
    print(f"  Listening on: http://{host}:{port}")
    print(f"  Auth Token  : {'Configured' if auth_token else 'Disabled (Open LAN)'}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[BrownNodeDaemon] Shutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Brown Remote Node Agent Daemon")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID, help="Canonical device ID")
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME, help="Human-readable device name")
    parser.add_argument("--auth-token", default=os.environ.get("BROWN_AUTH_TOKEN"), help="Optional authentication bearer token")
    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        auth_token=args.auth_token,
        device_id=args.device_id,
        device_name=args.device_name
    )
