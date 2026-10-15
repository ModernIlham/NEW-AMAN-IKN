"""Network-free checks for the separate, hash-pinned deployment installer."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import warnings
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/releases/pinned_installer.py"
SPEC = importlib.util.spec_from_file_location("pinned_installer", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Installer unit tests must never access the network")
    monkeypatch.setattr(installer.urllib.request.OpenerDirector, "open", forbidden)


def make_wheel(tmp_path, members=None):
    members = [("pip/__init__.py", b"__version__ = 'fixture'\n")] if members is None else members
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in members:
                archive.writestr(name, content)
    payload = buffer.getvalue()
    wheel = tmp_path / "fixture.whl"
    wheel.write_bytes(payload)
    return wheel, hashlib.sha256(payload).hexdigest()


def extract(wheel, destination, digest):
    installer._extract_verified_wheel(wheel, destination, expected_sha256=digest)


def test_pin_matches_reviewed_requirements_and_provenance():
    metadata = json.loads((ROOT / "docs/bukti-optimasi/OPT-24/installer-bootstrap.json").read_text())
    assert installer.PIP_VERSION == metadata["version"] == "26.2.1"
    assert installer.WHEEL_SHA256 == metadata["sha256"]
    assert installer.WHEEL_FILENAME == metadata["filename"]
    assert installer.WHEEL_URL == metadata["url"]
    requirements = (ROOT / "scripts/releases/installer-requirements.txt").read_text()
    assert f"pip=={installer.PIP_VERSION} --hash=sha256:{installer.WHEEL_SHA256}" in requirements


def test_verified_fixture_extracts_only_into_private_site(tmp_path):
    wheel, digest = make_wheel(tmp_path, [
        ("pip/", b""),
        ("pip/__init__.py", b"__version__ = 'fixture'\n"),
        ("pip/_vendor/data.txt", b"verified data"),
    ])
    destination = tmp_path / "site"
    extract(wheel, destination, digest)
    assert (destination / "pip/_vendor/data.txt").read_bytes() == b"verified data"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert stat.S_IMODE((destination / "pip/__init__.py").stat().st_mode) == 0o600
    assert not (destination / "setuptools").exists()


def test_checksum_is_checked_before_creating_site(tmp_path):
    wheel, _ = make_wheel(tmp_path)
    with pytest.raises(installer.PinnedInstallerError, match="SHA256"):
        extract(wheel, tmp_path / "site", "0" * 64)
    assert not (tmp_path / "site").exists()


def test_production_api_refuses_an_unapproved_local_wheel(tmp_path):
    wheel, _ = make_wheel(tmp_path)
    directory = tmp_path / "installer"
    with pytest.raises(installer.PinnedInstallerError, match="approved pin"):
        installer.build_installer(directory, wheel)
    assert directory.is_dir()
    assert not (directory / "site").exists()
    assert not (directory / "runner.py").exists()


@pytest.mark.parametrize("name", [
    "../escape.py", "pip/../../escape.py", "/absolute.py", "C:/escape.py",
    "pip\\escape.py", "pip//escape.py", "./pip.py", "pip/./escape.py",
])
def test_archive_paths_rejected_before_any_extraction(tmp_path, name):
    wheel, digest = make_wheel(tmp_path, [(name, b"unsafe")])
    with pytest.raises(installer.PinnedInstallerError, match="Unsafe"):
        extract(wheel, tmp_path / "site", digest)
    assert not (tmp_path / "site").exists()
    assert not (tmp_path / "escape.py").exists()


def test_raw_nul_filename_is_rejected_before_extraction(tmp_path):
    wheel, _ = make_wheel(tmp_path, [("pipXevil.py", b"unsafe")])
    # ZipInfo truncates NULs when writing, so construct the on-disk malformed
    # local/central filename directly rather than testing a normalized fixture.
    payload = wheel.read_bytes().replace(b"pipXevil.py", b"pip\x00evil.py")
    wheel.write_bytes(payload)
    with pytest.raises(installer.PinnedInstallerError, match="Unsafe"):
        extract(wheel, tmp_path / "site", hashlib.sha256(payload).hexdigest())
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("kind", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFSOCK])
def test_non_regular_archive_members_are_rejected(tmp_path, kind):
    member = zipfile.ZipInfo("pip/foreign")
    member.create_system = 3
    member.external_attr = (kind | 0o777) << 16
    wheel, digest = make_wheel(tmp_path, [(member, b"../../outside")])
    with pytest.raises(installer.PinnedInstallerError, match="Unsafe"):
        extract(wheel, tmp_path / "site", digest)
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("members", [
    [("pip/file.py", b"first"), ("pip/file.py", b"second")],
    [("pip", b"file"), ("pip/child.py", b"nested")],
])
def test_duplicate_and_file_directory_conflicts_are_rejected(tmp_path, members):
    wheel, digest = make_wheel(tmp_path, members)
    with pytest.raises(installer.PinnedInstallerError, match="Duplicate|Conflicting"):
        extract(wheel, tmp_path / "site", digest)
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("limit,value", [
    ("MAX_WHEEL_BYTES", 1), ("MAX_MEMBERS", 1),
    ("MAX_MEMBER_BYTES", 3), ("MAX_EXTRACTED_BYTES", 7),
])
def test_archive_resource_bounds_before_extraction(tmp_path, monkeypatch, limit, value):
    wheel, digest = make_wheel(tmp_path, [("pip/one.py", b"1234"), ("pip/two.py", b"5678")])
    monkeypatch.setattr(installer, limit, value)
    with pytest.raises(installer.PinnedInstallerError, match="bounded|limit"):
        extract(wheel, tmp_path / "site", digest)
    assert not (tmp_path / "site").exists()


def test_symlink_wheel_and_existing_destination_are_not_followed(tmp_path):
    wheel, digest = make_wheel(tmp_path)
    linked_wheel = tmp_path / "linked.whl"
    linked_wheel.symlink_to(wheel)
    with pytest.raises(installer.PinnedInstallerError):
        extract(linked_wheel, tmp_path / "new-site", digest)
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep").write_bytes(b"untouched")
    destination = tmp_path / "site"
    destination.symlink_to(victim, target_is_directory=True)
    with pytest.raises(installer.PinnedInstallerError):
        extract(wheel, destination, digest)
    assert list(victim.iterdir()) == [victim / "keep"]
    assert (victim / "keep").read_bytes() == b"untouched"


def test_fifo_wheel_is_rejected_without_waiting_for_a_writer(tmp_path):
    wheel = tmp_path / "pipe.whl"
    os.mkfifo(wheel, mode=0o600)
    with pytest.raises(installer.PinnedInstallerError, match="regular file"):
        extract(wheel, tmp_path / "site", "0" * 64)
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("kind", ["public", "symlink", "nonempty"])
def test_installer_directory_cannot_reuse_unsafe_or_stale_paths(tmp_path, kind):
    wheel, _ = make_wheel(tmp_path)
    directory = tmp_path / "installer"
    if kind == "symlink":
        victim = tmp_path / "victim"
        victim.mkdir(mode=0o700)
        directory.symlink_to(victim, target_is_directory=True)
    else:
        directory.mkdir(mode=0o700)
        if kind == "public":
            directory.chmod(0o755)
        else:
            (directory / "keep").write_bytes(b"untouched")
    with pytest.raises(installer.PinnedInstallerError, match="private|empty"):
        installer.build_installer(directory, wheel)
    assert not (directory / "site").exists()
    if kind == "nonempty":
        assert (directory / "keep").read_bytes() == b"untouched"


def test_corrupt_zip_is_never_executable(tmp_path):
    wheel = tmp_path / "corrupt.whl"
    wheel.write_bytes(b"not a zip archive")
    with pytest.raises(installer.PinnedInstallerError, match="safely extracted"):
        extract(wheel, tmp_path / "site", hashlib.sha256(wheel.read_bytes()).hexdigest())
    assert not (tmp_path / "site").exists()


def test_runner_uses_only_extracted_pip_and_keeps_arguments(tmp_path):
    fake_main = (
        "import json, pathlib, sys, pip\n"
        "print(json.dumps({'module':str(pathlib.Path(pip.__file__).resolve()),"
        "'args':sys.argv[1:],'setuptools':'setuptools' in sys.modules}))\n"
    ).encode()
    wheel, digest = make_wheel(tmp_path, [
        ("pip/__init__.py", b"__version__ = 'fixture'\n"),
        ("pip/__main__.py", fake_main),
    ])
    directory = tmp_path / "installer with spaces"
    directory.mkdir(mode=0o700)
    extract(wheel, directory / "site", digest)
    runner = installer._write_runner(directory)
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(runner), "--python", "/runtime with spaces/bin/python", "check"],
        env=installer.sanitized_environment(), capture_output=True, text=True, check=True, timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "module": str(directory / "site/pip/__init__.py"),
        "args": ["--python", "/runtime with spaces/bin/python", "check"],
        "setuptools": False,
    }
    assert stat.S_IMODE(runner.stat().st_mode) == 0o600


def test_environment_sanitization_keeps_proxy_and_ca_bindings():
    environment = {
        "PATH": "/trusted/bin", "HOME": "/home/example",
        "PYTHONHOME": "/foreign", "PYTHONPATH": "/foreign/site", "PYTHONUSERBASE": "/foreign/user",
        "PIP_TARGET": "/foreign/target", "PIP_PREFIX": "/foreign/prefix", "PIP_USER": "1",
        "PIP_CONFIG_FILE": "/foreign/pip.conf", "PIP_REQUIRE_VIRTUALENV": "1",
        "PIP_INDEX_URL": "https://index.example/simple", "PIP_TRUSTED_HOST": "foreign.example",
        "_PIP_RUNNING_IN_SUBPROCESS": "1", "PYTHONNOUSERSITE": "0",
        "HTTPS_PROXY": "https://proxy.example", "https_proxy": "https://proxy-lower.example",
        "HTTP_PROXY": "http://proxy.example", "NO_PROXY": "localhost",
        "SSL_CERT_FILE": "/trusted/ca.pem", "SSL_CERT_DIR": "/trusted/ca",
        "REQUESTS_CA_BUNDLE": "/trusted/requests.pem", "CURL_CA_BUNDLE": "/trusted/curl.pem",
    }
    before = dict(environment)
    sanitized = installer.sanitized_environment(environment)
    assert environment == before
    for name in environment:
        if name.startswith("PIP_") or name in {
            "PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "_PIP_RUNNING_IN_SUBPROCESS", "PYTHONNOUSERSITE",
        }:
            continue
        assert sanitized[name] == environment[name]
    assert {name for name in sanitized if name.startswith("PIP_")} == {"PIP_CONFIG_FILE"}
    assert sanitized["PIP_CONFIG_FILE"] == os.devnull
    assert sanitized["PYTHONNOUSERSITE"] == "1"
    assert not {"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "_PIP_RUNNING_IN_SUBPROCESS"} & sanitized.keys()


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, payload, length=None, url=None):
        super().__init__(payload)
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.url = installer.WHEEL_URL if url is None else url

    def geturl(self):
        return self.url


def mock_response(monkeypatch, response):
    class FakeOpener:
        def open(self, url, timeout):
            assert url == installer.WHEEL_URL
            assert timeout == 30
            return response
    monkeypatch.setattr(installer.urllib.request, "build_opener", lambda handler: FakeOpener())


def test_download_uses_fixed_url_and_private_exclusive_file(tmp_path, monkeypatch):
    response = FakeResponse(b"fixture", length=7)
    mock_response(monkeypatch, response)
    destination = tmp_path / installer.WHEEL_FILENAME
    installer._download_wheel(destination)
    assert destination.read_bytes() == b"fixture"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    mock_response(monkeypatch, FakeResponse(b"replacement", length=11))
    with pytest.raises(installer.PinnedInstallerError):
        installer._download_wheel(destination)
    assert destination.read_bytes() == b"fixture"


@pytest.mark.parametrize("payload,length", [(b"123456", None), (b"1", 10), (b"1", "invalid"), (b"1", -1)])
def test_download_is_bounded_even_without_trusted_content_length(tmp_path, monkeypatch, payload, length):
    monkeypatch.setattr(installer, "MAX_WHEEL_BYTES", 5)
    mock_response(monkeypatch, FakeResponse(payload, length))
    with pytest.raises(installer.PinnedInstallerError, match="limit|size"):
        installer._download_wheel(tmp_path / "download.whl")


def test_download_rejects_truncation_and_different_final_url(tmp_path, monkeypatch):
    mock_response(monkeypatch, FakeResponse(b"short", length=10))
    with pytest.raises(installer.PinnedInstallerError, match="Incomplete"):
        installer._download_wheel(tmp_path / "truncated.whl")
    mock_response(monkeypatch, FakeResponse(b"data", url="http://files.pythonhosted.org/other"))
    with pytest.raises(installer.PinnedInstallerError, match="Unexpected"):
        installer._download_wheel(tmp_path / "redirected.whl")
    assert not (tmp_path / "redirected.whl").exists()


def test_http_redirects_are_rejected():
    with pytest.raises(installer.PinnedInstallerError, match="redirects"):
        installer._RejectRedirects().redirect_request(None, None, 302, "", {}, "http://other.example/")


def test_cli_has_no_pin_override_and_does_not_prepare_directory(tmp_path):
    directory = tmp_path / "installer"
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), str(directory), "--sha256", "0" * 64],
        env=installer.sanitized_environment(), capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert not directory.exists()
