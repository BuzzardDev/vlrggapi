import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from api.scrapers import vlr_match_detail
from utils.http_client import close_http_client
from utils.websocket_manager import manager

logger = logging.getLogger(__name__)

async def poll_matches():
    while True:
        subscribed_matches = list(manager.subscriptions.keys())
        if not subscribed_matches:
            await asyncio.sleep(1)
            continue

        tasks = [vlr_match_detail(match_id) for match_id in subscribed_matches]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for match_id, result in zip(subscribed_matches, results):
            if isinstance(result, Exception) or "data" not in result:
                continue

            new_data = result["data"]["segments"][0]
            old_state = manager.match_states.get(match_id)
            events = []

            if not old_state:
                events.append("match_start")
            else:
                # Detect score updates (series/map score changes)
                old_scores = [t.get("score") for t in old_state.get("teams", [])]
                new_scores = [t.get("score") for t in new_data.get("teams", [])]
                if old_scores != new_scores:
                    events.append("score_update")
                
                # Detect round ends (compare round count in the latest map)
                old_maps = old_state.get("maps", [])
                new_maps = new_data.get("maps", [])
                if old_maps and new_maps:
                    old_rounds = len(old_maps[-1].get("rounds", []))
                    new_rounds = len(new_maps[-1].get("rounds", []))
                    if old_rounds != new_rounds:
                        events.append("round_end")

                # Detect match end
                old_status = old_state.get("status")
                new_status = new_data.get("status")
                if old_status != new_status and new_status == "Completed":
                    events.append("match_end")

            # Broadcast all detected events
            for event in events:
                await manager.broadcast(match_id, event, new_data)

            # Update stored state
            manager.match_states[match_id] = new_data

        # Reduced polling interval for better realtime responsiveness
        await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting vlrggapi with WebSocket polling")
    polling_task = asyncio.create_task(poll_matches())
    yield
    polling_task.cancel()
    logger.info("Shutting down — closing HTTP client")
    await close_http_client()

# App initialization
app = FastAPI(lifespan=lifespan)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if "subscribe" in data:
                await manager.subscribe(websocket, str(data["subscribe"]))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
