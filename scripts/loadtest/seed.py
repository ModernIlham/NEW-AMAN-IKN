#!/usr/bin/env python3
"""Seed/cleanup nyata, hanya Mongo loopback dan DB aman_ci_* khusus run ini."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from fixture_target import mongo_loopback
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOQq8gDAAG8AQXYenKcAAAAAElFTkSuQmCC"


def safe_database(url, database):
    mongo_loopback(url)
    if not re.fullmatch(r"aman_ci_[a-zA-Z0-9_]{6,64}", database):
        raise ValueError("Database seed wajib aman_ci_* dengan identitas run")
    return database


def private_file(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(value)


def seed(args):
    from pymongo import MongoClient
    import bcrypt
    import jwt
    # Avoid importing root scripts/loadtest as backend.scripts, or runtime db.
    sys.path.insert(0, str(ROOT / "backend"))
    from scripts.synthdata import generate_assets
    args.mongo_url = mongo_loopback(args.mongo_url)
    safe_database(args.mongo_url, args.database)
    if not 10 <= args.count <= 100000 or not 1 <= args.accounts <= 100:
        raise ValueError("Seed: 10..100000 aset, 1..100 akun")
    rid = args.run_id or uuid.uuid4().hex
    if not re.fullmatch(r"[a-f0-9]{8,32}", rid):
        raise ValueError("run-id wajib 8..32 karakter hex")
    for output in [args.accounts_file, args.runtime_env_file, args.manifest]:
        if Path(output).exists():
            raise ValueError("Output seed sudah ada; gunakan nama run baru")
    prefix = "loadtest-" + rid
    now = datetime.now(timezone.utc).isoformat()
    secret = secrets.token_urlsafe(48)
    accounts, activities = [], []
    category_labels=set()
    with MongoClient(args.mongo_url, serverSelectionTimeoutMS=5000) as client:
        db = client[args.database]
        if any(db[name].estimated_document_count() for name in db.list_collection_names()):
            raise ValueError("Seed menolak database yang berisi data; gunakan database run baru")
        for index in range(3):
            db.satker.insert_one({"id":f"{prefix}-satker-{index}", "kode_satker":f"990{index:03}",
                "nama_satker":f"Satker sintetis {index}", "loadtest_run_id":rid})
        for index in range(5):
            aid = f"{prefix}-activity-{index}"
            activity = {"id":aid, "nama_kegiatan":f"Uji sintetis {index}",
                "kode_satker":f"990{index % 3:03}", "status_pengesahan":"draft", "created_at":now,
                "loadtest_run_id":rid}
            db.inventory_activities.insert_one(activity)
            activities.append({"id":aid,"kode_satker":activity["kode_satker"],"count":0})
        for start in range(0, args.count, 500):
            batch = generate_assets(min(500, args.count-start), seed=args.seed+start, profile=args.profile)
            for offset, asset in enumerate(batch):
                number = start + offset
                group = activities[number % 5]
                asset.update(id=f"{prefix}-asset-{number:06}", asset_code=f"{3_000_000_000+number:010}",
                    NUP="1", activity_id=group["id"], loadtest_run_id=rid, version=1,
                    created_at=now, updated_at=now, asset_name=f"Aset seri {number % 20:02}",
                    notes=f"[loadtest:{rid}] data sintetis")
                if args.profile!="edge":
                    # Form requires 32 hex; legacy generator REG123456 is not
                    # a clean smoke fixture. Edge profile remains explicit.
                    asset["kode_register"]=uuid.uuid5(uuid.NAMESPACE_URL,f"{rid}:{number}").hex
                if number % 7 == 0:
                    asset.pop("location", None)
                    asset.pop("purchase_date", None)
                if number % 10 == 0:
                    asset.update(photos=[PNG], thumbnail=PNG)
                if number % 5 == 0:
                    asset["document_checklist"] = [{"name":"STNK", "checked":True, "photos":[PNG], "documents":[]}]
                group["count"] += 1
                category_labels.add(asset["category"])
            db.assets.insert_many(batch)
        for index,label in enumerate(sorted(category_labels)):
            db.categories.insert_one({"id":f"{prefix}-category-{index}","label":label,
                "kode_aset":str(3_999_900_000+index),"loadtest_run_id":rid})
        for index in range(args.accounts):
            group = activities[index % 5]
            username = f"{prefix}-user-{index:03}"
            password = "Uji9-" + secrets.token_urlsafe(24)
            uid = f"{prefix}-user-id-{index:03}"
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            db.users.insert_one({"id":uid,"username":username,"password":hashed,"role":"admin",
                "is_active":True,"name":f"Penguji sintetis {index}","kode_satker":group["kode_satker"],
                "created_at":now,"loadtest_run_id":rid})
            token = jwt.encode({"user_id":uid,"username":username,"sesi_epoch":0,
                "exp":(datetime.now(timezone.utc)+timedelta(hours=12)).timestamp()}, secret, algorithm="HS256")
            accounts.append({"username":username,"password":password,"access_token":token,
                "activity_id":group["id"],"expected_count":group["count"],"kode_satker":group["kode_satker"]})
        actual = db.assets.count_documents({"loadtest_run_id":rid})
        if actual != args.count:
            raise ValueError("Verifikasi jumlah seed Mongo gagal")
        db["_loadtest_runs"].insert_one({"_id":rid,"count":actual,"created_at":now})
    manifest = {"schema_version":1,"run_id":rid,"database":args.database,"asset_count":actual,
        "seed":args.seed,"profile":args.profile,"satker_count":3,"activity_count":5,
        "accounts_count":len(accounts),"category_count":len(category_labels),"activities":activities,
        "media_profile":"10% tiny inline PNG, 20% checklist photo; bukan distribusi media produksi"}
    private_file(args.accounts_file, json.dumps({"run_id":rid,"accounts":accounts}, indent=2))
    private_file(args.runtime_env_file, f"MONGO_URL={args.mongo_url}\nDB_NAME={args.database}\nJWT_SECRET={secret}\n")
    private_file(args.manifest, json.dumps(manifest, indent=2))
    print(json.dumps({"database":args.database,"run_id":rid,"asset_count":actual,"accounts_count":len(accounts)}))


def cleanup(args):
    from pymongo import MongoClient
    args.mongo_url = mongo_loopback(args.mongo_url)
    safe_database(args.mongo_url, args.database)
    manifest = json.loads(Path(args.manifest).read_text())
    rid = manifest["run_id"]
    if manifest["database"] != args.database or not re.fullmatch(r"[a-f0-9]{8,32}", rid):
        raise ValueError("Manifest bukan milik database run ini")
    with MongoClient(args.mongo_url, serverSelectionTimeoutMS=5000) as client:
        db = client[args.database]
        marker = db["_loadtest_runs"].find_one({"_id":rid})
        if not marker:
            raise ValueError("Marker run tidak ditemukan; cleanup dibatalkan")
        usernames = [u["username"] for u in db.users.find({"loadtest_run_id":rid},{"username":1})]
        if db.unduhan.count_documents({"dibuat_oleh":{"$in":usernames},"status":{"$in":["queued","running"]}}):
            raise ValueError("Unduhan run masih aktif; tunggu selesai sebelum cleanup")
        activities = [a["id"] for a in manifest["activities"]]
        db.assets.delete_many({"$or":[{"loadtest_run_id":rid},{"notes":{"$regex":r"^\[loadtest:"+rid+r"\]"}}]})
        db.audit_logs.delete_many({"activity_id":{"$in":activities}})
        for category in db.categories.find({"loadtest_run_id":rid},{"label":1}):
            if not db.assets.count_documents({"category":category["label"]}):
                db.categories.delete_one({"_id":category["_id"],"loadtest_run_id":rid})
        for name in ["users","satker","inventory_activities"]:
            db[name].delete_many({"loadtest_run_id":rid})
        db["_loadtest_runs"].delete_one({"_id":rid})
    print(json.dumps({"run_id":rid,"cleanup":"scoped documents only; database tidak di-drop"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed","cleanup"])
    parser.add_argument("--mongo-url", default=os.environ.get("AMAN_LOADTEST_MONGO_URL", ""))
    parser.add_argument("--database", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--accounts", type=int, default=10)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", choices=["normal","mixed","edge"], default="mixed")
    parser.add_argument("--accounts-file", default="")
    parser.add_argument("--runtime-env-file", default="")
    args = parser.parse_args()
    if args.action == "seed" and (not args.accounts_file or not args.runtime_env_file):
        parser.error("seed membutuhkan --accounts-file dan --runtime-env-file privat")
    try:
        (seed if args.action == "seed" else cleanup)(args)
    except Exception as exc:
        # Do not print MongoClient exceptions, URLs, passwords, JWTs.
        if isinstance(exc, ValueError):
            parser.exit(2, str(exc) + "\n")
        parser.exit(2, "Seed/cleanup gagal; periksa layanan lokal dan output privat\n")


if __name__ == "__main__":
    main()
