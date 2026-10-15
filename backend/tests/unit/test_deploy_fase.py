"""Production stdin deployer with real Git, venvs, local wheels and rollback.

Only Mongo, installer download, Supervisor, HTTP and frontend tooling are
external stubs. Filesystem changes and deployment helpers execute for real.
"""
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import socketserver
import subprocess
import sys
import tempfile
import threading
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/deploy_vps.sh"
PINNED_SPEC = importlib.util.spec_from_file_location("deploy_test_pinned", ROOT / "scripts/releases/pinned_installer.py")
PINNED = importlib.util.module_from_spec(PINNED_SPEC)
PINNED_SPEC.loader.exec_module(PINNED)


# Loaded outside the checkout by external stubs and the installer boundary.
# Rename hooks surround the real helper's calls without changing its source.
BOUNDARY = r'''
import json, os, pathlib, runpy, signal, socket, subprocess, sys

def context():
    return pathlib.Path(os.environ["APP_DIR"]), pathlib.Path(os.environ["AMAN_FAULT_STATE"])
def version():
    app,state=context(); return (app/"version.txt").read_text().strip()
def service():
    app,state=context(); return (state/"service-state").read_text().strip()
def fault(): return os.environ.get("AMAN_FAULT", "")
def record(name,args=(),**extra):
    app,state=context()
    event=dict(name=name,args=list(map(str,args)),version=version(),service=service(),
               action=os.environ.get("AMAN_GUARD_ACTION"),**extra)
    with (state/"events.jsonl").open("a") as log: log.write(json.dumps(event)+"\n")
def signal_root():
    os.kill(int(os.environ["AMAN_TEST_DEPLOY_PID"]),signal.SIGTERM)
    raise SystemExit(143)
def real(command,args):return subprocess.run([str(command),*map(str,args)]).returncode
def broker(action,mode='normal'):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(15)
        client.connect(os.environ['AMAN_TEST_SUPERVISOR_SOCKET'])
        client.sendall(json.dumps({'action':action,'mode':mode}).encode()+b'\n')
        with client.makefile('rb') as source:result=json.loads(source.readline(8192))
    if 'error' in result:raise RuntimeError('fixture process broker failed: '+result['error'])
    return result['pid']

def wrap_python(venv):
    python=venv/"bin/python"; actual=venv/"bin/python-real"
    if actual.exists():return
    python.rename(actual)
    python.write_text(
        "#!/usr/bin/env python3\nimport os,pathlib,sys\n"
        "if sys.argv[1:] == ['-']:\n"
        "    mongo=os.environ['AMAN_TEST_MONGO']\n"
        "    os.execv(mongo,[mongo])\n"
        "real=pathlib.Path(__file__).resolve().with_name('python-real')\n"
        "os.execv(str(real),[sys.argv[0],*sys.argv[1:]])\n")
    python.chmod(0o755)

def installer(args):
    app,state=context()
    for key in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE','_PIP_RUNNING_IN_SUBPROCESS'):
        assert key not in os.environ,'unsanitized installer destination'
    assert {k for k in os.environ if k.startswith('PIP_')}=={'PIP_CONFIG_FILE'}
    assert os.environ['PIP_CONFIG_FILE']==os.devnull
    args=list(args)
    if 'install' in args:
        i=args.index('install')+1
        args[i:i]=['--no-index','--find-links',os.environ['AMAN_TEST_WHEELS'],'--no-cache-dir']
    record('pip',args)
    if 'install' in args and fault()=='signal_pip':signal_root()
    if 'install' in args and fault()=='pip':raise SystemExit(19)
    if 'check' in args and fault()=='pip_check':raise SystemExit(19)
    target=pathlib.Path(args[args.index('--python')+1]).parent.parent
    sys.path.insert(0,os.environ['AMAN_TEST_PIP_SITE'])
    sys.argv[:]=[sys.argv[0],*args]
    try:runpy.run_module('pip',run_name='__main__',alter_sys=True)
    except SystemExit as result:
        if result.code:raise
    if 'install' in args:
        wrap_python(target)
        value=subprocess.check_output([str(target/'bin/python'),'-I','-c',
            "import importlib.metadata;print(importlib.metadata.version('aman-deploy-fixture'))"],text=True).strip()
        (state/'dependency-version').write_text(value)

def bootstrap(directory):
    record('installer_bootstrap')
    if fault()=='signal_installer':signal_root()
    if fault()=='installer':raise RuntimeError('isolated bootstrap fault')
    directory=pathlib.Path(directory);directory.mkdir(mode=0o700)
    runner=directory/'runner.py'
    runner.write_text("import runpy,sys\nscope=runpy.run_path("+repr(os.environ['AMAN_TEST_BOUNDARY'])+")\nscope['installer'](sys.argv[1:])\n")
    return runner

def patch_filesystem():
    app,state=context();stable=app/'backend/venv'
    old_rename,old_replace=os.rename,os.replace
    def rename(source,destination,*args,**kwargs):
        source,destination=pathlib.Path(source),pathlib.Path(destination)
        forward=source==stable and destination.name.startswith('legacy-')
        rollback=source.name.startswith('legacy-') and destination==stable
        if forward or rollback:
            record('venv_restore' if rollback else 'venv_move',[source,destination])
            assert service()=='STOPPED','venv directory moved before stop'
            if forward and fault()=='venv_move':raise OSError('migration fault')
            if rollback and fault()=='rollback_venv':raise OSError('restore fault')
        result=old_rename(source,destination,*args,**kwargs)
        if forward and fault()=='signal_venv_move':signal_root()
        return result
    def replace(source,destination,*args,**kwargs):
        source,destination=pathlib.Path(source),pathlib.Path(destination)
        switch=destination==stable and source.name.startswith('.venv-switch-')
        if switch:
            record('venv_link',[source,destination],target=os.readlink(source))
            assert service()=='STOPPED','venv pointer switched before stop'
            if fault()=='venv_link':raise OSError('pointer switch fault')
        result=old_replace(source,destination,*args,**kwargs)
        if switch and fault()=='signal_venv_link':signal_root()
        return result
    os.rename,os.replace=rename,replace

def guard():
    app,state=context();action=os.environ['AMAN_GUARD_ACTION'];lock=state/'lock.json'
    current=json.loads(lock.read_text()) if lock.exists() else {'state':'completed'}
    if fault()=='guard_error':return 1
    if action=='drain':print(1 if fault()=='active_jobs' else 0)
    elif action=='release':
        if fault()=='release':print(1)
        elif current.get('owner')==os.environ['AMAN_GUARD_OWNER']:
            lock.write_text(json.dumps({'state':'completed','active':False}));print(0)
        else:print(1)
    elif current['state'] not in ['completed','rolled_back','aborted']:print(1)
    elif action=='acquire':
        lock.write_text(json.dumps({'state':'deploying','owner':os.environ['AMAN_GUARD_OWNER']}));print(0)
    else:print(0)
    return 0

def dispatch():
    name,args=pathlib.Path(sys.argv[0]).name,sys.argv[1:]
    app,state=context();record(name,args);f,v=fault(),version()
    if name=='git':
        if args[0]=='fetch':return 128 if f=='fetch' else 0
        if args==['rev-parse','HEAD'] and f=='head_mismatch' and v=='new':print('0'*40);return 0
        if args[:2]==['reset','--hard']:
            assert service()=='STOPPED','source reset before proven stop'
            if f=='rollback_git' and args[2]==os.environ['AMAN_PREV']:return 19
            rc=real(os.environ['AMAN_REAL_GIT'],args)
            if args[2]==os.environ['AMAN_TARGET']:
                if f=='signal_reset':signal_root()
                if f=='reset':return 19
            return rc
        return real(os.environ['AMAN_REAL_GIT'],args)
    if name=='mongosh':return guard()
    if name=='sudo':return 1
    if name=='supervisorctl':
        action=args[0]
        if action=='stop':
            counter=state/'stop-count';count=int(counter.read_text())+1 if counter.exists() else 1
            counter.write_text(str(count))
            if f=='stop_persistent' or f=='stop' and count==1:return 19
            if f in ['rollback_stop','rollback_status'] and v=='new':return 19 if f=='rollback_stop' else 0
            if f in ['stop_unproven','status_unknown'] and count==1:return 0
            broker('stop')
            (state/'service-state').write_text('STOPPED')
            if f=='signal_stop' and count==1:signal_root()
            return 0
        if action=='status':
            label='UNKNOWN' if f=='status_unknown' and (state/'stop-count').read_text()=='1' else service()
            print('inventarisasi-backend '+label)
            if f=='signal_status' and (state/'stop-count').read_text()=='1':signal_root()
            return 3 if label=='STOPPED' else 0
        if action=='start':
            if v=='new' and f=='restart' or v=='old' and f=='rollback_restart':return 19
            dependency=subprocess.check_output([str(app/'backend/venv/bin/python'),'-I','-c',
                "import importlib.metadata;print(importlib.metadata.version('aman-deploy-fixture'))"],text=True).strip()
            assert dependency==('1.0' if v=='old' else '2.0'),'source/runtime generations differ'
            mode='normal'
            if v=='new' and f in ['process_cwd','process_entry','process_pythonenv']:mode=f
            if v=='old' and f=='rollback_process':mode='process_cwd'
            pid=broker('start',mode)
            record('worker_started',pid=pid,mode=mode)
            (state/'backend-version').write_text(v)
            sha=subprocess.check_output([os.environ['AMAN_REAL_GIT'],'-C',str(app),'rev-parse','HEAD'],text=True).strip()
            (state/'backend-sha').write_text(sha);(state/'service-state').write_text('RUNNING')
            if v=='new' and f=='signal_restart':signal_root()
            return 0
        if action=='pid':
            pid=broker('pid')
            print(0 if v=='new' and f=='pid_invalid' else pid)
            return 0
        raise AssertionError('unexpected Supervisor operation')
    if name=='curl':
        if service()!='RUNNING':return 22
        if v=='old' and f=='rollback_health':return 22
        if v=='new':
            docroot=app/'frontend/build/index.html'
            activated=docroot.is_file() and docroot.read_text()=='bundel baru'
            if f=='signal_final' and activated:signal_root()
            if f=='health' or f=='deep' and args[-1].endswith('/deep'):return 22
            if f=='final_health' and activated:return 22
        if '-o' in args:
            sha=(state/'backend-sha').read_text()
            if v=='new' and f=='health_stale_sha':sha=os.environ['AMAN_PREV']
            if v=='old' and f=='rollback_sha':sha=os.environ['AMAN_TARGET']
            payload={} if v=='new' and f=='health_missing_sha' else {'release_sha':sha}
            pathlib.Path(args[args.index('-o')+1]).write_text(json.dumps(payload))
        return 0
    if name=='sleep':return 0
    if name=='yarn':
        if args[0]=='install':
            if f=='signal_install':signal_root()
            return 19 if f=='install' else 0
        if args[0]=='build':
            if f=='signal_build':signal_root()
            recovery=['rollback_git','rollback_env','rollback_venv','rollback_inventory','rollback_restart','rollback_process',
                'rollback_health','rollback_sha','rollback_stop','rollback_status']
            if f=='rollback_inventory':
                metadata=next((app/'backend/.venv-releases').glob('legacy-*/lib/python*/site-packages/aman_deploy_fixture-1.0.dist-info/METADATA'))
                metadata.write_text(metadata.read_text().replace('Version: 1.0','Version: 1.1'))
            if f=='build' or f in recovery:return 19
            if f=='missing_build':return 0
            (app/'frontend/build.new').mkdir()
            (app/'frontend/build.new/index.html').write_text('bundel baru')
            (app/'frontend/build.new/asset-manifest.json').write_text('{"files":{}}')
            legacy=v=='old' and (app/'backend/.venv-releases/legacy-retained.json').exists()
            if f!='frontend_missing_sha' and not legacy:
                sha='0'*40 if f=='frontend_stale_sha' else os.environ['REACT_APP_RELEASE_SHA']
                (app/'frontend/build.new/aman-release.json').write_text(json.dumps({'source_sha':sha}))
            return 0
    if name=='mv':
        if f=='env' and v=='new' and args[-1].endswith('backend/.env'):return 19
        if f=='rollback_env' and v=='old' and args[-1].endswith('backend/.env'):return 19
        if args==['build','build.old'] and f=='archive_move':return 19
        if args==['build.new','build'] and f in ['activate','rollback_frontend']:return 19
        if args==['frontend/build.old','frontend/build'] and f=='rollback_frontend':return 19
        rc=real(os.environ['AMAN_REAL_MV'],args)
        if f=='signal_env' and v=='new' and args[-1].endswith('backend/.env'):signal_root()
        if args==['build','build.old'] and f=='signal_archive':signal_root()
        if args==['build.new','build'] and f=='signal_activate':signal_root()
        return rc
    if name=='rm':
        if args==['-rf','build.new'] and f=='clear_new':return 19
        if args==['-rf','build.old'] and f=='clear_old':return 19
        return real(os.environ['AMAN_REAL_RM'],args)
    if name=='mktemp':
        result=subprocess.run([os.environ['AMAN_REAL_MKTEMP'],*args],capture_output=True,text=True)
        if result.returncode==0 and result.stdout.startswith('/tmp/aman-env.'):
            with (state/'snapshots').open('a') as log:log.write(result.stdout)
        sys.stdout.write(result.stdout);return result.returncode
    raise AssertionError('unknown external stub: '+name)
'''


