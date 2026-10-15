#!/usr/bin/env python3
"""Single-VPS budget activation. Execute only through the CI-approved ops workflow.

No account/token is created. Authenticated export smoke is a separate operation;
--rollback-journal restores the exact private configuration after a failed smoke.
"""
from __future__ import annotations
import argparse
import configparser
from datetime import datetime,timedelta,timezone
import fcntl
import hashlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import zipfile

AMAN_EXPORT_BUDGET_PROTOCOL=1
TERMINAL=["completed","rolled_back","aborted"]
JOB_TERMINAL=["done","error","completed","failed","cancelled","canceled","dismissed","downloaded"]
KEYS=("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED","AMAN_EXPORT_GLOBAL_SLOTS","AMAN_EXPORT_SATKER_SLOTS","AMAN_EXPORT_LOCK_DIR")
EXPECTED_CAPABILITY={"enabled":True,"ok":True,"slots":1,"satker_slots":1,"error_category":None}
FORBIDDEN_FEATURES=("AMAN_EXPORT_DURABLE_XLSX_ENABLED","AMAN_CHECKLIST_GRIDFS_WRITE")


def digest(data):return hashlib.sha256(data).hexdigest()

def owned(path,directory=False,private=False):
    path=Path(path);metadata=path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or metadata.st_uid!=os.geteuid() or metadata.st_mode&0o022:
        raise ValueError("Unsafe ownership/type/permission")
    if directory and not stat.S_ISDIR(metadata.st_mode) or not directory and not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Unexpected filesystem type")
    if private and metadata.st_mode&0o077:raise ValueError("Private state must be mode0700/0600")
    return metadata


def sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def atomic_bytes(path,data,mode=0o600):
    temporary=path.with_name("."+path.name+"."+uuid.uuid4().hex)
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
        with os.fdopen(fd,"wb") as output:output.write(data);output.flush();os.fsync(output.fileno())
        os.replace(temporary,path);sync_directory(path.parent)
    finally:temporary.unlink(missing_ok=True)


def save(journal,state):atomic_bytes(journal/"state.json",json.dumps(state,sort_keys=True).encode())


def patched_environment(original,lock_dir):
    text=original.decode("utf-8")
    if "\0" in text:raise ValueError("NUL in environment")
    path=str(lock_dir)
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+",path):raise ValueError("Unsafe lock directory")
    suffix=("\n" if original and not original.endswith(b"\n") else "")
    suffix+="# AMAN bounded export budget; original bytes retained in private operation journal\n"
    suffix+="AMAN_EXPORT_GLOBAL_BUDGET_ENABLED=1\nAMAN_EXPORT_GLOBAL_SLOTS=1\nAMAN_EXPORT_SATKER_SLOTS=1\nAMAN_EXPORT_LOCK_DIR="+path+"\n"
    return original+suffix.encode()


