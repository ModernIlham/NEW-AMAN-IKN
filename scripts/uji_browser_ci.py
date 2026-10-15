#!/usr/bin/env python3
"""Seed/run/clean an isolated real application for the Chromium CI smoke."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fixture_target import mongo_loopback
HTTP = requests.Session()
HTTP.trust_env = False


def isolated_mongo(value):
    """No multi-host seeds or replica discovery hidden behind loopback."""
    return mongo_loopback(value)


def create_browser_app():
    """Uvicorn factory: isolate storage BEFORE the real ASGI lifespan starts."""
    private = Path(os.environ["AMAN_BROWSER_PRIVATE_DIR"]).resolve()
    database = os.environ["DB_NAME"]
    if not re.fullmatch(r"aman_ci_browser_[a-f0-9]{32}", database) or not private.is_dir():
        raise ValueError("Konfigurasi fixture browser tidak valid")
    if os.environ["MONGO_URL"] != isolated_mongo(os.environ["MONGO_URL"]):
        raise ValueError("Mongo fixture belum dikunci directConnection")
    import slowapi
    original = slowapi.Limiter
    def limiter(*args, **kwargs):
        kwargs["storage_uri"] = "memory://"
        kwargs.pop("storage_options", None)
        return original(*args, **kwargs)
    slowapi.Limiter = limiter
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from server import app
    finally:
        slowapi.Limiter = original
    import routes.backup as backup
    from db import db
    assert db.name == database
    for name, directory in (("BACKUP_TEMP_DIR", "backup-temp"), ("BACKUP_ARSIP_DIR", "backup-arsip"), ("UPLOADS_DIR", "uploads")):
        path = private / directory
        path.mkdir(mode=0o700, exist_ok=True)
        setattr(backup, name, path)
    @app.get("/__browser_fixture__")
    async def fixture_identity():
        from shared_utils import limiter
        run_id = os.environ["AMAN_BROWSER_RUN_ID"]
        marker = await db["_loadtest_runs"].find_one({"_id": run_id}, {"_id": 1})
        storage = type(limiter._storage).__module__
        paths = (backup.BACKUP_TEMP_DIR, backup.BACKUP_ARSIP_DIR, backup.UPLOADS_DIR)
        return {"synthetic": bool(marker), "database": db.name, "run_id": run_id,
                "rate_limit_storage": "memory" if storage == "limits.storage.memory" else "unexpected",
                "private_filesystem": all(path.resolve().is_relative_to(private) for path in paths)}
    return app


def ready(url, process, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Layanan browser smoke berhenti sebelum siap")
        try:
            if HTTP.get(url, timeout=2, allow_redirects=False).status_code == 200:
                time.sleep(.15)
                if process.poll() is None:
                    return
        except requests.RequestException:
            pass
        time.sleep(.2)
    raise RuntimeError("Layanan browser smoke melewati tenggat startup")


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def cleanup_browser(state, private):
    """The parent also owns cleanup when timeout killed the Python child."""
    if not state.is_file():
        return
    data = json.loads(state.read_text())
    if data.get("closed"):
        return
    pid = int(data["pid"])
    profile = Path(data["profile"]).resolve()
    if not profile.is_relative_to(private.resolve()):
        raise ValueError("Profile browser bukan milik fixture ini")
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        current = stat.read_text().rsplit(")", 1)[1].split()[19]
        if current != data["process_start"] or os.getpgid(pid) != pid:
            raise ValueError("Identitas proses browser berubah; cleanup ditahan")
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 3
        while stat.exists() and time.monotonic() < deadline:
            if stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                break
            time.sleep(.05)
        if stat.exists() and stat.read_text().rsplit(")", 1)[1].split()[0] != "Z":
            os.killpg(pid, signal.SIGKILL)
    shutil.rmtree(profile, ignore_errors=True)


def public_diagnostics(private, output, secrets):
    spec = importlib.util.spec_from_file_location("browser_log_redaction", ROOT / "backend/log_setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("build", "backend", "frontend", "browser", "chromium"):
        source = private / (name + ".log")
        if source.is_file():
            with source.open("rb") as stream:
                stream.seek(max(0, source.stat().st_size - 65536))
                text = stream.read().decode("utf-8", errors="replace")
            for secret in sorted((value for value in secrets if value), key=len, reverse=True):
                text = text.replace(secret, "***")
            (output / (name + ".log")).write_text(module.redaksi_log(text))


def run(args):
    from pymongo import MongoClient
    args.mongo = isolated_mongo(args.mongo)
    database, run_id = "aman_ci_browser_" + uuid.uuid4().hex, uuid.uuid4().hex
    owner_collection = "_browser_smoke_owner_" + run_id
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Direktori bukti browser harus kosong untuk setiap run")
    # Chromium Unix sockets have a short pathname limit. Keep the private
    # sandbox in the OS temporary root, outside the publishable output tree.
    private = Path(tempfile.mkdtemp(prefix="aman-browser-ci-"))
    temporary = private / "tmp"
    temporary.mkdir(mode=0o700)
    manifest, accounts, runtime, state = [private / name for name in ("manifest.json", "accounts.json", "runtime.env", "browser-state.json")]
    backend_url, frontend_url = f"http://127.0.0.1:{args.api_port}", f"http://127.0.0.1:{args.frontend_port}"
    processes, logs, secrets, cleanup_errors = [], [], [], []
    failure = None
    report = {"ok": False, "stage": "reserve_database", "synthetic": True, "cleanup_errors": cleanup_errors}
    def cleanup(action, callback):
        try:
            callback()
        except Exception as exc:
            cleanup_errors.append({"action": action, "error_class": type(exc).__name__})
    def drop_owned_database():
        with MongoClient(args.mongo, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            if owner_collection in client[database].list_collection_names():
                assert re.fullmatch(r"aman_ci_browser_[a-f0-9]{32}", database)
                client.drop_database(database)
                assert database not in client.list_database_names()
    try:
        with MongoClient(args.mongo, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            if database in client.list_database_names():
                raise ValueError("Database fixture sudah ada")
            # Empty ownership collection survives partial seed failure without
            # making seed's non-empty-data guard reject the reservation.
            client[database].create_collection(owner_collection)
        report["stage"] = "seed"
        subprocess.run([sys.executable, str(ROOT / "scripts/loadtest/seed.py"), "seed", "--mongo-url", args.mongo,
            "--database", database, "--run-id", run_id, "--count", "1000", "--accounts", "1",
            "--manifest", str(manifest), "--accounts-file", str(accounts), "--runtime-env-file", str(runtime)],
            cwd=ROOT, check=True, stdout=subprocess.DEVNULL, timeout=90)
        settings = {}
        for line in runtime.read_text().splitlines():
            key, value = line.split("=", 1)
            assert key in {"MONGO_URL", "DB_NAME", "JWT_SECRET"}
            settings[key] = value
            secrets.append(value)
        for account in json.loads(accounts.read_text())["accounts"]:
            secrets.extend([account.get("password", ""), account.get("access_token", "")])
        env = {**os.environ, **settings, "REDIS_URL": "", "MEILI_URL": "", "MEILI_MASTER_KEY": "",
            "TINIFY_API_KEY": "", "RESEND_API_KEY": "", "ADMIN_BOOTSTRAP_TOKEN": "", "ALLOWED_ORIGINS": frontend_url,
            "AMAN_OBSERVABILITY_ENABLED": "0", "AMAN_EXPORT_GLOBAL_BUDGET_ENABLED": "0", "AMAN_EXPORT_DURABLE_XLSX_ENABLED": "0",
            "AMAN_BROWSER_PRIVATE_DIR": str(private), "AMAN_BROWSER_RUN_ID": run_id, "TMPDIR": str(temporary),
            "AMAN_EXPORT_LOCK_DIR": str(private / "export-locks")}
        build = Path(getattr(args, "build_dir", "") or ROOT / "frontend/build").resolve() if args.skip_build else private / "build"
        if not args.skip_build:
            report["stage"] = "build"
            build_env = {**env, "REACT_APP_BACKEND_URL": backend_url, "BUILD_PATH": str(build), "CI": "false"}
            with (private / "build.log").open("w") as log:
                subprocess.run([str(ROOT / "frontend/node_modules/.bin/craco"), "build"], cwd=ROOT / "frontend", env=build_env,
                    check=True, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        report["stage"] = "startup"
        for name, command in [
            ("backend", [sys.executable, "-m", "uvicorn", "uji_browser_ci:create_browser_app", "--factory", "--app-dir", str(ROOT / "scripts"),
                "--host", "127.0.0.1", "--port", str(args.api_port), "--log-level", "warning"]),
            ("frontend", [sys.executable, "-m", "http.server", str(args.frontend_port), "--bind", "127.0.0.1", "--directory", str(build)]),
        ]:
            log = (private / (name + ".log")).open("w")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT))
        ready(backend_url + "/__browser_fixture__", processes[0])
        ready(frontend_url, processes[1])
        report["stage"] = "browser"
        with (private / "browser.log").open("w") as log:
            subprocess.run([sys.executable, str(ROOT / "scripts/uji_browser.py"), "--frontend", frontend_url, "--backend", backend_url,
                "--accounts", str(accounts), "--output", str(output), "--chromium", args.chromium, "--browser-state", str(state)],
                cwd=ROOT, env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        report["stage"] = "completed"
    except BaseException as exc:
        failure = exc
        report["error_class"] = type(exc).__name__
    finally:
        cleanup("browser_process", lambda: cleanup_browser(state, private))
        for process in reversed(processes):
            cleanup("server_process", lambda process=process: stop_process(process))
        for log in logs:
            cleanup("log_close", log.close)
        cleanup("database", drop_owned_database)
        cleanup("diagnostics", lambda: public_diagnostics(private, output, secrets))
        cleanup("private_directory", lambda: shutil.rmtree(private))
        report["ok"] = failure is None and not cleanup_errors
        try:
            (output / "runner.json").write_text(json.dumps(report, indent=2) + "\n")
        except Exception:
            if failure is None:
                raise
    if failure:
        raise failure.with_traceback(failure.__traceback__)
    if cleanup_errors:
        raise RuntimeError("Cleanup fixture browser gagal; lihat runner.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--api-port", type=int, default=18001)
    parser.add_argument("--frontend-port", type=int, default=18765)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--skip-build", action="store_true", help="Build lokal yang sudah memakai port API ini")
    parser.add_argument("--build-dir", default="", help="Direktori build existing, hanya bersama --skip-build")
    run(parser.parse_args())
