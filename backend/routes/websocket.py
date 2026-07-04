"""WebSocket routes for real-time notifications and sync.

Cross-worker fanout via event_bus (capped collection + tailable cursor) so that
multiple uvicorn workers / pods share notifications without Redis."""
import json
import time
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import jwt

import event_bus
from db import db
from auth_utils import JWT_SECRET, JWT_ALGORITHM

logger = logging.getLogger(__name__)
ws_router = APIRouter()

# Presence snapshots from remote workers expire after this many seconds — a
# crashed/restarted worker stops publishing and its users drop off naturally.
PRESENCE_SNAPSHOT_TTL = 60
# How often each worker re-publishes its local presence (convergence after
# restarts/reconnects; must be < PRESENCE_SNAPSHOT_TTL).
PRESENCE_SNAPSHOT_INTERVAL = 30

# App-specific WebSocket close code for missing/invalid/expired token
# (4000-4999 is the range reserved for applications by RFC 6455).
WS_CLOSE_UNAUTHORIZED = 4401


class ConnectionManager:
    """Manages WebSocket connections per activity (in-memory, per worker process)."""

    def __init__(self):
        # { activity_id: { ws: { "user_id": str, "user_name": str } } }
        self.active: Dict[str, Dict[WebSocket, dict]] = {}
        # Latest presence snapshot per REMOTE worker:
        # { activity_id: { worker_id: { "users": [...], "received_at": float } } }
        self.remote_presence: Dict[str, Dict[str, dict]] = {}

    async def connect(self, ws: WebSocket, activity_id: str, user_id: str, user_name: str):
        await ws.accept()
        if activity_id not in self.active:
            self.active[activity_id] = {}
        self.active[activity_id][ws] = {"user_id": user_id, "user_name": user_name}
        # Broadcast online users (locally — presence is per-process; multi-worker
        # presence aggregation is handled via snapshot events on the bus)
        await self.broadcast_online_users(activity_id)
        # Share this worker's full local presence with other workers
        await self.publish_presence_snapshot(activity_id)

    async def disconnect(self, ws: WebSocket, activity_id: str):
        info = None
        if activity_id in self.active:
            info = self.active[activity_id].pop(ws, None)
            if not self.active[activity_id]:
                del self.active[activity_id]
        if info:
            # Publish the updated (possibly empty) local snapshot so other
            # workers drop this user unless they still see it elsewhere
            await self.publish_presence_snapshot(activity_id)

    def get_local_users(self, activity_id: str):
        """Users connected to THIS worker only (deduped by user_id)."""
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

    def get_online_users(self, activity_id: str):
        """Union of local users + live presence snapshots from remote workers,
        deduped by user_id. Stale snapshots (> TTL) are pruned at read time."""
        users = self.get_local_users(activity_id)
        seen = {u["user_id"] for u in users}
        now = time.time()
        snaps = self.remote_presence.get(activity_id, {})
        for wid in list(snaps.keys()):
            snap = snaps[wid]
            if now - snap.get("received_at", 0) > PRESENCE_SNAPSHOT_TTL:
                del snaps[wid]
                continue
            for u in snap.get("users", []):
                uid = u.get("user_id")
                if uid and uid not in seen:
                    seen.add(uid)
                    users.append({"user_id": uid, "user_name": u.get("user_name", "")})
        if not snaps and activity_id in self.remote_presence:
            del self.remote_presence[activity_id]
        return users

    def update_remote_presence(self, activity_id: str, worker_id: Optional[str], users: list) -> bool:
        """Store the latest snapshot from a remote worker. Returns True when the
        worker was not known for this activity (first contact — caller may want
        to answer with its own snapshot so both sides converge quickly)."""
        if not worker_id or worker_id == event_bus.WORKER_ID:
            return False
        snaps = self.remote_presence.setdefault(activity_id, {})
        is_new = worker_id not in snaps
        if users:
            snaps[worker_id] = {"users": users, "received_at": time.time()}
        else:
            snaps.pop(worker_id, None)
        if not snaps:
            self.remote_presence.pop(activity_id, None)
        return is_new

    async def publish_presence_snapshot(self, activity_id: str):
        """Publish this worker's FULL local presence for an activity (not the
        union — remote users must never be echoed back onto the bus)."""
        await event_bus.publish(db, activity_id, {
            "type": "__presence_snapshot__",
            "worker": event_bus.WORKER_ID,
            "users": self.get_local_users(activity_id),
            "snapshot_ts": datetime.now(timezone.utc).isoformat(),
        })

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
    if msg_type == "__presence_snapshot__":
        # Store the remote worker's snapshot and re-broadcast the union locally.
        first_contact = manager.update_remote_presence(
            activity_id, payload.get("worker"), payload.get("users") or []
        )
        # First contact with that worker for this activity: answer with our own
        # snapshot so it also learns OUR users immediately (instead of waiting
        # up to PRESENCE_SNAPSHOT_INTERVAL). Bounded: once both sides know each
        # other, no further answers are triggered.
        if first_contact and manager.get_local_users(activity_id):
            await manager.publish_presence_snapshot(activity_id)
        await manager.broadcast_online_users(activity_id)
        return
    if msg_type == "__presence_join__" or msg_type == "__presence_leave__":
        # Legacy presence events (older workers during rolling deploys) — we
        # can't attribute them to a worker snapshot, just refresh the local view
        await manager.broadcast_online_users(activity_id)
        return
    exclude_uid = payload.get("user_id") or None
    await manager.broadcast_local(activity_id, payload, exclude_user_id=exclude_uid)