def lock_directory(path,create=False,expected_configuration=True):
    path=Path(path)
    if not path.is_absolute() or ".." in path.parts:raise ValueError("Lock directory must be absolute")
    # Every existing ancestor is checked; never follow an operations symlink.
    for parent in reversed((path,*path.parents)):
        if parent==Path("/"):continue
        if parent.is_symlink():raise ValueError("Lock path may not contain symlinks")
        if not parent.exists():
            if create:parent.mkdir(mode=0o700)
            else:continue
        metadata=parent.lstat()
        trusted_sticky=(parent==Path("/tmp") and metadata.st_mode&stat.S_ISVTX and parent!=path)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or metadata.st_mode&0o022 and not trusted_sticky:
            raise ValueError("Unsafe lock directory ancestor")
        if metadata.st_uid not in {0,os.geteuid()} and not trusted_sticky:raise ValueError("Unexpected ancestor owner")
    if not path.exists():return
    owned(path,True,True)
    entries=list(path.iterdir())
    if len(entries)>1024:raise ValueError("Unbounded lock inventory")
    for item in entries:
        owned(item,False)
        if item.name=="configuration.json":
            if item.stat().st_size>4096:raise ValueError("Unbounded physical configuration")
            config=json.loads(item.read_text())
            if expected_configuration and config!={"schema":1,"capacity":1,"satker_slots":1}:
                raise ValueError("Existing physical configuration is not1/1; operator drain/reconfiguration required")
            if not expected_configuration and (set(config)!={"schema","capacity","satker_slots"} or config["schema"]!=1 or
                    not isinstance(config["capacity"],int) or not isinstance(config["satker_slots"],int) or
                    not 1<=config["satker_slots"]<=config["capacity"]<=8):raise ValueError("Invalid previous physical configuration")
        elif item.suffix==".lock":
            fd=os.open(item,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:os.close(fd)
        else:raise ValueError("Unexpected file in physical lock directory")


def activate(runtime,journal,*,rollback=False):
    """Transactional configuration change; injected runtime enables fault tests."""
    runtime.failure_phase="preflight"
    journal=Path(journal)
    if rollback:
        owned(journal,True,True);state=json.loads((journal/"state.json").read_text())
        owned(journal/"state.json",False,True)
        owned(journal/"backend.env",False,True)
        original=(journal/"backend.env").read_bytes()
        if digest(original)!=state["original_sha256"]:raise ValueError("Original environment snapshot changed")
        if str(runtime.lock_dir)!=state["lock_dir"]:raise ValueError("Physical lock directory differs from journal")
        if digest(runtime.environment_bytes())!=state["new_sha256"]:raise ValueError("Active configuration changed; refuse automatic overwrite")
        runtime.preflight(expected_capability=EXPECTED_CAPABILITY)
    else:
        original,metadata,old_capability=runtime.preflight()
        journal.mkdir(mode=0o700)
        owned(journal,True,True)
        atomic_bytes(journal/"backend.env",original)
        state={"protocol":1,"source_sha":runtime.sha,"lock_dir":str(runtime.lock_dir),"original_sha256":digest(original),
               "original_mode":stat.S_IMODE(metadata.st_mode),"old_capability":old_capability,
               "new_sha256":digest(patched_environment(original,runtime.lock_dir)),"phase":"prepared"}
        save(journal,state)
    if state["source_sha"]!=runtime.sha:raise ValueError("Release changed since journal was created")
    target=original if rollback else patched_environment(original,runtime.lock_dir)
    target_capability=state["old_capability"] if rollback else EXPECTED_CAPABILITY
    current=runtime.environment_bytes();current_capability=EXPECTED_CAPABILITY if rollback else state["old_capability"]
    owner="budget:"+uuid.uuid4().hex
    acquire_attempted=False;acquired=False;service_touched=False;env_touched=False;release_attempted=False
    try:
        acquire_attempted=True
        runtime.acquire(owner);acquired=True
        runtime.failure_phase="draining"
        state.update(phase="draining",owner=owner,operation="rollback" if rollback else "activate");save(journal,state)
        runtime.drain();runtime.physical_locks(create=not rollback)
        runtime.assert_owner(owner)
        if runtime.environment_bytes()!=current:raise ValueError("Environment changed during preflight")
        service_touched=True;runtime.stop()
        runtime.failure_phase="stopped"
        state["phase"]="stopped";save(journal,state)
        runtime.assert_owner(owner)
        env_touched=True;runtime.install_environment(target,state["original_mode"])
        runtime.failure_phase="configured"
        state["phase"]="configured";save(journal,state)
        runtime.start();runtime.verify(target_capability)
        runtime.failure_phase="healthy"
        state["phase"]="healthy";save(journal,state)
        # A committed-but-unacknowledged release never authorizes compensation.
        release_attempted=True
        runtime.release(owner);acquired=False
        state["phase"]="rolled_back" if rollback else "completed";save(journal,state)
        return {"ok":True,"operation":state["operation"],"source_sha":runtime.sha,"capability":target_capability,"authenticated_export_smoke":"required_separately"}
    except BaseException:
        if release_attempted:
            state["phase"]="release_acknowledgement_unknown";save(journal,state)
            raise RuntimeError("RECOVERY_REQUIRED: preserve current healthy release; verify actual GLOBAL owner before further operations") from None
        if acquire_attempted and not acquired:
            state["phase"]="acquire_acknowledgement_unknown";save(journal,state)
            raise RuntimeError("GLOBAL busy or acquisition unverified; no service/configuration changed, inspect actual owner") from None
        if acquired and service_touched:
            try:
                runtime.assert_owner(owner);runtime.stop()
                if env_touched:
                    if runtime.environment_bytes()!=target:raise ValueError("Environment changed during compensation")
                    runtime.install_environment(current,state["original_mode"])
                runtime.start();runtime.verify(current_capability)
                state["phase"]="compensated";save(journal,state)
            except BaseException:
                state["phase"]="recovery_required";save(journal,state)
                raise RuntimeError("RECOVERY_REQUIRED: mutex and private journal retained; configuration recovery is unverified") from None
        if acquired:
            try:runtime.release(owner)
            except BaseException:
                state["phase"]="release_acknowledgement_unknown";save(journal,state)
                raise RuntimeError("RECOVERY_REQUIRED: restored service verified but GLOBAL release is unverified") from None
        state["phase"]="aborted" if not service_touched else "compensated";save(journal,state)
        raise RuntimeError("Activation failed; previous configuration and health were preserved or verified restored") from None


def activate_with_smoke(runtime,journal):
    result=activate(runtime,journal)
    try:
        proof=runtime.smoke()
        state=json.loads((Path(journal)/"state.json").read_text());state["smoke"]=proof;save(Path(journal),state)
        return {**result,"public_document_smoke":proof,"authenticated_export_smoke":"covered_by_isolated_contracts"}
    except BaseException:
        # The first mutex has been released so public render admission works.
        # Rollback must acquire a NEW mutex, drain NEW admissions, and verify
        # unchanged source/env before restoring bytes. Never overwrite a restore.
        try:activate(runtime,journal,rollback=True)
        except BaseException:raise RuntimeError("RECOVERY_REQUIRED: smoke failed and fresh-mutex rollback could not be verified") from None
        raise RuntimeError("Public smoke failed; fresh-mutex rollback restored previous bytes and verified health") from None


class ProductionRuntime:
    def __init__(self,app,sha,supervisor_config,lock_dir,health_url):
        self.app=Path(app).resolve();self.sha=sha;self.config=Path(supervisor_config);self.lock_dir=Path(lock_dir)
        if not re.fullmatch(r"[0-9a-f]{40}",sha):raise ValueError("Full source SHA required")
        if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}/api/health",health_url):raise ValueError("Only fixed loopback health endpoint allowed")
        self.health_url=health_url;self.env_path=self.app/"backend/.env";self.client=None
        self.failure_phase="preflight"
        spec=importlib.util.spec_from_file_location("activation_environment",self.app/"scripts/releases/backend_environment.py")
        self.helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.helper)

    def command(self,args):
        result=subprocess.run(args,cwd=self.app,capture_output=True,text=True,timeout=40)
        if result.returncode:raise RuntimeError("Operator command failed")
        return result.stdout.strip()

    def request(self,url):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise ValueError("Health redirects forbidden")
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(url,timeout=5) as response:data=response.read(256*1024+1)
        if len(data)>256*1024:raise ValueError("Unbounded health response")
        return json.loads(data)

    def capability(self):
        value=self.request(self.health_url)
        if value.get("ok") is not True or value.get("release_sha")!=self.sha:raise ValueError("Running API release differs")
        return value["capabilities"]["export_global_budget"]

    def environment_bytes(self):
        metadata=owned(self.env_path,False,True)
        if metadata.st_size>1024*1024:raise ValueError("Environment too large")
        return self.env_path.read_bytes()

    def pid(self):return int(self.command(["supervisorctl","pid","inventarisasi-backend"]))

    def preflight(self,expected_capability=None):
        if self.command(["git","rev-parse","HEAD"])!=self.sha:raise ValueError("Repository SHA differs")
        self.command(["git","merge-base","--is-ancestor",self.sha,"origin/main"])
        self.command(["git","diff","--exit-code",self.sha,"--","backend","scripts/activate_export_budget.py","scripts/releases"])
        self.helper.attest_supervisor(self.app,self.config)
        pid=self.pid();self.helper.attest_process(self.app,pid,sys._base_executable)
        if Path(f"/proc/{pid}").stat().st_uid!=os.geteuid():raise ValueError("API UID differs from controller UID")
        raw=self.environment_bytes();metadata=self.env_path.stat()
        from dotenv import dotenv_values
        values=dotenv_values(stream=StringIO(raw.decode()))
        for key in FORBIDDEN_FEATURES:
            if str(values.get(key,"")).lower() not in {"","0","false","no"}:raise ValueError("Other optional features must remain off")
        parser=configparser.ConfigParser(interpolation=None);parser.read(self.config)
        configured=parser["program:inventarisasi-backend"].get("environment","")
        if any(re.search(r"(?:^|,)\s*"+key+r"\s*=",configured) for key in (*KEYS,*FORBIDDEN_FEATURES,"MONGO_URL","DB_NAME")):
            raise ValueError("Conflicting Supervisor feature override; no system configuration changed")
        process_environment=Path(f"/proc/{pid}/environ").read_bytes()
        # Inherited environment survives dotenv; current file-derived keys do
        # not appear in Linux's original exec-time environ range.
        for value in process_environment.split(b"\0"):
            name,_,content=value.partition(b"=")
            if name in {b"MONGO_URL",b"DB_NAME"} and content.decode()!=str(values.get(name.decode()) or ("inventaris_bmn" if name==b"DB_NAME" else "")):
                raise ValueError("Actual process database differs from private configuration")
            if value.partition(b"=")[0].decode(errors="ignore") in (*KEYS,*FORBIDDEN_FEATURES):
                raise ValueError("Inherited feature override must be removed explicitly")
        capability=self.capability()
        if capability.get("ok") is not True:raise ValueError("Current budget capability invalid")
        if expected_capability is not None and capability!=expected_capability:raise ValueError("Current capability differs from rollback baseline")
        if self.request(self.health_url+"/deep").get("ok") is not True:raise ValueError("Initial deep health failed")
        lock_directory(self.lock_dir)
        from pymongo import MongoClient
        if not values.get("MONGO_URL"):raise ValueError("Mongo URL missing")
        self.client=MongoClient(values["MONGO_URL"],serverSelectionTimeoutMS=5000,connectTimeoutMS=5000,socketTimeoutMS=5000)
        self.db=self.client[values.get("DB_NAME") or "inventaris_bmn"]
        suffix=hashlib.sha256(self.db.name.encode()).hexdigest()[:12]
        inherited=dict(value.decode(errors="strict").split("=",1) for value in process_environment.split(b"\0") if b"=" in value)
        previous_tmp=inherited.get("TMPDIR") or inherited.get("TEMP") or inherited.get("TMP") or "/tmp"
        self.previous_lock_dir=Path(values.get("AMAN_EXPORT_LOCK_DIR") or (Path(previous_tmp)/f"aman-render-{os.getuid()}-{suffix}"))
        return raw,metadata,capability

    def acquire(self,owner):
        from pymongo import ReturnDocument
        from pymongo.errors import DuplicateKeyError
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=30)).isoformat()
        if self.db.backup_jobs.count_documents({"type":"restore","active_lock":"GLOBAL","status":{"$in":["queued","running"]},"updated_at":{"$gt":cutoff}},maxTimeMS=5000):
            raise ValueError("Legacy restore active")
        try:
            result=self.db.restore_control.find_one_and_update({"_id":"GLOBAL","state":{"$in":TERMINAL}},
                {"$set":{"state":"deploying","owner":owner,"active":True,"destructive_started":False,"updated_at":datetime.now(timezone.utc).isoformat()}},upsert=True,return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:raise ValueError("GLOBAL busy/recovery required") from None
        if not result or result.get("owner")!=owner:raise ValueError("GLOBAL acquisition unverified")

    def assert_owner(self,owner):
        if not self.db.restore_control.find_one({"_id":"GLOBAL","state":"deploying","owner":owner}):raise ValueError("GLOBAL ownership lost")

    def drain(self):
        deadline=time.monotonic()+60
        while True:
            writers=self.db.restore_write_leases.count_documents({},maxTimeMS=5000)
            jobs=self.db.unduhan.count_documents({"status":{"$in":["queued","running"]}},maxTimeMS=5000)
            detached=self.db.background_jobs.count_documents({"status":{"$nin":JOB_TERMINAL},"done":{"$ne":True},"$nor":[{"worker_protocol":"export_v1","status":"queued"}]},maxTimeMS=5000)
            budget=self.db.export_resource_budget.find_one({"_id":"render_v1"}) or {}
            if not writers and not jobs and not detached and not budget.get("queue") and not budget.get("holders"):return
            if time.monotonic()>=deadline:raise ValueError("Writers/jobs/physical owners not drained; no TTL takeover")
            time.sleep(.5)

    def physical_locks(self,create=False):
        previous=getattr(self,"previous_lock_dir",self.lock_dir)
        if previous!=self.lock_dir:lock_directory(previous,expected_configuration=False)
        lock_directory(self.lock_dir,create)

    def stop(self):
        result=subprocess.run(["supervisorctl","stop","inventarisasi-backend"],capture_output=True,text=True,timeout=45)
        result=subprocess.run(["supervisorctl","status","inventarisasi-backend"],capture_output=True,text=True,timeout=10)
        if result.stdout.split()[:2]!=["inventarisasi-backend","STOPPED"]:raise ValueError("Whole API group STOPPED not proven")

    def start(self):self.command(["supervisorctl","start","inventarisasi-backend"])

    def install_environment(self,data,mode):atomic_bytes(self.env_path,data,mode)

    def verify(self,capability):
        self.helper.attest_process(self.app,self.pid(),sys._base_executable)
        deadline=time.monotonic()+90
        while True:
            try:
                if self.capability()!=capability:raise ValueError("Actual running capability differs")
                deep=self.request(self.health_url+"/deep")
                if deep.get("ok") is not True:raise ValueError("Deep health failed")
                return
            except Exception:
                if time.monotonic()>=deadline:raise ValueError("Release/capability/deep health unverified") from None
                time.sleep(1)

    def release(self,owner):
        result=self.db.restore_control.update_one({"_id":"GLOBAL","state":"deploying","owner":owner},{"$set":{"state":"completed","active":False,"updated_at":datetime.now(timezone.utc).isoformat()}})
        if result.matched_count!=1:raise ValueError("GLOBAL release unverified")

    def smoke(self):
        """Two bounded public static DOCX reads; no account or tenant data."""
        url=self.health_url.removesuffix("/api/health")+"/api/documents/proposal"
        def fetch():
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):raise ValueError("Smoke redirects forbidden")
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            try:
                with opener.open(url,timeout=25) as response:
                    body=response.read(2*1024*1024+1)
                    return response.status,response.headers,body
            except urllib.error.HTTPError as response:
                with response:return response.code,response.headers,response.read(8192)
        lock_directory(self.lock_dir)
        fd=os.open(self.lock_dir/"cpu-0.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(fetch);deadline=time.monotonic()+10
                while True:
                    row=self.db.export_resource_budget.find_one({"_id":"render_v1"}) or {}
                    if row.get("queue"):break
                    if pending.done() or time.monotonic()>deadline:raise ValueError("Physical slot admission not observed")
                    time.sleep(.05)
                if self.capability()!=EXPECTED_CAPABILITY:raise ValueError("Health blocked during occupied physical slot")
                status,headers,_=pending.result(timeout=25)
            retry=headers.get("Retry-After","")
            if status!=429 or not retry.isdecimal() or not 1<=int(retry)<=60:raise ValueError("Occupied slot did not return bounded429")
        finally:os.close(fd)
        status,headers,body=fetch()
        if status!=200 or len(body)>2*1024*1024 or not body.startswith(b"PK\x03\x04") or "wordprocessingml.document" not in headers.get("Content-Type",""):
            raise ValueError("Static DOCX response invalid/unbounded")
        with zipfile.ZipFile(BytesIO(body)) as archive:
            entries=archive.infolist()
            if len(entries)>1000 or sum(item.file_size for item in entries)>8*1024*1024 or any(item.file_size>2*1024*1024 for item in entries):
                raise ValueError("DOCX inventory unbounded")
            if "word/document.xml" not in archive.namelist() or "[Content_Types].xml" not in archive.namelist():raise ValueError("DOCX members missing")
        deadline=time.monotonic()+10
        while True:
            row=self.db.export_resource_budget.find_one({"_id":"render_v1"}) or {}
            if not row.get("queue") and not row.get("holders") and not self.db.restore_write_leases.count_documents({},maxTimeMS=5000):break
            if time.monotonic()>deadline:raise ValueError("Post-smoke queue/holder/writer cleanup unverified")
            time.sleep(.1)
        return {"blocked_status":429,"retry_after_seconds":int(retry),"document_status":200,"document_bytes":len(body),
                "document_sha256":digest(body),"health_during_block":True,"queue_holders_writers_empty":True,"customer_data_read":False,"accounts_created":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app",required=True);parser.add_argument("--expected-sha",required=True)
    parser.add_argument("--supervisor-config",default="/etc/supervisor/conf.d/inventarisasi-backend.conf")
    parser.add_argument("--lock-dir",default="/var/lib/aman/export-locks")
    parser.add_argument("--health-url",default="http://127.0.0.1:8001/api/health")
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-only",action="store_true");action.add_argument("--apply-journal");action.add_argument("--rollback-journal")
    args=parser.parse_args();runtime=None
    signal_seen=[False]
    def interrupted(*_):
        if signal_seen[0]:return
        signal_seen[0]=True
        raise KeyboardInterrupt()
    for name in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(name,interrupted)
    try:
        runtime=ProductionRuntime(args.app,args.expected_sha,args.supervisor_config,args.lock_dir,args.health_url)
        if args.check_only:
            _,_,capability=runtime.preflight();result={"ok":True,"operation":"preflight","source_sha":runtime.sha,"capability":capability}
        else:
            journal=Path(args.rollback_journal or args.apply_journal)
            operations=Path("/var/lib/aman/operations")
            if journal.parent!=operations or not re.fullmatch(r"budget-[A-Za-z0-9_-]{1,80}",journal.name):
                raise ValueError("Production journal must use the fixed private operations directory")
            for parent in (operations,*operations.parents):
                if parent==Path("/"):continue
                metadata=parent.lstat()
                if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_uid not in {0,os.geteuid()} or metadata.st_mode&0o022:
                    raise ValueError("Unsafe private operations ancestor")
            owned(operations,True,True)
            result=activate(runtime,journal,rollback=True) if args.rollback_journal else activate_with_smoke(runtime,journal)
        print(json.dumps(result,sort_keys=True))
    except BaseException as error:
        allowed={"preflight","draining","stopped","configured","healthy"}
        phase=getattr(runtime,"failure_phase","unknown")
        category="validation" if isinstance(error,ValueError) else "unknown"
        if re.fullmatch(r"[0-9a-f]{40}",args.expected_sha):
            print(json.dumps({"ok":False,"source_sha":args.expected_sha,"operation":"check" if args.check_only else "rollback" if args.rollback_journal else "activate",
                              "failure_phase":phase if phase in allowed else "unknown","error_category":category}),flush=True)
        parser.exit(70,"Budget operation failed or recovery unverified; inspect private journal and actual GLOBAL owner. No secrets were printed.\n")
    finally:
        if runtime is not None and runtime.client is not None:runtime.client.close()


if __name__=="__main__":main()
