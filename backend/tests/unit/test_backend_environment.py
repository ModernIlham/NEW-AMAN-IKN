"""Real pipless venv transactions, using only tiny local hash-locked wheels.

Pip is an external test tool: its runner always injects --no-index and a local
wheelhouse. Venv creation, package installation, metadata, entry points, state
journals, rename boundaries, and rollback all use the production helper.
"""

import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/releases/backend_environment.py"
SPEC = importlib.util.spec_from_file_location("aman_test_backend_environment", SCRIPT)
environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(environment)
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
PROBE = "aman-environment-probe"


def _wheel(wheelhouse, name, version, *, entry_point=False):
    package = name.replace("-", "_")
    metadata = f"{package}-{version}.dist-info"
    source = f"VERSION = {version!r}\n"
    if entry_point:
        source += (
            "def main():\n"
            "    import json, sys\n"
            "    print(json.dumps({'version': VERSION, 'prefix': sys.prefix, 'executable': sys.executable}))\n"
            "    return 0\n"
        )
    files = {
        f"{package}/__init__.py": source.encode(),
        f"{metadata}/METADATA": (
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\nRequires-Python: >=3.11\n"
        ).encode(),
        f"{metadata}/WHEEL": b"Wheel-Version: 1.0\nGenerator: aman-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    if entry_point:
        files[f"{metadata}/entry_points.txt"] = (
            f"[console_scripts]\n{PROBE} = {package}:main\n"
        ).encode()
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for path, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        writer.writerow([path, "sha256=" + digest, len(content)])
    writer.writerow([f"{metadata}/RECORD", "", ""])
    files[f"{metadata}/RECORD"] = record.getvalue().encode()
    path = wheelhouse / f"{package}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name_in_zip, content in files.items():
            archive.writestr(name_in_zip, content)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _lock(path, requirements):
    path.write_text("".join(
        f"{name}=={version} \\\n    --hash=sha256:{digest}\n"
        for name, version, digest in requirements
    ))
    return path


def _command(arguments):
    return subprocess.run(
        [str(argument) for argument in arguments], env=environment.sanitized_environment(),
        text=True, capture_output=True, check=True, timeout=40,
    )


def _snapshot(directory):
    result = {}
    for path in directory.rglob("*"):
        relative = str(path.relative_to(directory))
        if path.is_symlink():
            result[relative] = ("link", os.readlink(path))
        elif path.is_file():
            result[relative] = ("file", stat.S_IMODE(path.stat().st_mode), hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            result[relative] = ("directory", stat.S_IMODE(path.stat().st_mode))
    return result


def _probe(stable, expected_path, version):
    script = stable / "bin" / PROBE
    result = json.loads(_command([script]).stdout)
    assert result["version"] == version
    assert Path(result["prefix"]).resolve() == expected_path.resolve()
    # Distlib uses a shell trampoline for paths with spaces; both forms retain
    # the permanent interpreter path inside the generated entry-point script.
    expected_interpreter = str(expected_path / "bin/python")
    assert expected_interpreter in script.read_text()
    assert result["executable"] == expected_interpreter
    return result


@pytest.fixture(scope="module")
def local_artifacts(tmp_path_factory):
    import pip

    directory = tmp_path_factory.mktemp("backend-environment-local-tools")
    wheelhouse = directory / "wheels"
    wheelhouse.mkdir()
    _, first_hash = _wheel(wheelhouse, "aman-environment-probe", "1.0", entry_point=True)
    _, second_hash = _wheel(wheelhouse, "aman-environment-probe", "2.0", entry_point=True)
    _, stale_hash = _wheel(wheelhouse, "aman-obsolete-fixture", "9.0")
    lock_a = _lock(directory / "a.lock", [
        ("aman-environment-probe", "1.0", first_hash),
        ("aman-obsolete-fixture", "9.0", stale_hash),
    ])
    lock_b = _lock(directory / "b.lock", [("aman-environment-probe", "2.0", second_hash)])
    lock_c = _lock(directory / "c.lock", [("aman-environment-probe", "1.0", first_hash)])
    events = directory / "installer-events.jsonl"
    runner = directory / "external-installer.py"
    runner.write_text(
        "import json, os, pathlib, runpy, sys\n"
        "for key in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE','_PIP_RUNNING_IN_SUBPROCESS'):\n"
        "    assert key not in os.environ, 'unsanitized Python/pip environment'\n"
        "assert [key for key in os.environ if key.startswith('PIP_')] == ['PIP_CONFIG_FILE']\n"
        "assert os.environ['PIP_CONFIG_FILE'] == os.devnull\n"
        "assert os.environ['PYTHONNOUSERSITE'] == '1'\n"
        "args = sys.argv[1:]\n"
        "if 'install' in args:\n"
        "    index = args.index('install') + 1\n"
        f"    args[index:index] = ['--no-index','--find-links',{str(wheelhouse)!r},'--no-cache-dir']\n"
        f"with pathlib.Path({str(events)!r}).open('a') as log:\n"
        "    log.write(json.dumps({'args': args}) + '\\n')\n"
        "sys.argv[1:] = args\n"
        f"sys.path.insert(0, {str(Path(pip.__file__).resolve().parent.parent)!r})\n"
        "runpy.run_module('pip', run_name='__main__', alter_sys=True)\n"
    )
    return SimpleNamespace(directory=directory, runner=runner, lock_a=lock_a, lock_b=lock_b,
                           lock_c=lock_c, events=events, second_hash=second_hash)


@pytest.fixture
def transaction(tmp_path, local_artifacts, monkeypatch):
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    app = tmp_path / "application with spaces"
    backend = app / "backend"
    backend.mkdir(parents=True)
    root = backend / ".venv-releases"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    stable = backend / "venv"
    _command([sys._base_executable, "-I", "-m", "venv", "--without-pip", stable])
    _command([sys._base_executable, "-I", "-S", local_artifacts.runner,
              "--isolated", "--python", stable / "bin/python", "install", "--require-hashes",
              "-r", local_artifacts.lock_a])
    old_inventory = environment.inventory(stable / "bin/python")["distributions"]
    assert old_inventory == {"aman-environment-probe": "1.0", "aman-obsolete-fixture": "9.0"}
    _probe(stable, stable, "1.0")
    original = _snapshot(stable)
    original_inode = stable.stat().st_ino
    sequence = 0

    def new_control():
        nonlocal sequence
        sequence += 1
        control = root / f".run-fixture-{sequence}"
        control.mkdir(mode=0o700)
        return control

    def prepare(*, target=SHA_B, previous=SHA_A, lock=None, manual=False, control=None):
        control = new_control() if control is None else control
        state = environment.prepare(
            app, control, target, previous, f"fixture:{sequence}",
            local_artifacts.lock_b if lock is None else lock,
            manual=manual, installer_runner=local_artifacts.runner,
            required_python=sys.version_info[:2],
        )
        return control, state

    def no_bootstrap(*args, **kwargs):
        raise AssertionError("Real bootstrap/network is outside this local-wheel fixture")
    monkeypatch.setattr(environment, "build_installer", no_bootstrap)
    return SimpleNamespace(app=app, root=root, stable=stable, original=original,
                           original_inode=original_inode, old_inventory=old_inventory,
                           new_control=new_control, prepare=prepare, artifacts=local_artifacts)


def _assert_original(transaction):
    assert transaction.stable.is_dir() and not transaction.stable.is_symlink()
    assert transaction.stable.stat().st_ino == transaction.original_inode
    assert _snapshot(transaction.stable) == transaction.original
    assert environment.inventory(transaction.stable / "bin/python")["distributions"] == transaction.old_inventory
    _probe(transaction.stable, transaction.stable, "1.0")


def test_real_pipless_a_b_a_restores_pristine_initial_directory(transaction, monkeypatch):
    t = transaction
    poison = t.app / "must remain absent"
    monkeypatch.setenv("_PIP_RUNNING_IN_SUBPROCESS", "1")
    monkeypatch.setenv("PYTHONPATH", str(poison / "python"))
    monkeypatch.setenv("PYTHONHOME", str(poison / "home"))
    monkeypatch.setenv("PYTHONUSERBASE", str(poison / "user"))
    monkeypatch.setenv("PIP_TARGET", str(poison / "target"))
    monkeypatch.setenv("PIP_PREFIX", str(poison / "prefix"))
    monkeypatch.setenv("PIP_USER", "1")
    control, state = t.prepare()
    candidate = Path(state["candidate"])
    assert state["phase"] == "prepared"
    _assert_original(t)
    expected = {"aman-environment-probe": "2.0"}
    actual = environment.inventory(candidate / "bin/python")["distributions"]
    assert actual == expected
    assert not (candidate / "bin/pip").exists()
    assert not (candidate / "bin/easy_install").exists()
    assert not {"pip", "setuptools", "aman-obsolete-fixture"} & actual.keys()
    metadata = json.loads((candidate / ".aman-environment.json").read_text())
    assert metadata["source_sha"] == SHA_B
    assert metadata["distributions"] == expected
    assert metadata["requirements_sha256"] == hashlib.sha256(t.artifacts.lock_b.read_bytes()).hexdigest()
    environment.activate(t.app, control)
    assert t.stable.is_symlink() and t.stable.resolve() == candidate
    _probe(t.stable, candidate, "2.0")
    assert _snapshot(Path(state["old_saved"])) == t.original
    environment.restore(t.app, control)
    _assert_original(t)
    environment.finalize(t.app, control, success=False)
    assert not candidate.exists()
    assert not poison.exists()
    events = [json.loads(line)["args"] for line in t.artifacts.events.read_text().splitlines()]
    assert any("check" in args and str(candidate / "bin/python") in args for args in events)
    assert all("--no-index" in args for args in events if "install" in args)


def test_success_retains_exact_legacy_sha_inventory_and_manual_a_rollback(transaction):
    t = transaction
    first_control, first_state = t.prepare()
    environment.activate(t.app, first_control)
    environment.finalize(t.app, first_control, success=True)
    b = Path(first_state["candidate"])
    saved_a = Path(first_state["old_saved"])
    manifest = json.loads((t.root / "legacy-retained.json").read_text())
    assert manifest["source_sha"] == SHA_A and len(manifest["source_sha"]) == 40
    assert manifest["distributions"] == t.old_inventory
    assert manifest["path"] == str(saved_a)
    assert _snapshot(saved_a) == t.original
    # The first retained legacy environment predates the clean-lock protocol.
    # Its exact SHA and recorded inventory support deliberate manual rollback.
    old_unhashed_lock = t.app / "legacy.lock"
    old_unhashed_lock.write_text("legacy requirements had no hash lock\n")
    manual_control, manual_state = t.prepare(target=SHA_A, previous=SHA_B, lock=old_unhashed_lock, manual=True)
    assert manual_state["candidate_legacy"] is True
    assert manual_state["candidate_owned"] is False
    assert Path(manual_state["candidate"]) == saved_a
    environment.activate(t.app, manual_control)
    _probe(t.stable, t.stable, "1.0")
    assert t.stable.resolve() == saved_a
    assert environment.inventory(t.stable / "bin/python")["distributions"] == t.old_inventory
    environment.restore(t.app, manual_control)
    assert t.stable.resolve() == b
    _probe(t.stable, b, "2.0")
    environment.finalize(t.app, manual_control, success=False)
    assert saved_a.is_dir() and b.is_dir()
    assert _snapshot(saved_a) == t.original


def test_future_managed_switch_and_rollback_preserve_previous_symlink(transaction):
    t = transaction
    first_control, first_state = t.prepare()
    environment.activate(t.app, first_control)
    environment.finalize(t.app, first_control, success=True)
    old_link = os.readlink(t.stable)
    old_b = Path(first_state["candidate"])
    old_b_snapshot = _snapshot(old_b)
    next_control, next_state = t.prepare(target=SHA_C, previous=SHA_B, lock=t.artifacts.lock_c)
    c = Path(next_state["candidate"])
    environment.activate(t.app, next_control)
    assert t.stable.resolve() == c
    _probe(t.stable, c, "1.0")
    environment.restore(t.app, next_control)
    assert os.readlink(t.stable) == old_link
    assert t.stable.resolve() == old_b
    assert _snapshot(old_b) == old_b_snapshot
    environment.finalize(t.app, next_control, success=False)
    assert not c.exists() and old_b.exists()


@pytest.mark.parametrize("boundary", ["after_directory_rename", "after_new_link"])
def test_interrupted_initial_migration_uses_real_disk_state_to_restore(transaction, monkeypatch, boundary):
    t = transaction
    control, state = t.prepare()
    candidate = Path(state["candidate"])
    saved = Path(state["old_saved"])
    with monkeypatch.context() as interrupted:
        if boundary == "after_directory_rename":
            real_rename = environment.os.rename
            def rename_then_interrupt(source, destination):
                real_rename(source, destination)
                if Path(source) == t.stable and Path(destination) == saved:
                    raise KeyboardInterrupt("simulated signal after real rename")
            interrupted.setattr(environment.os, "rename", rename_then_interrupt)
        else:
            real_link = environment.atomic_link
            def link_then_interrupt(target, stable):
                real_link(target, stable)
                raise KeyboardInterrupt("simulated signal after real symlink swap")
            interrupted.setattr(environment, "atomic_link", link_then_interrupt)
        with pytest.raises(KeyboardInterrupt):
            environment.activate(t.app, control)
    assert saved.is_dir()
    assert json.loads((control / "state.json").read_text())["phase"] == "switching"
    if boundary == "after_directory_rename":
        assert not t.stable.exists() and not t.stable.is_symlink()
    else:
        assert t.stable.is_symlink() and t.stable.resolve() == candidate
    environment.restore(t.app, control)
    _assert_original(t)
    assert not saved.exists()
    environment.finalize(t.app, control, success=False)
    assert not candidate.exists()


def test_late_failure_after_finalize_removes_only_its_legacy_journal(transaction):
    t = transaction
    control, state = t.prepare()
    environment.activate(t.app, control)
    environment.finalize(t.app, control, success=True)
    assert (t.root / "legacy-retained.json").is_file()
    assert json.loads((control / "state.json").read_text())["phase"] == "completed"
    # Deployment can still fail when its persistent mutex release fails.
    environment.restore(t.app, control)
    _assert_original(t)
    assert not (t.root / "legacy-retained.json").exists()
    environment.finalize(t.app, control, success=False)
    assert not Path(state["candidate"]).exists()


def test_failed_hashed_install_never_switches_and_cleans_only_its_candidate(transaction):
    t = transaction
    bad_lock = _lock(t.app / "bad.lock", [("aman-environment-probe", "2.0", "0" * 64)])
    neighbor = t.root / "unrelated-environment"
    neighbor.mkdir()
    (neighbor / "keep").write_text("untouched")
    control = t.new_control()
    with pytest.raises(RuntimeError, match="gagal"):
        t.prepare(lock=bad_lock, control=control)
    _assert_original(t)
    state = json.loads((control / "state.json").read_text())
    candidate = Path(state["candidate"])
    assert candidate.is_dir()
    environment.finalize(t.app, control, success=False)
    assert not candidate.exists()
    assert (neighbor / "keep").read_text() == "untouched"
    _assert_original(t)


@pytest.mark.parametrize("contents", [
    "", "aman-probe==1.0\n", "aman-probe>=1.0\n",
    "aman-probe==1.0 --hash=sha256:" + "1" * 64 + "\n",
    "--index-url https://unapproved.example/simple\n",
    "aman-probe==1.0; python_version >= '3.11'\n",
    "aman-probe==1.0 \\\n --hash=sha256:short\n",
    "--hash=sha256:" + "1" * 64 + "\n",
    "aman_probe==1.0 \\\n --hash=sha256:" + "1" * 64 + "\naman-probe==2.0 \\\n --hash=sha256:" + "2" * 64 + "\n",
])
def test_malformed_unhashed_or_duplicate_lock_is_rejected(tmp_path, contents):
    lock = tmp_path / "invalid.lock"
    lock.write_text(contents)
    with pytest.raises(ValueError):
        environment.parse_lock(lock)


def test_unhashed_prepare_fails_before_creating_a_candidate(transaction):
    t = transaction
    invalid = t.app / "unhashed.lock"
    invalid.write_text("aman-environment-probe==2.0\n")
    control = t.new_control()
    with pytest.raises(ValueError, match="hash"):
        t.prepare(lock=invalid, control=control)
    state = json.loads((control / "state.json").read_text())
    assert not Path(state["candidate"]).exists()
    _assert_original(t)
    environment.finalize(t.app, control, success=False)


@pytest.mark.parametrize("kind", ["foreign_root_symlink", "writable_root", "public_control", "foreign_control"])
def test_roots_reject_foreign_symlinks_or_unsafe_permissions(tmp_path, kind):
    app = tmp_path / "app"
    backend = app / "backend"
    backend.mkdir(parents=True)
    root = backend / ".venv-releases"
    if kind == "foreign_root_symlink":
        foreign = tmp_path / "foreign"
        foreign.mkdir(mode=0o755)
        (foreign / "keep").write_text("untouched")
        root.symlink_to(foreign, target_is_directory=True)
    else:
        root.mkdir(mode=0o755)
    control = root / ".run-test"
    if kind == "foreign_control":
        control = tmp_path / ".run-foreign"
    control.mkdir(mode=0o700)
    if kind == "writable_root":
        root.chmod(0o777)
    if kind == "public_control":
        control.chmod(0o755)
    with pytest.raises(ValueError):
        environment.roots(app, control)
    assert not (control / "state.json").exists()
    if kind == "foreign_root_symlink":
        assert (foreign / "keep").read_text() == "untouched"


def test_external_stable_symlink_is_rejected_without_mutating_its_target(transaction, tmp_path):
    t = transaction
    foreign = tmp_path / "foreign-existing-environment"
    os.rename(t.stable, foreign)
    original = _snapshot(foreign)
    t.stable.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="luar root"):
        t.prepare()
    assert t.stable.is_symlink() and t.stable.resolve() == foreign
    assert _snapshot(foreign) == original


def test_stable_symlink_must_belong_to_deployer(transaction, monkeypatch):
    t = transaction
    old = t.root / "retained-old"
    os.rename(t.stable, old)
    t.stable.symlink_to(old, target_is_directory=True)
    original_lstat = Path.lstat
    def foreign_owner(path, *args, **kwargs):
        metadata = original_lstat(path, *args, **kwargs)
        if path == t.stable:
            values = list(metadata)
            values[4] = os.geteuid() + 1
            return os.stat_result(values)
        return metadata
    with monkeypatch.context() as ownership:
        ownership.setattr(Path, "lstat", foreign_owner)
        with pytest.raises(ValueError, match="deployer"):
            t.prepare()
    assert t.stable.resolve() == old
    assert _snapshot(old) == t.original


def test_manual_retained_legacy_refuses_changed_inventory(transaction):
    t = transaction
    control, state = t.prepare()
    environment.activate(t.app, control)
    environment.finalize(t.app, control, success=True)
    legacy = Path(state["old_saved"])
    site = next((legacy / "lib").glob("python*/site-packages"))
    metadata = site / "foreign_added-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: foreign-added\nVersion: 1.0\n")
    active = t.stable.resolve()
    with pytest.raises(ValueError, match="Inventory retained"):
        t.prepare(target=SHA_A, previous=SHA_B, lock=t.artifacts.lock_a, manual=True)
    assert t.stable.resolve() == active


