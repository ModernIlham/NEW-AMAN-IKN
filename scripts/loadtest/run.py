#!/usr/bin/env python3
"""Runner berbatas: preflight nyata, Locust tetap, ambang dan laporan tanpa rahasia."""
import argparse
import contextlib
import csv
from datetime import datetime,timezone
import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from contracts import bounded_int, csv_artifact, duration_seconds, json_object, list_result, load_pool, safe_host

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def locust_command(host,users,rate,seconds,prefix):
    # Every HTTP task has a 30s timeout. Allow an in-flight request to finish
    # before stopping its greenlet, otherwise test shutdown creates status0.
    return [sys.executable,"-m","locust","-f",str(HERE/"locustfile.py"),"--host",host,
        "--headless","--users",str(users),"--spawn-rate",str(rate),"--run-time",str(seconds)+"s",
        "--stop-timeout","35","--exit-code-on-error","1","--csv",str(prefix),"--only-summary"]


def preflight(host, accounts, manifest, heavy=False, job=False):
    import requests
    expected = {a["id"]:a["count"] for a in manifest.get("activities",[])}
    if not expected or not manifest.get("run_id"):
        raise ValueError("Manifest wajib mencantumkan run_id dan jumlah aset per kegiatan server")
    report = []
    verified_snapshots={}
    for account in accounts:
        activity = account["activity_id"]
        count = expected.get(activity)
        if not isinstance(count,int) or count < 1:
            raise ValueError("Akun tidak memiliki kegiatan/dataset dalam manifest")
        token = account.get("access_token")
        session = requests.Session()
        if not token:
            response = session.post(host+"/api/auth/login",json={"username":account["username"],"password":account["password"]},timeout=15,allow_redirects=False)
            token = json_object(response,["access_token"])["access_token"]
            account["access_token"] = token
        session.headers["Authorization"] = "Bearer "+token
        def get(path, params=None):
            return session.get(host+path,params=params,timeout=30,allow_redirects=False,
                               stream=path.endswith("/file") or path=="/api/export/csv")
        value = list_result(get("/api/assets",{"activity_id":activity,"page_size":10}),expected=count,activity=activity)
        snapshot = list_result(get("/api/assets/offline-snapshot",{"activity_id":activity,"limit":200}),expected=count,activity=activity,snapshot=True)
        if not value["items"] or not snapshot["items"]:
            raise ValueError("Dataset server kosong meskipun total nonzero")
        if activity not in verified_snapshots:
            snapshot_ids={row["id"] for row in snapshot["items"]}
            cursor=snapshot.get("next_cursor")
            while cursor:
                next_page=list_result(get("/api/assets/offline-snapshot",{"activity_id":activity,"limit":200,"cursor":cursor}),expected=count,activity=activity,snapshot=True,cursor=True)
                new_ids={row["id"] for row in next_page["items"]}
                if snapshot_ids.intersection(new_ids) or not new_ids and len(snapshot_ids)<count:
                    raise ValueError("Snapshot cursor berulang atau terpotong")
                snapshot_ids.update(new_ids)
                if len(snapshot_ids)>count:
                    raise ValueError("Snapshot mengembalikan aset melebihi total")
                cursor=next_page.get("next_cursor")
            if len(snapshot_ids)!=count:
                raise ValueError("Snapshot lengkap tidak setara count dataset server")
            verified_snapshots[activity]=len(snapshot_ids)
        stats = json_object(get("/api/assets/stats",{"activity_id":activity}),["total_assets","total_value"])
        if stats["total_assets"] != count:
            raise ValueError("Statistik tidak setara jumlah aset server")
        json_object(get("/api/assets/analytics",{"activity_id":activity}),["by_category"])
        item = {"activity_id":activity,"server_total":value["total"],"snapshot_items":len(snapshot["items"]),
                "snapshot_verified_total":verified_snapshots[activity]}
        if heavy:
            item["csv"] = csv_artifact(get("/api/export/csv",{"activity_id":activity}),expected=count)
        if job:
            from urllib.parse import urlencode
            path="/export/csv?"+urlencode({"activity_id":activity})
            started=session.post(host+"/api/unduhan/mulai",json={"path":path,"nama_file":"loadtest.csv","label":"Loadtest "+manifest["run_id"]},timeout=30,allow_redirects=False)
            jid=json_object(started,["unduhan_id"])["unduhan_id"]
            done=False
            for _ in range(60):
                listing=json_object(get("/api/unduhan"),["items"])["items"]
                found=next((row for row in listing if row.get("unduhan_id")==jid),{})
                if found.get("status") == "done":
                    item["job_csv"]=csv_artifact(get("/api/unduhan/"+jid+"/file"),expected=count)
                    done=True
                    break
                if found.get("status") == "error":
                    raise ValueError("Job export nyata gagal")
                time.sleep(1)
            if not done:
                raise ValueError("Job export melewati batas 60 detik; job aktif tidak dibatalkan paksa")
            deleted=session.delete(host+"/api/unduhan/"+jid,timeout=30,allow_redirects=False)
            if deleted.status_code != 200:
                raise ValueError("Cleanup artifact job selesai gagal")
        report.append(item)
    return report


