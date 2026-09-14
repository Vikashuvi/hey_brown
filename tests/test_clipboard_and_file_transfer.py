"""Unit tests for Phase D (Clipboard) & Phase E (Secure File Transfer)."""

import os
import time
import base64
import hashlib
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from agents.local_agent import LocalAgent
from agents.remote_agent import RemoteAgent
from tools.system_tools import GetClipboardTool, SetClipboardTool, SyncClipboardTool, TransferFileTool
from devices.base import DeviceCommandResult


def test_local_agent_clipboard_size_limit():
    agent = LocalAgent()
    oversized_text = "A" * 600000  # > 512KB
    res = agent.set_clipboard_text(oversized_text)
    assert res.success is False
    assert "exceeds 512KB" in res.message


def test_local_agent_clipboard_mock():
    agent = LocalAgent()
    with patch("subprocess.run") as mock_sub:
        mock_sub.return_value.returncode = 0
        mock_sub.return_value.stdout = "Copied text content"

        read_res = agent.get_clipboard_text()
        assert read_res.success is True
        assert read_res.data["text"] == "Copied text content"

        set_res = agent.set_clipboard_text("New content")
        assert set_res.success is True


def test_remote_agent_clipboard_mock():
    agent = RemoteAgent(base_url="http://mock-remote:8765")
    with patch.object(agent, "_send_command") as mock_cmd:
        mock_cmd.return_value = DeviceCommandResult(
            success=True,
            message="Remote clipboard read",
            data={"text": "Remote string"}
        )
        res = agent.get_clipboard_text()
        assert res.success is True
        assert res.data["text"] == "Remote string"
        mock_cmd.assert_called_once_with("clipboard/get", method="GET", timeout=2.0)


def test_sync_clipboard_tool():
    src_mock = MagicMock()
    src_mock.display_name = "Source Dev"
    src_mock.get_clipboard_text.return_value = DeviceCommandResult(
        success=True,
        message="OK",
        data={"text": "Shared snippet"}
    )

    dst_mock = MagicMock()
    dst_mock.display_name = "Target Dev"
    dst_mock.set_clipboard_text.return_value = DeviceCommandResult(
        success=True,
        message="OK",
        data={"length": 14}
    )

    devices = {"mac": src_mock, "linux": dst_mock}
    tool = SyncClipboardTool(devices)
    res = tool.execute(from_device="mac", to_device="linux")

    assert res.success is True
    src_mock.get_clipboard_text.assert_called_once()
    dst_mock.set_clipboard_text.assert_called_once_with("Shared snippet")


def test_file_transfer_path_traversal_protection():
    agent = LocalAgent()
    res = agent.receive_file(filename="../../etc/passwd", content_b64=base64.b64encode(b"malicious").decode("utf-8"))
    assert res.success is False
    assert "Invalid or unsafe filename" in res.message


def test_file_transfer_checksum_and_atomic_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = LocalAgent(device_id="test_host", display_name="Test Host")
        content = b"Hello, secure world of Brown file transfer!"
        content_b64 = base64.b64encode(content).decode("utf-8")
        sha256_hash = hashlib.sha256(content).hexdigest()

        # 1. Valid transfer
        res = agent.receive_file(
            filename="hello.txt",
            content_b64=content_b64,
            target_dir=tmpdir,
            expected_sha256=sha256_hash
        )
        assert res.success is True
        final_file = os.path.join(tmpdir, "hello.txt")
        assert os.path.exists(final_file)
        with open(final_file, "rb") as f:
            assert f.read() == content

        # 2. Checksum mismatch defense
        res_bad = agent.receive_file(
            filename="tampered.txt",
            content_b64=content_b64,
            target_dir=tmpdir,
            expected_sha256="wrong_checksum"
        )
        assert res_bad.success is False
        assert "checksum mismatch" in res_bad.message.lower()
        assert not os.path.exists(os.path.join(tmpdir, "tampered.txt"))


def test_transfer_file_tool():
    src_mock = MagicMock()
    src_mock.display_name = "Source Dev"
    src_mock.send_file.return_value = DeviceCommandResult(
        success=True,
        message="Ready",
        data={
            "filename": "code.py",
            "content_b64": base64.b64encode(b"print('ok')").decode("utf-8"),
            "sha256": hashlib.sha256(b"print('ok')").hexdigest(),
            "bytes": 11
        }
    )

    dst_mock = MagicMock()
    dst_mock.display_name = "Dest Dev"
    dst_mock.receive_file.return_value = DeviceCommandResult(
        success=True,
        message="Saved",
        data={"filename": "code.py"}
    )

    devices = {"dev_a": src_mock, "dev_b": dst_mock}
    tool = TransferFileTool(devices)
    res = tool.execute(filename="code.py", from_device="dev_a", to_device="dev_b")

    assert res.success is True
    src_mock.send_file.assert_called_once()
    dst_mock.receive_file.assert_called_once()
