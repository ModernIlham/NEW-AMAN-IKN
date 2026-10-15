"""Seed CLI mengisi Mongo lokal dan cleanup mempertahankan data run lain."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
import uuid

import bcrypt
from pymongo import MongoClient
import pytest

pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[3]


def test_seed_real_mongo_private_pool_and_run_scoped_cleanup(tmp_path):
    uri=os.environ.get("AMAN_CONTRACT_MONGO_URL","")
    if urlparse(uri).hostname not in {"127.0.0.1","localhost","::1"}:
        pytest.fail("Kontrak seed membutuhkan Mongo loopback eksplisit")
    name="aman_ci_seed_"+uuid.uuid4().hex
    files={key:tmp_path/(key+".json") for key in ["manifest","accounts","runtime"]}
    command=[sys.executable,str(ROOT/"scripts/loadtest/seed.py")]
    common=["--mongo-url",uri,"--database",name,"--manifest",str(files["manifest"])]
    client=MongoClient(uri,serverSelectionTimeoutMS=3000)
    db=client[name]
    try:
        result=subprocess.run(command+["seed",*common,"--count","20","--accounts","2",
            "--accounts-file",str(files["accounts"]),"--runtime-env-file",str(files["runtime"])],capture_output=True,text=True,timeout=40)
        assert result.returncode==0,result.stderr
        manifest=json.loads(files["manifest"].read_text())
        accounts=json.loads(files["accounts"].read_text())["accounts"]
        rid=manifest["run_id"]
        assert manifest["asset_count"]==db.assets.count_documents({"loadtest_run_id":rid})==20
        assert db.satker.count_documents({})==3 and db.inventory_activities.count_documents({})==5
        assert {a["count"] for a in manifest["activities"]}=={4}
        assert all(re.fullmatch(r"[0-9]{10}",row["asset_code"]) for row in db.assets.find({"loadtest_run_id":rid},{"asset_code":1}))
        assert all(re.fullmatch(r"[a-f0-9]{32}",row["kode_register"]) for row in db.assets.find({"loadtest_run_id":rid},{"kode_register":1}))
        labels={row["label"] for row in db.categories.find({"loadtest_run_id":rid})}
        assert {row["category"] for row in db.assets.find({"loadtest_run_id":rid})}.issubset(labels)
        assert files["accounts"].stat().st_mode&0o777==0o600
        assert files["runtime"].stat().st_mode&0o777==0o600
        assert "password" not in manifest and accounts[0]["password"] not in result.stdout+result.stderr
        user=db.users.find_one({"username":accounts[0]["username"]})
        assert bcrypt.checkpw(accounts[0]["password"].encode(),user["password"].encode())
        retained_category=next(iter(labels))
        db.assets.insert_one({"id":"foreign-sentinel","notes":"another run","category":retained_category})
        result=subprocess.run(command+["cleanup",*common],capture_output=True,text=True,timeout=20)
        assert result.returncode==0,result.stderr
        assert db.assets.count_documents({"loadtest_run_id":rid})==0
        assert db.assets.count_documents({"id":"foreign-sentinel"})==1
        assert db.users.count_documents({"loadtest_run_id":rid})==0
        assert db.categories.count_documents({"loadtest_run_id":rid,"label":retained_category})==1
        assert db.categories.count_documents({"loadtest_run_id":rid,"label":{"$ne":retained_category}})==0
    finally:
        if db.name==name and db.name.startswith("aman_ci_seed_"):
            client.drop_database(name)
        client.close()
