"""Dua proses AMAN nyata membuktikan health mengidentifikasi worker saat import."""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid

from pymongo import MongoClient
import pytest
import requests

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_real_aman_old_worker_keeps_source_sha_after_checkout_and_new_worker_changes(tmp_path):
    mongo=os.environ.get("AMAN_CONTRACT_MONGO_URL","")
    target=urlsplit(mongo)
    assert target.scheme=="mongodb" and target.hostname in {"localhost","127.0.0.1","::1"}, "Mongo kontrak wajib loopback"
    database="aman_ci_release_"+uuid.uuid4().hex
    client=MongoClient(mongo,serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    app=tmp_path/"app"
    shutil.copytree(ROOT/"backend",app/"backend",ignore=shutil.ignore_patterns(
        "tests","venv","__pycache__","*.pyc",".env*","uploads","*.log"))
    (app/".gitignore").write_text("backend/.env\n**/__pycache__/\n")
    def git(*args):
        return subprocess.check_output(["git","-C",str(app),*args],text=True,stderr=subprocess.DEVNULL).strip()
    git("init","-q");git("config","user.email","fixture@example.test");git("config","user.name","Release fixture")
    git("add",".");git("commit","-qm","AMAN release A")
    a=git("rev-parse","HEAD")
    sentinel=app/"backend/.env"
    sentinel.write_bytes(b"ENV_SENTINEL=isolated-private-do-not-log\n")
    sentinel.chmod(0o600)
    environment=dict(os.environ,MONGO_URL=mongo,DB_NAME=database,JWT_SECRET=secrets.token_urlsafe(48),
        ADMIN_BOOTSTRAP_TOKEN=secrets.token_urlsafe(48),REDIS_URL="",MEILI_URL="",MEILI_MASTER_KEY="",
        TINIFY_API_KEY="",RESEND_API_KEY="",AMAN_OBSERVABILITY_ENABLED="0",AMAN_EXPORT_WORKER_ENABLED="0",
        # Known Git must win over a stale env hint.
        AMAN_RELEASE_SHA="0"*40)
    processes=[]
    logs=[]
    def start(label):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1",0));port=listener.getsockname()[1]
        log=(tmp_path/("server-"+label+".log")).open("w")
        logs.append(log)
        process=subprocess.Popen([sys.executable,"-m","uvicorn","server:app","--host","127.0.0.1",
                                  "--port",str(port),"--no-access-log"],cwd=app/"backend",env=environment,
                                 stdout=log,stderr=subprocess.STDOUT)
        processes.append(process)
        host="http://127.0.0.1:"+str(port)
        for _ in range(120):
            assert process.poll() is None,"Isolated AMAN process failed; inspect private fixture log"
            try:
                if requests.get(host+"/api/health/deep",timeout=1).status_code==200:
                    return host
            except requests.RequestException:
                pass
            time.sleep(.25)
        pytest.fail("Isolated AMAN startup timeout")
    def identity(host,sha):
        for path,field in [("/health","status"),("/api/health","ok")]:
            response=requests.get(host+path,timeout=3)
            assert response.status_code==200
            assert response.json()["release_sha"]==sha
            assert response.json()[field] in [True,"ok"]
    try:
        host_a=start("a")
        identity(host_a,a)
        (app/"release-change").write_text("AMAN release B")
        git("add","release-change");git("commit","-qm","AMAN release B")
        b=git("rev-parse","HEAD")
        assert a!=b
        identity(host_a,a)
        host_b=start("b")
        identity(host_b,b)
        identity(host_a,a)
        assert sentinel.read_bytes()==b"ENV_SENTINEL=isolated-private-do-not-log\n"
        assert sentinel.stat().st_mode&0o777==0o600
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        for log in logs:log.close()
        # Only this generated, loopback database can be dropped.
        if database.startswith("aman_ci_release_"):client.drop_database(database)
        client.close()