def evaluate_csv(prefix,max_error,p95_ms):
    path=Path(str(prefix)+"_stats.csv")
    if not path.exists():
        raise ValueError("Locust tidak menghasilkan statistik")
    rows=list(csv.DictReader(path.open()))
    total=next((r for r in rows if r.get("Name")=="Aggregated"),None)
    if not total or int(total["Request Count"]) == 0:
        raise ValueError("Tidak ada request terukur; load test gagal")
    requests=int(total["Request Count"])
    failures=int(total["Failure Count"])
    p95=float(total.get("95%") or 0)
    report={"requests":requests,"failures":failures,"failure_ratio":failures/requests,
        "p50_ms":float(total.get("50%") or 0),"p95_ms":p95,"p99_ms":float(total.get("99%") or 0),
        "requests_per_second":float(total.get("Requests/s") or 0),
        "routes":[{"method":r["Type"],"name":r["Name"],"requests":int(r["Request Count"]),
            "failures":int(r["Failure Count"]),"p95_ms":float(r.get("95%") or 0)} for r in rows if r["Name"]!="Aggregated"]}
    report["thresholds_passed"]=report["failure_ratio"] < max_error and p95 <= p95_ms
    return report


def watch_resources(proc,target_pid=None,maximum_seconds=1890):
    import psutil
    samples=[]
    target=psutil.Process(target_pid) if target_pid else None
    client=psutil.Process(proc.pid)
    hot_since=None
    stopped=None
    started=time.monotonic()
    while proc.poll() is None:
        try:
            actors=[client,*client.children(recursive=True)]
            server=[target,*target.children(recursive=True)] if target and target.is_running() else []
            cpu=psutil.cpu_percent(interval=1)
            free=psutil.disk_usage(str(ROOT)).free/psutil.disk_usage(str(ROOT)).total
            sample={"time":time.time(),"host_cpu_pct":cpu,"disk_free_ratio":free,
                "client_rss_bytes":sum(p.memory_info().rss for p in actors if p.is_running()),
                "server_rss_bytes":sum(p.memory_info().rss for p in server if p.is_running()) if target else None}
            io=psutil.disk_io_counters()
            sample["host_io_read_bytes"]=io.read_bytes if io else None
            sample["host_io_write_bytes"]=io.write_bytes if io else None
            samples.append(sample)
            if cpu>85:
                hot_since=hot_since or time.monotonic()
            else:
                hot_since=None
            if free<0.2 or hot_since and time.monotonic()-hot_since>=120 or time.monotonic()-started>maximum_seconds:
                stopped="disk_free<20%" if free<0.2 else "CPU>85% selama 2 menit" if hot_since and time.monotonic()-hot_since>=120 else "batas wall-clock terlampaui"
                proc.terminate()
                break
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            break
    return samples,stopped


