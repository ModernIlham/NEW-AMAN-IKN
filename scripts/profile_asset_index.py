#!/usr/bin/env python3
"""Measure one index on an owned loopback synthetic dataset, including writes.

Requires explicit --allow-local-index-change; can drop/recreate ONLY the named
candidate in this synthetic DB. No production origin or ordinary DB is accepted.
"""
import argparse
import copy
import json
from pathlib import Path
import time
import uuid

from profile_asset_reads import validate_target, summarize_explain
from fixture_target import mongo_loopback

INDEX = "asset_activity_name_id"
KEYS = [("activity_id", 1), ("asset_name", 1), ("id", 1)]


def benchmark(args):
    if not args.allow_local_index_change:
        raise ValueError("Gunakan --allow-local-index-change hanya untuk dataset sintetis lokal")
    from pymongo import MongoClient
    manifest = json.loads(Path(args.manifest).read_text())
    validate_target(args.mongo_url, args.database, manifest)
    args.mongo_url = mongo_loopback(args.mongo_url)
    with MongoClient(args.mongo_url, serverSelectionTimeoutMS=5000) as client:
        db = client[args.database]
        marker = db["_loadtest_runs"].find_one({"_id": manifest["run_id"]})
        if not marker or marker.get("count") != manifest["asset_count"]:
            raise ValueError("Marker run tidak cocok")
        if db.assets.count_documents({"loadtest_run_id": manifest["run_id"]}) != manifest["asset_count"]:
            raise ValueError("Jumlah dataset tidak cocok")
        activity = manifest["activities"][0]["id"]
        pipeline = [{"$match": {"activity_id": activity}}, {"$sort": {"asset_name": 1, "id": 1}},
                    {"$limit": 50}, {"$project": {"_id": 0, "id": 1, "asset_name": 1}}]
        samples = list(db.assets.find({"loadtest_run_id": manifest["run_id"]}).limit(min(500, manifest["asset_count"])))
        probe = "indexprobe-" + uuid.uuid4().hex
        rows = []
        for index, source in enumerate(samples):
            row = copy.deepcopy(source)
            row.pop("_id", None)
            row.update(id=probe + str(index), asset_code=probe + str(index), NUP="1",
                       activity_id=probe, loadtest_run_id=probe)
            rows.append(row)
        ids = [row["id"] for row in rows]
        def measure(label):
            queries, writes, deletes = [], [], []
            for _ in range(7):
                start = time.perf_counter()
                list(db.assets.aggregate(pipeline, maxTimeMS=30000))
                queries.append((time.perf_counter() - start) * 1000)
            for _ in range(5):
                start = time.perf_counter()
                db.assets.insert_many(copy.deepcopy(rows))
                writes.append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                result = db.assets.delete_many({"id": {"$in": ids}})
                deletes.append((time.perf_counter() - start) * 1000)
                assert result.deleted_count == len(rows)
            explanation = db.command("explain", {"aggregate": "assets", "pipeline": pipeline, "cursor": {}}, verbosity="executionStats")
            stats = db.command("collStats", "assets")
            return {"label": label, "query_samples_ms": queries, "write_batch_rows": len(rows),
                    "insert_samples_ms": writes, "delete_samples_ms": deletes,
                    "index_count": stats["nindexes"], "candidate_index_bytes": stats["indexSizes"].get(INDEX, 0),
                    "total_index_bytes": stats["totalIndexSize"], **summarize_explain(explanation)}
        try:
            if INDEX in db.assets.index_information():
                db.assets.drop_index(INDEX)
            before = measure("without_candidate")
            start = time.perf_counter()
            db.assets.create_index(KEYS, name=INDEX)
            build_ms = (time.perf_counter() - start) * 1000
            after = measure("with_candidate")
            assert db.assets.count_documents({"loadtest_run_id": manifest["run_id"]}) == manifest["asset_count"]
            output = {"dataset_rows": manifest["asset_count"], "scope_rows": db.assets.count_documents({"activity_id": activity}),
                      "candidate": {"name": INDEX, "keys": KEYS, "build_ms": build_ms}, "before": before, "after": after,
                      "limits": "Warm local synthetic shared-host samples; writes are bulk batches, not API/production capacity; candidate remains installed"}
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
            print(json.dumps(output, indent=2))
        finally:
            db.assets.delete_many({"id": {"$in": ids}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-url", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-local-index-change", action="store_true")
    benchmark(parser.parse_args())


if __name__ == "__main__":
    main()
