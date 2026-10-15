"""Read-only migration audit: python backend/audit_unduhan_claims.py.

Exit 2 means drain admission and wait for active legacy jobs before deploying
mixed writers. This command never changes, cancels or deletes an existing job.
"""
import asyncio
import json

from db import client, db


async def audit(collection=None):
    collection = db.unduhan if collection is None else collection
    active = legacy = terminal_locks = 0
    owners = {}
    async for row in collection.find(
            {"$or": [{"status": {"$in": ["queued", "running"]}}, {"active_lock": True}]},
            {"_id": 0, "dibuat_oleh": 1, "status": 1, "active_lock": 1}):
        if row.get("status") in ("queued", "running"):
            active += 1
            legacy += row.get("active_lock") is not True
            owner = row.get("dibuat_oleh") or ""
            owners[owner] = owners.get(owner, 0) + 1
        else:
            terminal_locks += 1
    indexes = await collection.index_information()
    index = indexes.get("unduhan_satu_aktif_per_owner") or {}
    return {
        "active": active, "legacy_active": legacy,
        "duplicate_active_owners": sum(n > 1 for n in owners.values()),
        "terminal_locks": terminal_locks,
        "claim_index_ready": bool(index.get("unique") and
                                  index.get("partialFilterExpression") == {"active_lock": True}),
        "safe_to_deploy_without_active_legacy": legacy == 0 and not terminal_locks
            and all(n == 1 for n in owners.values()),
    }


async def main():
    try:
        result = await audit()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["safe_to_deploy_without_active_legacy"] else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