def mongo_evidence(manifest):
    """Optional local server metrics; never infer server usage from client RSS."""
    url=os.environ.get("AMAN_LOADTEST_MONGO_URL")
    if not url:
        return {"collected":False,"reason":"Mongo loopback eksplisit tidak diset"}
    from seed import safe_database
    from pymongo import MongoClient
    database=manifest.get("database","")
    safe_database(url,database)
    with MongoClient(url,serverSelectionTimeoutMS=3000) as client:
        db=client[database]
        group=manifest["activities"][0]
        explained=db.command("explain",{"find":"assets","filter":{"activity_id":group["id"]},"sort":{"id":1},"limit":50},verbosity="executionStats")
        stats=explained["executionStats"]
        active=db.unduhan.count_documents({"status":{"$in":["queued","running"]}})
        oldest=db.unduhan.find_one({"status":{"$in":["queued","running"]}},sort=[("created_at",1)])
        created=(oldest or {}).get("created_at")
        age=None
        if created:
            stamp=datetime.fromisoformat(created.replace("Z","+00:00")) if isinstance(created,str) else created
            if stamp.tzinfo is None:
                stamp=stamp.replace(tzinfo=timezone.utc)
            age=max(0,(datetime.now(timezone.utc)-stamp).total_seconds())
        return {"collected":True,"query":"activity_id + id sort + limit50",
                "docs_examined":stats["totalDocsExamined"],"keys_examined":stats["totalKeysExamined"],
                "returned":stats["nReturned"],"active_download_jobs":active,"oldest_active_job_age_seconds":age,
                "index_count":len(list(db.assets.list_indexes()))}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host",default=os.environ.get("AMAN_TARGET_HOST",""))
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--users",default=os.environ.get("AMAN_LOADTEST_USERS","10"))
    p.add_argument("--spawn-rate",default=os.environ.get("AMAN_LOADTEST_SPAWN_RATE","1"))
    p.add_argument("--run-time",default=os.environ.get("AMAN_LOADTEST_RUN_TIME","5m"))
    p.add_argument("--profile",choices=["read","crud","heavy","auth"],default=os.environ.get("AMAN_LOADTEST_PROFILE","read"))
    p.add_argument("--manifest",default=os.environ.get("AMAN_DATASET_MANIFEST",""))
    p.add_argument("--accounts-file",default=os.environ.get("AMAN_ACCOUNTS_FILE",""))
    p.add_argument("--output",default="loadtest-result")
    p.add_argument("--p95-ms",type=float,default=2000)
    p.add_argument("--max-error",type=float,default=0.01)
    p.add_argument("--enable-job",action="store_true")
    args=p.parse_args(argv)
    try:
        users=bounded_int(args.users,1,50,"users")
        rate=float(args.spawn_rate)
        if not 0.1<=rate<=10:
            raise ValueError("spawn-rate harus 0.1..10/detik")
        seconds=duration_seconds(args.run_time)
        if not 0<args.max_error<=0.01 or not 1<=args.p95_ms<=30000:
            raise ValueError("Ambang harus max-error >0..1%, p95 1..30000 ms")
        with contextlib.ExitStack() as stack:
            temporary=Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="aman-loadtest-")))
            if args.dry_run:
                from fake_api import FixtureAPI
                fixture=stack.enter_context(FixtureAPI())
                host=fixture.host
                accounts=[{"username":"dry-run-tanpa-target","access_token":"fixture-only-token",
                    "activity_id":"fixture-only-activity","expected_count":1}]
                manifest={"run_id":"fixture-only","activities":[{"id":"fixture-only-activity","count":1}],"asset_count":1}
                users,rate,seconds=1,1,3
                heavy=True
                if args.profile in {"crud","auth"} or args.enable_job:
                    raise ValueError("Dry-run fixture mendukung smoke read+CSV; CRUD/auth/job wajib API staging nyata")
            else:
                host=safe_host(args.host,os.environ.get("AMAN_STAGING_HOSTS",""))
                accounts=load_pool(args.accounts_file,os.environ.get("AMAN_USERNAME",""),os.environ.get("AMAN_PASSWORD",""),os.environ.get("AMAN_ACTIVITY_ID",""))
                if users>len(accounts):
                    raise ValueError("Throughput memerlukan pool akun unik setidaknya sebanyak users")
                if not args.manifest:
                    raise ValueError("Manifest dataset server wajib; NDJSON lokal bukan bukti seed server")
                manifest=json.loads(Path(args.manifest).read_text())
                heavy=args.profile=="heavy"
            if len({a["username"] for a in accounts})!=len(accounts):
                raise ValueError("Pool akun mengandung username duplikat")
            if args.profile=="auth" and any(not account.get("password") for account in accounts):
                raise ValueError("Profil auth memerlukan password akun sintetis, bukan token saja")
            if args.enable_job and os.environ.get("AMAN_ENABLE_JOB")!="1":
                raise ValueError("Job workload memerlukan flag AMAN_ENABLE_JOB=1")
            if args.profile=="crud" and os.environ.get("AMAN_ENABLE_CRUD")!="1":
                raise ValueError("CRUD memerlukan flag eksplisit AMAN_ENABLE_CRUD=1")
            report=preflight(host,accounts,manifest,heavy=heavy,job=args.enable_job)
            pool=temporary/"accounts.json"
            pool.write_text(json.dumps({"accounts":accounts}))
            pool.chmod(0o600)
            prefix=Path(args.output).resolve()
            prefix.parent.mkdir(parents=True,exist_ok=True)
            env=dict(os.environ,AMAN_ACCOUNTS_FILE=str(pool),AMAN_LOADTEST_PROFILE=args.profile,
                AMAN_DRY_RUN_FIXTURE="1" if args.dry_run else "0",
                AMAN_FINAL_STATS_FILE=str(prefix)+".final.json",
                AMAN_LOADTEST_RUN_ID=manifest["run_id"],AMAN_ENABLE_HEAVY="1" if heavy else "0",
                AMAN_ENABLE_CRUD="1" if args.profile=="crud" else "0",AMAN_THINK_MIN="0.05" if args.dry_run else "1",
                AMAN_THINK_MAX="0.1" if args.dry_run else "3")
            command=locust_command(host,users,rate,seconds,prefix)
            with Path(str(prefix)+".log").open("w") as log:
                proc=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
                target_pid=int(os.environ["AMAN_TARGET_PID"]) if os.environ.get("AMAN_TARGET_PID") else None
                samples,stopped=watch_resources(proc,target_pid,seconds+90)
                try:
                    rc=proc.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc=proc.wait(timeout=10)
                    stopped="Locust tidak berhenti setelah terminate; dihentikan paksa"
            evaluate_csv(prefix,args.max_error,args.p95_ms)  # CSV tetap wajib sebagai artifact.
            metrics=json.loads(Path(str(prefix)+".final.json").read_text())
            if not metrics.get("requests"):
                raise ValueError("Statistik final tidak berisi request terukur")
            metrics["thresholds_passed"]=metrics["failure_ratio"]<args.max_error and metrics["p95_ms"]<=args.p95_ms
            postflight=preflight(host,accounts,manifest) if not args.dry_run else []
            sha=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
            dirty=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())
            public_manifest={key:manifest[key] for key in ["schema_version","run_id","database","asset_count","seed","profile","satker_count","activity_count","accounts_count","category_count","media_profile"] if key in manifest}
            public_manifest["activities"]=[{key:activity[key] for key in ["id","count","kode_satker"] if key in activity} for activity in manifest["activities"]]
            summary={"source_sha":sha,"working_tree_dirty":dirty,
                "harness_sha256":{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ["locustfile.py","contracts.py","run.py","seed.py"]},
                "python":platform.python_version(),"locust":importlib.metadata.version("locust"),
                "target":host,"dry_run_fixture":args.dry_run,"profile":args.profile,"users":users,"spawn_rate":rate,
                "duration_seconds":seconds,"dataset":public_manifest,"accounts_count":len(accounts),"preflight":report,
                "postflight":postflight,"metrics":metrics,"resource_samples":samples,"resource_stop":stopped,
                "cache_profile":os.environ.get("AMAN_CACHE_PROFILE","unspecified"),
                "mongo":mongo_evidence(manifest) if not args.dry_run else {"collected":False,"reason":"fixture HTTP"},
                "browser_request_count":None,"browser_measurement":"API harness tidak mengukur browser/WS/offline replay",
                "server_resource_measurement":"local target PID" if target_pid else "tidak diset; RSS client bukan RSS server",
                "capacity_claim":False}
            if args.dry_run:
                required={"/api/assets","/api/assets/stats","/api/assets/analytics","/api/assets/offline-snapshot","/api/export/csv"}
                if not required.issubset(fixture.requests):
                    raise ValueError("Dry-run tidak menjalankan semua endpoint kontrak")
                summary["fixture_routes"]=sorted(set(fixture.requests))
            Path(str(prefix)+".json").write_text(json.dumps(summary,indent=2))
            print(json.dumps({"summary":str(prefix)+".json","requests":metrics["requests"],"failure_ratio":metrics["failure_ratio"],"p95_ms":metrics["p95_ms"],"passed":rc==0 and metrics["thresholds_passed"] and not stopped}))
            return 0 if rc==0 and metrics["thresholds_passed"] and not stopped else 1
    except Exception as exc:
        # Response bodies, JWTs, passwords, and Mongo exceptions stay private.
        if isinstance(exc,(ValueError,FileNotFoundError)):
            print("Load test gagal: "+str(exc),file=sys.stderr)
        else:
            print("Load test gagal: endpoint/dependency tidak dapat diverifikasi",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
