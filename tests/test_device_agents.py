import pytest
from unittest.mock import patch, MagicMock
from devices.paperball import PaperballAgent
from devices.error_boy import ErrorBoyAgent


def test_paperball_agent_security_validation():
    agent = PaperballAgent()

    # Reject shell injection attempts
    bad_apps = [
        "Safari; rm -rf /",
        "Terminal && echo hacked",
        "App | cat /etc/passwd",
        "$(whoami)",
        "`calc`"
    ]
    for bad in bad_apps:
        res = agent.open_application(bad)
        assert not res.success
        assert "Invalid or unsafe application name" in res.message


def test_paperball_agent_url_validation():
    agent = PaperballAgent()

    # Invalid URL
    res = agent.open_url("not a url with spaces / :")
    assert not res.success or "http" in res.message

    # Valid status query
    status = agent.get_system_status()
    assert status.success
    assert "load1" in status.data


def test_error_boy_agent_offline_graceful_handling():
    # Attempting to talk to a non-existent port on localhost should fail gracefully without throwing
    agent = ErrorBoyAgent(base_url="http://127.0.0.1:59999", timeout=0.2)
    assert not agent.is_online

    res = agent.open_application("VS Code")
    assert not res.success
    assert "offline" in res.message.lower() or "unreachable" in res.message.lower()

    res_url = agent.open_url("https://github.com")
    assert not res_url.success
    assert "offline" in res_url.message.lower() or "unreachable" in res_url.message.lower()


def test_error_boy_agent_online_mock():
    agent = ErrorBoyAgent(base_url="http://mock-error-boy:8000")

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "message": "Opened VS Code on Error Boy."}
        mock_post.return_value = mock_resp

        res = agent.open_application("VS Code")
        assert res.success
        assert "Opened VS Code" in res.message


def test_device_agents_capabilities_and_running_apps():
    # Paperball
    pb = PaperballAgent()
    caps = pb.get_device_capabilities()
    assert caps.success
    assert caps.data["device"] == "paperball"
    assert "open_application" in caps.data["capabilities"]

    # Error Boy mock capabilities
    eb = ErrorBoyAgent(base_url="http://mock-error-boy:8000")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "message": "Capabilities",
            "data": {"device": "error_boy", "capabilities": ["get_device_status", "get_running_apps"]}
        }
        mock_get.return_value = mock_resp

        eb_caps = eb.get_device_capabilities()
        assert eb_caps.success
        assert "get_running_apps" in eb_caps.data["capabilities"]