def test_manual_legacy_matching_requires_the_complete_sha(transaction):
    t = transaction
    control, _ = t.prepare()
    environment.activate(t.app, control)
    environment.finalize(t.app, control, success=True)
    registry = t.root / "legacy-retained.json"
    descriptor = json.loads(registry.read_text())
    descriptor["source_sha"] = SHA_A[:12]
    registry.write_text(json.dumps(descriptor))
    invalid = t.app / "legacy-unhashed.lock"
    invalid.write_text("legacy has no current hash lock\n")
    active = t.stable.resolve()
    with pytest.raises(ValueError, match="lock|pin|hash"):
        t.prepare(target=SHA_A, previous=SHA_B, lock=invalid, manual=True)
    assert t.stable.resolve() == active


def test_preexisting_candidate_collision_never_grants_cleanup_ownership(transaction, monkeypatch):
    t = transaction
    identifier = "d" * 32
    collision = t.root / (SHA_B + "-" + identifier)
    collision.mkdir()
    (collision / "keep").write_bytes(b"preexisting environment owned by another run")
    control = t.new_control()
    with monkeypatch.context() as fixed_identifier:
        fixed_identifier.setattr(environment.uuid, "uuid4", lambda: SimpleNamespace(hex=identifier))
        with pytest.raises(FileExistsError):
            t.prepare(control=control)
    journal = json.loads((control / "state.json").read_text())
    assert journal["candidate"] == str(collision)
    assert journal["candidate_owned"] is False
    environment.finalize(t.app, control, success=False)
    assert (collision / "keep").read_bytes() == b"preexisting environment owned by another run"
    _assert_original(t)


def test_replaced_candidate_inode_blocks_activation_and_cleanup(transaction):
    t = transaction
    control, state = t.prepare()
    candidate = Path(state["candidate"])
    original_allocation = t.root / "original-allocation-preserved"
    candidate.rename(original_allocation)
    candidate.mkdir()
    (candidate / "keep").write_bytes(b"replacement must survive")
    assert candidate.stat().st_ino != original_allocation.stat().st_ino
    with pytest.raises(ValueError, match="Allocation candidate"):
        environment.activate(t.app, control)
    with pytest.raises(ValueError, match="Allocation candidate"):
        environment.finalize(t.app, control, success=False)
    assert (candidate / "keep").read_bytes() == b"replacement must survive"
    assert original_allocation.is_dir()
    _assert_original(t)
