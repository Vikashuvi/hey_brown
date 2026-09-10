import time
import socket
import threading
import requests
from http.server import ThreadingHTTPServer
from devices.error_boy_server import (
    ErrorBoyRequestHandler,
    resolve_linux_binary,
    get_linux_system_stats,
    LINUX_APP_MAP
)
from devices.error_boy import ErrorBoyAgent


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def test_linux_binary_resolution():
    assert resolve_linux_binary("vs code") == "code"
    assert resolve_linux_binary("code") == "code"
    assert resolve_linux_binary("firefox") == "firefox"
    assert resolve_linux_binary("browser") == "firefox"
    assert resolve_linux_binary("discord") == "discord"
    assert resolve_linux_binary("terminal") in ("alacritty", "kitty", "foot", "xterm")


def test_linux_system_stats():
    stats = get_linux_system_stats()
    assert "hostname" in stats
    assert "platform" in stats
    assert "load1" in stats
    assert stats["cpu_count"] >= 1


def test_error_boy_server_lifecycle_and_endpoints():
    port = find_free_port()
    auth_token = "secret-arch-token-123"
    ErrorBoyRequestHandler.auth_token = auth_token

    server = ThreadingHTTPServer(("127.0.0.1", port), ErrorBoyRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Health endpoint (with auth)
        agent = ErrorBoyAgent(base_url=base_url, auth_token=auth_token, timeout=2.0)
        assert agent.is_online

        # 2. Health endpoint without auth should fail
        unauth_agent = ErrorBoyAgent(base_url=base_url, auth_token=None, timeout=2.0)
        assert not unauth_agent.is_online

        # 3. System status query
        status_res = agent.get_system_status()
        assert status_res.success
        assert "healthy" in status_res.message.lower() or "load" in status_res.message.lower()
        assert "hostname" in status_res.data

        # 4. Open app (using an executable guaranteed to be on the test system)
        open_res = agent.open_application("python3")
        assert open_res.success
        assert "Launched" in open_res.message

        # Missing app should report gracefully without failing or crashing
        missing_res = agent.open_application("some_fake_nonexistent_app_12345")
        assert not missing_res.success
        assert "not installed" in missing_res.message or "not found" in missing_res.message

        # 5. Close app
        close_res = agent.close_application("python3")
        assert close_res.success
        assert "Closed" in close_res.message

        # 6. Open URL
        url_res = agent.open_url("https://archlinux.org")
        assert url_res.success
        assert "Opened" in url_res.message

        # Invalid URL validation
        bad_url_res = agent.open_url("not a url with spaces")
        assert not bad_url_res.success

        # 7. Running apps query
        apps_res = agent.get_running_apps()
        assert apps_res.success
        assert "running_apps" in apps_res.data

        # 8. Device capabilities query
        caps_res = agent.get_device_capabilities()
        assert caps_res.success
        assert caps_res.data["device"] == "error_boy"
        assert "open_application" in caps_res.data["capabilities"]
        assert "get_device_capabilities" in caps_res.data["capabilities"]

        # 9. Shell injection rejection test on app open
        injection_res = agent.open_application("firefox; rm -rf /")
        assert not injection_res.success
        assert "Invalid or unsafe" in injection_res.message

    finally:
        server.shutdown()
        server.server_close()
        ErrorBoyRequestHandler.auth_token = None
