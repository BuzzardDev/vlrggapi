import asyncio
import json
import time
from typing import Dict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self.match_states: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

    def disconnect(self, websocket: WebSocket):
        # Discard the websocket from all subscriptions
        for match_id in list(self.subscriptions.keys()):
            self.subscriptions[match_id].discard(websocket)
            # Clean up the match_id key if no clients are listening anymore
            if not self.subscriptions[match_id]:
                del self.subscriptions[match_id]

    async def subscribe(self, websocket: WebSocket, match_id: str):
        if match_id not in self.subscriptions:
            self.subscriptions[match_id] = set()
        self.subscriptions[match_id].add(websocket)

    async def broadcast(self, match_id: str, event_type: str, data: dict):
        if match_id in self.subscriptions:
            message = json.dumps({
                "event": event_type,
                "match_id": match_id,
                "timestamp": time.time(),
                "data": data
            })
            for connection in list(self.subscriptions[match_id]):
                try:
                    await connection.send_text(message)
                except Exception:
                    self.disconnect(connection)

manager = ConnectionManager()
