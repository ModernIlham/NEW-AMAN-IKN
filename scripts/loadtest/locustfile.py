"""Beban terukur dengan pool akun, assertion domain, snapshot dan CSV nyata.

Jalankan melalui run.py untuk validasi target, preflight dataset server dan
ambang hasil. AMAN_USERNAME/AMAN_PASSWORD adalah fallback staging yang Wajib
diisi bila AMAN_ACCOUNTS_FILE tidak dipakai; tidak ada kredensial bawaan.
"""
import itertools
import json
import os
from pathlib import Path
import random
import sys
import time
import uuid

import locust
from locust import HttpUser, between, task
from locust.exception import StopUser

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import csv_artifact, json_object, list_result, load_pool, safe_host,transport_exception_kind

USERNAME = os.environ.get("AMAN_USERNAME", "").strip()
PASSWORD = os.environ.get("AMAN_PASSWORD", "")
POOL_PATH = os.environ.get("AMAN_ACCOUNTS_FILE", "")
ACTIVITY_ID = os.environ.get("AMAN_ACTIVITY_ID", "")
if not POOL_PATH and (not USERNAME or not PASSWORD):
    raise SystemExit("AMAN_USERNAME dan AMAN_PASSWORD wajib diisi dengan akun staging; atur secrets LOADTEST_USERNAME dan LOADTEST_PASSWORD atau AMAN_ACCOUNTS_FILE privat.")
# Keep import credential validation independent of network/Locust lifecycle.
# Runner requires scoped pool; legacy import-only validation may omit activity.
ACCOUNTS = load_pool(POOL_PATH) if POOL_PATH else [{"username":USERNAME,"password":PASSWORD,"activity_id":ACTIVITY_ID}]
ACCOUNT_CYCLE = itertools.cycle(ACCOUNTS)
THINK_MIN = float(os.environ.get("AMAN_THINK_MIN", "1"))
THINK_MAX = float(os.environ.get("AMAN_THINK_MAX", "3"))
if not 0 <= THINK_MIN <= THINK_MAX <= 30:
    raise SystemExit("AMAN_THINK_MIN/MAX harus 0..30 dan berurutan")
ENABLE_CRUD = os.environ.get("AMAN_ENABLE_CRUD", "0") == "1"
ENABLE_HEAVY = os.environ.get("AMAN_ENABLE_HEAVY", "0") == "1"
ENABLE_JOB = os.environ.get("AMAN_ENABLE_JOB", "0") == "1"
RUN_ID = os.environ.get("AMAN_LOADTEST_RUN_ID", "")
PROFILE = os.environ.get("AMAN_LOADTEST_PROFILE", "read")
MAX_RESPONSE = 64 * 1024 * 1024


def checked(response, validator):
    try:
        result = validator(response)
        response.success()
        return result
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        response.failure("Status/schema/domain respons tidak sesuai kontrak load test")
        return None


class SatkerUser(HttpUser):
    abstract = PROFILE == "auth"
    wait_time = between(THINK_MIN, THINK_MAX)

    def on_start(self):
        safe_host(self.host, os.environ.get("AMAN_STAGING_HOSTS", ""))
        self.account = next(ACCOUNT_CYCLE)
        self.activity = self.account.get("activity_id")
        if not self.activity:
            raise StopUser("activity_id wajib untuk snapshot/data scope")
        token = self.account.get("access_token")
        self.owned_assets = []
        if not token:
            with self.client.post("/api/auth/login", json={"username":self.account["username"],
                "password":self.account["password"]}, name="POST /auth/login", catch_response=True,timeout=30,allow_redirects=False) as response:
                result = checked(response, lambda r: json_object(r, ["access_token"]))
                token = result.get("access_token") if result else None
        if not token:
            raise StopUser("Login gagal")
        self.headers = {"Authorization":"Bearer " + token}
        if os.environ.get("AMAN_DRY_RUN_FIXTURE")=="1":
            # Smoke coverage must not depend on random task selection in 3s.
            self.daftar()
            self.statistik()
            self.analitik()
            self.snapshot()
            self.ekspor()

    @task(10)
    def daftar(self):
        with self.client.get("/api/assets", params={"activity_id":self.activity,"page_size":50,"page":random.choice([1,2]),"sort_by":"name_asc"},
                headers=self.headers, name="GET /assets list", catch_response=True,timeout=30,allow_redirects=False) as response:
            checked(response, lambda r:list_result(r, activity=self.activity))

    @task(4)
    def statistik(self):
        with self.client.get("/api/assets/stats", params={"activity_id":self.activity}, headers=self.headers,
                name="GET /assets stats", catch_response=True,timeout=30,allow_redirects=False) as response:
            checked(response, lambda r:json_object(r,["total_assets","total_value"]))

    @task(3)
    def analitik(self):
        with self.client.get("/api/assets/analytics", params={"activity_id":self.activity}, headers=self.headers,
                name="GET /assets analytics", catch_response=True,timeout=30,allow_redirects=False) as response:
            checked(response, lambda r:json_object(r,["by_category"]))

    @task(2)
    def snapshot(self):
        with self.client.get("/api/assets/offline-snapshot", params={"activity_id":self.activity,"limit":200},
                headers=self.headers, name="GET /assets offline-snapshot", catch_response=True,timeout=30,allow_redirects=False) as response:
            checked(response, lambda r:list_result(r,activity=self.activity,snapshot=True))

    @task(1)
    def crud(self):
        if not ENABLE_CRUD:
            return
        marker = "[loadtest:" + RUN_ID + "]"
        body = {"asset_code":"3999999999","NUP":str(uuid.uuid4().int%1_000_000_000+1),"asset_name":"Aset CRUD sintetis",
            "category":"Peralatan dan Mesin","activity_id":self.activity,"notes":marker}
        with self.client.post("/api/assets", json=body, headers=self.headers,
                name="POST /assets CRUD", catch_response=True,timeout=30,allow_redirects=False) as response:
            created = checked(response, lambda r:json_object(r,["id","asset_code","activity_id"]))
        if not created:
            return
        aid = created["id"]
        self.owned_assets.append(aid)
        with self.client.get("/api/assets/" + aid, headers=self.headers,
                name="GET /assets detail CRUD", catch_response=True,timeout=30,allow_redirects=False) as response:
            def validate(r):
                value = json_object(r,["id","notes"])
                if value["id"] != aid or value["notes"] != marker:
                    raise ValueError("Integritas create/read gagal")
                return value
            checked(response,validate)
        self.delete_owned(aid)

    def delete_owned(self, aid):
        with self.client.delete("/api/assets/"+aid, headers=self.headers,
                name="DELETE /assets CRUD", catch_response=True,timeout=30,allow_redirects=False) as response:
            result = checked(response,lambda r:json_object(r,["message"]))
        if result:
            self.owned_assets.remove(aid)

    @task(1)
    def ekspor(self):
        if not ENABLE_HEAVY:
            return
        with self.client.get("/api/export/csv", params={"activity_id":self.activity}, headers=self.headers,
                name="GET /export/csv actual artifact", catch_response=True,timeout=30,allow_redirects=False,stream=True) as response:
            checked(response,csv_artifact)
            # Streaming HTTP timing otherwise stops at headers; include the
            # complete validated artifact transfer in the reported latency.
            response.request_meta["response_time"]=(time.time()-response.request_meta["start_time"])*1000

    def on_stop(self):
        # Only IDs created by this virtual user. Seed cleanup is separately
        # guarded by database/run ID and handles interrupted clients.
        for aid in list(getattr(self,"owned_assets",[])):
            self.delete_owned(aid)


