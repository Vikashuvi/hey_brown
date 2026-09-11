"""Decoupled UI Event Bridge for Brown AI Assistant.
Provides a thread-safe, non-blocking WebSocket broadcast server
allowing any desktop, web, or mobile UI to receive live state, audio energy,
and speech playback synchronization events without modifying core voice loops.
"""

import json
import time
import asyncio
import threading
from enum import Enum
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass, asdict


class EventType(str, Enum):
    STATE_CHANGE = "state_change"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    TRANSCRIPT = "transcript"
    TTS_START = "tts_start"
    TTS_END = "tts_end"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


@dataclass
class UIEvent:
    event: str
    data: Dict[str, Any]
    timestamp: float


BrownEvent = UIEvent


class UIEventBridge:
    """Thread-safe WebSocket server that broadcasts Brown engine events to connected UIs."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.host = host
        self.port = port
        self.clients: Set[Any] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._server = None
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Start the WebSocket broadcast server in a dedicated background daemon thread."""
        if self._running:
            return

        self._running = True
        started_evt = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, args=(started_evt,), daemon=True, name="UIEventBridge")
        self._thread.start()
        started_evt.wait(timeout=3.0)
        print(f"[UIEventBridge] Server listening on ws://{self.host}:{self.port}")

    def stop(self):
        """Gracefully stop the server and close all client connections."""
        if not self._running:
            return

        self._running = False
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        print("[UIEventBridge] Server stopped.")

    def broadcast(self, event: str, data: Optional[Dict[str, Any]] = None):
        """Thread-safe non-blocking broadcast to all connected UI clients."""
        if not self._running or not self._loop or not self.clients:
            return

        payload = {
            "event": event,
            "data": data or {},
            "timestamp": time.time()
        }
        msg = json.dumps(payload)

        try:
            asyncio.run_coroutine_threadsafe(self._send_to_all(msg), self._loop)
        except Exception:
            pass

    # Async internal handling
    async def _send_to_all(self, message: str):
        if not self.clients:
            return

        with self._lock:
            active_clients = list(self.clients)

        tasks = []
        for client in active_clients:
            tasks.append(self._safe_send(client, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, client, message: str):
        try:
            await client.send(message)
        except Exception:
            with self._lock:
                self.clients.discard(client)

    async def _handle_connection(self, websocket):
        with self._lock:
            self.clients.add(websocket)

        # Send initial welcome & handshake
        handshake = json.dumps({
            "event": "connected",
            "data": {"message": "Connected to Brown UI Event Bridge", "port": self.port},
            "timestamp": time.time()
        })
        try:
            await websocket.send(handshake)
            # Keep alive loop listening for ping/pong or UI poke messages
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                    # Support UI poking or wake requests if sent from UI
                    if data.get("action") == "ping":
                        await websocket.send(json.dumps({"event": "pong", "timestamp": time.time()}))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            with self._lock:
                self.clients.discard(websocket)

    async def _shutdown_async(self):
        with self._lock:
            clients = list(self.clients)
            self.clients.clear()

        for c in clients:
            try:
                await c.close()
            except Exception:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def _run_loop(self, started_evt: threading.Event):
        import websockets

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def main_async():
            self._server = await websockets.serve(self._handle_connection, self.host, self.port)
            started_evt.set()
            await self._server.wait_closed()

        try:
            self._loop.run_until_complete(main_async())
        except Exception:
            started_evt.set()
        finally:
            self._loop.close()


# Global default bridge singleton
_bridge_instance: Optional[UIEventBridge] = None
_bridge_lock = threading.Lock()


def get_event_bridge(host: str = "127.0.0.1", port: int = 8766) -> UIEventBridge:
    """Retrieve or initialize the global UI event bridge singleton."""
    global _bridge_instance
    with _bridge_lock:
        if _bridge_instance is None:
            _bridge_instance = UIEventBridge(host=host, port=port)
        return _bridge_instance
