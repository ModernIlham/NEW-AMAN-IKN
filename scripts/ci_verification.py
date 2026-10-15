#!/usr/bin/env python3
"""Publish bounded test counts, without test output or fixture credentials."""
import argparse
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET


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
    text = json.dumps(summary(args.kind, args.path), separators=(",", ":"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("summary=" + text + "\n")
    print(text)
