"""Offline DR snapshot and encrypted offsite adapter; invoked only by operator.

No scheduler or provider is enabled here. Keys/credentials come from local
operator configuration. The adapter verifies a full remote readback before it
reports success; metadata/HEAD alone never counts as a readable backup.
"""
import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from urllib.parse import urlsplit
import zipfile
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from backup_archive import CHUNK_SIZE, validate_archive, write_manifest

MAGIC = b"AMAN-DR1\n"
CONSISTENCY = "database_fsync_locked_services_stopped"


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as fp:
        while True:
            chunk = fp.read(CHUNK_SIZE)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def load_key(path):
    path = Path(path)
    if path.stat().st_mode & 0o077:
        raise ValueError("Key DR harus privat (chmod 600); simpan salinan di luar host")
    with path.open("rb") as fp:
        key = fp.read(33)
    if len(key) != 32:
        raise ValueError("Key DR wajib 32 byte acak; bukan password teks")
    return key


def machine_fingerprint():
    """Opaque host identity; no hostname/address is recorded in receipts."""
    identity = Path("/etc/machine-id").read_text().strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", identity):
        raise ValueError("Identitas mesin tidak tersedia; escrow tidak dapat diverifikasi")
    return hashlib.sha256(("aman-dr-host-v1:" + identity.lower()).encode()).hexdigest()


def key_fingerprint(key):
    if len(key) != 32:
        raise ValueError("Key DR wajib 32 byte")
    return hashlib.sha256(b"aman-dr-key-v1:" + key).hexdigest()


