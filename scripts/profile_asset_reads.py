#!/usr/bin/env python3
"""Read-only query profiles of a verified local synthetic AMAN dataset.

No credential files, raw asset values, query terms or explain documents are
written to the report. Pipeline expressions are taken from repository handlers.
"""
import argparse
import ast
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fixture_target import mongo_loopback


def validate_target(url, database, manifest):
    mongo_loopback(url)
    if "?" in url:
        raise ValueError("Profile tidak menerima options dalam URL")
    from re import fullmatch
    if not fullmatch(r"aman_ci_[A-Za-z0-9_]{6,64}", database):
        raise ValueError("Profile wajib database sintetis aman_ci_*")
    if manifest.get("database") != database or not fullmatch(r"[a-f0-9]{8,32}", manifest.get("run_id", "")):
        raise ValueError("Manifest bukan milik target profile")
    if not 10 <= manifest.get("asset_count", 0) <= 100000:
        raise ValueError("Dataset profile harus10..100000aset")


def handler_expression(path, function, expression, bindings):
    """Evaluate a pure pipeline constructor from trusted checked-out code."""
    tree = ast.parse(Path(path).read_text())
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == function)
    value = None
    for node in ast.walk(handler):
        if expression == "pipeline" and isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "pipeline" for target in node.targets):
            value = node.value
            break
        if expression == "aggregate" and isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "aggregate" and node.args:
            value = node.args[0]
            break
    if value is None:
        raise ValueError(f"Pipeline handler tidak ditemukan: {function}")
    return eval(compile(ast.Expression(value), str(path), "eval"), {"__builtins__": {}}, bindings)


def summarize_explain(value):
    result = {"docs_examined": 0, "keys_examined": 0, "indexes": [], "in_memory_sort": False, "used_disk": False}
    indexes = set()
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, item in node.items():
                if key in {"rejectedPlans", "allPlansExecution", "command", "serverInfo", "serverParameters"}:
                    continue
                if key == "executionStats" and isinstance(item, dict):
                    result["docs_examined"] += item.get("totalDocsExamined", 0)
                    result["keys_examined"] += item.get("totalKeysExamined", 0)
                if key == "indexName":
                    indexes.add(str(item))
                if (key == "stage" and item == "SORT") or key == "$sort":
                    result["in_memory_sort"] = True
                if key == "usedDisk" and item:
                    result["used_disk"] = True
                walk(item)
    walk(value)
    result["indexes"] = sorted(indexes)
    return result


def percentile(values, ratio):
    return sorted(values)[max(0, math.ceil(len(values) * ratio) - 1)]


