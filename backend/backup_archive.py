"""Bounded ZIP/JSON readers and verifiable archive manifest (no database IO)."""
import hashlib
import io
import json
import re
import stat
from datetime import datetime, timezone
from pathlib import PurePosixPath

from bson import BSON

from backup_utils import collections_from_backup, LEGACY_COLLECTION_ALIASES

MANIFEST_NAME = "backup-manifest.json"
CHUNK_SIZE = 256 * 1024
MAX_DOCUMENT_CHARS = 16 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 ** 3
MAX_ENTRIES = 500_000
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_COL = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,119}$")
_BCRYPT = re.compile(r"^\$2[aby]\$(?:0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{21}[.Oeu][./A-Za-z0-9]{30}[.CGKOSWaeimquy26]$")


def usable_central_admin(document):
    """Mirror persisted login/central-admin policy without knowing a password.

    Bcrypt shape is validated without executing an attacker-controlled cost.
    Act-as fields never grant authority; login subsequently strips those fields.
    """
    if (document.get("role") != "admin" or str(document.get("kode_satker") or "").strip()
            or document.get("is_active", True) is not True):
        return False
    for field in ("id", "username"):
        value = document.get(field)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            return False
    if not isinstance(document.get("name"), str) or not isinstance(document.get("created_at"), str):
        return False
    locked_until = document.get("login_terkunci_hingga")
    if locked_until:
        try:
            locked = datetime.fromisoformat(str(locked_until))
            if locked.tzinfo is None:
                locked = locked.replace(tzinfo=timezone.utc)
            if locked > datetime.now(timezone.utc):
                return False
        except (ValueError, OverflowError):
            pass  # Login itself ignores malformed lock timestamps.
    return isinstance(document.get("password"), str) and bool(_BCRYPT.fullmatch(document["password"]))



def iter_json_documents(binary, max_document_chars=MAX_DOCUMENT_CHARS):
    """Read both legacy compact and line-oriented JSON arrays one dict at a time.

    Buffer bounded by one BSON-sized document plus a 64 KiB read. Reject trailing
    data, malformed separators, non-document elements, and oversized documents.
    """
    reader = io.TextIOWrapper(binary, encoding="utf-8", errors="strict")
    decoder = json.JSONDecoder()
    buf, eof, started, need_value = "", False, False, False
    try:
        while True:
            buf = buf.lstrip()
            if not buf and not eof:
                chunk = reader.read(65536)
                buf += chunk
                eof = not chunk
                continue
            if not started:
                if not buf.startswith("["):
                    raise ValueError("Koleksi harus berupa array JSON")
                buf, started, need_value = buf[1:], True, True
                continue
            if buf.startswith("]"):
                tail = buf[1:]
                while True:
                    if tail.strip():
                        raise ValueError("Data tambahan setelah array JSON")
                    tail = reader.read(65536)
                    if not tail:
                        return
            if not need_value:
                if not buf.startswith(","):
                    raise ValueError("Pemisah koleksi JSON tidak valid")
                buf, need_value = buf[1:], True
                # A comma must be followed by an object, not a closing bracket.
                while not buf.strip() and not eof:
                    chunk = reader.read(65536)
                    buf += chunk
                    eof = not chunk
                if buf.lstrip().startswith("]"):
                    raise ValueError("Trailing comma pada koleksi JSON")
                continue
            try:
                value, end = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                if eof or len(buf) > max_document_chars:
                    raise ValueError("Dokumen JSON rusak atau melebihi batas") from None
                chunk = reader.read(65536)
                buf += chunk
                eof = not chunk
                continue
            if end > max_document_chars or not isinstance(value, dict):
                raise ValueError("Elemen koleksi harus dokumen dengan ukuran terbatas")
            yield value
            buf, need_value = buf[end:], False
    finally:
        reader.detach()


def read_json(zf, name):
    if zf.getinfo(name).file_size > MAX_METADATA_BYTES:
        raise ValueError(f"Metadata terlalu besar: {name}")
    with zf.open(name) as fp:
        return json.load(fp)


