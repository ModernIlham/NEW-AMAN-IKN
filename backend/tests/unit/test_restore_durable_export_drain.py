import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.backup as backup


@pytest.mark.parametrize("job,lease,blocked", [
    ({"status": "queued", "done": False}, False, True),
    ({"worker_protocol": "export_v1", "status": "queued", "done": False}, False, False),
    ({"worker_protocol": "export_v1", "status": "running", "done": False}, False, True),
    ({"worker_protocol": "export_v1", "status": "queued", "done": False}, True, True),
])
def test_drain_excludes_only_unclaimed_immutable_export_queue(monkeypatch, job, lease, blocked):
    database = AsyncMongoMockClient()["unit_restore_export_drain"]
    monkeypatch.setattr(backup, "db", database)
    async def scenario():
        await database.background_jobs.insert_one(job)
        if lease:
            await database.restore_write_leases.insert_one({"_id": "live-writer"})
        if blocked:
            with pytest.raises(RuntimeError, match="belum selesai"):
                await backup._wait_writer_drain(timeout=.001)
        else:
            await backup._wait_writer_drain(timeout=.001)
    asyncio.run(scenario())
