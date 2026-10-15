"""Guard target dan bukti data/artifact diuji tanpa mengirim beban ke produksi."""
import importlib.util
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import requests

ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/"scripts/loadtest"
sys.path.insert(0,str(HERE))
from contracts import csv_artifact, duration_seconds, list_result, load_pool, safe_host,transport_exception_kind
from fake_api import FixtureAPI
from run import evaluate_csv, preflight
from seed import PNG, safe_database


def response(data,status=200,content_type="application/json"):
    result=requests.Response()
    result.status_code=status
    result.headers["Content-Type"]=content_type
    result._content=data if isinstance(data,bytes) else json.dumps(data).encode()
    result._content_consumed=True
    return result


@pytest.mark.parametrize("host",["https://amanikn-inventarisasi.com","https://www.amanikn-inventarisasi.com",
    "https://AMANIKN-INVENTARISASI.COM.","https://staging.amanikn-inventarisasi.com"])
def test_production_denied_even_if_accidentally_allowlisted(host):
    with pytest.raises(ValueError,match="produksi"):
        safe_host(host,"amanikn-inventarisasi.com,www.amanikn-inventarisasi.com,staging.amanikn-inventarisasi.com")


@pytest.mark.parametrize("host",["https://unexpected.example","http://staging.example","https://user:password@staging.example",
    "https://staging.example/path","https://staging.example?x=y","file:///tmp/data","http://127.0.0.1:99999"])
def test_invalid_or_unapproved_origin_never_accepted(host):
    with pytest.raises(ValueError):
        safe_host(host,"staging.example")


def test_only_explicit_staging_or_loopback_accepted():
    assert safe_host("http://127.0.0.1:8002")=="http://127.0.0.1:8002"
    assert safe_host("https://staging.example","staging.example")=="https://staging.example"


def test_transport_diagnostics_only_use_bounded_types_never_secret_messages_or_dynamic_names():
    from http.client import RemoteDisconnected
    from urllib3.exceptions import ProtocolError
    error=requests.ConnectionError(ProtocolError("https://private-url?token=secret",RemoteDisconnected("Bearer secret")))
    assert transport_exception_kind(error)=="ConnectionError>ProtocolError>RemoteDisconnected"
    malicious=type("private-nip-and-token-secret",(Exception,),{})("private body",error)
    key=transport_exception_kind(malicious)
    assert key.startswith("OtherTransportError>")
    assert "private" not in key and "secret" not in key
    reset=ConnectionResetError(104,"sensitive host and credential")
    assert transport_exception_kind(reset)=="ConnectionResetError(errno=104)"


@pytest.mark.parametrize("duration",["0s","-1m","31m","2s","1h","5m;cmd","nan"])
def test_duration_resource_bounds(duration):
    with pytest.raises(ValueError):
        duration_seconds(duration)


def test_seed_requires_disposable_loopback_database():
    assert safe_database("mongodb://127.0.0.1:27017/","aman_ci_fixture123")=="aman_ci_fixture123"
    for url,database in [("mongodb://example.test/","aman_ci_fixture123"),("mongodb://127.0.0.1/","inventaris_bmn")]:
        with pytest.raises(ValueError):
            safe_database(url,database)


def test_seed_media_is_a_valid_image_fixture():
    from PIL import Image
    Image.open(io.BytesIO(base64.b64decode(PNG.split(",",1)[1]))).verify()