def profile(args):
    from pymongo import MongoClient
    manifest = json.loads(Path(args.manifest).read_text())
    validate_target(args.mongo_url, args.database, manifest)
    args.mongo_url = mongo_loopback(args.mongo_url)
    if not 3 <= args.samples <= 15:
        raise ValueError("Samples wajib3..15")
    os.environ.update(MONGO_URL=args.mongo_url, DB_NAME=args.database, JWT_SECRET="test-profile-no-auth-server")
    sys.path.insert(0, str(ROOT / "backend"))
    from asset_sorting import tahapan_urutan_aset, ekspresi_harga
    from routes.assets import LIST_PROJECTION, build_asset_search_query
    from db import client as runtime_client
    with MongoClient(args.mongo_url, serverSelectionTimeoutMS=5000) as client:
        # limits.MongoDBStorage lazily constructs a client AND creates its own
        # indexes in __del__. No limiter is executed by this read-only profiler;
        # bind that unused storage to our already-open client to prevent I/O at
        # interpreter shutdown. Do not change the application's limiter config.
        from shared_utils import limiter
        limiter_storage = limiter._storage
        if hasattr(limiter_storage, "_storage") and limiter_storage._storage is None:
            limiter_storage._storage = client
        database = client[args.database]
        run = database["_loadtest_runs"].find_one({"_id": manifest["run_id"]})
        if not run or run.get("count") != manifest["asset_count"]:
            raise ValueError("Marker seed/count tidak sah")
        if database.assets.count_documents({"loadtest_run_id": manifest["run_id"]}) != manifest["asset_count"]:
            raise ValueError("Dataset server tidak sama dengan manifest")
        activity = manifest["activities"][0]["id"]
        scope = {"activity_id": activity}
        count = database.assets.count_documents(scope)
        first = database.assets.find_one(scope, {"_id": 0, "category": 1, "condition": 1}) or {}
        source = ROOT / "backend/routes/assets.py"
        cases = {}
        def listing(label, sort_by="newest", query=None, skip=0):
            cases[label] = handler_expression(source, "get_assets", "pipeline", {
                "read_query": query or scope, "sort_by": sort_by, "skip": skip, "fetch_limit": 50,
                "projection": LIST_PROJECTION, "tahapan_urutan_aset": tahapan_urutan_aset,
            })
        listing("list_first")
        listing("list_deep", skip=max(0, count - 50))
        listing("list_name", "name_asc")
        listing("list_price", "price_asc")
        listing("list_substring", query=build_asset_search_query(activity_id=activity, search="seri"))
        listing("list_multi_filter", query=build_asset_search_query(activity_id=activity,
                category=first.get("category", ""), condition=first.get("condition", "")))
        cases["count_exact"] = [{"$match": scope}, {"$count": "n"}]
        cases["stats"] = handler_expression(source, "get_assets_stats", "pipeline", {"query": scope, "ekspresi_harga": ekspresi_harga})
        cases["analytics"] = handler_expression(source, "get_assets_analytics", "aggregate", {"query": scope,
            "price_convert": ekspresi_harga()})
        cases["groups"] = handler_expression(ROOT / "backend/routes/batch.py", "get_asset_groups", "pipeline", {
            "match": scope, "lewati": 0, "ukuran": 100})
        cases["snapshot_first"] = [{"$match": scope}, {"$sort": {"id": 1}}, {"$limit": 1000}, {"$project": LIST_PROJECTION}]
        anchor = database.assets.find(scope, {"_id": 0, "id": 1, "created_at": 1}).sort([("created_at", -1), ("id", 1)]).skip(max(0, count - 51)).limit(1)
        row = next(anchor, None)
        if row and isinstance(row.get("created_at"), str):
            keyset = {"$and": [scope, {"$or": [{"created_at": {"$lt": row["created_at"]}},
                {"created_at": row["created_at"], "id": {"$gt": row["id"]}}]}]}
            listing("candidate_created_id_cursor", query=keyset)
        profile_rows = []
        for name, pipeline in cases.items():
            explanation = database.command("explain", {"aggregate": "assets", "pipeline": pipeline, "cursor": {}}, verbosity="executionStats")
            elapsed = []
            result_count = 0
            for _ in range(args.samples):
                started = time.perf_counter()
                rows = list(database.assets.aggregate(pipeline, maxTimeMS=30000))
                elapsed.append((time.perf_counter() - started) * 1000)
                result_count = len(rows)
            profile_rows.append({"name": name, "returned": result_count, "samples": args.samples,
                "p50_ms": round(percentile(elapsed, .5), 3), "p95_ms": round(percentile(elapsed, .95), 3),
                **summarize_explain(explanation)})
        stats = database.command("collStats", "assets")
        media_shape = list(database.assets.aggregate([
            {"$match": {"loadtest_run_id": manifest["run_id"]}},
            {"$project": {"bytes": {"$bsonSize": "$$ROOT"}, "checklist_bytes": {
                "$bsonSize": {"items": {"$ifNull": ["$document_checklist", []]}}}}},
            {"$facet": {"summary": [{"$group": {"_id": None, "count": {"$sum": 1},
                "min": {"$min": "$bytes"}, "max": {"$max": "$bytes"}, "avg": {"$avg": "$bytes"},
                "checklist_max": {"$max": "$checklist_bytes"}, "checklist_avg": {"$avg": "$checklist_bytes"}}}],
                "histogram": [{"$bucket": {"groupBy": "$bytes", "boundaries": [0, 1024, 4096, 16384, 65536,
                    262144, 1048576, 4194304, 12582912, 16777216], "default": "over_16MiB", "output": {"count": {"$sum": 1}}}}]}}
        ]))[0]
        media_shape["summary"] = [{k: v for k, v in row.items() if k != "_id"} for row in media_shape["summary"]]
        media_shape["histogram"] = [{"lower_bound_bytes": row["_id"], "count": row["count"]} for row in media_shape["histogram"]]
        output = {"schema_version": 1, "synthetic_bson_shape": media_shape, "dataset_rows": manifest["asset_count"], "scope_rows": count,
            "cache": "warm_repeated_queries_no_restart", "source": "checked_out_handler_pipeline",
            "index_count": stats["nindexes"], "index_bytes": stats["totalIndexSize"],
            "data_bytes": stats["size"], "queries": profile_rows,
            "limits": "Local synthetic query latency, not API/concurrency/production capacity; no write benchmark"}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
        print(json.dumps(output, indent=2))
    runtime_client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-url", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--output", required=True)
    profile(parser.parse_args())


if __name__ == "__main__":
    main()
