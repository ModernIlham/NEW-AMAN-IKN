#!/usr/bin/env python3
"""Bootstrap a hash-pinned pip tool without adding tools to the runtime venv.

The caller supplies its verified base Python and a fresh private directory. Run
the returned runner with that Python, ``-I -S``, and ``sanitized_environment()``.
Installation into a pipless runtime uses ``--isolated --python RUNTIME_PYTHON``.
Failed builds retain their private staging directory for the caller to handle.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Mapping
import urllib.error
import urllib.request
import zipfile


PIP_VERSION = "26.2.1"
WHEEL_FILENAME = "pip-26.2.1-py3-none-any.whl"
WHEEL_SHA256 = "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e"
WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f3/6e/"
    "1736e5b4ae2b778ef2f81c47d797de9f891d4d8acb047a24ca37a60294dd/"
    + WHEEL_FILENAME
)
MAX_WHEEL_BYTES = 16 * 1024 * 1024
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 5000
_CHUNK_BYTES = 64 * 1024


class PinnedInstallerError(ValueError):
    """The fixed installer artifact or its staging directory is unsuitable."""


def sanitized_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Keep proxy/CA bindings while removing Python and pip destination overrides."""
    source = os.environ if environment is None else environment
    removed = {"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "_PIP_RUNNING_IN_SUBPROCESS"}
    result = {
        name: value
        for name, value in source.items()
        if name not in removed and not name.startswith("PIP_")
    }
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PYTHONNOUSERSITE"] = "1"
    return result


def _private_directory(directory: Path) -> None:
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    metadata = directory.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise PinnedInstallerError("Installer directory must be owned, private, and not a symlink")
    if any(directory.iterdir()):
        raise PinnedInstallerError("Installer directory must be empty")


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PinnedInstallerError("Installer download redirects are not permitted")


def _download_wheel(destination: Path) -> None:
    # The default opener preserves configured HTTPS proxies and CA validation.
    opener = urllib.request.build_opener(_RejectRedirects())
    try:
        with opener.open(WHEEL_URL, timeout=30) as response:
            if response.geturl() != WHEEL_URL or response.status != 200:
                raise PinnedInstallerError("Unexpected installer download response")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared_size = int(length)
                except ValueError:
                    raise PinnedInstallerError("Invalid installer download size") from None
                if not 0 < declared_size <= MAX_WHEEL_BYTES:
                    raise PinnedInstallerError("Installer download exceeds size limit")
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as target:
                count = 0
                while block := response.read(_CHUNK_BYTES):
                    count += len(block)
                    if count > MAX_WHEEL_BYTES:
                        raise PinnedInstallerError("Installer download exceeds size limit")
                    target.write(block)
                if length is not None and count != declared_size:
                    raise PinnedInstallerError("Incomplete installer download")
    except (urllib.error.URLError, TimeoutError, OSError):
        # Proxy/network exceptions may contain credential-bearing URLs.
        raise PinnedInstallerError("Installer download failed with TLS verification enabled") from None


def _validated_members(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    members = archive.infolist()
    if not members or len(members) > MAX_MEMBERS:
        raise PinnedInstallerError("Installer archive exceeds member limit")
    validated = []
    paths: dict[PurePosixPath, bool] = {}
    total = 0
    for member in members:
        name = member.filename
        components = name.rstrip("/").split("/")
        path = PurePosixPath(name)
        mode = member.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if (
            member.orig_filename != name
            or "\x00" in name
            or "\\" in name
            or ":" in name
            or path.is_absolute()
            or any(part in ("", ".", "..") for part in components)
            or file_type not in (0, stat.S_IFREG, stat.S_IFDIR)
            or (file_type == stat.S_IFDIR and not member.is_dir())
            or (member.is_dir() and file_type == stat.S_IFREG)
            or member.flag_bits & 1
            or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
        ):
            raise PinnedInstallerError("Unsafe installer archive member")
        if path in paths:
            raise PinnedInstallerError("Duplicate installer archive member")
        if member.file_size > MAX_MEMBER_BYTES:
            raise PinnedInstallerError("Installer archive member exceeds size limit")
        total += member.file_size
        if total > MAX_EXTRACTED_BYTES:
            raise PinnedInstallerError("Installer archive exceeds extracted size limit")
        paths[path] = member.is_dir()
        validated.append((member, path))
    for path in paths:
        if any(parent in paths and not paths[parent] for parent in path.parents):
            raise PinnedInstallerError("Conflicting installer archive members")
    return validated


def _extract_verified_wheel(wheel_path: Path, destination: Path, *, expected_sha256: str) -> None:
    """Verify before extracting; the hash argument is internal, never a CLI option."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise PinnedInstallerError("Invalid expected installer hash")
    try:
        fd = os.open(wheel_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as wheel:
            metadata = os.fstat(wheel.fileno())
            if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_WHEEL_BYTES:
                raise PinnedInstallerError("Installer wheel is not a bounded regular file")
            payload = wheel.read(MAX_WHEEL_BYTES + 1)
            if len(payload) > MAX_WHEEL_BYTES:
                raise PinnedInstallerError("Installer wheel exceeds size limit")
            if hashlib.sha256(payload).hexdigest() != expected_sha256:
                raise PinnedInstallerError("Installer wheel SHA256 does not match the approved pin")
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = _validated_members(archive)
                destination.mkdir(mode=0o700)
                for member, relative in members:
                    target = destination.joinpath(*relative.parts)
                    if member.is_dir():
                        target.mkdir(mode=0o700, parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, "wb") as output, archive.open(member) as source:
                        written = 0
                        while block := source.read(_CHUNK_BYTES):
                            written += len(block)
                            if written > member.file_size or written > MAX_MEMBER_BYTES:
                                raise PinnedInstallerError("Installer archive member exceeds size limit")
                            output.write(block)
                        if written != member.file_size:
                            raise PinnedInstallerError("Incomplete installer archive member")
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise PinnedInstallerError("Installer wheel could not be safely extracted") from None


def _write_runner(directory: Path) -> Path:
    runner = directory / "runner.py"
    source = (
        "import pathlib, runpy, sys\n"
        "site = pathlib.Path(__file__).resolve().parent / 'site'\n"
        "sys.path.insert(0, str(site))\n"
        "runpy.run_module('pip', run_name='__main__', alter_sys=True)\n"
    )
    fd = os.open(runner, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(source)
    return runner


def build_installer(directory: str | Path, wheel_path: str | Path | None = None) -> Path:
    """Return a standalone pip runner verified against the fixed approved wheel."""
    directory = Path(directory).absolute()
    _private_directory(directory)
    if wheel_path is None:
        wheel = directory / WHEEL_FILENAME
        _download_wheel(wheel)
    else:
        wheel = Path(wheel_path)
    _extract_verified_wheel(wheel, directory / "site", expected_sha256=WHEEL_SHA256)
    return _write_runner(directory)


bootstrap_installer = build_installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--wheel", type=Path, help="Use a local copy of the same approved wheel")
    args = parser.parse_args(argv)
    try:
        runner = build_installer(args.directory, args.wheel)
    except (PinnedInstallerError, OSError):
        print("GAGAL: bootstrap installer pip terverifikasi tidak dapat disiapkan.", file=sys.stderr)
        return 1
    print(runner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