def test_synthetic_generator_import_does_not_initialize_runtime_db_or_limiter():
    code='from scripts.synthdata import generate_assets; import sys; assert not {"db","shared_utils","redis_utils"}.intersection(sys.modules); assert len(generate_assets(2))==2'
    result=subprocess.run([sys.executable,"-c",code],cwd=ROOT/"backend",capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert not result.stderr


def test_account_pool_missing_scope_or_nonprivate_file_rejected(tmp_path):
    path=tmp_path/"accounts.json"
    path.write_text(json.dumps({"accounts":[{"username":"fixture","password":"fixture"}]}))
    path.chmod(0o600)
    with pytest.raises(ValueError,match="activity_id"):
        load_pool(str(path))
    path.write_text(json.dumps({"accounts":[{"username":"fixture","access_token":"fixture","activity_id":"fixture"}]}))
    assert load_pool(str(path))[0]["activity_id"]=="fixture"
    if os.name!="nt":
        path.chmod(0o644)
        with pytest.raises(ValueError,match="privat"):
            load_pool(str(path))


@pytest.mark.parametrize("status",[401,422,500])
def test_non200_responses_never_pass_domain_assertion(status):
    with pytest.raises(ValueError):
        list_result(response({"items":[],"total":0},status))


def test_partial_or_cross_activity_list_fails_even_with_http200():
    row={"id":"a","activity_id":"own"}
    with pytest.raises(ValueError,match="parsial"):
        list_result(response({"items":[row],"total":2,"page_size":10,"page":1}))
    with pytest.raises(ValueError,match="Isolasi"):
        list_result(response({"items":[row],"total":1}),activity="foreign")


@pytest.mark.parametrize("body,ctype",[(b'{"detail":"error"}',"application/json"),
    (b"wrong,header\n1,2\n","text/csv"),(b"asset_code,asset_name,NUP\n","text/csv"),
    (b"asset_code,asset_name,NUP\nLT.1,A,1,extra\n","text/csv")])
def test_fake_or_partial_artifact_is_failure(body,ctype):
    with pytest.raises(ValueError):
        csv_artifact(response(body,content_type=ctype),expected=1)


def test_valid_csv_exact_count_and_bounded_read():
    body=b"# Kegiatan: fixture\nasset_code,asset_name,NUP\nLT.1,A,1\n"
    assert csv_artifact(response(body,content_type="text/csv"),expected=1)["rows"]==1
    with pytest.raises(ValueError,match="batas"):
        csv_artifact(response(body,content_type="text/csv"),maximum=5)
    with pytest.raises(ValueError,match="jumlah"):
        csv_artifact(response(body,content_type="text/csv"),expected=2)


def test_real_http_preflight_checks_server_snapshot_and_actual_export():
    with FixtureAPI() as api:
        accounts=[{"username":"fixture","access_token":"fixture-only-token","activity_id":"fixture-only-activity"}]
        manifest={"run_id":"fixture-only","activities":[{"id":"fixture-only-activity","count":1}]}
        report=preflight(api.host,accounts,manifest,heavy=True)
        assert report[0]["snapshot_verified_total"]==1
        assert report[0]["csv"]["rows"]==1
        assert {"/api/assets/offline-snapshot","/api/export/csv"}.issubset(api.requests)
        manifest["activities"][0]["count"]=2
        with pytest.raises(ValueError,match="Jumlah dataset"):
            preflight(api.host,accounts,manifest)


def test_runner_refuses_production_before_credentials_or_http(tmp_path):
    result=subprocess.run([sys.executable,str(HERE/"run.py"),"--host","https://amanikn-inventarisasi.com", "--output",str(tmp_path/"unused")],capture_output=True,text=True)
    assert result.returncode==2 and "produksi" in result.stderr
    assert not list(tmp_path.iterdir())


def test_threshold_failure_and_no_requests_cannot_report_success(tmp_path):
    prefix=tmp_path/"result"
    path=tmp_path/"result_stats.csv"
    path.write_text('Type,Name,Request Count,Failure Count,50%,95%,99%,Requests/s\n,Aggregated,100,1,10,30,50,5\n')
    assert evaluate_csv(prefix,.01,2000)["thresholds_passed"] is False
    path.write_text('Type,Name,Request Count,Failure Count,50%,95%,99%,Requests/s\n,Aggregated,100,0,10,3000,5000,5\n')
    assert evaluate_csv(prefix,.01,2000)["thresholds_passed"] is False
    path.write_text('Type,Name,Request Count,Failure Count,50%,95%,99%,Requests/s\n,Aggregated,0,0,0,0,0,0\n')
    with pytest.raises(ValueError,match="Tidak ada request"):
        evaluate_csv(prefix,.01,2000)


def test_workflow_pins_tool_and_does_not_swallow_dry_run_or_interpolate_input():
    workflow=(ROOT/".github/workflows/loadtest.yml").read_text()
    assert "|| true" not in workflow and "exit-code-on-error 0" not in workflow
    assert "${{ github.event.inputs." not in workflow
    assert "pip install -r scripts/loadtest/requirements.txt" in workflow
    assert (HERE/"requirements.txt").read_text().splitlines()[-1]=="locust==2.37.14"
    assert "AMAN_STAGING_HOSTS: ${{ vars.LOADTEST_STAGING_HOSTS }}" in workflow
