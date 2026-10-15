"""Operator-only bounded checklist backfill and read-only orphan inventory."""
import argparse
import asyncio
import json
from checklist_storage import backfill_asset, orphan_report


async def run(args):
    from db import db, fs_bucket, client
    try:
        if args.action == "audit-orphans":
            return await orphan_report(db, grace_days=args.grace_days,
                                       max_documents=args.max_documents, limit=args.limit)
        if not 1 <= len(args.asset_id) <= 25 or len(set(args.asset_id)) != len(args.asset_id):
            raise ValueError("Pilih 1–25 ID aset unik untuk satu batch")
        results = []
        for asset_id in args.asset_id:
            results.append(await backfill_asset(db, fs_bucket, asset_id, dry_run=not args.apply))
        return {"dry_run": not args.apply, "inline_retained": True, "results": results}
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    fill = sub.add_parser("backfill")
    fill.add_argument("--asset-id", action="append", required=True)
    fill.add_argument("--apply", action="store_true",
                      help="Tambahkan referensi dengan CAS; tidak pernah menghapus inline")
    audit = sub.add_parser("audit-orphans")
    audit.add_argument("--grace-days", type=int, default=7)
    audit.add_argument("--max-documents", type=int, default=10000)
    audit.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False))


if __name__ == "__main__":
    main()