def _wheel(directory, name, version):
    package = name.replace("-", "_")
    metadata = f"{package}-{version}.dist-info"
    files = {
        f"{package}/__init__.py": f"VERSION = {version!r}\n".encode(),
        f"{metadata}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode(),
        f"{metadata}/WHEEL": b"Wheel-Version: 1.0\nGenerator: aman-fault-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    if name == "aman-deploy-fixture":
        files[f"{package}/__init__.py"] = (
            f"VERSION = {version!r}\n"
            "def main():\n"
            "    import json,os,signal\n"
            "    print(json.dumps({'ready':True,'version':VERSION,'pid':os.getpid()}),flush=True)\n"
            "    while True:signal.pause()\n"
        ).encode()
        files[f"{metadata}/entry_points.txt"] = f"[console_scripts]\nuvicorn = {package}:main\n".encode()
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for path, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow([path, "sha256="+digest, len(content)])
    writer.writerow([f"{metadata}/RECORD", "", ""])
    files[f"{metadata}/RECORD"] = record.getvalue().encode()
    wheel = directory / f"{package}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name_in_zip, content in files.items():
            archive.writestr(name_in_zip, content)
    return hashlib.sha256(wheel.read_bytes()).hexdigest()


def _write_lock(path, requirements):
    path.write_text("".join(f"{name}=={version} \\\n    --hash=sha256:{digest}\n" for name, version, digest in requirements))


def _venv_snapshot(directory):
    return {
        str(path.relative_to(directory)): ("link", os.readlink(path)) if path.is_symlink()
        else ("file", hashlib.sha256(path.read_bytes()).hexdigest())
        for path in directory.rglob("*") if path.is_symlink() or path.is_file()
    }


class _WorkerBroker:
    """The pytest process owns and reaps every simulated Supervisor worker."""

    def __init__(self, app, environment):
        self.app = app
        self.environment = dict(environment)
        self.worker = None
        # AF_UNIX paths must stay below the kernel's short pathname limit.
        self.directory = tempfile.TemporaryDirectory(prefix="aman-test-supervisor-")
        self.socket = str(Path(self.directory.name) / "control.sock")
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                try:
                    request = json.loads(self.rfile.readline(8192))
                    action = request["action"]
                    if action == "start":
                        pid = owner.start_worker(request["mode"])
                    elif action == "stop":
                        owner.stop_worker()
                        pid = 0
                    elif action == "pid":
                        pid = owner.worker.pid if owner.worker is not None and owner.worker.poll() is None else 0
                    else:
                        raise ValueError("Unknown broker action")
                    response = {"pid":pid}
                except Exception as error:
                    response = {"error":type(error).__name__}
                self.wfile.write(json.dumps(response).encode()+b"\n")

        self.server = socketserver.UnixStreamServer(self.socket,Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":0.05},daemon=True)
        self.thread.start()

    def start_worker(self, mode="normal"):
        if self.worker is not None:
            raise RuntimeError("Previous fixture worker was not stopped")
        stable = self.app / "backend/venv/bin"
        command = [str(stable / "uvicorn"),"server:app","--host","127.0.0.1","--port","8001"]
        cwd = self.app / "backend"
        child_env = dict(self.environment)
        if mode == "process_cwd":
            cwd = self.app
        elif mode == "process_entry":
            command = [str(stable / "python"),"-c","from aman_deploy_fixture import main;main()"]
        elif mode == "process_pythonenv":
            child_env["PYTHONUSERBASE"] = str(self.app / "foreign-userbase")
        elif mode != "normal":
            raise ValueError("Unknown fixture process mode")
        self.worker = subprocess.Popen(command,cwd=cwd,env=child_env,stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,start_new_session=True)
        try:
            readable,_,_ = select.select([self.worker.stdout],[],[],10)
            if not readable:
                raise TimeoutError("Fixture uvicorn did not reach readiness")
            ready = json.loads(self.worker.stdout.readline(4096))
            if ready.get("ready") is not True or ready.get("pid") != self.worker.pid:
                raise RuntimeError("Fixture uvicorn readiness differs")
            return self.worker.pid
        except BaseException:
            self.stop_worker()
            raise

    def stop_worker(self):
        worker,self.worker = self.worker,None
        if worker is None:
            return
        if worker.poll() is None:
            os.killpg(worker.pid,signal.SIGTERM)
            try:
                worker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(worker.pid,signal.SIGKILL)
                worker.wait(timeout=3)
        else:
            worker.wait()
        worker.stdout.close()
        worker.stderr.close()

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.stop_worker()
        self.server.server_close()
        self.directory.cleanup()


@pytest.fixture(scope="module")
def local_runtime(tmp_path_factory):
    import pip

    managed = Path("/workspace/.aman/python/cpython-3.11.17-linux-x86_64-gnu/bin/python3.11")
    if sys.version_info[:2] == (3, 11):
        python = Path(sys._base_executable)
    elif managed.is_file():
        python = managed
    else:
        pytest.fail("Deployment phase tests require the production Python3.11 interpreter")
    directory = tmp_path_factory.mktemp("deploy-local-wheels")
    first = _wheel(directory, "aman-deploy-fixture", "1.0")
    second = _wheel(directory, "aman-deploy-fixture", "2.0")
    stale = _wheel(directory, "aman-deploy-obsolete", "9.0")
    return python, str(Path(pip.__file__).resolve().parent.parent), directory, first, second, stale


@pytest.fixture
def deploy_case(tmp_path, local_runtime):
    python, pip_site, wheels, first_hash, second_hash, stale_hash = local_runtime
    app = tmp_path / "aplikasi dengan spasi"
    app.mkdir()
    state = tmp_path / "batas-eksternal"
    state.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    support = state / "boundary.py"
    support.write_text(BOUNDARY)
    (state / "service-state").write_text("RUNNING")
    (state / "backend-version").write_text("old")
    git = shutil.which("git")

    def git_run(*args):
        return subprocess.check_output([git, "-C", str(app), *args], text=True).strip()

    git_run("init", "-q")
    git_run("config", "user.email", "uji@example.test")
    git_run("config", "user.name", "Fault injection")
    (app / "backend").mkdir()
    (app / "frontend").mkdir()
    (app / "scripts").mkdir()
    shutil.copyfile(ROOT / "scripts/retain_static_assets.py", app / "scripts/retain_static_assets.py")
    (app / ".gitignore").write_text("backend/.env\nfrontend/.env\nbackend/venv/\nbackend/.venv-releases/\nfrontend/build*/\n")
    (app / "version.txt").write_text("old")
    (app / "backend/requirements.txt").write_text("--require-hashes\n-r requirements-runtime.lock\n")
    _write_lock(app / "backend/requirements-runtime.lock", [
        ("aman-deploy-fixture", "1.0", first_hash), ("aman-deploy-obsolete", "9.0", stale_hash),
    ])
    shutil.copyfile(ROOT / "backend/release_info.py", app / "backend/release_info.py")
    git_run("add", ".")
    git_run("commit", "-qm", "known good before clean-venv controller")
    prev = git_run("rev-parse", "HEAD")
    # Old checkout deliberately has neither newly introduced helper.
    releases = app / "scripts/releases"
    releases.mkdir()
    shutil.copyfile(ROOT / "scripts/releases/backend_environment.py", releases / "backend_environment.py")
    (releases / "pinned_installer.py").write_text(
        "import importlib.util,runpy\n"
        f"spec=importlib.util.spec_from_file_location('actual_pinned_sanitizer',{str(ROOT / 'scripts/releases/pinned_installer.py')!r})\n"
        "module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)\n"
        "sanitized_environment=module.sanitized_environment\n"
        f"scope=runpy.run_path({str(support)!r})\n"
        "scope['patch_filesystem']()\n"
        "def build_installer(directory,wheel_path=None):return scope['bootstrap'](directory)\n"
    )
    (releases / "runtime_native_smoke.py").write_text(
        "import json,runpy,sys\n"
        f"scope=runpy.run_path({str(support)!r})\n"
        "scope['record']('native_smoke',sys.argv[1:])\n"
        "assert scope['service']() == 'RUNNING'\n"
        "if scope['fault']() == 'signal_native':scope['signal_root']()\n"
        "if scope['fault']() == 'native':raise SystemExit(19)\n"
        "print(json.dumps({'ok':True}))\n"
    )
    font = app / "backend/assets/fonts/Inter.ttf"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"native renderer is an isolated boundary in phase tests")
    (app / "version.txt").write_text("new")
    _write_lock(app / "backend/requirements-runtime.lock", [("aman-deploy-fixture", "2.0", second_hash)])
    git_run("add", ".")
    git_run("commit", "-qm", "target CI immutable clean-venv controller")
    target = git_run("rev-parse", "HEAD")
    (app / "version.txt").write_text("future unapproved")
    git_run("commit", "-qam", "main moves after CI")
    latest = git_run("rev-parse", "HEAD")
    git_run("update-ref", "refs/remotes/origin/main", latest)
    git_run("reset", "--hard", prev)
    original_env = b'MONGO_URL="mongodb://invalid.test:27017"\nDB_NAME=isolated_test\nPRIVATE_FIXTURE=never-log-this\n'
    (app / "backend/.env").write_bytes(original_env)
    (app / "frontend/.env").write_bytes(b"PUBLIC_FIXTURE=synthetic\n")
    (app / "frontend/build").mkdir()
    (app / "frontend/build/index.html").write_text("bundel lama")
    (app / "frontend/build/asset-manifest.json").write_text('{"files":{}}')
    (app / "frontend/build.old").mkdir()
    (app / "frontend/build.old/index.html").write_text("bundel lebih lama")
    for name in ["git", "mongosh", "sudo", "supervisorctl", "curl", "sleep", "yarn", "mv", "rm", "mktemp"]:
        tool = bin_dir / name
        tool.write_text("#!/usr/bin/env python3\nimport runpy\nscope=runpy.run_path("+repr(str(support))+")\nraise SystemExit(scope['dispatch']())\n")
        tool.chmod(0o755)
    supervisor = state / "supervisor.conf"
    supervisor.write_text(
        "[program:inventarisasi-backend]\n"
        f"command={shlex.quote(str(app / 'backend/venv/bin/uvicorn'))} server:app --host 127.0.0.1 --port 8001\n"
        f"directory={app / 'backend'}\nstopasgroup=true\nkillasgroup=true\n"
    )
    env = dict(os.environ, APP_DIR=str(app), PATH=str(bin_dir)+os.pathsep+os.environ["PATH"],
               AMAN_FAULT_STATE=str(state), AMAN_REAL_GIT=git, AMAN_REAL_MV=shutil.which("mv"),
               AMAN_REAL_MKTEMP=shutil.which("mktemp"), AMAN_REAL_RM=shutil.which("rm"),
               AMAN_PREV=prev, AMAN_TARGET=target, AMAN_SUPERVISOR_CONFIG=str(supervisor),
               AMAN_TEST_BOUNDARY=str(support), AMAN_TEST_WHEELS=str(wheels), AMAN_TEST_PIP_SITE=pip_site,
               AMAN_TEST_MONGO=str(bin_dir / "mongosh"), PYTHONDONTWRITEBYTECODE="1")
    initial_runner = state / "initial-installer.py"
    initial_runner.write_text("import runpy,sys\nscope=runpy.run_path("+repr(str(support))+")\nscope['installer'](sys.argv[1:])\n")
    install_env = PINNED.sanitized_environment(env)
    subprocess.run([str(python), "-I", "-m", "venv", "--without-pip", str(app / "backend/venv")],
                   env=install_env, check=True, capture_output=True, text=True, timeout=40)
    subprocess.run([str(python), "-I", "-S", str(initial_runner), "--isolated", "--python",
                    str(app / "backend/venv/bin/python"), "install", "--require-hashes", "-r",
                    str(app / "backend/requirements-runtime.lock")],
                   env=install_env, check=True, capture_output=True, text=True, timeout=40)
    (state / "backend-sha").write_text(prev)
    original_venv = _venv_snapshot(app / "backend/venv")
    (state / "old-venv-snapshot.json").write_text(json.dumps(original_venv))
    (state / "old-venv-inode").write_text(str((app / "backend/venv").stat().st_ino))
    broker = _WorkerBroker(app,PINNED.sanitized_environment(env))
    env["AMAN_TEST_SUPERVISOR_SOCKET"] = broker.socket

    def run(fault="", target_sha=target, mode="otomatis", control_state=None, controller_sha=None):
        if control_state:
            (state / "lock.json").write_text(json.dumps({"state":control_state,"destructive_started":True}))
        if fault.startswith("attest_"):
            content = supervisor.read_text()
            if fault == "attest_command": content = content.replace("backend/venv/bin/uvicorn", "backend/other/bin/uvicorn")
            elif fault == "attest_directory": content = content.replace(f"directory={app / 'backend'}", f"directory={app}")
            elif fault == "attest_stopgroup": content = content.replace("stopasgroup=true", "stopasgroup=false")
            elif fault == "attest_killgroup": content = content.replace("killasgroup=true", "killasgroup=false")
            elif fault == "attest_pythonpath": content += "environment=PYTHONPATH=foreign\n"
            supervisor.write_text(content)
        offset = len((state / "events.jsonl").read_text().splitlines())
        command = ["bash", "-s", "--", target_sha, mode]
        if controller_sha is not None: command.append(controller_sha)
        source = "export AMAN_TEST_DEPLOY_PID=$BASHPID\n" + SCRIPT.read_text()
        result = subprocess.run(command,input=source,
            env=dict(env,AMAN_FAULT=fault,AMAN_STATIC_BUDGET_MB="0" if fault=="retention" else "256"),
            capture_output=True,text=True,timeout=90)
        events = [json.loads(line) for line in (state / "events.jsonl").read_text().splitlines()[offset:]]
        assert "never-log-this" not in result.stdout+result.stderr
        assert (app / "backend/.env").read_bytes() == original_env
        assert (app / "frontend/.env").read_bytes() == b"PUBLIC_FIXTURE=synthetic\n"
        for event in events:
            mutation = event["name"] in ["venv_move","venv_link","venv_restore"] or event["name"] == "git" and event["args"][:2] == ["reset","--hard"]
            if mutation: assert event["service"] == "STOPPED",event
            if event["name"] == "pip" and "install" in event["args"]:
                assert "--no-index" in event["args"]
                assert event["version"] == "old" and event["service"] == "RUNNING"
        return result,events

    try:
        broker.start_worker()
        yield app,state,prev,target,latest,git_run,run
    finally:
        broker.close()
        if (state / "snapshots").exists():
            for snapshot in (state / "snapshots").read_text().splitlines():
                path = Path(snapshot)
                if path.parent == Path("/tmp") and path.name.startswith("aman-env."):
                    shutil.rmtree(path,ignore_errors=True)


def _assert_original_venv(app,state):
    stable = app / "backend/venv"
    assert stable.is_dir() and not stable.is_symlink()
    assert stable.stat().st_ino == int((state / "old-venv-inode").read_text())
    assert json.loads(json.dumps(_venv_snapshot(stable))) == json.loads((state / "old-venv-snapshot.json").read_text())


def test_deploy_success_exact_ci_sha_keeps_previous_frontend(deploy_case):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run()
    assert result.returncode == 0,result.stderr
    assert git_run("rev-parse","HEAD") == target != latest
    assert (app / "frontend/build/index.html").read_text() == "bundel baru"
    assert (app / "frontend/build.old/index.html").read_text() == "bundel lama"
    assert json.loads((state / "lock.json").read_text())["state"] == "completed"
    assert "Deploy selesai:" in result.stdout
    assert (app / "backend/.env").stat().st_mode & 0o777 == 0o600
    stable = app / "backend/venv"
    assert stable.is_symlink()
    descriptor = json.loads((stable / ".aman-environment.json").read_text())
    assert descriptor["source_sha"] == target
    assert descriptor["distributions"] == {"aman-deploy-fixture":"2.0"}
    pid = next(e["pid"] for e in reversed(events) if e["name"] == "worker_started")
    arguments = (Path("/proc") / str(pid) / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
    # A real wheel entry point embeds the permanent candidate interpreter,
    # while Supervisor invokes its stable uvicorn path. Both must attest.
    assert arguments[:3] == [str(stable.resolve() / "bin/python").encode(),
                             str(stable / "bin/uvicorn").encode(),b"server:app"]
    assert (Path("/proc") / str(pid) / "cwd").resolve() == app / "backend"
    legacy = json.loads((app / "backend/.venv-releases/legacy-retained.json").read_text())
    assert legacy["source_sha"] == prev
    assert legacy["distributions"] == {"aman-deploy-fixture":"1.0","aman-deploy-obsolete":"9.0"}
    assert any(e["name"] == "git" and e["args"] == ["show",f"{target}:scripts/releases/backend_environment.py"] for e in events)
    assert any(e["name"] == "git" and e["args"] == ["show",f"{target}:backend/requirements-runtime.lock"] for e in events)
    pip_index = next(i for i,e in enumerate(events) if e["name"] == "pip")
    smoke_index = next(i for i,e in enumerate(events) if e["name"] == "native_smoke")
    stop_index = next(i for i,e in enumerate(events) if e["name"] == "supervisorctl" and e["args"][0] == "stop")
    reset_index = next(i for i,e in enumerate(events) if e["name"] == "git" and e["args"][:2] == ["reset","--hard"])
    assert pip_index < smoke_index < stop_index < reset_index
    for snapshot in (state / "snapshots").read_text().splitlines():assert not Path(snapshot).exists()


@pytest.mark.parametrize("fault", [
    "reset","head_mismatch","env","restart","health","health_stale_sha","health_missing_sha","deep",
    "install","build","missing_build","frontend_stale_sha","frontend_missing_sha","retention",
    "clear_new","clear_old","archive_move","activate","final_health","venv_move","venv_link",
    "signal_reset","signal_env","signal_restart","signal_install","signal_build","signal_archive",
    "signal_activate","signal_final","signal_stop","signal_status","signal_venv_move","signal_venv_link",
    "stop","stop_unproven","status_unknown","process_cwd","process_entry","process_pythonenv","pid_invalid",
])
def test_every_mutating_failure_restores_verified_old_pair(deploy_case,fault):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run(fault)
    assert result.returncode in [1,19,143],result.stderr
    assert git_run("rev-parse","HEAD") == prev
    assert (app / "frontend/build/index.html").read_text() == "bundel lama"
    assert (state / "backend-version").read_text() == "old"
    assert (state / "service-state").read_text() == "RUNNING"
    _assert_original_venv(app,state)
    assert "ROLLBACK selesai" in result.stderr
    assert "Deploy selesai:" not in result.stdout
    assert any(e["name"] == "curl" and e["version"] == "old" and e["args"][-1].endswith("/deep") for e in events)
    assert json.loads((state / "lock.json").read_text())["state"] == "completed"
    assert len([e for e in events if e["name"] == "pip" and "install" in e["args"]]) == 1
    if fault in ["process_cwd","process_entry","process_pythonenv","pid_invalid"]:
        assert not any(e["name"] == "curl" and e["version"] == "new" for e in events)
    if fault != "env":
        assert all(not Path(path).exists() for path in (state / "snapshots").read_text().splitlines())


@pytest.mark.parametrize("fault", [
    "rollback_git","rollback_env","rollback_venv","rollback_inventory","rollback_restart","rollback_process","rollback_health",
    "rollback_sha","rollback_frontend","rollback_stop","rollback_status","stop_persistent","release",
])
def test_failed_recovery_never_announces_success_and_blocks_next_deploy(deploy_case,fault):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run(fault)
    assert result.returncode == 70,result.stderr
    assert "RECOVERY_REQUIRED" in result.stderr
    if fault != "release":assert "ROLLBACK selesai" not in result.stderr
    assert "Deploy selesai:" not in result.stdout
    assert json.loads((state / "lock.json").read_text())["state"] == "deploying"
    if fault == "rollback_frontend":
        assert (app / "frontend/build.old/index.html").read_text() == "bundel lama"
    if fault in ["rollback_stop","rollback_status"]:
        assert git_run("rev-parse","HEAD") == target
        assert not any(e["name"] == "git" and e["args"] == ["reset","--hard",prev] for e in events)
    if fault == "stop_persistent":
        assert git_run("rev-parse","HEAD") == prev
        assert not any(e["name"] == "git" and e["args"][:2] == ["reset","--hard"] for e in events)
    if fault == "release":
        _assert_original_venv(app,state)
        assert not (app / "backend/.venv-releases/legacy-retained.json").exists()
    blocked,blocked_events = run()
    assert blocked.returncode != 0
    assert not any(e["name"] in ["pip","supervisorctl","yarn"] for e in blocked_events)
    assert not any(e["name"] == "git" and e["args"][0] in ["fetch","reset"] for e in blocked_events)


@pytest.mark.parametrize("control", ["preparing","restoring","rolling_back","recovery_required","deploying","unknown"])
def test_restore_or_unknown_persistent_control_blocks_before_fetch_or_reset(deploy_case,control):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run(control_state=control)
    assert result.returncode == 1
    assert git_run("rev-parse","HEAD") == prev
    assert not any(e["name"] == "git" and e["args"][0] in ["fetch","reset"] for e in events)


@pytest.mark.parametrize("fault", [
    "guard_error","fetch","active_jobs","installer","pip","pip_check","signal_installer","signal_pip",
    "native","signal_native","attest_command","attest_directory","attest_stopgroup","attest_killgroup","attest_pythonpath",
])
def test_preflight_error_never_mutates_active_release(deploy_case,fault):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run(fault)
    assert result.returncode != 0
    assert git_run("rev-parse","HEAD") == prev
    assert (app / "frontend/build/index.html").read_text() == "bundel lama"
    assert (state / "service-state").read_text() == "RUNNING"
    _assert_original_venv(app,state)
    assert "ROLLBACK selesai" not in result.stderr
    assert not any(e["name"] in ["supervisorctl","yarn","venv_move","venv_link"] for e in events)
    assert not any(e["name"] == "git" and e["args"][:2] == ["reset","--hard"] for e in events)
    if fault not in ["guard_error","fetch"]:
        assert json.loads((state / "lock.json").read_text())["state"] == "completed"


def test_anti_downgrade_and_explicit_manual_rollback(deploy_case):
    app,state,prev,target,latest,git_run,run = deploy_case
    deployed,_ = run()
    assert deployed.returncode == 0,deployed.stderr
    result,events = run(target_sha=prev)
    assert result.returncode == 1
    assert git_run("rev-parse","HEAD") == target
    assert not any(e["name"] in ["pip","supervisorctl"] for e in events)
    result,events = run(target_sha=prev,mode="manual",controller_sha=target)
    assert result.returncode == 0,result.stderr
    assert git_run("rev-parse","HEAD") == prev
    assert "MANUAL LEGACY" in result.stderr
    assert not any(e["name"] == "pip" for e in events)


def test_existing_commit_outside_main_never_activates(deploy_case):
    app,state,prev,target,latest,git_run,run = deploy_case
    tree = git_run("rev-parse",target+"^{tree}")
    outside_main = git_run("commit-tree",tree,"-p",prev,"-m","outside approved main")
    result,events = run(target_sha=outside_main)
    assert result.returncode == 1
    assert git_run("rev-parse","HEAD") == prev
    assert not any(e["name"] == "git" and e["args"][0] == "reset" for e in events)


def test_automatic_controller_must_equal_target_before_any_remote_work(deploy_case):
    app,state,prev,target,latest,git_run,run = deploy_case
    result,events = run(controller_sha=latest)
    assert result.returncode == 2
    assert not events
    _assert_original_venv(app,state)
