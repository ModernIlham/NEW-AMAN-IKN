import importlib.util
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/ci_failure_summary.py"
spec = importlib.util.spec_from_file_location("ci_failure_summary", SCRIPT)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
SHA = "a" * 40


def test_synthetic_junit_failure_published_over_real_http_without_secrets(tmp_path):
    secret = "SYNTHETIC_SECRET_MUST_NOT_LEAVE_REPORT"
    root = ET.Element("testsuite", tests="999999999", failures="999999999")
    for index in range(30):
        case = ET.SubElement(root, "testcase", file="/private/" + secret + "/test_scope.py",
                             classname="backend.tests.test_scope.TestCase[" + secret + "]",
                             name=f"test_scope_{index}[{secret}]", token=secret)
        ET.SubElement(case, "failure", message=secret, type=secret).text = "Traceback " + secret
        ET.SubElement(case, "system-out").text = secret
    ET.SubElement(root, "testcase", name="test_passed", classname="backend.tests.test_scope")
    report = tmp_path / "report.xml"
    ET.ElementTree(root).write(report)
    result = summary.failure_summary(report)
    assert result["counts"] == dict(tests=31, passed=1, failures=30, errors=0, skipped=0)
    assert len(result["failed_tests"]) == 25 and result["omitted_failures"] == 5
    assert result["failed_tests"][0] == dict(test_file="test_scope.py", class_name="backend.tests.test_scope.TestCase", test_name="test_scope_0", failure_type="failure", failure_line=None)
    captured = []
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(201); self.end_headers()
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def local_transport(request, timeout):
        # Only the test seam changes destination; CLI always uses api.github.com.
        local = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/check-runs", data=request.data, method="POST")
        return urllib.request.urlopen(local, timeout=timeout)
    try:
        summary.publish_check(summary.check_payload(result, "Contract failure details", SHA), "owner/repo", "synthetic-token", opener=local_transport)
    finally:
        server.shutdown(); server.server_close(); thread.join(2)
    assert len(captured) == 1
    assert secret.encode() not in captured[0]
    payload = json.loads(captured[0])
    assert payload["head_sha"] == SHA and payload["conclusion"] == "failure"
    assert len(captured[0]) < 15000


def test_missing_invalid_and_untrusted_identifiers_are_typed(tmp_path):
    assert summary.failure_summary(tmp_path / "missing.xml") == {"report_state": "missing"}
    report = tmp_path / "bad.xml"
    report.write_text('<!DOCTYPE x [<!ENTITY x "secret">]><testsuite/>')
    assert summary.failure_summary(report) == {"report_state": "invalid"}
    report.write_text('<testsuite><testcase file="/private/credentials.txt" classname="bad name" name="bad`name"><error message="secret"/></testcase></testsuite>')
    item = summary.failure_summary(report)["failed_tests"][0]
    assert item == dict(test_file="redacted_invalid_source", class_name="redacted_invalid_identifier", test_name="redacted_invalid_identifier", failure_type="error", failure_line=None)


def test_context_rejects_invalid_or_mismatched_sha_without_network(monkeypatch, capsys):
    monkeypatch.setattr(summary, "publish_check", lambda *args: (_ for _ in ()).throw(AssertionError("must not publish")))
    env = dict(GITHUB_TOKEN="synthetic-secret", GITHUB_REPOSITORY="owner/repo", GITHUB_SHA=SHA)
    for sha in ["not-a-sha", "b" * 40]:
        assert summary.main(["--junit", "missing", "--check-name", "Contract failure details", "--expected-sha", sha], env) == 2
    assert "synthetic-secret" not in capsys.readouterr().err


def test_valid_cli_context_and_missing_report_publish_no_paths_or_token(monkeypatch, capsys, tmp_path):
    captured = []
    monkeypatch.setattr(summary, "publish_check", lambda *args: captured.append(args))
    report_path = tmp_path / "SYNTHETIC_PRIVATE_PATH.xml"
    env = dict(GITHUB_TOKEN="SYNTHETIC_SECRET_TOKEN", GITHUB_REPOSITORY="owner/repo", GITHUB_SHA=SHA)
    assert summary.main(["--junit", str(report_path), "--check-name", "Contract failure details", "--expected-sha", SHA], env) == 0
    payload, repository, token = captured[0]
    assert payload["head_sha"] == SHA and repository == "owner/repo" and token == env["GITHUB_TOKEN"]
    assert json.loads(payload["output"]["summary"].split("\n")[1]) == {"report_state": "missing"}
    assert "SYNTHETIC_PRIVATE_PATH" not in json.dumps(payload)
    output = capsys.readouterr()
    assert "SYNTHETIC_SECRET_TOKEN" not in output.out + output.err
    report_path.write_bytes('<!DOCTYPE x [<!ENTITY x "secret">]><testsuite/>'.encode("utf-16"))
    assert summary.failure_summary(report_path) == {"report_state": "invalid"}


def test_trace_extracts_only_last_bounded_same_file_line_without_message(tmp_path):
    secret = "SYNTHETIC_SECRET_TRACE_ASSERTION_EXPECTED_ACTUAL"
    root = ET.Element("testsuite")
    case = ET.SubElement(root, "testcase", file="backend/tests/contract/test_scope.py", classname="backend.tests.contract.test_scope", name="test_scope[" + secret + "]")
    failure = ET.SubElement(case, "failure", message=secret)
    failure.text = (secret + "\nbackend/tests/contract/test_scope.py:17: assertion " + secret
                    + "\nbackend/tests/contract/test_other.py:100: foreign assertion " + secret
                    + "\ntest_scope.py:42: expected " + secret + " actual " + secret
                    + "\ntest_scope.py:0\ntest_scope.py:100001\ntest_scope.py:9999999")
    report = tmp_path / "trace.xml"
    ET.ElementTree(root).write(report)
    result = summary.failure_summary(report)
    assert result["failed_tests"][0]["failure_line"] == 42
    published = json.dumps(summary.check_payload(result, "Contract failure details", SHA))
    assert secret not in published and "assertion" not in published and "test_other.py" not in published
    failure.text = "backend/tests/contract/test_other.py:90: " + secret
    ET.ElementTree(root).write(report)
    assert summary.failure_summary(report)["failed_tests"][0]["failure_line"] is None
