"""The advisory gate cannot turn partial/unavailable coverage into success."""
import json
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("aman_audit_gate", Path(__file__).resolve().parents[3] / "scripts/audit_dependencies.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
lock_pins, validate_report = gate.lock_pins, gate.validate_report


@pytest.fixture
def audit_files(tmp_path):
    lock, report = tmp_path / "runtime.lock", tmp_path / "audit.json"
    lock.write_text("some-package==1.2.3 \\\n    --hash=sha256:" + "a" * 64 + "\n")
    report.write_text(json.dumps({"dependencies": [{"name": "some_package", "version": "1.2.3", "vulns": []}]}))
    return lock, report


def test_complete_hashlock_and_audit_report_pass(audit_files):
    lock, report = audit_files
    assert validate_report(lock, report) == 1


@pytest.mark.parametrize("rows", [[],
    [{"name": "some-package", "skip_reason": "PyPI unavailable"}],
    [{"name": "some-package", "version": "1.2.4", "vulns": []}],
    [{"name": "some-package", "version": "1.2.3", "vulns": [{"id": "CVE-test"}]}],
    [{"name": "some-package", "version": "1.2.3"}],
    [{"name": "other-package", "version": "1.2.3", "vulns": []}],
    [{"name": "some-package", "version": "1.2.3", "vulns": []}] * 2])
def test_incomplete_skipped_vulnerable_or_wrong_reports_fail(audit_files, rows):
    lock, report = audit_files
    report.write_text(json.dumps({"dependencies": rows}))
    with pytest.raises(ValueError):
        validate_report(lock, report)


@pytest.mark.parametrize("content", ["", "some-package>=1.2.3\n", "some-package==1.2.3\n",
    "some-package==1.2.3 \\\n    --hash=md5:aaaaaaaa\n"])
def test_incomplete_or_unhashed_inputs_fail(tmp_path, content):
    lock = tmp_path / "invalid.lock"
    lock.write_text(content)
    with pytest.raises(ValueError):
        lock_pins(lock)