def digest_entry(zf, name):
    digest, size = hashlib.sha256(), 0
    with zf.open(name) as fp:
        while True:
            chunk = fp.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise ValueError("Ukuran entri backup melewati batas")
    return {"size": size, "sha256": digest.hexdigest()}


def write_manifest(zf, stats, gridfs_files, upload_files, consistency="application_best_effort"):
    manifest = {"schema_version": 1, "complete": True,
                "consistency": consistency,
                "collections": stats, "gridfs_files": gridfs_files,
                "upload_files": upload_files,
                "files": {name: digest_entry(zf, name) for name in zf.namelist()
                          if not name.endswith("/") and name != MANIFEST_NAME}}
    zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False))
    return manifest


# Explicit CURRENT owner fields read by media consumers. Audit/history payloads
# may mention deliberately deleted older blobs and are not live ownership.
# Add a path here whenever a new current GridFS owner/consumer is introduced.
CURRENT_MEDIA_REFERENCES = {
    "assets": ("photo_gridfs_ids.*", "bast_file_id",
               "document_checklist.*.photo_gridfs_ids.*",
               "document_checklist.*.documents.*.gridfs_id"),
    "inventory_activities": ("documents.*.gridfs_id", "pengesahan_dokumen.*.gridfs_id"),
    "pegawai": ("foto_file_id", "foto_asli_file_id", "ttd_file_id"),
    "pejabat": ("ttd_file_id",),
    "report_settings": ("kasatker_ttd_file_id",),
    "signature_requests": ("dok_file_id", "signers.*.signature_file_id"),
    "bast_serah_terima": ("bukti.file_id",),
    "spasial_node": ("properties.denah_overlay.file_id",),
    "psp": ("lampiran.*.file_id",),
    "pengadaan": ("lampiran_berkas.*.file_id",),
    "pemanfaatan": ("lampiran.*.file_id", "lampiran_wasdal.*.file_id"),
    "usulan_penghapusan": ("lampiran.*.file_id",),
    "pemindahtanganan": ("lampiran.*.file_id",),
    "pemantauan_insidentil": ("lampiran.*.file_id",),
    "pemusnahan": ("lampiran.*.file_id",),
    "pengamanan_dokumen": ("lampiran.*.file_id",),
}


def _media_path(value, path):
    if not path:
        if isinstance(value, str) and value.strip():
            yield value
        return
    field, *rest = path
    if field == "*":
        if isinstance(value, list):
            for item in value:
                yield from _media_path(item, rest)
    elif isinstance(value, dict):
        yield from _media_path(value.get(field), rest)


def _references(collection, document):
    for path in CURRENT_MEDIA_REFERENCES.get(collection, ()):
        yield from _media_path(document, path.split("."))


