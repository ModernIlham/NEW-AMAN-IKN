#!/usr/bin/env python3
"""Read-only fixed-path VPS inventory; strict allowlisted JSON, no secrets.

No target/path parameters, no process arguments/config dumps, no writes or
service changes. --validate validates a captured report from stdin locally.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import HTTPError

APP = Path("/var/www/inventarisasi")
MAX_OUTPUT = 48 * 1024
SERVICES = ("mongod", "nginx", "redis-server", "meilisearch", "supervisor", "cron")
VERSION_RE = re.compile(r"(?<![0-9])\d{1,3}\.\d{1,3}(?:\.\d{1,5})?(?:[-+][A-Za-z0-9.]{1,30})?\b")
KNOWN_OLD_CHUNK = "static/js/9311.08c8148e.chunk.js"
PUBLIC_JS_RE = re.compile(r"static/js/[A-Za-z0-9_.-]{1,90}\.[0-9a-f]{8,64}(?:\.chunk)?\.js")


def static_retention_inventory(app=APP, nginx=Path("/etc/nginx")):
    """Fixed public build metadata only; never publish config text or paths."""
    result={};current_assets={}
    try:
        path=app/"frontend/build/.aman-static-retention.json"
        if path.is_file() and not path.is_symlink() and path.stat().st_size<=8*1024*1024:
            value=json.loads(path.read_text())
            if value.get("schema_version")==1 and isinstance(value.get("assets"),dict) and len(value["assets"])<=20000:current_assets=value["assets"]
    except Exception:pass
    for label,directory in (("current","build"),("previous","build.old")):
        root=app/"frontend"/directory;asset=root/KNOWN_OLD_CHUNK
        row={"file_present":asset.exists(),"file_regular":False,"file_bytes":None,"file_sha256":None,
             "own_manifest_contains":None,"ledger_present":False,"ledger_contains":None,
             "ledger_sha256":None,"ledger_bytes":None,"ledger_last_seen_epoch":None,"ledger_created_epoch":None,
             "own_manifest_sha256":None,"own_js_sample":[],"ledger_grace_hours":None}
        try:
            row["file_regular"]=asset.is_file() and not asset.is_symlink()
            if row["file_regular"]:
                row["file_bytes"]=asset.stat().st_size
                if row["file_bytes"]<=2*1024*1024:row["file_sha256"]=hashlib.sha256(asset.read_bytes()).hexdigest()
            manifest=root/"asset-manifest.json"
            if manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size<=8*1024*1024:
                content=manifest.read_bytes();row["own_manifest_sha256"]=hashlib.sha256(content).hexdigest()
                value=json.loads(content);files=value.get("files",{})
                if isinstance(files,dict) and len(files)<=20000:
                    row["own_manifest_contains"]=any(isinstance(value,str) and value.lstrip("/")==KNOWN_OLD_CHUNK for value in files.values())
                    names={value.lstrip("/") for value in files.values() if isinstance(value,str) and PUBLIC_JS_RE.fullmatch(value.lstrip("/"))}
                    for name in sorted(names,key=lambda item:(not item.startswith("static/js/main."),item))[:3]:
                        sample={"path":name,"file_sha256":None,"file_bytes":None,"current_ledger_contains":name in current_assets,
                                "current_ledger_sha256":None,"current_ledger_last_seen_epoch":None}
                        source=root/name
                        if source.is_file() and not source.is_symlink() and source.stat().st_size<=2*1024*1024:
                            sample["file_bytes"]=source.stat().st_size;sample["file_sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
                        metadata=current_assets.get(name)
                        if isinstance(metadata,dict):
                            checksum=metadata.get("sha256");seen=metadata.get("last_seen")
                            if isinstance(checksum,str) and re.fullmatch(r"[0-9a-f]{64}",checksum):sample["current_ledger_sha256"]=checksum
                            if type(seen) in (int,float) and math.isfinite(seen) and 0<=seen<2**63:sample["current_ledger_last_seen_epoch"]=seen
                        row["own_js_sample"].append(sample)
            ledger=root/".aman-static-retention.json"
            row["ledger_present"]=ledger.is_file() and not ledger.is_symlink()
            if row["ledger_present"] and ledger.stat().st_size<=8*1024*1024:
                value=json.loads(ledger.read_text());assets=value.get("assets",{})
                if value.get("schema_version")==1 and isinstance(assets,dict) and len(assets)<=20000:
                    row["ledger_contains"]=KNOWN_OLD_CHUNK in assets
                    metadata=assets.get(KNOWN_OLD_CHUNK) or {}
                    checksum=metadata.get("sha256")
                    row["ledger_sha256"]=checksum if isinstance(checksum,str) and re.fullmatch(r"[0-9a-f]{64}",checksum) else None
                    for output,raw in (("ledger_bytes",metadata.get("bytes")),("ledger_last_seen_epoch",metadata.get("last_seen")),("ledger_created_epoch",value.get("created_at")),("ledger_grace_hours",value.get("grace_hours"))):
                        if type(raw) in (int,float) and math.isfinite(raw) and 0<=raw<2**63:row[output]=raw
        except Exception:pass
        result[label]=row
    flags={"enabled_config_readable":False,"enabled_config_truncated":False,"current_root_mentioned":False,
           "previous_root_mentioned":False,"previous_static_alias_mentioned":False,"loaded_config_attested":False}
    files=[nginx/"nginx.conf"]
    for directory in (nginx/"sites-enabled",nginx/"conf.d"):
        try:
            entries=sorted(directory.iterdir())
            flags["enabled_config_truncated"]|=len(entries)>64
            files.extend(entries[:64])
        except OSError:pass
    remaining=256*1024
    for path in files:
        try:
            target=path.resolve()
            if not target.is_relative_to(nginx.resolve()) or not target.is_file():continue
            size=target.stat().st_size
            if size>128*1024 or size>remaining:flags["enabled_config_truncated"]=True;continue
            remaining-=size
            text="\n".join(line.split("#",1)[0] for line in target.read_text().splitlines())
            flags["enabled_config_readable"]=True
            prefix=re.escape(str(app/"frontend"))
            flags["current_root_mentioned"]|=bool(re.search(r"\b(?:root|alias)\s+[\"']?"+prefix+r"/build(?:/|;|[\"'])",text))
            flags["previous_root_mentioned"]|=bool(re.search(r"\b(?:root|alias)\s+[\"']?"+prefix+r"/build\.old(?:/|;|[\"'])",text))
            flags["previous_static_alias_mentioned"]|=bool(re.search(r"\balias\s+[\"']?"+prefix+r"/build\.old/static(?:/|;|[\"'])",text))
        except Exception:pass
    result["nginx_flags"]=flags
    return result


def command(arguments, timeout=10):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True,
                                timeout=timeout, check=False,
                                env={**os.environ, "COREPACK_ENABLE_NETWORK": "0",
                                     "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0"})
        return result.stdout[:4096], result.stderr[:4096], result.returncode
    except Exception:
        return "", "", -1


def version(arguments):
    out, err, _ = command(arguments)
    match = VERSION_RE.search(out + "\n" + err)
    return match.group(0) if match else None


def collect():
    began = time.monotonic()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, value = line.split(":", 1)
            if name in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                mem[name] = int(value.split()[0]) * 1024
    except Exception:
        pass
    disk = shutil.disk_usage("/")
    fs = os.statvfs("/")
    system = {"cpu_count": os.cpu_count(), "architecture": platform.machine()
              if platform.machine() in {"x86_64", "aarch64", "arm64", "armv7l"} else "other",
              "memory_total_bytes": mem.get("MemTotal"), "memory_available_bytes": mem.get("MemAvailable"),
              "swap_total_bytes": mem.get("SwapTotal"), "swap_free_bytes": mem.get("SwapFree"),
              "disk_total_bytes": disk.total, "disk_free_bytes": disk.free,
              "inode_total": fs.f_files, "inode_available": fs.f_favail,
              "load_average": [round(value, 3) for value in os.getloadavg()]}
    process_count, backend_fd_count, scanned = 0, 0, 0
    try:
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            scanned += 1
            if scanned > 4096:
                break
            try:
                if process.joinpath("comm").read_text().strip() in {"uvicorn", "gunicorn"}:
                    process_count += 1
                    backend_fd_count += sum(1 for _ in process.joinpath("fd").iterdir())
            except OSError:
                continue
    except OSError:
        pass
    system.update({"uvicorn_gunicorn_process_count": process_count,
                   "observed_backend_fd_count": backend_fd_count,
                   "process_scan_truncated": scanned > 4096})
    software = {name: version(args) for name, args in {
        "python_system": ["python3", "--version"],
        "python_backend": [str(APP / "backend/venv/bin/python"), "--version"],
        "node": ["node", "--version"], "yarn": ["yarn", "--version"],
        "mongo_binary": ["mongod", "--version"], "redis_binary": ["redis-server", "--version"],
        "nginx": ["nginx", "-v"], "meili_binary": ["meilisearch", "--version"],
    }.items()}
    services = {}
    allowed = {"active", "inactive", "failed", "activating", "deactivating", "unknown"}
    for name in SERVICES:
        out, _, _ = command(["systemctl", "is-active", name + ".service"])
        value = out.strip()
        services[name] = value if value in allowed else "unknown"
    out, _, _ = command(["supervisorctl", "status", "inventarisasi-backend"])
    parts = out.split()
    supervisor = parts[1] if len(parts) > 1 else "UNKNOWN"
    if supervisor not in {"RUNNING", "STOPPED", "STARTING", "EXITED", "FATAL", "BACKOFF", "STOPPING"}:
        supervisor = "UNKNOWN"
    versions = {}
    sha, _, _ = command(["git", "-C", str(APP), "rev-parse", "HEAD"])
    sha = sha.strip()
    versions["backend_git_sha"] = sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    manifest = APP / "frontend/build/asset-manifest.json"
    versions["frontend_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() and manifest.stat().st_size < 1024 ** 2 else None
    archives = APP / "backend/backup_arsip"
    archive_stats = []
    if archives.is_dir():
        for entry in archives.iterdir():
            if re.fullmatch(r"backup_(otomatis|manual)_\d{8}_\d{6}\.zip", entry.name) and entry.is_file():
                info = entry.stat()
                archive_stats.append((info.st_size, info.st_mtime))
    backup = {"archive_count": len(archive_stats), "archive_total_bytes": sum(a[0] for a in archive_stats),
              "latest_archive_age_seconds": max(0, int(datetime.datetime.now().timestamp() - max(a[1] for a in archive_stats))) if archive_stats else None,
              "archive_on_separate_device": bool(archives.exists() and archives.stat().st_dev != APP.stat().st_dev) if APP.exists() else None}
    configuration = {key: False for key in ("redis_configured", "meili_configured", "offsite_destination_configured", "dr_key_file_configured")}
    mongo = {"readable": False, "version": None, "topology": "unknown", "indexes": None,
             "write_concern_acknowledged": None, "restore_state": "unknown",
             "restore_destructive_started": None, "active_writer_leases": None,
             "active_background_jobs": None, "active_downloads": None,
             "latest_recorded_backup_success_age_seconds": None}
    try:
        from dotenv import dotenv_values
        config = dotenv_values(APP / "backend/.env")
        configuration.update({"redis_configured": bool(config.get("REDIS_URL")),
            "meili_configured": bool(config.get("MEILI_URL")),
            "offsite_destination_configured": bool(config.get("AMAN_DR_DESTINATION") or config.get("BACKUP_OFFSITE_URI")),
            "dr_key_file_configured": bool(config.get("AMAN_DR_KEY_FILE"))})
        from pymongo import MongoClient
        uri = config.get("MONGO_URL")
        name = config.get("DB_NAME")
        if not uri or not name:
            raise ValueError("unconfigured")
        with MongoClient(uri, serverSelectionTimeoutMS=3000, socketTimeoutMS=5000,
                         connectTimeoutMS=3000, maxPoolSize=2) as client:
            db = client[name]
            hello = client.admin.command("hello")
            mongo["readable"] = bool(db.command("ping").get("ok"))
            build_version = client.server_info().get("version", "")
            mongo["version"] = build_version if VERSION_RE.fullmatch(build_version) else None
            mongo["topology"] = "replica_set" if hello.get("setName") else "mongos" if hello.get("msg") == "isdbgrid" else "standalone"
            mongo["write_concern_acknowledged"] = bool(db.write_concern.acknowledged)
            mongo["indexes"] = sum(len(list(db[n].list_indexes())) for n in db.list_collection_names() if not n.startswith("system."))
            control = db.restore_control.find_one({"_id": "GLOBAL"}) or {}
            state = control.get("state", "none")
            mongo["restore_state"] = state if state in {"none", "preparing", "restoring", "rolling_back", "recovery_required", "completed", "rolled_back", "aborted", "deploying"} else "unknown"
            mongo["restore_destructive_started"] = bool(control.get("destructive_started"))
            mongo["active_writer_leases"] = db.restore_write_leases.count_documents({})
            mongo["active_background_jobs"] = db.background_jobs.count_documents({"status": {"$nin": ["done", "error", "failed", "completed", "cancelled", "canceled", "dismissed"]}})
            mongo["active_downloads"] = db.unduhan.count_documents({"status": {"$in": ["queued", "running"]}})
            settings = db.report_settings.find_one({"type": "backup_otomatis"}) or {}
            timestamp = settings.get("terakhir_sukses")
            if timestamp:
                stamp = datetime.datetime.fromisoformat(str(timestamp))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=datetime.timezone.utc)
                mongo["latest_recorded_backup_success_age_seconds"] = max(0, int((datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()))
    except Exception:
        # Never print exception: a provider/driver error may include a secret URI.
        pass
    health = {"http_status": None, "ok": None, "mongodb_ms": None,
              "gridfs_ms": None, "redis_ms": None, "index_failures": None, "maintenance": None,
              "mongodb_ok": None, "gridfs_ok": None, "redis_ok": None, "indexes_ok": None}
    try:
        try:
            response = urlopen("http://127.0.0.1:8001/api/health/deep", timeout=5)
        except HTTPError as error:
            response = error
        with response:
            health["http_status"] = response.status
            payload = json.loads(response.read(65537))
        health["ok"] = bool(payload.get("ok"))
        checks = payload.get("checks") or {}
        for name in ("mongodb", "gridfs", "redis"):
            flag = (checks.get(name) or {}).get("ok")
            health[name + "_ok"] = flag if type(flag) is bool else None
            value = (checks.get(name) or {}).get("latency_ms")
            health[name + "_ms"] = float(value) if isinstance(value, (float, int)) and math.isfinite(value) else None
        index = checks.get("indexes") or checks.get("indeks") or {}
        health["indexes_ok"] = index.get("ok") if type(index.get("ok")) is bool else None
        value = index.get("failure_count", index.get("gagal"))
        health["index_failures"] = value if type(value) is int else None
        health["maintenance"] = bool((checks.get("pemeliharaan") or {}).get("aktif"))
    except Exception:
        pass
    return {"schema_version": 1, "collected_at": now, "read_only": True,
            "collection_duration_ms": round((time.monotonic() - began) * 1000), "health": health,
            "system": system, "software": software, "services": services,
            "backend_supervisor_state": supervisor, "release": versions,
            "static_retention":static_retention_inventory(APP),
            "backup": backup, "configuration_presence": configuration, "mongo": mongo,
            "capacity_claim": "inventory_only_not_a_load_test"}


def validate_report(report):
    """Reject extra fields and unbounded strings before publishing a check run."""
    expected = {"schema_version", "collected_at", "read_only", "system", "software", "services",
                "backend_supervisor_state", "release", "backup", "configuration_presence", "mongo", "capacity_claim", "health", "collection_duration_ms", "static_retention"}
    if set(report) != expected or report["schema_version"] != 1 or report["read_only"] is not True:
        raise ValueError("Invalid inventory schema")
    if report["capacity_claim"] != "inventory_only_not_a_load_test":
        raise ValueError("Invalid capacity classification")
    allowed_keys = {
        "system": {"cpu_count", "architecture", "memory_total_bytes", "memory_available_bytes", "swap_total_bytes", "swap_free_bytes", "disk_total_bytes", "disk_free_bytes", "inode_total", "inode_available", "load_average", "uvicorn_gunicorn_process_count", "observed_backend_fd_count", "process_scan_truncated"},
        "health": {"http_status", "ok", "mongodb_ms", "gridfs_ms", "redis_ms", "index_failures", "maintenance", "mongodb_ok", "gridfs_ok", "redis_ok", "indexes_ok"},
        "software": {"python_system", "python_backend", "node", "yarn", "mongo_binary", "redis_binary", "nginx", "meili_binary"},
        "services": set(SERVICES), "release": {"backend_git_sha", "frontend_manifest_sha256"},
        "backup": {"archive_count", "archive_total_bytes", "latest_archive_age_seconds", "archive_on_separate_device"},
        "configuration_presence": {"redis_configured", "meili_configured", "offsite_destination_configured", "dr_key_file_configured"},
        "mongo": {"readable", "version", "topology", "indexes", "write_concern_acknowledged", "restore_state", "restore_destructive_started", "active_writer_leases", "active_background_jobs", "active_downloads", "latest_recorded_backup_success_age_seconds"},
    }
    for section, keys in allowed_keys.items():
        if not isinstance(report[section], dict) or set(report[section]) != keys:
            raise ValueError("Unexpected inventory fields")
    # Every string is bounded and restricted to a value grammar. This excludes
    # hostnames, usernames, paths, URLs, command lines and arbitrary log text.
    def check(value, path=()):
        if isinstance(value, dict):
            for key, entry in value.items():
                check(entry, path + (key,))
        elif isinstance(value, list):
            if path in {("static_retention","current","own_js_sample"),("static_retention","previous","own_js_sample")}:
                if len(value)>3:raise ValueError("Invalid static sample count")
                for entry in value:check(entry,path+("sample",))
            elif path != ("system", "load_average") or len(value) != 3 or any(not isinstance(n, (float, int)) for n in value):
                raise ValueError("Invalid list")
        elif isinstance(value, str):
            if len(path)==5 and path[:1]==("static_retention",) and path[2:]==("own_js_sample","sample","path"):
                if not PUBLIC_JS_RE.fullmatch(value) or len(value)>128:raise ValueError("Invalid public JS sample")
                return
            if len(value) > 128 or any(char in value for char in ("/", "\\", "@", "\n", "`", "<", ">")):
                raise ValueError("Unsafe inventory value")
            if path[0] == "software" or path == ("mongo", "version"):
                if not VERSION_RE.fullmatch(value):
                    raise ValueError("Invalid version")
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise ValueError("Invalid value type")
    check(report)
    retention=report["static_retention"]
    if set(retention)!={"current","previous","nginx_flags"}:raise ValueError("Invalid static inventory")
    row_keys={"file_present","file_regular","file_bytes","file_sha256","own_manifest_contains","ledger_present","ledger_contains","ledger_sha256","ledger_bytes","ledger_last_seen_epoch","ledger_created_epoch","own_manifest_sha256","own_js_sample","ledger_grace_hours"}
    for label in ("current","previous"):
        row=retention[label]
        if set(row)!=row_keys:raise ValueError("Invalid static metadata fields")
        for key in ("file_sha256","ledger_sha256","own_manifest_sha256"):
            if row[key] is not None and not re.fullmatch(r"[0-9a-f]{64}",row[key]):raise ValueError("Invalid public static digest")
        for key in ("file_present","file_regular","ledger_present"):
            if type(row[key]) is not bool:raise ValueError("Invalid public static presence")
        for key in ("own_manifest_contains","ledger_contains"):
            if row[key] is not None and type(row[key]) is not bool:raise ValueError("Invalid static reference flag")
        for key in ("file_bytes","ledger_bytes","ledger_last_seen_epoch","ledger_created_epoch","ledger_grace_hours"):
            if row[key] is not None and (type(row[key]) not in (int,float) or not math.isfinite(row[key]) or not 0<=row[key]<2**63):raise ValueError("Invalid static count/time")
        for sample in row["own_js_sample"]:
            if not isinstance(sample,dict) or set(sample)!={"path","file_sha256","file_bytes","current_ledger_contains","current_ledger_sha256","current_ledger_last_seen_epoch"}:raise ValueError("Invalid static sample fields")
            if type(sample["current_ledger_contains"]) is not bool:raise ValueError("Invalid static sample presence")
            for key in ("file_sha256","current_ledger_sha256"):
                if sample[key] is not None and (not isinstance(sample[key],str) or not re.fullmatch(r"[0-9a-f]{64}",sample[key])):raise ValueError("Invalid static sample digest")
            for key in ("file_bytes","current_ledger_last_seen_epoch"):
                raw=sample[key]
                if raw is not None and (type(raw) not in (int,float) or not math.isfinite(raw) or not 0<=raw<2**63):raise ValueError("Invalid static sample number")
    flags=retention["nginx_flags"]
    if set(flags)!={"enabled_config_readable","enabled_config_truncated","current_root_mentioned","previous_root_mentioned","previous_static_alias_mentioned","loaded_config_attested"} or any(type(value) is not bool for value in flags.values()):raise ValueError("Invalid nginx public flags")
    datetime.datetime.fromisoformat(report["collected_at"])
    if report["system"]["architecture"] not in {"x86_64", "aarch64", "arm64", "armv7l", "other"}:
        raise ValueError("Invalid architecture")
    if report["backend_supervisor_state"] not in {"RUNNING", "STOPPED", "STARTING", "EXITED", "FATAL", "BACKOFF", "STOPPING", "UNKNOWN"}:
        raise ValueError("Invalid supervisor state")
    for value in report["services"].values():
        if value not in {"active", "inactive", "failed", "activating", "deactivating", "unknown"}:
            raise ValueError("Invalid service state")
    if report["mongo"]["topology"] not in {"standalone", "replica_set", "mongos", "unknown"}:
        raise ValueError("Invalid topology")
    if report["mongo"]["restore_state"] not in {"none", "preparing", "restoring", "rolling_back", "recovery_required", "completed", "rolled_back", "aborted", "deploying", "unknown"}:
        raise ValueError("Invalid restore state")
    for key, value in report["release"].items():
        if value is not None and not re.fullmatch(r"[0-9a-f]{40}" if key == "backend_git_sha" else r"[0-9a-f]{64}", value):
            raise ValueError("Invalid release digest")
    for value in report["configuration_presence"].values():
        if type(value) is not bool:
            raise ValueError("Invalid configuration presence")
    numeric = [value for key, value in report["system"].items() if key not in {"architecture", "load_average", "process_scan_truncated"}]
    numeric.append(report["collection_duration_ms"])
    numeric += [report["health"][key] for key in ("http_status", "index_failures")]
    numeric += [report["backup"][key] for key in ("archive_count", "archive_total_bytes", "latest_archive_age_seconds")]
    numeric += [report["mongo"][key] for key in ("indexes", "active_writer_leases", "active_background_jobs", "active_downloads", "latest_recorded_backup_success_age_seconds")]
    if any(value is not None and (type(value) is not int or value < 0 or value > 2 ** 63 - 1) for value in numeric):
        raise ValueError("Invalid inventory count")
    if any(not math.isfinite(value) or value < 0 for value in report["system"]["load_average"]):
        raise ValueError("Invalid load average")
    for name in ("mongodb_ms", "gridfs_ms", "redis_ms"):
        value = report["health"][name]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid health latency")
    for value in (report["health"]["mongodb_ok"], report["health"]["gridfs_ok"], report["health"]["redis_ok"], report["health"]["indexes_ok"], report["health"]["ok"], report["health"]["maintenance"], report["system"]["process_scan_truncated"], report["backup"]["archive_on_separate_device"], report["mongo"]["readable"],
                  report["mongo"]["write_concern_acknowledged"], report["mongo"]["restore_destructive_started"]):
        if value is not None and type(value) is not bool:
            raise ValueError("Invalid inventory flag")
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if len(encoded.encode()) > MAX_OUTPUT:
        raise ValueError("Inventory too large")
    return encoded


if __name__ == "__main__":
    if sys.argv[1:] == ["--validate"]:
        source = sys.stdin.read(MAX_OUTPUT + 1)
        if len(source.encode()) > MAX_OUTPUT:
            raise SystemExit("Invalid inventory size")
        print(validate_report(json.loads(source)))
    elif sys.argv[1:]:
        raise SystemExit("No target/path arguments are accepted")
    else:
        print(validate_report(collect()))
