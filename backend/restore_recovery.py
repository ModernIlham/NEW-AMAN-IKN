"""Local operator recovery: python restore_recovery.py status|recover --job-id ID.

Run as the application Unix operator using existing backend/.env, after stopping
ALL backend workers and writer schedulers. No credentials are printed. This
path remains available even when restored users cannot authenticate in the UI.
"""
import argparse
import asyncio
import json


async def main(args):
    from routes.backup import restore_control_status, recover_restore
    if args.action == "status":
        print(json.dumps(await restore_control_status(), ensure_ascii=False, default=str, indent=2))
        return
    if args.action == "clear-writer-leases":
        if not args.workers_stopped:
            raise SystemExit("Hentikan semua worker dahulu; --workers-stopped wajib")
        from db import db
        result = await db.restore_write_leases.delete_many({})
        print(json.dumps({"cleared_writer_leases": result.deleted_count}))
        return
    if not args.workers_stopped or not args.job_id:
        raise SystemExit("recover memerlukan --workers-stopped dan --job-id; hentikan semua worker dan scheduler penulis dahulu")
    from db import db
    control = await restore_control_status()
    if control.get("job_id") != args.job_id:
        raise SystemExit("Job ID tidak sama dengan kontrol recovery aktif")
    if args.action == "abort-preflight":
        if control.get("destructive_started") is True or control.get("state") != "preparing":
            raise SystemExit("Hanya preparing sebelum destructive_started yang boleh dibatalkan tanpa restore")
        result = await db.restore_control.update_one(
            {"_id": "GLOBAL", "job_id": args.job_id, "state": "preparing", "destructive_started": False},
            {"$set": {"state": "aborted", "active": False, "aborted_by": "local-unix-operator"}})
        print(json.dumps({"aborted": bool(result.modified_count)}))
        return
    # Explicit --workers-stopped fences a crashed process before adopting its
    # durable journal. Never use heartbeat expiry alone as proof of safety.
    if control.get("state") in {"preparing", "restoring", "rolling_back"}:
        if not control.get("destructive_started"):
            raise SystemExit("Belum ada wipe; gunakan abort-preflight setelah worker dihentikan")
        await db.restore_control.update_one(
            {"_id": "GLOBAL", "job_id": args.job_id, "state": control["state"]},
            {"$set": {"state": "recovery_required", "active": True}})
    print(json.dumps(await recover_restore(args.job_id, "local-unix-operator"), ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "recover", "abort-preflight", "clear-writer-leases"])
    parser.add_argument("--job-id")
    parser.add_argument("--workers-stopped", action="store_true")
    asyncio.run(main(parser.parse_args()))
