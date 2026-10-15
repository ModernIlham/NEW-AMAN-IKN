"""A production inventory can publish only a fixed non-sensitive value schema."""
from copy import deepcopy
import importlib.util
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("aman_inventory", ROOT / "scripts/inventaris_vps_json.py")
inv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inv)


@pytest.fixture
def report(monkeypatch, tmp_path):
    monkeypatch.setattr(inv, "APP", tmp_path)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/.env").write_text("MONGO_URL=mongodb://SENTINEL_USER:SENTINEL_PASSWORD@private-host/db\nDB_NAME=private_db\nREDIS_URL=redis://SENTINEL_PASSWORD@private-host\n")
    def command(args, timeout=10):
        if args[0] == "systemctl":
            return "active\n", "", 0
        if args[0] == "supervisorctl":
            return "inventarisasi-backend RUNNING pid 42 SENTINEL_USERNAME", "", 0
        if args[0] == "git":
            return "a" * 40, "", 0
        return "v24.19.0 SENTINEL_PASSWORD private-host", "", 0
    monkeypatch.setattr(inv, "command", command)
    class Collection:
        def list_indexes(self):
            return [{"name": "_id_", "secret": "SENTINEL_PASSWORD"}]
        def find_one(self, query):
            return None
        def count_documents(self, query):
            return 0
    class DB:
        write_concern = SimpleNamespace(acknowledged=True)
        def command(self, name):
            assert name == "ping"
            return {"ok": 1}
        def list_collection_names(self):
            return ["SENTINEL_INTERNAL_COLLECTION"]
        def __getitem__(self, name):
            return Collection()
        def __getattr__(self, name):
            return Collection()
    class Client:
        admin = SimpleNamespace(command=lambda name: {"setName": "SENTINEL_REPLICA_NAME"})
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def __getitem__(self, name):
            return DB()
        def server_info(self):
            return {"version": "7.0.30", "host": "SENTINEL_HOST"}
    import pymongo
    monkeypatch.setattr(pymongo, "MongoClient", Client)
    def no_health(*args, **kwargs):
        raise OSError("SENTINEL_HEALTH_INTERNAL_ERROR")
    monkeypatch.setattr(inv, "urlopen", no_health)
    return inv.collect()


def test_collect_publishes_only_typed_whitelist_and_version_not_raw_output(report):
    text = inv.validate_report(report)
    assert "SENTINEL" not in text and "private-host" not in text
    assert "mongodb://" not in text and "redis://" not in text
    assert report["software"]["node"] == "24.19.0"
    assert report["configuration_presence"]["redis_configured"] is True
    assert report["mongo"]["topology"] == "replica_set"
    assert report["mongo"]["indexes"] == 1
    assert report["backend_supervisor_state"] == "RUNNING"
    assert report["capacity_claim"] == "inventory_only_not_a_load_test"


@pytest.mark.parametrize("section,key,value", [
    ("release", "backend_git_sha", "SENTINEL_PASSWORD"),
    ("software", "node", "mongodb://secret@private-host"),
    ("services", "nginx", "SENTINEL_USERNAME"),
    ("mongo", "restore_state", "SENTINEL_USERNAME"),
    ("configuration_presence", "redis_configured", "SECRET"),
    ("system", "memory_total_bytes", "SECRET"),
])
def test_validation_rejects_injected_sensitive_or_untyped_values(report, section, key, value):
    report[section][key] = value
    with pytest.raises(ValueError):
        inv.validate_report(report)


def test_validation_rejects_new_arbitrary_fields(report):
    report["mongo"]["uri"] = "mongodb://secret@private-host"
    with pytest.raises(ValueError):
        inv.validate_report(report)


def test_mongo_exception_can_never_be_published(report, monkeypatch):
    # Unknown exception contents are not part of the schema at all.
    assert all("error" not in key for key in report["mongo"])
    assert len(inv.validate_report(report).encode()) < inv.MAX_OUTPUT


def test_known_static_chunk_reports_manifest_ledger_and_bytes_independently(tmp_path):
    app=tmp_path/"app";nginx=tmp_path/"nginx"
    current=app/"frontend/build";previous=app/"frontend/build.old"
    current.mkdir(parents=True);(previous/"static/js").mkdir(parents=True)
    payload=b"known public hashed javascript"
    checksum=hashlib.sha256(payload).hexdigest()
    main="static/js/main.abcdef123456.js"
    (previous/inv.KNOWN_OLD_CHUNK).write_bytes(payload)
    (previous/main).write_bytes(payload)
    (current/"asset-manifest.json").write_text(json.dumps({"files":{"main.js":"/static/js/other.12345678.js"}}))
    (previous/"asset-manifest.json").write_text(json.dumps({"files":{"known":"/"+inv.KNOWN_OLD_CHUNK,"main.js":"/"+main}}))
    (current/".aman-static-retention.json").write_text(json.dumps({"schema_version":1,"created_at":1000,"grace_hours":24,"assets":{main:{"sha256":checksum,"bytes":len(payload),"last_seen":700}}}))
    (previous/".aman-static-retention.json").write_text(json.dumps({"schema_version":1,"created_at":900,"assets":{inv.KNOWN_OLD_CHUNK:{"sha256":checksum,"bytes":len(payload),"last_seen":800}}}))
    (nginx/"sites-enabled").mkdir(parents=True)
    (nginx/"sites-enabled/default").write_text(f"# SENTINEL_SECRET\nroot {current};\nlocation /static/ {{ alias {previous}/static/; }}")
    data=inv.static_retention_inventory(app,nginx)
    assert data["current"]["file_present"] is False
    assert data["current"]["own_manifest_contains"] is False
    assert data["current"]["ledger_contains"] is False
    assert data["previous"]["file_sha256"]==checksum
    assert data["previous"]["file_bytes"]==len(payload)
    assert data["previous"]["own_manifest_contains"] is True
    assert data["previous"]["ledger_last_seen_epoch"]==800
    assert data["previous"]["ledger_created_epoch"]==900
    assert data["current"]["ledger_grace_hours"]==24
    assert data["previous"]["own_manifest_sha256"]==hashlib.sha256((previous/"asset-manifest.json").read_bytes()).hexdigest()
    assert data["previous"]["own_js_sample"][0]=={"path":main,"file_bytes":len(payload),"file_sha256":checksum,"current_ledger_contains":True,"current_ledger_sha256":checksum,"current_ledger_last_seen_epoch":700}
    assert data["nginx_flags"]["current_root_mentioned"] is True
    assert data["nginx_flags"]["previous_static_alias_mentioned"] is True
    assert data["nginx_flags"]["loaded_config_attested"] is False
    assert "SENTINEL" not in json.dumps(data)
    assert str(tmp_path) not in json.dumps(data)


