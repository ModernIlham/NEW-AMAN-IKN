#!/usr/bin/env python3
"""Artefak SHA tetap dan aktivasi pointer untuk staging terisolasi OPT-25.

Belum mengganti layout produksi. API activate() menerima callback restart/health
milik staging harness; CLI hanya package, stage, dan verify tanpa service ops.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
import platform
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid

SCHEMA=1
MAX_BYTES=512*1024*1024
MAX_FILES=30000


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda:source.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def full_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}",value):
        raise ValueError("SHA rilis wajib 40 karakter hex lowercase")
    return value


def relative_name(value):
    path=PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path)!=value or "\\" in value or not value:
        raise ValueError("Nama anggota artifact tidak aman")
    return value


def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True).strip()


def create_artifact(repo,build,release_sha,output,public_config=None):
    repo=Path(repo).resolve()
    build=Path(build).resolve()
    release_sha=full_sha(release_sha)
    if git(repo,"rev-parse","HEAD")!=release_sha:
        raise ValueError("HEAD source tidak sama dengan SHA CI yang diminta")
    runtime_paths=["backend","frontend/src","frontend/public","frontend/plugins","frontend/scripts",
                   "frontend/package.json","frontend/yarn.lock","frontend/craco.config.js"]
    if git(repo,"status","--porcelain","--untracked-files=all","--",*runtime_paths):
        raise ValueError("Source runtime dirty/untracked; artifact wajib dari checkout CI bersih")
    if not (build/"index.html").is_file() or not (build/"asset-manifest.json").is_file():
        raise ValueError("Frontend production build/asset-manifest.json tidak lengkap")
    configuration=public_config or {}
    allowed={"REACT_APP_BACKEND_URL","REACT_APP_VERSION","PUBLIC_URL"}
    if any(key not in allowed or not isinstance(value,str) for key,value in configuration.items()):
        raise ValueError("Manifest hanya menerima konfigurasi frontend publik yang dikenal")
    files={}
    for name in git(repo,"ls-files","backend").splitlines():
        path=Path(name)
        if "tests" in path.parts or "__pycache__" in path.parts or any(part.startswith(".env") for part in path.parts):
            continue
        source=repo/path
        if source.is_symlink() or not source.is_file():
            raise ValueError("Source artifact harus regular file tanpa symlink")
        files[name]=source
    for source in build.rglob("*"):
        if source.is_symlink():
            raise ValueError("Build artifact tidak boleh memuat symlink")
        if source.is_file():
            files["frontend/build/"+source.relative_to(build).as_posix()]=source
    if "backend/requirements.txt" not in files:
        raise ValueError("requirements backend tidak ditemukan")
    if len(files)>MAX_FILES or sum(path.stat().st_size for path in files.values())>MAX_BYTES:
        raise ValueError("Artifact melampaui batas file/bytes staging")
    frontend=json.loads(files["frontend/build/asset-manifest.json"].read_bytes())
    release_metadata=files.get("frontend/build/aman-release.json")
    if release_metadata is None or release_metadata.stat().st_size>1024*1024:
        raise ValueError("Metadata source SHA frontend hilang/terlalu besar")
    frontend_release=json.loads(release_metadata.read_bytes())
    if not isinstance(frontend_release,dict) or frontend_release.get("source_sha")!=release_sha:
        raise ValueError("Source SHA frontend berbeda dari source artifact")
    for path in [*frontend.get("files",{}).values(),*frontend.get("entrypoints",[])]:
        if not isinstance(path,str) or "://" in path or path.startswith("//") or "?" in path:
            raise ValueError("Manifest frontend menunjuk file di luar artifact")
        name="frontend/build/"+relative_name(path.lstrip("/"))
        if name not in files:
            raise ValueError("Chunk/media frontend yang dirujuk manifest tidak ada")
    manifest={"schema_version":SCHEMA,"release_sha":release_sha,"source_sha":release_sha,
        "toolchain":{"python":platform.python_version(),"node":os.environ.get("AMAN_BUILD_NODE_VERSION","not_supplied"),"yarn":os.environ.get("AMAN_BUILD_YARN_VERSION","not_supplied")},
        "public_config":configuration,"public_config_sha256":sha256(json.dumps(configuration,sort_keys=True).encode()),
        "requirements_sha256":file_sha256(files["backend/requirements.txt"]),
        "frontend_entrypoints":frontend.get("entrypoints",[]),"frontend_source_sha":frontend_release["source_sha"],
        "font_manifest":{name:file_sha256(path) for name,path in files.items() if Path(name).suffix.lower() in {".woff",".woff2",".ttf",".otf"}},
        "files":{name:{"sha256":file_sha256(path),"bytes":path.stat().st_size} for name,path in sorted(files.items())}}
    if Path(output).exists():
        raise ValueError("Artifact immutable sudah ada; tidak ditimpa")
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,"wb") as stream,tarfile.open(fileobj=stream,mode="w:gz") as archive:
            for name,path in files.items():
                info=tarfile.TarInfo(relative_name(name))
                info.size=path.stat().st_size
                info.mode=0o644
                info.mtime=0
                with path.open("rb") as source:
                    archive.addfile(info,source)
            data=json.dumps(manifest,sort_keys=True).encode()
            info=tarfile.TarInfo("release-manifest.json")
            info.size=len(data)
            info.mode=0o644
            archive.addfile(info,io.BytesIO(data))
    except BaseException:
        Path(output).unlink(missing_ok=True)
        raise
    return manifest


def staging_root(root):
    root=Path(root)
    if root.is_symlink():
        raise ValueError("Root staging tidak boleh symlink")
    resolved=root.resolve()
    # This utility deliberately cannot silently migrate /var/www production.
    if not (str(resolved).startswith("/tmp/aman-release-") or str(resolved).startswith("/workspace/.aman/release-staging-")):
        raise ValueError("Gunakan root staging khusus /tmp/aman-release-* atau /workspace/.aman/release-staging-*")
    resolved.mkdir(parents=True,exist_ok=True,mode=0o700)
    if resolved.stat().st_uid!=os.geteuid() or resolved.stat().st_mode&0o077:
        raise ValueError("Root staging harus milik pengguna ini dan privat mode0700")
    if (resolved/"releases").is_symlink():
        raise ValueError("Direktori releases tidak boleh symlink")
    (resolved/"releases").mkdir(exist_ok=True)
    return resolved


def verify_release(release):
    release=Path(release)
    if release.is_symlink() or not release.is_dir():
        raise ValueError("Release bukan direktori regular")
    if (release/"release-manifest.json").stat().st_size>8*1024*1024:
        raise ValueError("Manifest release terlalu besar")
    manifest=json.loads((release/"release-manifest.json").read_text())
    if (manifest.get("schema_version")!=SCHEMA or full_sha(manifest["release_sha"])!=release.name
            or manifest.get("source_sha")!=release.name):
        raise ValueError("Identitas/schema direktori release tidak cocok")
    expected=set(manifest["files"])
    if any(path.is_symlink() for path in release.rglob("*")):
        raise ValueError("Release memuat symlink setelah staging")
    actual={path.relative_to(release).as_posix() for path in release.rglob("*") if path.is_file()}
    if actual!=expected|{"release-manifest.json"}:
        raise ValueError("Set file release berbeda dari manifest")
    for name,meta in manifest["files"].items():
        source=release/relative_name(name)
        if source.is_symlink() or not source.is_file() or source.stat().st_size!=meta["bytes"] or file_sha256(source)!=meta["sha256"]:
            raise ValueError("Checksum/bytes release tidak cocok")
    return manifest


def stage_artifact(root,artifact,expected_sha,expected_digest):
    root=staging_root(root)
    expected_sha=full_sha(expected_sha)
    if Path(artifact).stat().st_size>MAX_BYTES+MAX_FILES*1024:
        raise ValueError("Ukuran archive terkompresi melampaui batas")
    if not re.fullmatch(r"[0-9a-f]{64}",expected_digest) or file_sha256(artifact)!=expected_digest:
        raise ValueError("Checksum archive bukan digest artifact CI yang dipercaya")
    temporary=Path(tempfile.mkdtemp(prefix=".stage-",dir=root))
    try:
        with tarfile.open(artifact,mode="r|gz") as archive:
            names=set()
            size=0
            for member in archive:
                size+=member.size
                if len(names)>=MAX_FILES+1 or size>MAX_BYTES:
                    raise ValueError("Batas artifact terlampaui")
                name=relative_name(member.name)
                if name in names or not member.isfile():
                    raise ValueError("Artifact duplicate/link/device/directory ditolak")
                if name=="release-manifest.json" and member.size>8*1024*1024:
                    raise ValueError("Manifest release terlalu besar")
                names.add(name)
                target=temporary/name
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as source,target.open("xb") as destination:
                    shutil.copyfileobj(source,destination,length=65536)
                target.chmod(0o644)
        manifest=json.loads((temporary/"release-manifest.json").read_text())
        if manifest.get("release_sha")!=expected_sha:
            raise ValueError("SHA artifact bukan SHA CI yang diharapkan")
        # Verification binds name to SHA before any pointer is eligible.
        named=temporary/expected_sha
        named.mkdir()
        for child in list(temporary.iterdir()):
            if child!=named:
                child.rename(named/child.name)
        verify_release(named)
        destination=root/"releases"/expected_sha
        if destination.exists():
            if verify_release(destination)!=manifest:
                raise ValueError("SHA yang sama memiliki artifact berbeda; immutable release ditolak")
        else:
            named.rename(destination)
        return destination
    finally:
        shutil.rmtree(temporary,ignore_errors=True)


def pointer(root,name):
    path=root/name
    if not path.exists() and not path.is_symlink():
        return None
    if not path.is_symlink():
        raise ValueError("Pointer rilis harus symlink")
    target=path.resolve(strict=True)
    if target.parent!=root/"releases" or not re.fullmatch(r"[0-9a-f]{40}",target.name):
        raise ValueError("Pointer menunjuk di luar releases staging")
    return target


def replace_pointer(root,name,target):
    temporary=root/("."+name+"-"+uuid.uuid4().hex)
    try:
        temporary.symlink_to(target.relative_to(root))
        os.replace(temporary,root/name)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive(root):
    import fcntl
    descriptor=os.open(root/".activation.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,"a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def activate(root,release_sha,prepare,restart,health):
    """Stage dependency first; atomically switch; verify pair; compensate failure.

    prepare(path) must create isolated dependency state before it returns.
    restart(path) handles only the isolated staging process. health(sha,path)
    must validate backend release SHA plus frontend/manifest/chunks together.
    Callbacks never come from shell strings; production services are not wired.
    """
    root=staging_root(root)
    target=root/"releases"/full_sha(release_sha)
    with exclusive(root):
        if (root/"RECOVERY_REQUIRED.json").exists():
            raise RuntimeError("RECOVERY_REQUIRED: verifikasi pemulihan operator wajib sebelum aktivasi")
        verify_release(target)
        previous=pointer(root,"current")
        prepare(target)  # Failure cannot touch current or its dependencies.
        switched=False
        try:
            switched=True
            replace_pointer(root,"current",target)
            restart(target)
            if not health(release_sha,target):
                raise RuntimeError("Health pasangan frontend/backend release gagal")
            if previous and previous!=target:
                replace_pointer(root,"previous",previous)
            return {"release_sha":release_sha,"previous_sha":previous.name if previous else None,"healthy":True}
        except BaseException as cause:
            if not switched:
                raise
            if previous:
                try:
                    replace_pointer(root,"current",previous)
                    restart(previous)
                    if not health(previous.name,previous):
                        raise RuntimeError("Health rollback gagal")
                except BaseException as rollback_error:
                    (root/"RECOVERY_REQUIRED.json").write_text(json.dumps({"target_sha":release_sha,"previous_sha":previous.name,"recovery_required":True}))
                    raise RuntimeError("RECOVERY_REQUIRED: pasangan sebelumnya belum sehat") from rollback_error
            else:
                (root/"current").unlink(missing_ok=True)
                (root/"RECOVERY_REQUIRED.json").write_text(json.dumps({"target_sha":release_sha,"previous_sha":None,"recovery_required":True}))
                raise RuntimeError("RECOVERY_REQUIRED: belum ada rilis known-good") from cause
            raise RuntimeError("Aktivasi gagal; pasangan release sebelumnya terverifikasi pulih") from cause


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    package=sub.add_parser("package")
    package.add_argument("--repo",required=True)
    package.add_argument("--frontend-build",required=True)
    package.add_argument("--sha",required=True)
    package.add_argument("--output",required=True)
    package.add_argument("--public-config",required=True)
    stage=sub.add_parser("stage")
    stage.add_argument("--root",required=True)
    stage.add_argument("--artifact",required=True)
    stage.add_argument("--sha",required=True)
    stage.add_argument("--artifact-sha256",required=True)
    verify=sub.add_parser("verify")
    verify.add_argument("--release",required=True)
    args=p.parse_args()
    if args.action=="package":
        config=json.loads(Path(args.public_config).read_text()) if args.public_config else {}
        result=create_artifact(args.repo,args.frontend_build,args.sha,args.output,config)
        print(json.dumps({"release_sha":result["release_sha"],"file_count":len(result["files"]),"artifact_sha256":file_sha256(args.output)}))
    elif args.action=="stage":
        print(stage_artifact(args.root,args.artifact,args.sha,args.artifact_sha256))
    else:
        result=verify_release(args.release)
        print(json.dumps({"release_sha":result["release_sha"],"verified":True}))


if __name__=="__main__":
    main()
