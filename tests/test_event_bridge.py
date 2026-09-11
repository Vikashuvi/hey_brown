import time
import socket
import pytest
import asyncio
from core.events import UIEventBridge, EventType


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_ui_event_bridge_lifecycle():
    import websockets

    port = find_free_port()
    bridge = UIEventBridge(host="127.0.0.1", port=port)
    bridge.start()
    await asyncio.sleep(0.2)

    uri = f"ws://127.0.0.1:{port}"
    async with websockets.connect(uri) as ws:
        # 1. Receive handshake
        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
        assert "connected" in msg

        # 2. Test broadcast
        bridge.broadcast("state_change", {"state": "LISTENING", "old_state": "SLEEPING"})
        event_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
        assert "LISTENING" in event_raw
        assert "state_change" in event_raw

    bridge.stop()
