#!/usr/bin/env python3
"""Audit one complete hash lock using a separate pip-audit 2.9.0 environment.

No application dependencies are installed or changed. Advisory lookup failures,
skipped packages, incomplete reports and vulnerabilities all fail the gate.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

AUDITOR_VERSION = "2.9.0"


def lock_pins(path):
    """Read uv's resolved hash-lock grammar, retaining active PEP 508 markers."""
    pins, pending = {}, ""
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        continued = line.endswith("\\")
        pending += " " + (line[:-1] if continued else line)
        if continued:
            continue
        hashes = re.findall(r"--hash=\S+", pending)
        if not hashes or any(not re.fullmatch(r"--hash=sha256:[a-f0-9]{64}", item) for item in hashes):
            raise ValueError("Setiap resolved dependency wajib memiliki hash SHA256 yang sah")
        requirement = Requirement(re.sub(r"\s*--hash=\S+", "", pending).strip())
        pending = ""
        specs = list(requirement.specifier)
        if requirement.url or requirement.extras or len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
            raise ValueError("Audit hanya menerima resolved hash lock dengan versi exact")
        if requirement.marker and not requirement.marker.evaluate():
            continue
        key = canonicalize_name(requirement.name)
        if key in pins:
            raise ValueError("Resolved dependency duplikat: " + key)
        pins[key] = str(Version(specs[0].version))
    if pending or not pins:
        raise ValueError("Resolved hash lock kosong atau tidak lengkap")
    return pins


def validate_report(lock, output):
    expected = lock_pins(lock)
    document = json.loads(Path(output).read_text())
    rows = document.get("dependencies")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Report audit tidak lengkap: dependencies tidak ada")
    actual = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("skip_reason") or not row.get("version"):
            raise ValueError("Dependency dilewati atau tidak dapat diaudit")
        name = canonicalize_name(row["name"])
        if name in actual:
            raise ValueError("Dependency duplikat pada report audit")
        if not isinstance(row.get("vulns"), list) or row["vulns"]:
            raise ValueError("Report memuat advisory atau hasil advisory tidak lengkap")
        actual[name] = str(Version(row["version"]))
    if actual != expected:
        raise ValueError("Cakupan audit berbeda dari seluruh resolved hash lock")
    return len(actual)


def run_audit(lock, output):
    if importlib.metadata.version("pip-audit") != AUDITOR_VERSION:
        raise ValueError("Gunakan environment tooling terpisah dengan pip-audit==" + AUDITOR_VERSION)
    lock_pins(lock)  # Fail locally before any network contact for invalid inputs.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)  # Never upload/reuse an older successful report.
    # Cache exists only for this invocation. A weekly audit must fetch current
    # advisories, not restore last week's vulnerability responses from CI cache.
    with tempfile.TemporaryDirectory(prefix="aman-dependency-audit-") as cache:
        command = [sys.executable, "-m", "pip_audit", "--strict", "--no-deps",
                   "--disable-pip", "--require-hashes", "--vulnerability-service", "pypi",
                   "--timeout", "10", "--progress-spinner", "off", "--cache-dir", cache,
                   "--format", "json", "--output", str(output), "-r", str(lock)]
        result = subprocess.run(command, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError(f"pip-audit gagal (exit {result.returncode}); periksa advisory atau jaringan. Audit tidak lulus.")
    count = validate_report(lock, output)
    print(f"Audit lengkap: {count} dependency, 0 advisory, 0 skip, 0 ignore ({Path(lock).name})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_audit(args.lock, args.output)
    except (Exception, KeyboardInterrupt) as error:
        print("AUDIT GAGAL: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