def validate_archive(zf, required=True, require_admin=None):
    """Preflight EVERY entry, CRC, digest, collection and referenced media.

    Legacy archives lack checksums; CRC, JSON, IDs, blob sizes and relationships
    still validate. Never extract paths from an unvalidated archive.
    """
    require_admin = required if require_admin is None else require_admin
    infos = zf.infolist()
    names = [i.filename for i in infos]
    if len(names) > MAX_ENTRIES or len(set(names)) != len(names):
        raise ValueError("Entri ZIP duplikat atau terlalu banyak")
    if sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES:
        raise ValueError("Hasil dekompresi backup melebihi batas 100 GiB")
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        if (not name or "\\" in name or "\x00" in name or path.is_absolute()
                or ".." in path.parts or ":" in name
                or stat.S_ISLNK(info.external_attr >> 16)
                or info.flag_bits & 1):
            raise ValueError(f"Path/format ZIP tidak aman: {name}")
        if name.endswith("/"):
            continue
        if name in {"metadata.json", MANIFEST_NAME, "gridfs/manifest.json"}:
            continue
        if name.startswith("uploads/") and len(path.parts) > 1:
            continue
        if name.startswith("gridfs/") and name.endswith(".bin") and _ID.fullmatch(name[7:-4]):
            continue
        if "/" not in name and name.endswith(".json") and _COL.fullmatch(name[:-5]):
            continue
        raise ValueError(f"Entri backup tidak dikenal: {name}")
    if "metadata.json" not in names:
        raise ValueError("metadata.json tidak ditemukan")
    metadata = read_json(zf, "metadata.json")
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json harus objek")
    if metadata.get("archive_schema_version") not in (None, 1):
        raise ValueError("Versi schema backup tidak didukung")
    if metadata.get("archive_schema_version") == 1 and MANIFEST_NAME not in names:
        raise ValueError("Manifest wajib untuk backup schema baru")
    cols = collections_from_backup(names)
    canonical = [LEGACY_COLLECTION_ALIASES.get(c, c) for c in cols]
    if len(set(canonical)) != len(canonical):
        raise ValueError("Nama koleksi legacy dan kanonik bertabrakan")
    if required:
        missing = {"users", "categories", "assets", "inventory_activities"} - set(canonical)
        if missing:
            raise ValueError("Data tidak lengkap: " + ", ".join(sorted(missing)))
    gridfs = read_json(zf, "gridfs/manifest.json") if "gridfs/manifest.json" in names else []
    if not isinstance(gridfs, list):
        raise ValueError("Manifest GridFS harus array")
    blob_ids = set()
    for entry in gridfs:
        if (not isinstance(entry, dict) or not isinstance(entry.get("_id"), str)
                or not _ID.fullmatch(entry["_id"])):
            raise ValueError("ID GridFS tidak valid")
        fid = str(entry["_id"])
        if fid in blob_ids:
            raise ValueError("ID GridFS duplikat")
        blob_ids.add(fid)
        name = f"gridfs/{fid}.bin"
        if name not in names:
            raise ValueError(f"Blob GridFS hilang: {fid}")
        if entry.get("length") is not None and int(entry["length"]) != zf.getinfo(name).file_size:
            raise ValueError(f"Ukuran blob GridFS tidak cocok: {fid}")
    stats = {}
    has_usable_admin = False
    for col, canonical_name in zip(cols, canonical):
        count = 0
        with zf.open(f"{col}.json") as fp:
            for doc in iter_json_documents(fp):
                try:
                    if len(BSON.encode(doc)) > 16 * 1024 * 1024 or isinstance(doc.get("_id"), (dict, list)):
                        raise ValueError("Dokumen MongoDB terlalu besar atau _id tidak valid")
                except (OverflowError, TypeError) as error:
                    raise ValueError("Dokumen tidak dapat disimpan sebagai BSON") from error
                count += 1
                if canonical_name == "users" and usable_central_admin(doc):
                    has_usable_admin = True
                for reference in _references(canonical_name, doc):
                    if reference not in blob_ids:
                        raise ValueError(f"Referensi GridFS tanpa blob: {canonical_name}/{reference}")
        stats[canonical_name] = count
    if require_admin and not has_usable_admin:
        raise ValueError("Backup harus memiliki admin pusat aktif dengan identitas dan hash password login yang valid")
    digests = {name: digest_entry(zf, name) for name in names
               if not name.endswith("/") and name != MANIFEST_NAME}
    for entry in gridfs:
        if entry.get("sha256") and entry["sha256"] != digests["gridfs/" + entry["_id"] + ".bin"]["sha256"]:
            raise ValueError("Checksum manifest GridFS tidak cocok")
    manifest = read_json(zf, MANIFEST_NAME) if MANIFEST_NAME in names else None
    if manifest is not None:
        if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
                or manifest.get("complete") is not True
                or manifest.get("files") != digests):
            raise ValueError("Manifest backup incomplete, rusak, atau checksum tidak cocok")
        expected_stats = {k: v for k, v in stats.items()}
        manifest_stats = {k: v for k, v in (manifest.get("collections") or {}).items()
                          if k != "gridfs_files"}
        if (manifest_stats != expected_stats or manifest.get("gridfs_files") != len(gridfs)
                or manifest.get("upload_files") != sum(n.startswith("uploads/") and not n.endswith("/") for n in names)):
            raise ValueError("Jumlah dokumen/blob pada manifest tidak cocok")
    return {"metadata": metadata, "collections": stats, "gridfs": gridfs,
            "manifest": manifest, "digests": digests}