def escrow_attestation(key, source_machine, *, escrow_machine=None, now=None):
    """Run on the escrow machine after retrieving its stored copy of the key.

    HMAC proves possession and catches key/receipt mixups. Operator inventory
    still establishes real host/provider independence; this is not remote
    attestation against a malicious operator who also possesses the source key.
    """
    escrow_machine = escrow_machine or machine_fingerprint()
    if (not re.fullmatch(r"[0-9a-f]{64}", str(source_machine))
            or not re.fullmatch(r"[0-9a-f]{64}", str(escrow_machine))
            or source_machine == escrow_machine):
        raise ValueError("Escrow harus diverifikasi pada identitas mesin berbeda")
    body = {"schema_version": 1, "key_fingerprint": key_fingerprint(key),
            "source_machine": source_machine, "escrow_machine": escrow_machine,
            "verified_at": (now or datetime.now(timezone.utc)).isoformat(),
            "key_possession_verified": True}
    body["proof"] = hmac.new(key, json.dumps(body, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    return body


def validate_escrow_attestation(key, attestation, *, source_machine=None, now=None):
    source_machine = source_machine or machine_fingerprint()
    now = now or datetime.now(timezone.utc)
    fields = {"schema_version", "key_fingerprint", "source_machine", "escrow_machine",
              "verified_at", "key_possession_verified", "proof"}
    if not isinstance(attestation, dict) or set(attestation) != fields:
        raise ValueError("Bukti escrow key yang sah wajib sebelum upload offsite")
    body = {name: value for name, value in attestation.items() if name != "proof"}
    expected = hmac.new(key, json.dumps(body, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    try:
        verified = datetime.fromisoformat(str(body["verified_at"]))
        if verified.tzinfo is None:
            raise ValueError("Timestamp escrow wajib memiliki zona waktu")
        age = (now - verified).total_seconds()
    except (TypeError, ValueError):
        raise ValueError("Timestamp bukti escrow tidak valid") from None
    if (body.get("schema_version") != 1 or body.get("key_possession_verified") is not True
            or body.get("key_fingerprint") != key_fingerprint(key)
            or body.get("source_machine") != source_machine
            or not re.fullmatch(r"[0-9a-f]{64}", str(body.get("escrow_machine")))
            or body.get("escrow_machine") == source_machine
            or not 0 <= age <= 365 * 24 * 3600
            or not hmac.compare_digest(str(attestation.get("proof")), expected)):
        raise ValueError("Bukti escrow salah key/mesin, kedaluwarsa, atau belum diverifikasi")
    return body


def encrypt_file(source, destination, key):
    key_fingerprint(key)
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    header = MAGIC + nonce
    encryptor.authenticate_additional_data(header)
    owned = False
    try:
        with Path(source).open("rb") as src, Path(destination).open("xb") as dest:
            owned = True
            os.chmod(destination, 0o600)
            dest.write(header)
            while True:
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break
                dest.write(encryptor.update(chunk))
            dest.write(encryptor.finalize())
            dest.write(encryptor.tag)
            dest.flush()
            os.fsync(dest.fileno())
    except BaseException:
        if owned:
            Path(destination).unlink(missing_ok=True)
        raise
    return file_sha256(destination)


def decrypt_file(source, destination, key):
    key_fingerprint(key)
    source, destination = Path(source), Path(destination)
    staging = destination.with_name(destination.name + ".decrypting")
    if destination.exists():
        raise FileExistsError("Target dekripsi sudah ada")
    owned = False
    try:
        with source.open("rb") as src:
            header = src.read(len(MAGIC) + 12)
            if len(header) != len(MAGIC) + 12 or not header.startswith(MAGIC):
                raise ValueError("Envelope DR tidak dikenal")
            src.seek(-16, os.SEEK_END)
            tag = src.read(16)
            payload_size = source.stat().st_size - len(header) - 16
            if payload_size < 0:
                raise ValueError("Envelope DR terpotong")
            src.seek(len(header))
            decryptor = Cipher(algorithms.AES(key), modes.GCM(header[len(MAGIC):], tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            with staging.open("xb") as dest:
                owned = True
                os.chmod(staging, 0o600)
                remaining = payload_size
                while remaining:
                    chunk = src.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ValueError("Envelope DR terpotong")
                    remaining -= len(chunk)
                    dest.write(decryptor.update(chunk))
                dest.write(decryptor.finalize())  # GCM tag must verify before publish.
                dest.flush()
                os.fsync(dest.fileno())
        os.link(staging, destination)
        staging.unlink()
    except BaseException:
        if owned:
            staging.unlink(missing_ok=True)
        raise
    return file_sha256(destination)


def parse_s3_destination(destination):
    url = urlsplit(destination)
    prefix = url.path.strip("/")
    if (url.scheme != "s3" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{1,62}", url.netloc)
            or url.query or url.fragment or not prefix or ".." in prefix.split("/")):
        raise ValueError("Tujuan harus s3://bucket/prefix-khusus tanpa query/path traversal")
    return url.netloc, prefix + "/"


def verified_offsite_upload(archive, key, destination, client, *, escrow=None):
    """Provider adapter; testable with fake client without contacting a service."""
    escrow_verified = validate_escrow_attestation(key, escrow)
    archive = Path(archive)
    with zipfile.ZipFile(archive) as zf:
        validation = validate_archive(zf, required=True)
    bucket, prefix = parse_s3_destination(destination)
    if shutil.disk_usage(archive.parent).free < archive.stat().st_size * 3 + 200 * 1024 ** 2:
        raise RuntimeError("Ruang disk tidak cukup untuk enkripsi/readback/dekripsi terverifikasi")
    with tempfile.TemporaryDirectory(prefix="aman-dr-encrypted-", dir=archive.parent) as work:
        work = Path(work)
        encrypted = work / "backup.aman"
        digest = encrypt_file(archive, encrypted, key)
        object_key = prefix + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + digest + ".aman"
        metadata = {"sha256": digest, "encryption": "aes256-gcm-aman-dr1"}
        client.upload_file(str(encrypted), bucket, object_key, ExtraArgs={"Metadata": metadata})
        head = client.head_object(Bucket=bucket, Key=object_key)
        if (head.get("ContentLength") != encrypted.stat().st_size
                or head.get("Metadata", {}).get("sha256") != digest):
            raise ValueError("HEAD offsite tidak cocok; backup belum dianggap sukses")
        downloaded = work / "readback.aman"
        client.download_file(bucket, object_key, str(downloaded))
        if file_sha256(downloaded) != digest:
            raise ValueError("Checksum readback offsite tidak cocok")
        restored = work / "readback.zip"
        decrypt_file(downloaded, restored, key)
        if file_sha256(restored) != file_sha256(archive):
            raise ValueError("Roundtrip enkripsi offsite tidak cocok")
        with zipfile.ZipFile(restored) as zf:
            validate_archive(zf, required=True)
        return {"uploaded_verified": True, "destination": f"s3://{bucket}/{object_key}",
                "encrypted_sha256": digest, "encrypted_bytes": encrypted.stat().st_size,
                "consistency": (validation["manifest"] or {}).get("consistency", "legacy_unclassified"),
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "source_independent_restore_drill": False,
                "key_escrow_verified": True,
                "key_fingerprint": escrow_verified["key_fingerprint"]}


def verify_stopped_services(services, runner=subprocess.run):
    if not services or any(not re.fullmatch(r"[A-Za-z0-9_.:-]+", name) for name in services):
        raise ValueError("Daftar semua service penulis wajib dan nama harus aman")
    result = runner(["supervisorctl", "status", *services], capture_output=True, text=True, timeout=20)
    rows = [line.split() for line in result.stdout.splitlines() if line.strip()]
    observed = {row[0]: row[1] for row in rows if len(row) > 1}
    if any(observed.get(service) not in {"STOPPED", "EXITED"} for service in services):
        raise RuntimeError("Semua service penulis harus STOPPED/EXITED; snapshot dibatalkan")
    return observed


def _private_journal(path, owner, phase):
    """Private fsynced intent journal remains writable while Mongo is locked."""
    path = Path(path)
    if path.exists():
        current = json.loads(path.read_text())
        if current.get("owner") != owner:
            raise RuntimeError("Journal snapshot dimiliki operasi lain")
    staging = path.with_name(path.name + ".updating")
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as fp:
            json.dump({"schema_version": 1, "owner": owner, "phase": phase,
                       "updated_at": datetime.now(timezone.utc).isoformat()}, fp)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(staging, path)
        _fsync_directory(path.parent)
    finally:
        staging.unlink(missing_ok=True)


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


async def offline_snapshot(destination, services, inventory, supervisor_runner=subprocess.run):
    """Verified stopped writers + owned Mongo fsyncLock, with no speculative unlock.

    A lost acquire/unlock response keeps the durable gate and filesystem journal.
    No Mongo write is attempted while lock outcome is unknown. Only an explicit
    acknowledged unlock to lockCount=0 allows release of this operation's mutex.
    """
    import routes.backup as rb
    from backup_utils import KEEP_ID_COLLECTIONS
    from db import client, db
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Snapshot tujuan sudah ada")
    inventory_path = Path(inventory)
    if inventory_path.stat().st_size > 64 * 1024:
        raise ValueError("Inventaris penulis terlalu besar")
    inventory = json.loads(inventory_path.read_text())
    if (inventory.get("all_writers_enumerated") is not True
            or sorted(inventory.get("supervisor_services") or []) != sorted(services)
            or inventory.get("external_upload_writers") != []):
        raise ValueError("Inventaris penulis harus lengkap dan semua penulis uploads eksternal dihentikan")
    stopped = verify_stopped_services(services, supervisor_runner)
    control = await rb.restore_control_status()
    if (control.get("state") not in (None, "completed", "rolled_back", "aborted")
            or (control.get("state") is None and (control.get("active") is True
                                                  or control.get("destructive_started") is True))):
        raise RuntimeError("Restore/deploy/recovery aktif; snapshot offline dibatalkan")
    if await db.restore_write_leases.count_documents({}):
        raise RuntimeError("Lease penulis masih tersisa; operator harus menghentikan worker lalu memeriksanya")
    owner = "snapshot_" + uuid.uuid4().hex
    try:
        claimed = await db.restore_control.find_one_and_update(
            {"_id": "GLOBAL", "$or": [{"state": {"$in": ["completed", "rolled_back", "aborted"]}},
                {"state": {"$exists": False}, "active": {"$ne": True}, "destructive_started": {"$ne": True}}]},
            {"$set": {"state": "preparing", "active": True, "owner": owner,
                      "job_id": owner, "destructive_started": False,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "source_artifact": destination.name}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        raise RuntimeError("Restore/deploy lain menguasai mutex; snapshot dibatalkan") from None
    if not claimed or claimed.get("owner") != owner:
        raise RuntimeError("Kepemilikan mutex snapshot tidak terverifikasi")
    staging = destination.with_name(destination.name + ".building")
    journal = destination.parent / (".aman-dr-" + owner + ".json")
    acquisition_attempted, own_increment = False, False
    staging_owned, published, lock_released = False, False, False
    started = datetime.now(timezone.utc)
    try:
        _private_journal(journal, owner, "mutex_claimed")
        current = await client.admin.command({"currentOp": 1})
        if current.get("fsyncLock"):
            raise RuntimeError("Mongo sudah fsyncLocked oleh operator lain")
        _private_journal(journal, owner, "acquire_intent")
        acquisition_attempted = True
        acquired = await client.admin.command({"fsync": 1, "lock": True})
        count = acquired.get("lockCount")
        # A positive acknowledged count proves one increment belongs to us.
        # count>1 cannot prove exclusive snapshot consistency, so abort and
        # decrement ONLY our own increment once in finally.
        own_increment = type(count) is int and count > 0
        if count != 1:
            raise RuntimeError("Mongo lockCount tidak eksklusif")
        _private_journal(journal, owner, "exclusive_lock_acknowledged")
        verify_stopped_services(services, supervisor_runner)
        stats = {}
        fd = os.open(staging, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        staging_owned = True
        with os.fdopen(fd, "w+b") as raw, zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as zf:
            for col in await rb._app_collections():
                stats[col] = await rb._tulis_koleksi_json(zf, col, col in KEEP_ID_COLLECTIONS)
            gridfs = await rb.export_gridfs(zf)
            uploads = 0
            if rb.UPLOADS_DIR.exists():
                for source in rb.UPLOADS_DIR.rglob("*"):
                    if source.is_symlink():
                        raise ValueError("Uploads mengandung symlink")
                    if source.is_file():
                        zf.write(source, "uploads/" + source.relative_to(rb.UPLOADS_DIR).as_posix())
                        uploads += 1
            zf.writestr("metadata.json", json.dumps({"version": rb.APP_VERSION,
                "archive_schema_version": 1, "consistency": CONSISTENCY,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "writer_services": stopped, "writer_inventory": inventory,
                "created_by": "offline-unix-operator"}))
            await asyncio.to_thread(write_manifest, zf, stats, gridfs, uploads, CONSISTENCY)
        with zipfile.ZipFile(staging) as zf:
            await asyncio.to_thread(validate_archive, zf, False, True)
        verify_stopped_services(services, supervisor_runner)
        with staging.open("rb") as fp:
            os.fsync(fp.fileno())
        os.link(staging, destination)
        staging.unlink()
        _fsync_directory(destination.parent)
        published = True
        _private_journal(journal, owner, "archive_published")
        return {"snapshot_verified": True, "consistency": CONSISTENCY,
                "sha256": file_sha256(destination), "bytes": destination.stat().st_size,
                "duration_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
                "offsite_verified": False}
    finally:
        if own_increment:
            _private_journal(journal, owner, "unlock_intent")
            try:
                unlocked = await client.admin.command({"fsyncUnlock": 1})
                lock_released = unlocked.get("lockCount") == 0
            except BaseException:
                _private_journal(journal, owner, "unlock_outcome_unknown")
                raise RuntimeError("Hasil fsyncUnlock tidak diketahui; mutex dan journal dipertahankan untuk operator") from None
            if not lock_released:
                _private_journal(journal, owner, "other_lock_still_active")
                raise RuntimeError("Mongo masih fsyncLocked; hanya increment sendiri dilepas, mutex dipertahankan")
        elif acquisition_attempted:
            _private_journal(journal, owner, "acquire_outcome_unknown")
            raise RuntimeError("Hasil fsyncLock tidak diketahui; jangan membuka lock spekulatif, periksa journal operator") from None
        # No acquisition attempted, or acknowledged unlock reached zero: safe
        # to perform Mongo writes and release only our own known mutex.
        released = await db.restore_control.update_one({"_id": "GLOBAL", "owner": owner, "state": "preparing"},
            {"$set": {"state": "completed" if published else "aborted", "active": False,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        if not released.matched_count:
            _private_journal(journal, owner, "mutex_release_not_acknowledged")
            raise RuntimeError("Pelepasan mutex snapshot tidak terverifikasi; journal dipertahankan")
        if staging_owned:
            staging.unlink(missing_ok=True)
        if journal.exists():
            journal.unlink()
            _fsync_directory(journal.parent)


def receipt_freshness(receipt, max_age_hours=24, now=None):
    """Exit-code-friendly stale check for the existing monitoring scheduler."""
    now = now or datetime.now(timezone.utc)
    try:
        verified = datetime.fromisoformat(str(receipt.get("verified_at", "")))
        if verified.tzinfo is None:
            verified = verified.replace(tzinfo=timezone.utc)
        age = (now - verified).total_seconds()
    except (TypeError, ValueError):
        return {"fresh": False, "reason": "missing_verified_receipt"}
    if (receipt.get("uploaded_verified") is not True
            or receipt.get("key_escrow_verified") is not True) or not 0 <= age <= max_age_hours * 3600:
        return {"fresh": False, "reason": "unverified_or_stale", "age_seconds": age}
    return {"fresh": True, "reason": "verified_offsite_readback", "age_seconds": age}