def test_static_inventory_rejects_arbitrary_digest_or_new_fields(report):
    report["static_retention"]["previous"]["ledger_sha256"]="SENTINEL_SECRET"
    with pytest.raises(ValueError):inv.validate_report(report)


def test_static_sample_validator_accepts_only_three_public_hashed_js_paths(report):
    sample={"path":"static/js/main.12345678.js","file_sha256":"a"*64,"file_bytes":1,"current_ledger_contains":True,"current_ledger_sha256":"a"*64,"current_ledger_last_seen_epoch":123}
    report["static_retention"]["previous"]["own_js_sample"]=[sample]
    inv.validate_report(report)
    for invalid in ("../../../SENTINEL", "https://SENTINEL", "static/js/SENTINEL.js"):
        sample["path"]=invalid
        with pytest.raises(ValueError):inv.validate_report(report)


def test_nginx_inventory_skips_symlink_outside_fixed_config_root(tmp_path):
    nginx=tmp_path/"nginx";(nginx/"sites-enabled").mkdir(parents=True)
    app=tmp_path/"app"
    secret=tmp_path/"outside";secret.write_text(f"root {app}/frontend/build.old; SENTINEL_SECRET")
    (nginx/"sites-enabled/outside").symlink_to(secret)
    flags=inv.static_retention_inventory(app,nginx)["nginx_flags"]
    assert flags["enabled_config_readable"] is False
    assert flags["previous_root_mentioned"] is False


def test_new_workflow_is_manual_readonly_with_checks_permission_and_exact_sha():
    source = (ROOT / ".github/workflows/inventaris-vps-json.yml").read_text()
    parsed = yaml.safe_load(source)
    assert set(parsed.get("on", parsed.get(True))) == {"workflow_dispatch"}
    assert parsed["permissions"] == {"contents": "read", "checks": "write"}
    assert parsed["concurrency"]["group"] == "deploy-vps"
    assert "scripts/inventaris_vps_json.py --validate" in source
    assert "head_sha: sha" in source and "process.env.GITHUB_SHA" in source
    assert "48 * 1024" in source and "github.rest.checks.create" in source
    assert "installed-software" not in source and "printenv" not in source


def test_readonly_script_does_not_write_or_execute_mutating_commands():
    import ast
    tree = ast.parse((ROOT / "scripts/inventaris_vps_json.py").read_text())
    writes = {"write_text", "write_bytes", "unlink", "mkdir", "rmdir", "rename",
              "update_one", "update_many", "insert_one", "insert_many", "delete_one", "delete_many", "drop_database"}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not [node.func.attr for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr in writes]

    assert not [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "replace" and not any(keyword.arg == "tzinfo" for keyword in node.keywords)]


@pytest.mark.parametrize("http_status,mongo_ok,redis_ok,index_ok", [(503, False, True, True), (200, True, False, False)])
def test_health_distinguishes_primary_failure_optional_warning_and_maintenance(report, monkeypatch, http_status, mongo_ok, redis_ok, index_ok):
    from io import BytesIO
    from urllib.error import HTTPError
    body = json.dumps({"ok": mongo_ok, "checks": {
        "mongodb": {"ok": mongo_ok, "latency_ms": 1.2, "error": "SENTINEL_SECRET"},
        "gridfs": {"ok": mongo_ok, "latency_ms": 0.8},
        "redis": {"ok": redis_ok, "latency_ms": 0.4},
        "indexes": {"ok": index_ok, "gagal": int(not index_ok), "detail": ["SENTINEL_SECRET"]},
        "pemeliharaan": {"aktif": True}}}).encode()
    def response(*a, **k):
        error = HTTPError("http://127.0.0.1:8001/api/health/deep", http_status, "ignored", {}, BytesIO(body))
        if http_status == 503:
            raise error
        return error
    monkeypatch.setattr(inv, "urlopen", response)
    data = inv.collect()
    assert data["health"]["http_status"] == http_status
    assert data["health"]["mongodb_ok"] == mongo_ok
    assert data["health"]["redis_ok"] == redis_ok
    assert data["health"]["indexes_ok"] == index_ok
    assert data["health"]["maintenance"] is True
    assert "SENTINEL_SECRET" not in inv.validate_report(data)
