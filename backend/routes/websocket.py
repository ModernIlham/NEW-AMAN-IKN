"""WebSocket routes for real-time notifications and sync.

Cross-worker fanout via event_bus (capped collection + tailable cursor) so that
multiple uvicorn workers / pods share notifications without Redis."""
import json
import asyncio
import logging
from typing import Dict
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import event_bus
from db import db

logger = logging.getLogger(__name__)
ws_router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections per activity (in-memory, per worker process)."""

    def __init__(self):
        # { activity_id: { ws: { "user_id": str, "user_name": str } } }
        self.active: Dict[str, Dict[WebSocket, dict]] = {}

    async def connect(self, ws: WebSocket, activity_id: str, user_id: str, user_name: str):
        await ws.accept()
        if activity_id not in self.active:
            self.active[activity_id] = {}
        self.active[activity_id][ws] = {"user_id": user_id, "user_name": user_name}
        # Broadcast online users (locally — presence is per-process; multi-worker
        # presence aggregation is handled via event_bus on connect/disconnect)
        await self.broadcast_online_users(activity_id)
        # Notify other workers that this user is now online for this activity
        await event_bus.publish(db, activity_id, {"type": "__presence_join__", "user_id": user_id, "user_name": user_name})

    async def disconnect(self, ws: WebSocket, activity_id: str):
        info = None
        if activity_id in self.active:
            info = self.active[activity_id].pop(ws, None)
            if not self.active[activity_id]:
                del self.active[activity_id]
        if info:
            # Tell other workers this user disconnected from this worker (presence may still be true via other connections)
            await event_bus.publish(db, activity_id, {"type": "__presence_leave__", "user_id": info["user_id"]})

    def get_online_users(self, activity_id: str):
        if activity_id not in self.active:
            return []
        seen = set()
        users = []
        for info in list(self.active[activity_id].values()):
            uid = info["user_id"]
            if uid not in seen:
                seen.add(uid)
                users.append({"user_id": uid, "user_name": info["user_name"]})
        return users

    async def broadcast_online_users(self, activity_id: str):
        users = self.get_online_users(activity_id)
        await self.broadcast_local(activity_id, {
            "type": "online_users",
            "users": users,
            "count": len(users)
        })

    async def broadcast_local(self, activity_id: str, message: dict, exclude_ws: WebSocket = None, exclude_user_id: str = None):
        """Broadcast to LOCAL WebSocket connections only (this worker)."""
        if activity_id not in self.active:
            return
        dead = []
        items = list(self.active[activity_id].items())
        for ws, info in items:
            if ws == exclude_ws:
                continue
            if exclude_user_id and info.get("user_id") == exclude_user_id:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active[activity_id].pop(ws, None)


manager = ConnectionManager()


# Handler invoked by event_bus when a REMOTE worker publishes an event for some activity.
# Forward it to local WS clients (excluding the original sender by user_id).
async def _on_remote_event(activity_id: str, payload: dict):
    msg_type = payload.get("type", "")
    if msg_type == "__presence_join__" or msg_type == "__presence_leave__":
        # Re-broadcast presence locally so users on this worker see all online users
        await manager.broadcast_online_users(activity_id)
        return
    exclude_uid = payload.get("user_id") or None
    await manager.broadcast_local(activity_id, payload, exclude_user_id=exclude_uid)


@ws_router.websocket("/ws/{activity_id}")
async def websocket_endpoint(ws: WebSocket, activity_id: str):
    user_id = ws.query_params.get("user_id", "unknown")
    user_name = ws.query_params.get("user_name", "Unknown")

    await manager.connect(ws, activity_id, user_id, user_name)
    logger.info(f"WS connected: {user_name} to activity {activity_id} (worker {event_bus.WORKER_ID})")

    # Server-initiated heartbeat — keeps WS alive through proxies (Cloudflare, nginx)
    # that may close idle connections after 30-60s.
    async def server_heartbeat():
        try:
            while True:
                await asyncio.sleep(25)
                try:
                    await ws.send_json({"type": "server_ping", "ts": datetime.now(timezone.utc).isoformat()})
                except Exception:
                    return
        except asyncio.CancelledError:
            return

    hb_task = asyncio.create_task(server_heartbeat())

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})

                elif msg_type == "lock":
                    # Local broadcast + remote publish
                    payload = {
                        "type": "asset_locked",
                        "asset_id": msg.get("asset_id"),
                        "user_id": user_id,
                        "user_name": user_name,
                    }
                    await manager.broadcast_local(activity_id, payload, exclude_ws=ws)
                    await event_bus.publish(db, activity_id, payload)

                elif msg_type == "unlock":
                    payload = {
                        "type": "asset_unlocked",
                        "asset_id": msg.get("asset_id"),
                        "user_id": user_id,
                        "user_name": user_name,
                    }
                    await manager.broadcast_local(activity_id, payload, exclude_ws=ws)
                    await event_bus.publish(db, activity_id, payload)

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(ws, activity_id)
        logger.info(f"WS disconnected: {user_name} from activity {activity_id}")
        await manager.broadcast_online_users(activity_id)
    except Exception as e:
        await manager.disconnect(ws, activity_id)
        logger.error(f"WS error: {e}")
        await manager.broadcast_online_users(activity_id)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


async def notify_asset_change(activity_id: str, event_type: str, asset_data: dict, user_name: str, user_id: str = None):
    """Called from asset CRUD routes to broadcast changes. Excludes the sender by user_id.

    Fanout strategy: local WS broadcast (immediate, in-process) + event_bus publish
    (async, reaches other workers/pods via tailable cursor)."""
    payload = {
        "type": event_type,
        "asset": asset_data,
        "user_name": user_name,
        "user_id": user_id or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_local(activity_id, payload, exclude_user_id=user_id)
    # Fire-and-forget remote publish — don't block the request on this
    asyncio.create_task(event_bus.publish(db, activity_id, payload))


# Helper to start the event bus tail loop (called from server.py startup)
async def start_event_bus():
    await event_bus.start(db, _on_remote_event)


async def stop_event_bus():
    await event_bus.stop()
