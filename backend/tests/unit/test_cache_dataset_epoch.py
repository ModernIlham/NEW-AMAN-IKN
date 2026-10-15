"""Cross-worker local cache partitions and late-fill fencing across restore."""
import asyncio
from cachetools import TTLCache
from mongomock_motor import AsyncMongoMockClient
import pytest

import shared_utils as cache
from dataset_epoch import rotate_generation


@pytest.fixture
def state(monkeypatch):
    database = AsyncMongoMockClient()["cache_dataset_epoch_test"]
    monkeypatch.setattr(cache, "db", database)
    monkeypatch.setattr(cache, "_redis_aktif", lambda: False)
    monkeypatch.setattr(cache, "_cache_epoch_state", (0.0, None, None))
    first = {name: TTLCache(maxsize=50, ttl=300) for name in cache._CACHE_LOCAL}
    second = {name: TTLCache(maxsize=50, ttl=300) for name in cache._CACHE_LOCAL}
    monkeypatch.setattr(cache, "_CACHE_LOCAL", first)
    return database, first, second


def test_two_workers_expire_old_epoch_and_late_fill_cannot_poison_new_dataset(state, monkeypatch):
    database, first, second = state
    async def scenario():
        await rotate_generation(database, "initial")
        first_query = asyncio.Event()
        late_fill = asyncio.Event()
        async def old_request():
            assert await cache.cache_get("stats", "scope") is None
            first_query.set()
            await late_fill.wait()
            await cache.cache_set("stats", "scope", {"dataset": "old"})
        request = asyncio.create_task(old_request())
        await first_query.wait()
        old_epoch_state = cache._cache_epoch_state
        monkeypatch.setattr(cache, "_CACHE_LOCAL", second)
        monkeypatch.setattr(cache, "_cache_epoch_state", (0.0, None, None))
        await cache.cache_get("stats", "scope")
        await cache.cache_set("stats", "scope", {"dataset": "old-worker-two"})
        second_epoch_state = cache._cache_epoch_state
        await rotate_generation(database, "restore_claim")
        # Restore's grace exceeds the per-worker epoch TTL.
        monkeypatch.setattr(cache, "_cache_epoch_state", (0.0, second_epoch_state[1], id(database)))
        assert await cache.cache_get("stats", "scope") is None
        await cache.cache_set("stats", "scope", {"dataset": "restored"})
        assert await cache.cache_get("stats", "scope") == {"dataset": "restored"}
        monkeypatch.setattr(cache, "_CACHE_LOCAL", first)
        monkeypatch.setattr(cache, "_cache_epoch_state", (0.0, old_epoch_state[1], id(database)))
        late_fill.set()
        await request
        assert await cache.cache_get("stats", "scope") is None
    asyncio.run(scenario())


def test_cache_set_without_captured_query_epoch_is_ignored(state):
    async def scenario():
        await cache.cache_set("stats", "unscoped", {"must": "not cache"})
        assert await cache.cache_get("stats", "unscoped") is None
    asyncio.run(scenario())


def test_database_epoch_failure_bypasses_old_cached_value_and_future_fill(state, monkeypatch):
    class Broken:
        async def find_one(self, *a, **k):
            raise IOError("epoch unavailable")
    class DB:
        dataset_state = Broken()
    async def scenario():
        await cache.cache_get("stats", "scope")
        await cache.cache_set("stats", "scope", {"old": True})
        monkeypatch.setattr(cache, "db", DB())
        assert await cache.cache_get("stats", "scope") is None
        await cache.cache_set("stats", "scope", {"unsafe": True})
        assert all(value != {"unsafe": True} for value in cache._CACHE_LOCAL["stats"].values())
    asyncio.run(scenario())
