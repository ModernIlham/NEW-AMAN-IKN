#!/usr/bin/env python3
"""Publish bounded test counts, without test output or fixture credentials."""
import argparse
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def diagnosa_browser(raw):
    """Di mana uji browser berhenti — hanya nilai berbentuk tetap.

    Dicetak ke log job saat uji gagal, supaya tahap dan barisnya terbaca tanpa
    mengunduh artefak. Yang lolos hanya nama tahap/kelas berpola sempit dan
    bilangan: `hasil.json` ditulis proses yang memegang akun sintetis, jadi
    teks bebas darinya tidak pernah diteruskan ke log.
    """
    def nama(nilai, pola):
        nilai = nilai if isinstance(nilai, str) else ""
        return nilai if re.fullmatch(pola, nilai) else ""

    def bilangan(nilai):
        return nilai if type(nilai) is int and 0 <= nilai <= 1000000 else 0

    checks = raw.get("checks")
    return {"stage": nama(raw.get("stage"), r"[a-z_]{1,40}"),
            "error_class": nama(raw.get("error_class"), r"[A-Za-z_]{1,60}"),
            "error_line": bilangan(raw.get("error_line")),
            "checks": len(checks) if isinstance(checks, list) else 0,
            "last_check": nama(checks[-1] if isinstance(checks, list) and checks else "",
                               r"[a-z0-9_]{1,80}")}


def summary(kind, path):
    path = Path(path)
    if kind == "junit":
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("./testsuite"))
        result = {key: sum(int(suite.get(key, "0")) for suite in suites)
                  for key in ("tests", "failures", "errors", "skipped")}
        result["passed"] = result["tests"] - sum(result[key] for key in ("failures", "errors", "skipped"))
        if not result["tests"] or result["failures"] or result["errors"] or result["passed"] < 1:
            raise ValueError("JUnit report is empty or contains failures")
    elif kind == "jest":
        raw = json.loads(path.read_text())
        if raw.get("success") is not True or raw.get("numFailedTests") or raw.get("numFailedTestSuites"):
            raise ValueError("Jest did not pass")
        result = {"tests": raw["numTotalTests"], "passed": raw["numPassedTests"],
                  "skipped": raw["numPendingTests"], "suites": raw["numPassedTestSuites"]}
        if result["passed"] < 1 or result["suites"] < 1:
            raise ValueError("Jest report is empty")
    else:
        raw = json.loads(path.read_text())
        if raw.get("ok") is not True:
            print("browser-gagal=" + json.dumps(diagnosa_browser(raw), separators=(",", ":")))
        offline = raw.get("offline") or {}
        if (raw.get("ok") is not True or raw.get("cleanup_errors") != []
                or not offline.get("backend_unchanged_while_offline")
                or not offline.get("second_reconnect_did_not_replay")):
            raise ValueError("Browser or offline verification did not pass")
        result = {"checks": len(raw["checks"]), "viewports_themes": len(raw["viewports"]),
                  "offline_once": True}
        if result["checks"] < 16 or result["viewports_themes"] != 8:
            raise ValueError("Browser coverage is incomplete")
    if any(type(value) is not bool and (type(value) is not int or not 0 <= value <= 1000000)
           for value in result.values()):
        raise ValueError("Invalid verification count")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["junit", "jest", "browser"])
    parser.add_argument("path")
    args = parser.parse_args()
    if args.kind == "browser" and not Path(args.path).exists():
        # Uji berhenti sebelum browser sempat menulis hasilnya (build, seed,
        # atau penyalaan server): tahapnya ada di catatan proses induk.
        induk = Path(args.path).with_name("runner.json")
        if induk.exists():
            print("browser-gagal=" + json.dumps(
                diagnosa_browser(json.loads(induk.read_text())), separators=(",", ":")))
        raise SystemExit("Hasil uji browser tidak ada")
    text = json.dumps(summary(args.kind, args.path), separators=(",", ":"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("summary=" + text + "\n")
    print(text)
