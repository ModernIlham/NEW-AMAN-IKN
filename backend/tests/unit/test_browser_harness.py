"""Failure paths must retain diagnostics and clean only owned local fixtures."""
import importlib.util
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fixture_target import mongo_loopback

ROOT = Path(__file__).resolve().parents[3]


def script(name):
    spec = importlib.util.spec_from_file_location("review_" + name.replace("/", "_"), ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("uri", ["mongodb+srv://localhost/", "mongodb://remote.example/",
    "mongodb://127.0.0.1:27017,remote.example:27017/", "mongodb://user:private@127.0.0.1/",
    "mongodb://127.0.0.1/?replicaSet=prod", "mongodb://127.0.0.1/?directConnection=false",
    "mongodb://127.0.0.1/?loadBalanced=true", "mongodb://127.0.0.1/application",
    "mongodb://127.0.0.1:99999/", "mongodb://127.0.0.1/#fragment"])
def test_disposable_tools_reject_nonlocal_or_discovering_uri_before_connection(uri):
    with pytest.raises(ValueError):
        mongo_loopback(uri)
    with pytest.raises(ValueError):
        script("uji_browser_ci").isolated_mongo(uri)


def test_direct_single_loopback_is_explicit_and_idempotent():
    for target in ("mongodb://localhost", "mongodb://127.0.0.1:27017/", "mongodb://[::1]:27017/"):
        result = mongo_loopback(target)
        assert result.endswith("/?directConnection=true") and mongo_loopback(result) == result


@pytest.mark.parametrize("uri", ["mongodb://127.0.0.1:27017,remote.example:27017/", "mongodb+srv://localhost/",
    "mongodb://user:private@localhost/", "mongodb://127.0.0.1/?directConnection=false"])
def test_real_tool_entrypoints_reject_before_constructing_client(uri, tmp_path, monkeypatch):
    import pymongo
    monkeypatch.setattr(pymongo, "MongoClient", lambda *a, **k: pytest.fail("unsafe target reached a Mongo client"))
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    database = "aman_ci_guard123"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"database": database, "run_id": "12345678", "asset_count": 10}))
    with pytest.raises(ValueError):
        script("loadtest/seed").seed(SimpleNamespace(mongo_url=uri, database=database))
    with pytest.raises(ValueError):
        script("profile_asset_reads").profile(SimpleNamespace(mongo_url=uri, database=database, manifest=manifest))
    with pytest.raises(ValueError):
        script("profile_asset_index").benchmark(SimpleNamespace(mongo_url=uri, database=database, manifest=manifest, allow_local_index_change=True))
    with pytest.raises(ValueError):
        asyncio.run(script("smoke_runtime").smoke(SimpleNamespace(mongo_url=uri)))
    with pytest.raises(ValueError):
        asyncio.run(script("spike_pymongo_async").probe(SimpleNamespace(mongo_url=uri)))


def test_failed_constructor_cleans_profile_and_process_even_if_cdp_close_fails(monkeypatch):
    browser = script("uji_browser")
    events, profile = [], []
    class PrimaryFailure(RuntimeError):
        pass
    class Process:
        pid = 987654
        def poll(self): return None
        def wait(self, **kwargs): events.append("wait")
    class Socket:
        def close(self): raise OSError("private payload must not escape")
    def fail(self, _chromium):
        profile.append(Path(self.profile.name))
        self.ws, self.process = Socket(), Process()
        raise PrimaryFailure("original startup failure")
    monkeypatch.setattr(browser.Browser, "_start", fail)
    monkeypatch.setattr(browser.os, "killpg", lambda pid, sig: events.append((pid, sig)))
    with pytest.raises(PrimaryFailure):
        browser.Browser("unused")
    assert events and "wait" in events and not profile[0].exists()