class AuthRateUser(HttpUser):
    """Profil rate limiter terpisah; 429 valid dihitung terpisah dari throughput."""
    abstract = PROFILE != "auth"
    wait_time = between(THINK_MIN, THINK_MAX)

    def on_start(self):
        safe_host(self.host, os.environ.get("AMAN_STAGING_HOSTS", ""))
        self.account=next(ACCOUNT_CYCLE)
        if not self.account.get("password"):
            raise StopUser("Profil auth memerlukan password akun sintetis")

    @task(1)
    def login_rate_limit(self):
        with self.client.post("/api/auth/login", json={"username":self.account["username"],"password":self.account["password"]},
                name="POST /auth/login rate-limit profile",catch_response=True,timeout=30,allow_redirects=False) as response:
            if response.status_code==429:
                try:
                    value=response.json()
                    if not isinstance(value,dict) or not (value.get("detail") or value.get("error")):
                        raise ValueError("429 schema")
                    response.success()
                except (ValueError,TypeError):
                    response.failure("Respons rate limiter tidak valid")
            else:
                checked(response,lambda r:json_object(r,["access_token"]))


if hasattr(locust, "events"):
    STATUS_COUNTS={}
    TRANSPORT_ERRORS={}

    @locust.events.request.add_listener
    def count_status(request_type,name,response=None,exception=None,**kwargs):
        status=getattr(response,"status_code",None)
        key=f"{request_type} {name} {status}"
        STATUS_COUNTS[key]=STATUS_COUNTS.get(key,0)+1
        if status==0:
            kind=transport_exception_kind(getattr(response,"error",None) or exception)
            if kind not in TRANSPORT_ERRORS and len(TRANSPORT_ERRORS)>=16:kind="OtherTransportError"
            TRANSPORT_ERRORS[kind]=TRANSPORT_ERRORS.get(kind,0)+1

    @locust.events.test_stop.add_listener
    def final_statistics(environment,**kwargs):
        path=os.environ.get("AMAN_FINAL_STATS_FILE")
        if not path:
            return
        total=environment.stats.total
        count=total.num_requests
        value={"requests":count,"failures":total.num_failures,"failure_ratio":total.fail_ratio,
            "p50_ms":total.get_response_time_percentile(0.5) or 0,
            "p95_ms":total.get_response_time_percentile(0.95) or 0,
            "p99_ms":total.get_response_time_percentile(0.99) or 0,
            "requests_per_second":total.total_rps,"status_counts":STATUS_COUNTS,
            "transport_errors":TRANSPORT_ERRORS,"max_response_time_ms":total.max_response_time,
            "routes":[{"method":entry.method,"name":entry.name,"requests":entry.num_requests,
                "failures":entry.num_failures,"p95_ms":entry.get_response_time_percentile(0.95) or 0}
                for entry in environment.stats.entries.values()]}
        Path(path).write_text(json.dumps(value,indent=2))

    @locust.events.init.add_listener
    def validate_direct_invocation(environment, **kwargs):
        safe_host(environment.host or "", os.environ.get("AMAN_STAGING_HOSTS", ""))
        if ENABLE_CRUD and not RUN_ID:
            raise ValueError("CRUD memerlukan AMAN_LOADTEST_RUN_ID")

    @locust.events.test_start.add_listener
    def stop_on_integrity_failure(environment, **kwargs):
        import gevent
        def monitor():
            while environment.runner and environment.runner.state not in {"stopped", "stopping", "cleanup"}:
                gevent.sleep(2)
                total = environment.stats.total
                if total.num_requests >= 20 and total.fail_ratio >= 0.01:
                    environment.process_exit_code = 1
                    environment.runner.quit()
                    return
        gevent.spawn(monitor)
