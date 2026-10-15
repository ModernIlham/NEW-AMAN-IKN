"""A production inventory can publish only a fixed non-sensitive value schema."""
from copy import deepcopy
import importlib.util
import json
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
