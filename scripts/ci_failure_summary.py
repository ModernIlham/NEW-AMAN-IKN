#!/usr/bin/env python3
"""Publish bounded JUnit failure identities; never publish messages or test output."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_FAILURES = 25
MAX_TESTS = 100000
API_URL = "https://api.github.com"


def safe_identifier(value):
    # Parametrization frequently contains fixture values or credentials.
    value = str(value or "").split("[", 1)[0]
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value) else "redacted_invalid_identifier"


def source_basename(case):
    value = case.get("file")
    if value:
        basename = re.split(r"[/\\]", value)[-1]
    else:
        modules = safe_identifier(case.get("classname")).split(".")
        basename = next((part + ".py" for part in reversed(modules) if part.startswith("test_")), "")
    return basename if re.fullmatch(r"test_[A-Za-z0-9_.-]{1,150}\.py", basename) else "redacted_invalid_source"


def failure_summary(path):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
    except FileNotFoundError:
        return {"report_state": "missing"}
    except (OSError, ValueError):
        return {"report_state": "unreadable"}
    if len(raw) > MAX_REPORT_BYTES:
        return {"report_state": "oversize"}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"report_state": "invalid"}
    # Only UTF-8 JUnit is admitted; reject NUL/UTF-16 and all DTD/entities.
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return {"report_state": "invalid"}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"report_state": "invalid"}
    if root.tag not in {"testsuite", "testsuites"}:
        return {"report_state": "invalid"}
    counts = dict(tests=0, passed=0, failures=0, errors=0, skipped=0)
    failed = []
    for case in root.iter("testcase"):
        counts["tests"] += 1
        if counts["tests"] > MAX_TESTS:
            return {"report_state": "oversize"}
        tags = {child.tag for child in case}
        kind = "error" if "error" in tags else "failure" if "failure" in tags else None
        if kind:
            counts["errors" if kind == "error" else "failures"] += 1
            if len(failed) < MAX_FAILURES:
                failed.append({"test_file": source_basename(case),
                               "class_name": safe_identifier(case.get("classname")),
                               "test_name": safe_identifier(case.get("name")),
                               "failure_type": kind})
        elif "skipped" in tags:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    return {"report_state": "parsed", "counts": counts, "failed_tests": failed,
            "omitted_failures": counts["failures"] + counts["errors"] - len(failed)}


def check_payload(report, name, sha):
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("invalid_sha")
    return {"name": name, "head_sha": sha, "status": "completed", "conclusion": "failure",
            "output": {"title": "Bounded JUnit failure identities",
                       "summary": "```json\n" + json.dumps(report, ensure_ascii=True, separators=(",", ":")) + "\n```"}}


def publish_check(payload, repository, token, opener=None):
    request = urllib.request.Request(API_URL + "/repos/" + repository + "/check-runs",
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "AMAN-bounded-CI-failure-summary"})
    # A redirect must never forward the token to a different endpoint.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    send = opener or urllib.request.build_opener(NoRedirect()).open
    with send(request, timeout=15) as response:
        if response.status != 201:
            raise ValueError("unexpected_status")
        # Response bodies can contain API/user data; they are not printed/read.


def main(argv=None, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True)
    parser.add_argument("--check-name", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--repository")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    sha = args.expected_sha.lower()
    context_sha = env.get("GITHUB_SHA", "").lower()
    repository = args.repository or env.get("GITHUB_REPOSITORY", "")
    valid_context = (re.fullmatch(r"[a-f0-9]{40}", sha) and sha == context_sha
                     and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", repository)
                     and env.get("GITHUB_API_URL", API_URL).rstrip("/") == API_URL
                     and re.fullmatch(r"[A-Za-z0-9 ._():/-]{1,100}", args.check_name)
                     and (not env.get("GITHUB_REPOSITORY") or repository == env["GITHUB_REPOSITORY"]))
    if not valid_context or not env.get("GITHUB_TOKEN"):
        print('{"published":false,"reason":"invalid_context_or_missing_token"}', file=sys.stderr)
        return 2
    report = failure_summary(args.junit)
    try:
        publish_check(check_payload(report, args.check_name, sha), repository, env["GITHUB_TOKEN"])
    except urllib.error.HTTPError as error:
        print(json.dumps({"published": False, "reason": "http_error", "status": error.code}), file=sys.stderr)
        return 1
    except Exception:
        print('{"published":false,"reason":"publish_failed"}', file=sys.stderr)
        return 1
    print('{"published":true}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
