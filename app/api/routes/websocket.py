"""
WebSocket routes — real-time communication for analysis progress and chat.
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        # Queue of messages that couldn't be sent due to disconnection
        self._pending_messages: dict[str, list[dict]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"🔌 WebSocket connected: {session_id}")

        # Flush any pending messages for this session
        pending = self._pending_messages.pop(session_id, [])
        for msg in pending:
            try:
                await websocket.send_json(msg)
                print(f"📨 [WS] Flushed pending {msg.get('event')} to {session_id}")
            except Exception:
                pass

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        print(f"🔌 WebSocket disconnected: {session_id}")

    async def send_event(self, session_id: str, event: str, data: dict[str, Any]):
        """Send a typed event to a specific session. Queues if disconnected."""
        message = {"event": event, "data": data}
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(message)
                return
            except Exception as e:
                print(f"⚠️ [WS] Failed to send {event} to {session_id}: {e}")
                # Connection is stale, remove it
                self.active_connections.pop(session_id, None)

        # If we get here, the connection is gone. Queue important messages.
        if event in ("analysis:result", "analysis:progress"):
            if session_id not in self._pending_messages:
                self._pending_messages[session_id] = []
            # Only queue the result event (not spammy progress events)
            if event == "analysis:result":
                self._pending_messages[session_id].append(message)
                print(f"📦 [WS] Queued {event} for {session_id} (will flush on reconnect)")

    async def broadcast(self, event: str, data: dict[str, Any]):
        """Broadcast an event to all connected clients."""
        message = json.dumps({"event": event, "data": data})
        for ws in self.active_connections.values():
            await ws.send_text(message)


# Singleton connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time updates.

    Events (server → client):
        - analysis:progress  — step-by-step agent progress
        - analysis:result    — final analysis result
        - execution:output   — code execution output
        - chat:message       — AI chat responses

    Events (client → server):
        - chat:message       — user chat input
    """
    await ws_manager.connect(session_id, websocket)

    try:
        while True:
            # Listen for client messages
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                event = message.get("event", "")
                data = message.get("data", {})

                if event == "chat:message":
                    # Echo back for now — will be handled by agent in Phase 2
                    await ws_manager.send_event(
                        session_id,
                        "chat:message",
                        {
                            "role": "assistant",
                            "content": f"🤖 Agent not yet connected (Phase 2). "
                            f"You said: {data.get('content', '')}",
                        },
                    )
                elif event == "ping":
                    await ws_manager.send_event(session_id, "pong", {})

            except json.JSONDecodeError:
                await ws_manager.send_event(
                    session_id, "error", {"message": "Invalid JSON"}
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
