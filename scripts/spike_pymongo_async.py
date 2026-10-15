#!/usr/bin/env python3
"""Isolated PyMongo Async compatibility probe; does not switch the app driver."""
import argparse
import asyncio
import inspect
import json
from pathlib import Path
import sys
import uuid


async def probe(args):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from fixture_target import mongo_loopback
    args.mongo_url = mongo_loopback(args.mongo_url)
    from bson import Decimal128, ObjectId
    from gridfs import AsyncGridFSBucket
    from pymongo import AsyncMongoClient, CursorType
    from pymongo.errors import DuplicateKeyError
    import pymongo

    name = "aman_ci_async_spike_" + uuid.uuid4().hex
    client = AsyncMongoClient(args.mongo_url, serverSelectionTimeoutMS=2000,
                              connectTimeoutMS=2000, socketTimeoutMS=3000)
    db = client[name]
    result = {"pymongo": pymongo.version, "production_driver_changed": False, "checks": {}}
    try:
        await db.command("ping")
        await db.rows.create_index("owner", unique=True, partialFilterExpression={"active": True})
        await db.rows.insert_one({"_id": "first", "owner": "fixture", "active": True,
                                  "version": 1, "value": Decimal128("100000000000000000.01")})
        try:
            await db.rows.insert_one({"_id": "second", "owner": "fixture", "active": True})
        except DuplicateKeyError:
            result["checks"]["partial_unique_index"] = True
        assert result["checks"].get("partial_unique_index")
        first, second = await asyncio.gather(*[
            db.rows.update_one({"_id": "first", "version": 1}, {"$inc": {"version": 1}})
            for _ in range(2)])
        assert first.matched_count + second.matched_count == 1
        result["checks"]["cas"] = True
        rows = await db.rows.find({}).sort("_id", 1).limit(3).to_list(length=3)
        assert len(rows) == 1 and str(rows[0]["value"].to_decimal()) == "100000000000000000.01"
        result["checks"]["async_cursor_decimal_codec"] = True
        aggregate = db.rows.aggregate([{"$count": "count"}])
        result["aggregate_requires_await"] = inspect.isawaitable(aggregate)
        aggregate = await aggregate if inspect.isawaitable(aggregate) else aggregate
        assert (await aggregate.to_list(length=1))[0]["count"] == 1
        bucket = AsyncGridFSBucket(db)
        fid = ObjectId()
        upload = bucket.open_upload_stream_with_id(fid, "fixture.bin")
        result["gridfs_open_upload_requires_await"] = inspect.isawaitable(upload)
        upload = await upload if inspect.isawaitable(upload) else upload
        for _ in range(8):
            await upload.write(b"fixture" * 65536)
        await upload.close()
        output = await bucket.open_download_stream(fid)
        size, chunks = 0, 0
        while data := await output.readchunk():
            size += len(data)
            chunks += 1
        assert size == 8 * 7 * 65536 and chunks > 1
        result["checks"]["gridfs_chunk_stream"] = {"bytes": size, "chunks": chunks}
        partial_id = ObjectId()
        partial = bucket.open_upload_stream_with_id(partial_id, "partial.bin")
        partial = await partial if inspect.isawaitable(partial) else partial
        await partial.write(b"partial" * 65536)
        await partial.abort()
        assert await db["fs.files"].count_documents({"_id": partial_id}) == 0
        assert await db["fs.chunks"].count_documents({"files_id": partial_id}) == 0
        result["checks"]["gridfs_abort"] = True
        await db.create_collection("events", capped=True, size=1024 * 1024, max=1000)
        await db.events.insert_one({"_id": ObjectId(), "number": 1})
        tail = db.events.find({}, cursor_type=CursorType.TAILABLE_AWAIT).max_await_time_ms(2000)
        assert (await anext(tail))["number"] == 1
        timed_out = False
        try:
            async with asyncio.timeout(0.02):
                await anext(tail)
        except TimeoutError:
            timed_out = True
        finally:
            await tail.close()
        assert timed_out
        result["checks"]["tailable_timeout_cancellation"] = True
        return result
    finally:
        assert name.startswith("aman_ci_async_spike_")
        await client.drop_database(name)
        close = client.close()
        result["client_close_requires_await"] = inspect.isawaitable(close)
        if inspect.isawaitable(close):
            await close


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-url", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = asyncio.run(probe(args))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