def test_nonfixture_backend_rejected_before_chromium_or_any_write(tmp_path, monkeypatch):
    browser = script("uji_browser")
    run_id = "a" * 32
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps({"run_id": run_id, "accounts": [{
        "username": "loadtest-" + run_id + "-user", "password": "private-password",
        "access_token": "private-token", "activity_id": "loadtest-" + run_id + "-activity-0"}]}))
    accounts.chmod(0o600)
    monkeypatch.setattr(browser.HTTP, "get", lambda *a, **k: SimpleNamespace(status_code=404))
    monkeypatch.setattr(browser.HTTP, "post", lambda *a, **k: pytest.fail("must never write to nonfixture backend"))
    monkeypatch.setattr(browser.Browser, "_start", lambda *a: pytest.fail("must reject before launching Chromium"))
    output = tmp_path / "public"
    with pytest.raises(AssertionError, match="fixture"):
        browser.run(SimpleNamespace(frontend="http://127.0.0.1:1", backend="http://127.0.0.1:2",
                                    accounts=accounts, output=output, chromium="unused"))
    report = json.loads((output / "hasil.json").read_text())
    assert not report["ok"] and report["stage"] == "fixture_identity" and report["error_class"] == "AssertionError"
    assert "private-password" not in (output / "hasil.json").read_text()


@pytest.mark.parametrize("drop_fails", [False, True])
def test_partial_seed_without_manifest_drops_only_reserved_database_and_keeps_primary(tmp_path, monkeypatch, drop_fails):
    ci = script("uji_browser_ci")
    databases = {"ordinary_database": {"assets"}}
    class Database:
        def __init__(self, name): self.name = name
        def create_collection(self, name): databases.setdefault(self.name, set()).add(name)
        def list_collection_names(self): return list(databases.get(self.name, []))
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def list_database_names(self): return list(databases)
        def __getitem__(self, name): return Database(name)
        def drop_database(self, name):
            if drop_fails:
                raise OSError("private cleanup failure")
            databases.pop(name)
    class SeedFailed(RuntimeError): pass
    def seed(*args, **kwargs):
        owned = next(name for name in databases if name.startswith("aman_ci_browser_"))
        databases[owned].add("partial_assets")
        raise SeedFailed("private seed failure")
    import pymongo
    monkeypatch.setattr(pymongo, "MongoClient", Client)
    monkeypatch.setattr(ci.subprocess, "run", seed)
    output = tmp_path / "public"
    private_paths = []
    make_temporary = ci.tempfile.mkdtemp
    def temporary(**kwargs):
        result = make_temporary(**kwargs)
        private_paths.append(Path(result))
        return result
    monkeypatch.setattr(ci.tempfile, "mkdtemp", temporary)
    with pytest.raises(SeedFailed):
        ci.run(SimpleNamespace(mongo="mongodb://127.0.0.1/", output=output, api_port=18127,
                               frontend_port=18827, skip_build=True, chromium="unused"))
    assert databases["ordinary_database"] == {"assets"}
    assert len(databases) == (2 if drop_fails else 1)
    assert private_paths and all(not path.exists() for path in private_paths)
    report = json.loads((output / "runner.json").read_text())
    assert report["stage"] == "seed" and report["error_class"] == "SeedFailed"
    assert report["cleanup_errors"] == ([{"action": "database", "error_class": "OSError"}] if drop_fails else [])


def test_parent_cleans_still_live_owned_browser_after_child_timeout(tmp_path):
    ci = script("uji_browser_ci")
    profile = tmp_path / "profile"
    profile.mkdir()
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    state = tmp_path / "browser.json"
    try:
        identity = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        state.write_text(json.dumps({"pid": process.pid, "process_start": "wrong-process", "profile": str(profile)}))
        with pytest.raises(ValueError, match="Identitas"):
            ci.cleanup_browser(state, tmp_path)
        assert process.poll() is None
        state.write_text(json.dumps({"pid": process.pid, "process_start": identity, "profile": str(profile)}))
        ci.cleanup_browser(state, tmp_path)
        assert process.wait(timeout=3) < 0 and not profile.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)


def test_public_failure_log_is_bounded_and_redacts_exact_seed_credentials(tmp_path):
    ci = script("uji_browser_ci")
    private, output = tmp_path / "private", tmp_path / "public"
    private.mkdir(); output.mkdir()
    secret = "exact-unique-seed-secret"
    (private / "backend.log").write_text("old noise" * 10000 + "\n" + secret + "\nAuthorization: Bearer abc.def.ghi\npassword=private-value\n")
    ci.public_diagnostics(private, output, [secret])
    text = (output / "backend.log").read_text()
    assert len(text) <= 65536 and secret not in text and "abc.def.ghi" not in text and "private-value" not in text