def _decode_ws_token(token: str) -> Optional[dict]:
    """Validate the JWT from the WS query string. Returns the payload or None.

    Deliberately a light jwt.decode (same secret/algorithm as auth_utils) — no
    DB lookup, so a burst of reconnecting clients can't hammer MongoDB."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:  # covers expired, malformed, bad signature
        return None
    if not payload.get("user_id"):
        return None
    return payload


@ws_router.websocket("/ws/{activity_id}")
async def websocket_endpoint(ws: WebSocket, activity_id: str):
    # Authenticate BEFORE registering the connection. Identity comes from the
    # token payload — client-supplied user_id/user_name query params are ignored.
    token_payload = _decode_ws_token(ws.query_params.get("token", ""))
    if token_payload is None:
        # Accept-then-close so the browser actually receives our app close code
        # (rejecting the handshake would surface as an opaque 1006 instead).
        await ws.accept()
        await ws.close(code=WS_CLOSE_UNAUTHORIZED, reason="Token tidak valid atau kedaluwarsa")
        logger.info(f"WS rejected (invalid/missing token) for activity {activity_id}")
        return
    user_id = token_payload["user_id"]
    user_name = token_payload.get("username") or "Unknown"

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


# Periodic presence re-publish: keeps remote snapshots fresh (they expire after
# PRESENCE_SNAPSHOT_TTL) and lets restarted/reconnected workers converge without
# waiting for the next join/leave.
_presence_task: Optional[asyncio.Task] = None


async def _presence_snapshot_loop():
    while True:
        await asyncio.sleep(PRESENCE_SNAPSHOT_INTERVAL)
        try:
            for activity_id in list(manager.active.keys()):
                await manager.publish_presence_snapshot(activity_id)
        except Exception as e:
            logger.warning(f"[presence] periodic snapshot failed: {e}")


# Helper to start the event bus tail loop (called from server.py startup)
async def start_event_bus():
    global _presence_task
    await event_bus.start(db, _on_remote_event)
    if _presence_task is None or _presence_task.done():
        _presence_task = asyncio.create_task(_presence_snapshot_loop())


async def stop_event_bus():
    global _presence_task
    if _presence_task:
        _presence_task.cancel()
        try:
            await _presence_task
        except asyncio.CancelledError:
            pass
        _presence_task = None
    await event_bus.stop()
