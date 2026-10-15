"""Execute manual budget-workflow guards with isolated Git/API/SSH boundaries."""
import copy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github/workflows/activate-export-budget.yml"
SOURCE = WORKFLOW.read_text()
CONFIG = yaml.safe_load(SOURCE)
STEPS = CONFIG["jobs"]["budget"]["steps"]
BY_ID = {step["id"]:step for step in STEPS if "id" in step}
SHA = "a" * 40
APPROVED = {"head_sha":SHA,"head_branch":"main","event":"push","status":"completed","conclusion":"success"}


def shell(source, directory, environment, *arguments):
    return subprocess.run(["bash","-s","--",*arguments],input=source,cwd=directory,
                          env=dict(os.environ,**environment),capture_output=True,text=True,timeout=10)


@pytest.fixture
def boundaries(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    script = (
        "#!/usr/bin/env python3\nimport json,os,pathlib,sys\n"
        "name=pathlib.Path(sys.argv[0]).name\n"
        "with pathlib.Path(os.environ['CALLS']).open('a') as log:log.write(json.dumps([name,*sys.argv[1:]])+'\\n')\n"
        "if name=='git':\n"
        "    if sys.argv[1:]==['rev-parse','HEAD']:print(os.environ['FAKE_HEAD'])\n"
        "    if sys.argv[1:3]==['merge-base','--is-ancestor'] and os.environ.get('BAD_ANCESTRY'):raise SystemExit(1)\n"
        "elif name=='curl':print(pathlib.Path(os.environ['CI_FIXTURE']).read_text())\n"
        "else:raise SystemExit(99)\n"
    )
    for name in ["git","curl"]:
        path = binary / name
        path.write_text(script)
        path.chmod(0o755)
    controller = tmp_path / "scripts/activate_export_budget.py"
    controller.parent.mkdir()
    controller.write_text("AMAN_EXPORT_BUDGET_PROTOCOL=1\n")
    response = tmp_path / "ci.json"
    response.write_text(json.dumps({"workflow_runs":[APPROVED]}))
    environment = {"PATH":str(binary)+os.pathsep+os.environ["PATH"],"CALLS":str(tmp_path / "calls"),
        "FAKE_HEAD":SHA,"CI_FIXTURE":str(response),"EXPECTED_SHA":SHA,"RUNNER_TEMP":str(tmp_path),
        "GITHUB_API_URL":"https://api.example.test","GITHUB_REPOSITORY":"owner/repository","GH_TOKEN":"DO_NOT_LOG_THIS"}
    return tmp_path,environment,response


def test_workflow_is_manual_serialized_immutable_and_does_not_forward_raw_output():
    assert set(CONFIG.get("on",CONFIG.get(True))) == {"workflow_dispatch"}
    assert CONFIG["permissions"] == {"contents":"read","actions":"read","checks":"write"}
    assert CONFIG["concurrency"] == {"group":"deploy-vps","cancel-in-progress":False}
    checkout = next(step for step in STEPS if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["ref"] == "${{ steps.validate.outputs.sha }}"
    assert STEPS.index(BY_ID["validate"]) < STEPS.index(checkout) < STEPS.index(BY_ID["approval"]) < STEPS.index(BY_ID["remote"])
    assert BY_ID["remote"]["if"] == "${{ steps.approval.outcome == 'success' }}"
    for step in STEPS:
        if "run" in step:
            assert "${{" not in step["run"]
    remote = BY_ID["remote"]["run"]
    assert remote.count("\nssh -i ") == 1
    assert '2> "$RUNNER_TEMP/budget-ssh.stderr"' in remote
    assert '> "$RUNNER_TEMP/budget-remote.raw"' in remote
    assert "tee " not in remote and "ssh-keyscan" not in remote
    assert "for attempt" not in remote and "set -x" not in SOURCE
    for secret in ["VPS_HOST","VPS_USER","VPS_PORT","VPS_SSH_KEY"]:
        assert BY_ID["remote"]["env"][secret] == "${{ secrets."+secret+" }}"
    assert "base64 -d" in remote and "ssh-keygen -y" in remote


@pytest.mark.parametrize("changes,success", [
    ({},True),({"EXPECTED_SHA_INPUT":"b"*40},False),({"EXPECTED_SHA_INPUT":"main"},False),
    ({"GITHUB_REF":"refs/heads/feature"},False),({"GITHUB_EVENT_NAME":"push"},False),
    ({"OPERATION_INPUT":"rollback"},False),({"OPERATION_INPUT":"arbitrary"},False),
    ({"JOURNAL_INPUT":"budget-a';touch injected"},False),
    ({"OPERATION_INPUT":"activate"},True),
])
def test_input_guard_executes_before_checkout(tmp_path,changes,success):
    output = tmp_path / "outputs"
    environment = {"EXPECTED_SHA_INPUT":SHA,"GITHUB_SHA":SHA,"GITHUB_REF":"refs/heads/main",
        "GITHUB_EVENT_NAME":"workflow_dispatch","GITHUB_RUN_ID":"12345","OPERATION_INPUT":"check",
        "JOURNAL_INPUT":"","GITHUB_OUTPUT":str(output)}
    environment.update(changes)
    result = shell(BY_ID["validate"]["run"],tmp_path,environment)
    assert (result.returncode == 0) is success
    if success:
        assert "sha="+SHA in output.read_text()
        if environment["OPERATION_INPUT"] == "activate":assert "journal=budget-12345" in output.read_text()
    else:
        assert not output.exists()
    assert not (tmp_path / "injected").exists()


@pytest.mark.parametrize("field,value", [(None,None),("head_sha","b"*40),("head_branch","feature"),
    ("event","pull_request"),("status","in_progress"),("conclusion","failure")])
def test_ci_guard_executes_exact_sha_branch_event_and_success(boundaries,field,value):
    directory,environment,response = boundaries
    run = dict(APPROVED)
    if field:run[field]=value
    response.write_text(json.dumps({"workflow_runs":[run],"private":"DO_NOT_LOG_THIS"}))
    result = shell(BY_ID["approval"]["run"],directory,environment)
    assert (result.returncode == 0) is (field is None)
    assert "DO_NOT_LOG_THIS" not in result.stdout+result.stderr
    calls = [json.loads(line) for line in (directory / "calls").read_text().splitlines()]
    assert ["git","merge-base","--is-ancestor",SHA,"origin/main"] in calls
    assert any(call[0] == "curl" and "head_sha="+SHA in call[-1] for call in calls)


def test_non_main_ancestry_blocks_api_request(boundaries):
    directory,environment,response = boundaries
    result = shell(BY_ID["approval"]["run"],directory,dict(environment,BAD_ANCESTRY="1"))
    assert result.returncode != 0
    assert '"curl"' not in (directory / "calls").read_text()


def remote_source(app):
    source = BY_ID["remote"]["run"].split("<<'AMAN_REMOTE'\n",1)[1].split("\nAMAN_REMOTE",1)[0]
    assert "APP=/var/www/inventarisasi" in source
    return source.replace("APP=/var/www/inventarisasi","APP="+shlex.quote(str(app)))


@pytest.mark.parametrize("action",["check","activate","rollback"])
def test_remote_sha_mismatch_stops_before_controller_or_directory_creation(boundaries,action):
    directory,environment,response = boundaries
    result = shell(remote_source(directory),directory,dict(environment,FAKE_HEAD="b"*40),SHA,action,"budget-123")
    assert result.returncode == 70
    calls = [json.loads(line) for line in (directory / "calls").read_text().splitlines()]
    assert calls == [["git","rev-parse","HEAD"]]


def test_remote_check_executes_only_current_venv_controller(boundaries):
    directory,environment,response = boundaries
    python = directory / "backend/venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/usr/bin/env python3\nimport json,os,pathlib,sys\npathlib.Path(os.environ['CONTROLLER_ARGS']).write_text(json.dumps(sys.argv[1:]))\nprint('{}')\n")
    python.chmod(0o755)
    arguments = directory / "controller-args"
    result = shell(remote_source(directory),directory,dict(environment,CONTROLLER_ARGS=str(arguments)),SHA,"check","")
    assert result.returncode == 0,result.stderr
    assert json.loads(arguments.read_text()) == ["-I","scripts/activate_export_budget.py","--app",str(directory),"--expected-sha",SHA,"--check-only"]


def publish(tmp_path,payload,*,outcome="success"):
    raw = tmp_path / "budget-remote.raw"
    raw.write_text(json.dumps(payload))
    script = next(step for step in STEPS if step.get("uses") == "actions/github-script@v7")["with"]["script"]
    harness = (
        "const captured={};const github={rest:{checks:{create:async value=>{captured.check=value;}}}};"
        "const context={repo:{owner:'owner',repo:'repo'}};"
        "const summary={addCodeBlock:()=>summary,write:async()=>{}};"
        "const core={summary,setFailed:message=>{captured.failed=message;}};"
        "const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;"
        "new AsyncFunction('require','github','context','core',"+json.dumps(script)+")"
        "(require,github,context,core).then(()=>process.stdout.write(JSON.stringify(captured)))"
        ".catch(()=>process.exit(1));"
    )
    node = shutil.which("node")
    assert node,"Node is required to execute the actual workflow publisher"
    result = subprocess.run([node,"-e",harness],env=dict(os.environ,RUNNER_TEMP=str(tmp_path),
        AMAN_TARGET_SHA=SHA,AMAN_OPERATION="activate",AMAN_REMOTE_OUTCOME=outcome),
        capture_output=True,text=True,check=True,timeout=10)
    return json.loads(result.stdout)


@pytest.fixture
def proof():
    return {"ok":True,"operation":"activate","source_sha":SHA,
        "capability":{"ok":True,"enabled":True,"slots":1,"satker_slots":1,"private":"DO_NOT_LOG_THIS"},
        "public_document_smoke":{"blocked_status":429,"retry_after_seconds":5,"document_status":200,
            "document_bytes":48065,"health_during_block":True,"queue_holders_writers_empty":True,
            "customer_data_read":False,"accounts_created":0,"raw":"DO_NOT_LOG_THIS"},"token":"DO_NOT_LOG_THIS"}


def test_checks_publisher_whitelists_only_typed_public_evidence(tmp_path,proof):
    result = publish(tmp_path,proof)
    assert result["check"]["head_sha"] == SHA and result["check"]["conclusion"] == "success"
    report = json.loads(result["check"]["output"]["summary"].split("```json\n",1)[1].split("\n```",1)[0])
    assert set(report) == {"status","operation","source_sha","capability","public_document_smoke","failure_phase","error_category"}
    assert report["status"] == "verified" and report["public_document_smoke"]["accounts_created"] == 0
    assert set(report["capability"]) == {"enabled","slots","satker_slots"}
    assert "DO_NOT_LOG_THIS" not in json.dumps(result)


def test_checks_publish_only_approved_failure_phase_and_category(tmp_path):
    result = publish(tmp_path,{"ok":False,"operation":"activate","source_sha":SHA,
        "failure_phase":"preflight","error_category":"validation","exception":"DO_NOT_LOG_THIS"},outcome="failure")
    report = json.loads(result["check"]["output"]["summary"].split("```json\n",1)[1].split("\n```",1)[0])
    assert result["check"]["conclusion"] == "failure" and report["status"] == "failed"
    assert report["failure_phase"] == "preflight" and report["error_category"] == "validation"
    assert report["capability"] == {"enabled":None,"slots":None,"satker_slots":None}
    assert "DO_NOT_LOG_THIS" not in json.dumps(result)


@pytest.mark.parametrize("fields",[{}, {"failure_phase":"DO_NOT_LOG_THIS","error_category":"DO_NOT_LOG_THIS"}])
def test_checks_discard_private_or_missing_failure_classification(tmp_path,fields):
    result = publish(tmp_path,{"ok":False,"operation":"activate","source_sha":SHA,**fields},outcome="failure")
    report = json.loads(result["check"]["output"]["summary"].split("```json\n",1)[1].split("\n```",1)[0])
    assert result["check"]["conclusion"] == "failure" and report["status"] == "failed"
    assert report["failure_phase"] == report["error_category"] == "unknown"
    assert "DO_NOT_LOG_THIS" not in json.dumps(result)


@pytest.mark.parametrize("case",["wrong_sha","bad_type","missing_smoke","customer_data","accounts","remote_failure"])
def test_checks_never_green_or_publish_untrusted_result_fields(tmp_path,proof,case):
    value = copy.deepcopy(proof)
    if case == "wrong_sha":value["source_sha"]="b"*40
    elif case == "bad_type":value["capability"]["slots"]="DO_NOT_LOG_THIS"
    elif case == "missing_smoke":value.pop("public_document_smoke")
    elif case == "customer_data":value["public_document_smoke"]["customer_data_read"]=True
    elif case == "accounts":value["public_document_smoke"]["accounts_created"]=1
    result = publish(tmp_path,value,outcome="failure" if case == "remote_failure" else "success")
    assert result["check"]["conclusion"] == "failure" and "failed" in result
    assert "DO_NOT_LOG_THIS" not in json.dumps(result)
