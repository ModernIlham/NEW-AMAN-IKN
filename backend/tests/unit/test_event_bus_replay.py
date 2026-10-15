import asyncio
from collections import deque

import pytest
from bson import ObjectId

import event_bus


@pytest.mark.asyncio
async def test_delivery_completion_in_same_turn_cannot_consume_external_cancellation():
    entered = asyncio.Event()
    release = asyncio.get_running_loop().create_future()
    async def handler(*_):
        entered.set()
        await release
    task = asyncio.create_task(event_bus._deliver(handler, "room", {}))
    await entered.wait()
    # With Python 3.11 wait_for, the child completes before the parent processes
    # its cancellation and wait_for returns its result, losing cancellation.
    # Direct await under asyncio.timeout must preserve that external signal.
    release.set_result(None)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_cursor_close_has_a_deadline_during_tail_cancellation(monkeypatch):
    monkeypatch.setattr(event_bus, "CURSOR_CLOSE_TIMEOUT_DETIK", 0.01)
    closing = asyncio.Event()
    class HungClose(Cursor):
        async def close(self):
            closing.set()
            await asyncio.Event().wait()
    cursor = HungClose([], wait=0.1)
    async def handler(*_):
        pass
    task = asyncio.create_task(event_bus._tail_loop({event_bus.COLLECTION_NAME: Collection(cursor)}, handler))
    await asyncio.sleep(0.01)
    task.cancel()
    done, pending = await asyncio.wait({task}, timeout=1)
    if pending:
        task.cancel()
    assert done == {task} and closing.is_set()
    assert task.cancelled()


def doc(number, worker="other"):
    return {"_id": ObjectId(f"66000000{number:016x}"), "worker_id": worker,
            "activity_id": "room", "type": "asset_updated", "number": number}


def test_restart_replays_natural_order_once_even_with_decreasing_object_ids():
    replay = event_bus.RingReplay(doc(100)["_id"])
    replay.begin_cursor()
    assert replay.accept(doc(100)) == (False, False)
    assert replay.accept(doc(90)) == (True, False)
    replay.begin_cursor()
    assert replay.accept(doc(100)) == (False, False)
    assert replay.accept(doc(90)) == (False, False)
    assert replay.accept(doc(80)) == (True, False)
    assert not replay.end_batch()


def test_rollover_requires_resync_and_dedup_is_bounded(monkeypatch):
    monkeypatch.setattr(event_bus, "DEDUP_MAX", 4)
    replay = event_bus.RingReplay()
    for n in range(10):
        assert replay.accept(doc(n))[0]
    assert len(replay.seen) == 4
    replay.begin_cursor()
    assert replay.accept(doc(50)) == (True, True)  # previous anchor rolled out
    assert replay.accept(doc(49)) == (True, False)
    assert replay.accept(doc(50)) == (False, False)


def test_bootstrap_missing_anchor_resyncs_instead_of_silent_skip():
    replay = event_bus.RingReplay(doc(100)["_id"])
    replay.begin_cursor()
    assert replay.accept(doc(1)) == (False, False)
    assert replay.end_batch() is True
    replay.begin_cursor()
    assert replay.accept(doc(1)) == (False, False)
    assert replay.accept(doc(0)) == (True, False)


class Cursor:
    def __init__(self, values, *, alive=True, wait=0):
        self.values = deque(values)
        self.alive = alive
        self.wait = wait
        self.reads = 0
        self.closed = False
    def max_await_time_ms(self, value):
        return self
    def __aiter__(self):
        return self
    async def __anext__(self):
        self.reads += 1
        if self.values:
            value = self.values.popleft()
            if isinstance(value, Exception):
                raise value
            return value
        await asyncio.sleep(self.wait)
        raise StopAsyncIteration
    async def close(self):
        self.closed = True


class Collection:
    def __init__(self, cursor):
        self.cursor, self.finds = cursor, 0
    async def find_one(self, *args, **kwargs):
        return None
    def find(self, *args, **kwargs):
        self.finds += 1
        return self.cursor


@pytest.mark.asyncio
async def test_alive_cursor_is_reused_and_fast_empty_batches_are_throttled():
    cursor = Cursor([], alive=True)
    collection = Collection(cursor)
    received = []
    async def handler(activity_id, payload):
        received.append(payload)
    task = asyncio.create_task(event_bus._tail_loop({event_bus.COLLECTION_NAME: collection}, handler))
    await asyncio.sleep(0.35)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert collection.finds == 1
    assert cursor.reads <= 5 and cursor.closed


