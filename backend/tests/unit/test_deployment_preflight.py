"""Bounded metadata-only deployment admission checks."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("deployment_preflight", ROOT / "scripts/releases/backend_environment.py")
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)


@pytest.mark.parametrize("free,total,minimum,accepted", [
    (3, 10, 3, True), (2, 10, 3, False), (3, 20, 3, False),
    (1, 5, 1, True), (1, 6, 1, False), (3, 0, 3, False),
])
def test_disk_headroom_preserves_absolute_and_relative_reserve(monkeypatch, free, total, minimum, accepted):
    gib = 1024**3
    monkeypatch.setattr(environment.os, "statvfs", lambda path: SimpleNamespace(
        f_blocks=total, f_bavail=free, f_frsize=gib,
    ))
    if accepted:
        proof = environment.disk_headroom(Path("/unused"), minimum*gib)
        assert proof == {"available_bytes":free*gib,"total_bytes":total*gib,"minimum_bytes":minimum*gib}
    else:
        with pytest.raises(ValueError, match="headroom"):
            environment.disk_headroom(Path("/unused"), minimum*gib)


@pytest.fixture
def process_metadata(tmp_path):
    app = tmp_path / "app"
    stable = app / "backend/venv/bin"
    stable.mkdir(parents=True)
    process = tmp_path / "proc/123"
    process.mkdir(parents=True)
    (process / "exe").symlink_to(Path(sys.executable).resolve())
    (process / "cwd").symlink_to(app / "backend")
    (process / "environ").write_bytes(b"AMAN_PRIVATE_SENTINEL=must-never-log\0")
    (process / "cmdline").write_bytes(os.fsencode(stable / "python") + b"\0" + os.fsencode(stable / "uvicorn") + b"\0server:app\0")
    (process / "stat").write_bytes(b"123 (name with spaces) S " + b"0 "*18 + b"1234 0\n")
    return SimpleNamespace(app=app,stable=stable,process=process,proc=process.parent)


def test_expected_process_is_accepted_without_printing_private_data(process_metadata, capsys):
    p = process_metadata
    environment.attest_process(p.app,123,sys.executable,p.proc)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("mutation", ["interpreter", "script", "cwd", "exe", "pythonpath", "stopped"])
def test_unproven_process_is_rejected(process_metadata, mutation):
    p = process_metadata
    if mutation in {"interpreter", "script"}:
        arguments = (p.process / "cmdline").read_bytes().split(b"\0")
        arguments[0 if mutation == "interpreter" else 1] = b"/foreign/bin/python"
        (p.process / "cmdline").write_bytes(b"\0".join(arguments))
    elif mutation in {"cwd", "exe"}:
        (p.process / mutation).unlink()
        (p.process / mutation).symlink_to(p.app)
    elif mutation == "pythonpath":
        (p.process / "environ").write_bytes(b"PYTHONPATH=/foreign\0")
    else:
        (p.process / "stat").write_bytes((p.process / "stat").read_bytes().replace(b") S ", b") T "))
    with pytest.raises(ValueError):
        environment.attest_process(p.app,123,sys.executable,p.proc)
