#!/usr/bin/env python3
"""Transaksi venv deploy; source/controller dipilih dengan SHA oleh shell deploy."""
import argparse
import configparser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import uuid

_spec=importlib.util.spec_from_file_location("aman_pinned_installer",Path(__file__).with_name("pinned_installer.py"))
_installer=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_installer)
build_installer=_installer.build_installer
sanitized_environment=_installer.sanitized_environment

PROTOCOL=1
SHA=re.compile(r"[0-9a-f]{40}")
SAFE_OWNER=re.compile(r"[A-Za-z0-9:_.-]{1,160}")
MIN_PREPARE_FREE_BYTES=3*1024**3
MIN_READY_FREE_BYTES=1024**3
INVENTORY_CODE=r'''
import importlib.metadata,json,sys
print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,
 "base_executable":sys._base_executable,"python":list(sys.version_info[:2]),
 "distributions":sorted((d.metadata["Name"],d.version) for d in importlib.metadata.distributions())}))
'''


def sha256(data):return hashlib.sha256(data).hexdigest()
def canonical(name):return re.sub(r"[-_.]+","-",name).lower()


def sync_directory(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def atomic_json(path,value):
    temporary=path.with_name("."+path.name+"."+uuid.uuid4().hex)
    try:
        with temporary.open("x") as stream:
            os.chmod(temporary,0o600)
            json.dump(value,stream,sort_keys=True)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        sync_directory(path.parent)
    finally:temporary.unlink(missing_ok=True)


def owned(path,directory=None):
    if path.is_symlink() or not path.exists() or path.stat().st_uid!=os.geteuid():
        raise ValueError("Jalur transaksi wajib dimiliki deployer tanpa symlink")
    if directory is True and not path.is_dir() or directory is False and not path.is_file():
        raise ValueError("Tipe jalur transaksi tidak cocok")
    if path.stat().st_mode&0o022:
        raise ValueError("Jalur transaksi writable oleh pengguna lain")
    return path


def run(command,timeout=1200):
    result=subprocess.run(command,env=sanitized_environment(),capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        # Pip/proxy diagnostics can contain credentials; never print them.
        raise RuntimeError("Command dependency/runtime gagal; rilis aktif belum diubah")
    return result.stdout


def inventory(python):
    value=json.loads(run([str(python),"-I","-c",INVENTORY_CODE]))
    distributions={}
    for name,version in value["distributions"]:
        name=canonical(name)
        if name in distributions:raise ValueError("Metadata distribution duplikat")
        distributions[name]=version
    value["distributions"]=distributions
    return value


def parse_lock(path):
    data=path.read_bytes()
    if len(data)>8*1024*1024:raise ValueError("Hash lock terlalu besar")
    result={};current=None;hashed=False
    for line in data.decode().splitlines():
        text=line.strip().rstrip("\\").strip()
        if not text or text.startswith("#"):continue
        if re.fullmatch(r"--hash=sha256:[0-9a-f]{64}",text):
            if current is None:raise ValueError("Hash tanpa requirement")
            hashed=True;continue
        match=re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)",text)
        if not match or current is not None and not hashed:
            raise ValueError("Runtime lock wajib pin/hash penuh tanpa directives/markers")
        name=canonical(match[1])
        if name in result:raise ValueError("Requirement duplikat")
        result[name]=match[2];current=name;hashed=False
    if not result or not hashed:raise ValueError("Runtime lock kosong atau hash hilang")
    return result,sha256(data)


def validate_prefix(value,path,required_python=(3,11)):
    if value["python"]!=list(required_python) or Path(value["prefix"]).resolve()!=path.resolve() or value["prefix"]==value["base_prefix"]:
        raise ValueError("Interpreter/prefix venv tidak sesuai Python3.11")
    config=(path/"pyvenv.cfg").read_text().lower()
    if not re.search(r"^include-system-site-packages\s*=\s*false\s*$",config,re.M):
        raise ValueError("System site packages wajib nonaktif")


def roots(app,control):
    app=Path(app).resolve()
    if app==Path("/") or (app/"backend").is_symlink():raise ValueError("Akar aplikasi tidak aman")
    root=app/"backend/.venv-releases"
    if not root.exists():root.mkdir(mode=0o755)
    owned(root,True)
    control=owned(Path(control),True)
    if control.stat().st_mode&0o077:raise ValueError("Control directory wajib privat0700")
    if control.resolve().parent!=root.resolve() or not control.name.startswith(".run-"):
        raise ValueError("Control directory bukan milik run deploy")
    return app,root,control


def read_state(app,control):
    app,root,control=roots(app,control)
    state=json.loads(owned(control/"state.json",False).read_text())
    if state.get("protocol")!=PROTOCOL or state.get("app")!=str(app):raise ValueError("State transaksi tidak cocok")
    for name in ["candidate","old_saved"]:
        path=Path(state[name])
        if path.parent!=root or path.is_symlink():raise ValueError("State menunjuk env di luar root")
    candidate=Path(state["candidate"])
    if state.get("candidate_owned") and candidate.exists():
        metadata=owned(candidate,True).stat()
        if metadata.st_ino!=state.get("candidate_inode") or metadata.st_dev!=state.get("candidate_device"):
            raise ValueError("Allocation candidate berubah; jangan aktivasi/hapus jalur pengganti")
    return app,root,control,state


def save(control,state):atomic_json(control/"state.json",state)


def disk_headroom(path,minimum=MIN_PREPARE_FREE_BYTES):
    capacity=os.statvfs(path)
    total=capacity.f_blocks*capacity.f_frsize
    available=capacity.f_bavail*capacity.f_frsize
    if total<=0 or available<minimum or available/total<.20:
        raise ValueError("Disk headroom wajib >=20% dan cukup untuk environment terpisah; tidak menghapus rilis lama otomatis")
    return {"available_bytes":available,"total_bytes":total,"minimum_bytes":minimum}


def prepare(app,control,target_sha,previous_sha,owner,lock_file,manual=False,installer_runner=None,required_python=(3,11),native_smoke=None):
    app,root,control=roots(app,control)
    storage=disk_headroom(root)
    if not SHA.fullmatch(target_sha) or not SHA.fullmatch(previous_sha) or not SAFE_OWNER.fullmatch(owner):
        raise ValueError("SHA/owner tidak valid")
    if (control/"state.json").exists():raise ValueError("Run sudah memiliki state; jangan ulang prepare")
    stable=app/"backend/venv"
    if stable.is_symlink() and stable.lstat().st_uid!=os.geteuid():raise ValueError("Pointer venv bukan milik deployer")
    old_link=os.readlink(stable) if stable.is_symlink() else None
    old=stable.resolve()
    if old_link is not None and old.parent!=root:raise ValueError("Symlink venv lama di luar root managed")
    owned(old,True)
    old_inventory=inventory(stable/"bin/python")
    validate_prefix(old_inventory,old,required_python)
    base=Path(old_inventory["base_executable"]).resolve()
    base_info=json.loads(run([str(base),"-I","-c","import json,sys;print(json.dumps(list(sys.version_info[:2])))"]))
    if base_info!=list(required_python):raise ValueError("Base Python tidak sesuai")
    state={"protocol":PROTOCOL,"app":str(app),"owner":owner,"target_sha":target_sha,"previous_sha":previous_sha,
        "old_kind":"symlink" if old_link else "directory","old_link":old_link,"old_target":str(old),
        "old_saved":str(root/("legacy-"+uuid.uuid4().hex)),"old_inode":old.stat().st_ino,"old_device":old.stat().st_dev,
        "old_inventory":old_inventory,"candidate":str(root/(target_sha+"-"+uuid.uuid4().hex)),
        "candidate_owned":False,"candidate_legacy":False,"phase":"preparing","base_python":str(base),"disk_before":storage}
    save(control,state)
    if manual:
        retained=[]
        legacy=root/"legacy-retained.json"
        if legacy.exists():
            descriptor=json.loads(owned(legacy,False).read_text())
            if descriptor.get("source_sha")==target_sha:
                retained.append((descriptor,True))
        for path in root.glob("*/.aman-environment.json"):
            descriptor=json.loads(owned(path,False).read_text())
            if descriptor.get("source_sha")==target_sha:retained.append((descriptor,False))
        for descriptor,is_legacy in retained:
            candidate=owned(Path(descriptor["path"]),True)
            if candidate.parent!=root:raise ValueError("Retained env di luar root")
            actual=inventory(candidate/"bin/python")
            validate_prefix(actual,candidate,required_python)
            if actual["distributions"]!=descriptor["distributions"]:raise ValueError("Inventory retained env berubah")
            if not is_legacy:
                expected,lock_sha=parse_lock(Path(lock_file))
                if actual["distributions"]!=expected or descriptor.get("requirements_sha256")!=lock_sha:
                    raise ValueError("Retained env berbeda dari lock target")
            state.update(candidate=str(candidate),candidate_owned=False,candidate_legacy=is_legacy)
            save(control,state)
            if native_smoke is not None:
                state["native_smoke"]=json.loads(run([str(candidate/"bin/python"),"-I",str(native_smoke),"--font",str(control/"Inter.ttf")],timeout=30))
            state.update(phase="prepared",disk_ready=disk_headroom(root,MIN_READY_FREE_BYTES));save(control,state)
            return state
    expected,lock_sha=parse_lock(Path(lock_file))
    candidate=Path(state["candidate"])
    candidate.mkdir(mode=0o755)
    # Exclusive creation must succeed before cleanup is ever authorized. A
    # crash before this proof is durable leaves an orphan, never a delete grant.
    metadata=candidate.stat()
    state.update(candidate_owned=True,candidate_inode=metadata.st_ino,candidate_device=metadata.st_dev)
    save(control,state)
    run([str(base),"-I","-m","venv","--without-pip",str(candidate)])
    runner=Path(installer_runner) if installer_runner is not None else build_installer(control/"installer")
    command=[str(base),"-I","-S",str(runner),"--isolated","--python",str(candidate/"bin/python")]
    run([*command,"install","--disable-pip-version-check","--no-input","--only-binary=:all:","--require-hashes","-r",str(lock_file)])
    run([*command,"check","--disable-pip-version-check"])
    actual=inventory(candidate/"bin/python")
    validate_prefix(actual,candidate,required_python)
    if actual["distributions"]!=expected:raise ValueError("Inventory runtime wajib persis hash lock, tanpa paket bootstrap/obsolete")
    native_result=None
    if native_smoke is not None:
        native_result=json.loads(run([str(candidate/"bin/python"),"-I",str(native_smoke),"--font",str(control/"Inter.ttf")],timeout=30))
    descriptor={"protocol":PROTOCOL,"source_sha":target_sha,"path":str(candidate),"requirements_sha256":lock_sha,
                "distributions":actual["distributions"],"python":actual["python"],"native_smoke":native_result}
    atomic_json(candidate/".aman-environment.json",descriptor)
    state.update(phase="prepared",requirements_sha256=lock_sha,disk_ready=disk_headroom(root,MIN_READY_FREE_BYTES))
    save(control,state)
    return state


def atomic_link(target,stable):
    temporary=stable.with_name(".venv-switch-"+uuid.uuid4().hex)
    try:
        temporary.symlink_to(target,target_is_directory=True)
        os.replace(temporary,stable)
        sync_directory(stable.parent)
    finally:temporary.unlink(missing_ok=True)


def activate(app,control):
    app,root,control,state=read_state(app,control)
    if state["phase"]!="prepared":raise ValueError("Candidate belum terverifikasi")
    stable=app/"backend/venv"
    state["phase"]="switching";save(control,state)
    if state["old_kind"]=="directory":
        if stable.is_symlink() or stable.stat().st_ino!=state["old_inode"] or stable.stat().st_dev!=state["old_device"]:
            raise ValueError("Venv awal berubah sebelum switch")
        os.rename(stable,state["old_saved"])
        sync_directory(root);sync_directory(stable.parent)
    elif not stable.is_symlink() or stable.resolve()!=Path(state["old_target"]):
        raise ValueError("Pointer venv lama berubah")
    atomic_link(state["candidate"],stable)
    state["phase"]="activated";save(control,state)


def restore(app,control):
    app,root,control,state=read_state(app,control)
    stable=app/"backend/venv"
    state["phase"]="restoring";save(control,state)
    if state["old_kind"]=="directory":
        saved=Path(state["old_saved"])
        if saved.exists():
            owned(saved,True)
            if stable.is_symlink() and stable.resolve()==Path(state["candidate"]):stable.unlink()
            elif stable.exists() or stable.is_symlink():raise ValueError("Pointer candidate tidak dikenal; jangan timpa")
            os.rename(saved,stable)
            sync_directory(root);sync_directory(stable.parent)
        if stable.is_symlink() or not stable.is_dir() or stable.stat().st_ino!=state["old_inode"] or stable.stat().st_dev!=state["old_device"]:
            raise ValueError("Venv directory lama tidak terbukti pulih")
    else:
        if not stable.is_symlink() or stable.resolve() not in {Path(state["candidate"]),Path(state["old_target"])}:
            raise ValueError("Pointer candidate tidak dikenal")
        atomic_link(state["old_link"],stable)
    actual=inventory(stable/"bin/python")
    if actual["distributions"]!=state["old_inventory"]["distributions"]:
        raise ValueError("Inventory lama berubah; jangan nyatakan rollback sehat")
    planned=state.get("legacy_manifest_planned")
    legacy=root/"legacy-retained.json"
    if planned and legacy.exists():
        if json.loads(owned(legacy,False).read_text())!=planned:
            raise ValueError("Manifest legacy berubah saat rollback")
        legacy.unlink();sync_directory(root)
    state["phase"]="restored";save(control,state)


def finalize(app,control,success):
    app,root,control,state=read_state(app,control)
    stable=app/"backend/venv"
    if success:
        if state["phase"]!="activated" or not stable.is_symlink() or stable.resolve()!=Path(state["candidate"]):
            raise ValueError("Aktivasi akhir tidak cocok")
        if state["old_kind"]=="directory":
            descriptor={"protocol":PROTOCOL,"source_sha":state["previous_sha"],"path":state["old_saved"],
                        "distributions":state["old_inventory"]["distributions"],"legacy":True}
            legacy=root/"legacy-retained.json"
            if legacy.exists() and json.loads(owned(legacy,False).read_text())!=descriptor:
                raise ValueError("Manifest legacy pertama tidak boleh ditimpa")
            if not legacy.exists():
                state["legacy_manifest_planned"]=descriptor;save(control,state)
                atomic_json(legacy,descriptor)
        state["phase"]="completed";save(control,state)
    else:
        if state["phase"] not in {"preparing","prepared","restored"}:raise ValueError("Recovery belum terbukti; candidate dipertahankan")
        candidate=Path(state["candidate"])
        if state["candidate_owned"] and candidate.exists():
            if stable.resolve()==candidate or state["old_target"]==str(candidate):raise ValueError("Jangan hapus env yang masih dirujuk")
            owned(candidate,True)
            shutil.rmtree(candidate)
            sync_directory(root)
    # Previous envs are intentionally retained. No age/prefix-based sweeping.


def attest_supervisor(app,path):
    app=Path(app).resolve();path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError("Config supervisor tidak dapat dipastikan")
    metadata=path.stat()
    if metadata.st_uid not in {0,os.geteuid()} or metadata.st_mode&0o022 or metadata.st_size>128*1024:
        raise ValueError("Pemilik/permission/ukuran config Supervisor tidak aman")
    parser=configparser.ConfigParser(interpolation=None)
    parser.read(path)
    section=parser["program:inventarisasi-backend"]
    command=shlex.split(section["command"])
    stable=app/"backend/venv/bin"
    accepted=(command[:2]==[str(stable/"uvicorn"),"server:app"] or
              command[:4]==[str(stable/"python"),"-m","uvicorn","server:app"])
    if not accepted or Path(section.get("directory","")).resolve()!=app/"backend":
        raise ValueError("Supervisor wajib menjalankan backend/venv pada direktori backend")
    if not section.getboolean("stopasgroup",False) or not section.getboolean("killasgroup",False):
        raise ValueError("Stop/killasgroup wajib agar seluruh worker lama berhenti")
    environment=section.get("environment","")
    if re.search(r"(?:^|,)\s*(?:PYTHONHOME|PYTHONPATH|PYTHONUSERBASE|MONGO_URL|DB_NAME)\s*=",environment):
        raise ValueError("Supervisor tidak boleh menyuntik jalur Python eksternal")


def attest_process(app,pid,base_python,proc=Path("/proc")):
    """Verify a fresh supervised process actually uses the stable entrypoint.

    Disk config alone cannot establish what supervisord has already loaded.
    Never print cmdline/environment: they can contain private configuration.
    """
    app=Path(app).resolve();stable=app/"backend/venv/bin"
    if not isinstance(pid,int) or pid<=1:raise ValueError("Supervisor PID tidak valid")
    process=Path(proc)/str(pid)
    def bounded(name):
        with (process/name).open("rb") as source:data=source.read(2*1024*1024+1)
        if len(data)>2*1024*1024:raise ValueError("Metadata process melebihi batas")
        return data
    before=bounded("stat")
    arguments=[value.decode() for value in bounded("cmdline").rstrip(b"\0").split(b"\0")]
    executable=Path(os.readlink(process/"exe")).resolve()
    cwd=Path(os.readlink(process/"cwd")).resolve()
    if executable!=Path(base_python).resolve() or cwd!=app/"backend":
        raise ValueError("Executable/cwd process backend tidak cocok")
    # Console scripts embed the immutable candidate interpreter path. The
    # script passed by Supervisor remains the stable uvicorn entrypoint.
    interpreter=bool(arguments and Path(arguments[0]).parent in {stable,stable.resolve()} and Path(arguments[0]).name in {"python","python3","python3.11"})
    command=arguments[1:]
    accepted=(command[:2]==[str(stable/"uvicorn"),"server:app"] or command[:3]==["-m","uvicorn","server:app"])
    if not interpreter or not accepted:raise ValueError("Process tidak memakai interpreter/entrypoint venv stabil")
    for value in bounded("environ").split(b"\0"):
        key,_,content=value.partition(b"=")
        if key in {b"PYTHONHOME",b"PYTHONPATH",b"PYTHONUSERBASE"} and content:
            raise ValueError("Process memakai jalur Python eksternal")
    after=bounded("stat")
    first=before.rsplit(b")",1)[1].split();last=after.rsplit(b")",1)[1].split()
    if first[19]!=last[19] or last[0] in {b"Z",b"T",b"t",b"X"}:
        raise ValueError("Process backend berubah/berhenti saat attestation")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["prepare","activate","restore","success","abort","show","attest","attest-process"])
    parser.add_argument("--app",required=True)
    parser.add_argument("--control")
    parser.add_argument("--target")
    parser.add_argument("--previous")
    parser.add_argument("--owner")
    parser.add_argument("--lock")
    parser.add_argument("--manual",action="store_true")
    parser.add_argument("--field",choices=["candidate_legacy","base_python"])
    parser.add_argument("--supervisor-config")
    parser.add_argument("--pid",type=int)
    parser.add_argument("--base-python")
    args=parser.parse_args()
    try:
        if args.action=="attest":attest_supervisor(args.app,args.supervisor_config)
        elif args.action=="attest-process":attest_process(args.app,args.pid,args.base_python)
        elif args.action=="prepare":prepare(args.app,args.control,args.target,args.previous,args.owner,args.lock,args.manual,
                                            native_smoke=Path(__file__).with_name("runtime_native_smoke.py"))
        elif args.action=="activate":activate(args.app,args.control)
        elif args.action=="restore":restore(args.app,args.control)
        elif args.action in {"success","abort"}:finalize(args.app,args.control,args.action=="success")
        elif args.action=="show":
            value=read_state(args.app,args.control)[3][args.field]
            print(int(value) if isinstance(value,bool) else value)
    except Exception:
        parser.exit(1,"GAGAL: transaksi environment backend tidak terverifikasi; periksa phase/state sebelum pemulihan.\n")


if __name__=="__main__":main()