@pytest.mark.asyncio
async def test_own_worker_events_are_deduped_but_not_delivered():
    cursor = Cursor([doc(10, event_bus.WORKER_ID), doc(9), doc(9)], wait=0.1)
    collection, received = Collection(cursor), []
    async def handler(activity_id, payload):
        received.append((activity_id, payload))
    task = asyncio.create_task(event_bus._tail_loop({event_bus.COLLECTION_NAME: collection}, handler))
    await asyncio.sleep(0.03)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert received == [("room", {"type": "asset_updated", "number": 9})]


@pytest.mark.asyncio
async def test_failed_publish_emits_local_and_recovery_resync(monkeypatch):
    received, inserted = [], []
    class FailedOnce:
        async def insert_one(self, row):
            if not inserted:
                inserted.append("failed")
                raise RuntimeError("temporary Mongo failure")
            inserted.append(row)
    async def handler(activity_id, payload):
        received.append((activity_id, payload))
    monkeypatch.setattr(event_bus, "_local_handler", handler)
    monkeypatch.setattr(event_bus, "_publish_gap_pending", False)
    db = {event_bus.COLLECTION_NAME: FailedOnce()}
    assert not await event_bus.publish(db, "room", {"type": "asset_updated"})
    assert received[0][0] == "*" and received[0][1]["type"] == "resync_required"
    assert await event_bus.publish(db, "room", {"type": "asset_updated"})
    assert any(isinstance(row, dict) and row.get("reason") == "publish_failed" for row in inserted)
    assert event_bus._publish_gap_pending is False


@pytest.mark.asyncio
async def test_slow_handler_has_deadline_then_receives_resync(monkeypatch):
    received = []
    monkeypatch.setattr(event_bus, "HANDLER_TIMEOUT_DETIK", 0.01)
    cursor = Cursor([doc(1)], wait=0.1)
    async def handler(activity_id, payload):
        if payload.get("type") != "resync_required":
            await asyncio.Event().wait()
        received.append((activity_id, payload))
    task = asyncio.create_task(event_bus._tail_loop({event_bus.COLLECTION_NAME: Collection(cursor)}, handler))
    await asyncio.sleep(0.04)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert received[0][0] == "room" and received[0][1]["reason"] == "handler_failed"


@pytest.mark.asyncio
async def test_periodic_reconciliation_covers_unpublished_events_after_process_crash(monkeypatch):
    received = []
    monkeypatch.setattr(event_bus, "RESYNC_INTERVAL_DETIK", 0.01)
    async def handler(activity_id, payload):
        received.append((activity_id, payload))
    task = asyncio.create_task(event_bus._tail_loop(
        {event_bus.COLLECTION_NAME: Collection(Cursor([], wait=0.01))}, handler))
    await asyncio.sleep(0.04)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert received[0][0] == "*" and received[0][1]["reason"] == "periodic_reconcile"


@pytest.mark.asyncio
async def test_global_resync_expands_only_to_existing_local_rooms(monkeypatch):
    import routes.websocket as websocket
    from types import SimpleNamespace
    sent = []
    async def broadcast(room, payload):
        sent.append((room, payload))
    monkeypatch.setattr(websocket, "manager", SimpleNamespace(
        active={"allowed-a": {}, "allowed-b": {}}, broadcast_local=broadcast))
    await websocket._on_remote_event("*", {"type": "resync_required", "reason": "ring_gap"})
    assert [room for room, _ in sent] == ["allowed-a", "allowed-b"]
    assert all(payload == {"type": "resync_required", "reason": "ring_gap"} for _, payload in sent)


@pytest.mark.asyncio
async def test_unavailable_capped_storage_uses_reconcile_without_regular_inserts(monkeypatch):
    received = []
    async def unavailable(db):
        return False
    async def handler(room, payload):
        received.append(payload)
    monkeypatch.setattr(event_bus, "ensure_capped_collection", unavailable)
    monkeypatch.setattr(event_bus, "_tail_task", None)
    monkeypatch.setattr(event_bus, "_bus_available", True)
    monkeypatch.setattr(event_bus, "_local_handler", None)
    monkeypatch.setattr(event_bus, "_publish_gap_pending", False)
    try:
        await event_bus.start({}, handler)
        await asyncio.sleep(0.01)
        assert received and received[0]["reason"] == "event_bus_unavailable"
        assert not await event_bus.publish({}, "room", {"type": "asset_updated"})
    finally:
        await event_bus.stop()
