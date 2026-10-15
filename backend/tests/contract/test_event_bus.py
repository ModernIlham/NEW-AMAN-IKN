"""Capped Mongo natural replay: lower IDs, processes, rollover and restart."""
import asyncio
import multiprocessing
import os
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


def _publisher(uri, database, collection, numbers):
    from urllib.parse import urlparse
    from bson import ObjectId
    from pymongo import MongoClient
    assert urlparse(uri).hostname in {"localhost", "127.0.0.1", "::1"}
    assert database.startswith("aman_ci_")
    client = MongoClient(uri)
    try:
        for number in numbers:
            client[database][collection].insert_one({
                "_id": ObjectId(f"66000000{number:016x}"), "activity_id": "room",
                "worker_id": "publisher-" + str(os.getpid()), "number": number,
                "type": "asset_updated"})
    finally:
        client.close()


async def _wait_until(predicate, timeout=8):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.02)


async def _collection(contract, monkeypatch, max_docs=1000):
    import event_bus
    name = "contract_events_" + uuid.uuid4().hex
    monkeypatch.setattr(event_bus, "COLLECTION_NAME", name)
    await contract.db.create_collection(name, capped=True, size=1024 * 1024, max=max_docs)
    return name, contract.db[name]


async def _stop(task):
    task.cancel()
    try:
        # Shield keeps this test's deadline cancellation separate from the
        # tail cancellation under test. A swallowed cancellation must fail
        # within eight seconds, never hang the session or pass on a second one.
        async with asyncio.timeout(8):
            await asyncio.shield(task)
    except asyncio.CancelledError:
        assert task.cancelled()
        return
    finally:
        if not task.done():
            task.cancel()
    raise AssertionError("Event tail returned without propagating cancellation")


async def test_two_publishers_with_lower_same_second_ids_are_delivered(contract, monkeypatch):
    import event_bus
    from bson import ObjectId
    name, collection = await _collection(contract, monkeypatch)
    await collection.insert_one({"_id": ObjectId("66000000ffffffffffffffff"),
                                  "activity_id": "room", "worker_id": "old"})
    ready, received = asyncio.Event(), []
    original = event_bus._id_mulai
    async def anchored(db):
        token = await original(db)
        ready.set()
        return token
    async def handler(room, payload):
        received.append((room, payload))
    monkeypatch.setattr(event_bus, "_id_mulai", anchored)
    task = asyncio.create_task(event_bus._tail_loop(contract.db, handler))
    ctx = multiprocessing.get_context("spawn")
    processes = [ctx.Process(target=_publisher, args=(os.environ["AMAN_CONTRACT_MONGO_URL"],
                    contract.database, name, numbers)) for numbers in ((5, 3), (4, 2))]
    try:
        await asyncio.wait_for(ready.wait(), 5)
        for process in processes:
            process.start()
        for process in processes:
            await asyncio.to_thread(process.join, 15)
            assert not process.is_alive() and process.exitcode == 0
        await _wait_until(lambda: len([p for _, p in received if "number" in p]) == 4)
        assert sorted(p["number"] for _, p in received if "number" in p) == [2, 3, 4, 5]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 5)
        await _stop(task)
        await collection.drop()


async def test_actual_cursor_restart_replays_without_duplicates(contract, monkeypatch):
    import event_bus
    from bson import ObjectId
    name, collection = await _collection(contract, monkeypatch)
    cursors, received, ready = [], [], asyncio.Event()
    await collection.insert_one({"_id": ObjectId("660000000000000000000100"), "worker_id": "old"})
    class WrappedCollection:
        async def find_one(self, *args, **kwargs):
            value = await collection.find_one(*args, **kwargs)
            ready.set()
            return value
        def find(self, *args, **kwargs):
            cursor = collection.find(*args, **kwargs)
            cursors.append(cursor)
            return cursor
    async def handler(room, payload):
        received.append(payload)
        if payload.get("number") == 9:
            await cursors[-1].close()
    task = asyncio.create_task(event_bus._tail_loop({name: WrappedCollection()}, handler))
    try:
        await ready.wait()
        for number in (9, 8):
            await collection.insert_one({"_id": ObjectId(f"66000000{number:016x}"),
                                          "worker_id": "remote", "activity_id": "room",
                                          "type": "asset_updated", "number": number})
            if number == 9:
                # Motor may retain buffered documents after close(). Prove a
                # real replacement cursor exists before publishing the next
                # event, rather than racing delivery from that first batch.
                await _wait_until(lambda: len(cursors) >= 2)
        await _wait_until(lambda: len([p for p in received if "number" in p]) == 2)
        assert [p["number"] for p in received if "number" in p] == [9, 8]
        assert len(cursors) >= 2
    finally:
        await _stop(task)
        await collection.drop()


async def test_rollover_while_slow_handler_requires_resync(contract, monkeypatch):
    import event_bus
    from bson import ObjectId
    name, collection = await _collection(contract, monkeypatch, max_docs=5)
    await collection.insert_one({"_id": ObjectId("660000000000000000000100"), "worker_id": "old"})
    ready, entered, release, received = asyncio.Event(), asyncio.Event(), asyncio.Event(), []
    original = event_bus._id_mulai
    async def anchored(db):
        value = await original(db)
        ready.set()
        return value
    async def handler(room, payload):
        received.append((room, payload))
        if payload.get("number") == 1:
            entered.set()
            await release.wait()
    monkeypatch.setattr(event_bus, "_id_mulai", anchored)
    task = asyncio.create_task(event_bus._tail_loop(contract.db, handler))
    try:
        await ready.wait()
        await collection.insert_one({"_id": ObjectId(), "worker_id": "remote", "activity_id": "room", "number": 1})
        await asyncio.wait_for(entered.wait(), 5)
        await collection.insert_many([{"_id": ObjectId(), "worker_id": "remote", "activity_id": "room", "number": n}
                                      for n in range(2, 40)])
        release.set()
        await _wait_until(lambda: any(payload.get("type") == "resync_required" for _, payload in received))
        assert any(room == "*" and payload["reason"] in {"ring_gap", "cursor_reconnected"}
                   for room, payload in received if payload.get("type") == "resync_required")
    finally:
        release.set()
        await _stop(task)
        await collection.drop()


async def test_idle_real_tail_keeps_one_cursor_instead_of_repeated_find(contract, monkeypatch):
    import event_bus
    from bson import ObjectId
    name, collection = await _collection(contract, monkeypatch)
    await collection.insert_one({"_id": ObjectId(), "worker_id": "old"})
    finds = []
    class WrappedCollection:
        async def find_one(self, *args, **kwargs):
            return await collection.find_one(*args, **kwargs)
        def find(self, *args, **kwargs):
            finds.append(1)
            return collection.find(*args, **kwargs)
    async def handler(*args):
        pass
    task = asyncio.create_task(event_bus._tail_loop({name: WrappedCollection()}, handler))
    try:
        await asyncio.sleep(0.6)
        assert len(finds) == 1
    finally:
        await _stop(task)
        await collection.drop()
