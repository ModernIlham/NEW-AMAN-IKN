"""Server media budgets; unchanged legacy media is readable and preservable."""
import base64
import binascii
from collections import defaultdict, deque

from bson import BSON
from fastapi import HTTPException

MAX_ITEMS = 50
MAX_PHOTOS_PER_ITEM = 3
MAX_DOCUMENTS_PER_ITEM = 1
MAX_MAIN_PHOTOS = 6
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_CHECKLIST_BSON_BYTES = 12 * 1024 * 1024
MAX_ASSET_BSON_BYTES = 14 * 1024 * 1024
ABSOLUTE_ASSET_BSON_BYTES = 16 * 1024 * 1024 - 64 * 1024


def _over(message):
    raise HTTPException(413, message)


def _raw(data, maximum, label):
    if not isinstance(data, str) or "," not in data:
        raise HTTPException(400, f"{label} harus berupa data unggahan baru")
    header, encoded = data.split(",", 1)
    if ";base64" not in header:
        raise HTTPException(400, f"{label} harus berupa base64")
    if len(encoded) > ((maximum + 2) // 3) * 4:
        _over(f"{label} melebihi batas {maximum // (1024 * 1024)} MB")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, f"{label} rusak atau bukan base64 yang valid")
    if len(raw) > maximum:
        _over(f"{label} melebihi batas {maximum // (1024 * 1024)} MB")
    return raw


def _image(data):
    raw = _raw(data, MAX_PHOTO_BYTES, "Foto")
    if not (raw.startswith(b"\xff\xd8") or raw.startswith(b"\x89PNG\r\n\x1a\n")
            or raw.startswith((b"GIF87a", b"GIF89a"))
            or raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"):
        raise HTTPException(400, "Foto harus berupa JPEG, PNG, WebP, atau GIF")


def _media_bytes(items):
    total = 0
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        for field in ("photos", "photo_thumbnails"):
            for value in item.get(field) if isinstance(item.get(field), list) else []:
                if isinstance(value, str):
                    total += len(value.encode())
        for doc in item.get("documents") if isinstance(item.get("documents"), list) else []:
            if isinstance(doc, dict) and isinstance(doc.get("data"), str):
                total += len(doc["data"].encode())
    return total


def _asset_media_bytes(document):
    value = _media_bytes(document.get("document_checklist"))
    for field in ("photos", "photo_thumbnails"):
        for data in document.get(field) if isinstance(document.get(field), list) else []:
            if isinstance(data, str):
                value += len(data.encode())
    for field in ("photo", "thumbnail", "gallery_thumbnail"):
        if isinstance(document.get(field), str):
            value += len(document[field].encode())
    return value


def validate_checklist(items, existing=None, *, staged_photos=(), staged_documents=()):
    old = existing if isinstance(existing, list) else []
    if not isinstance(items, list):
        raise HTTPException(400, "Kelengkapan dokumen harus berupa daftar")
    if len(items) > MAX_ITEMS and len(items) > len(old):
        _over(f"Maksimal {MAX_ITEMS} item kelengkapan per aset")
    previous = defaultdict(deque)
    known_photos, known_documents, known_photo_refs, known_document_refs = set(), set(), set(), set()
    # IDs can enter these private allowlists only from the server staging result.
    # External request fields never populate either allowlist.
    known_photo_refs.update(str(value) for value in staged_photos)
    known_document_refs.update(str(value) for value in staged_documents)
    for item in old:
        if not isinstance(item, dict):
            continue
        previous[item.get("name", "") if isinstance(item.get("name", ""), str) else ""].append(item)
        known_photos.update(p for p in (item.get("photos") if isinstance(item.get("photos"), list) else []) if isinstance(p, str))
        for document in (item.get("documents") if isinstance(item.get("documents"), list) else []):
            if isinstance(document, dict):
                if isinstance(document.get("data"), str):
                    known_documents.add(document["data"])
                if document.get("gridfs_id"):
                    known_document_refs.add(str(document["gridfs_id"]))
        known_photo_refs.update(str(gid) for gid in (item.get("photo_gridfs_ids") if isinstance(item.get("photo_gridfs_ids"), list) else []) if gid)
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise HTTPException(400, "Nama item kelengkapan wajib diisi")
        before = previous[item["name"]].popleft() if previous[item["name"]] else {}
        if not isinstance(item.get("checked", False), bool):
            raise HTTPException(400, "Status kelengkapan harus benar atau salah")
        if item.get("notes") is not None and not isinstance(item.get("notes", ""), str):
            raise HTTPException(400, "Catatan kelengkapan harus berupa teks")
        if len(item["name"]) > 200 and item["name"] != before.get("name"):
            _over("Nama item kelengkapan maksimal 200 karakter")
        if len(str(item.get("notes") or "")) > 4000 and item.get("notes") != before.get("notes"):
            _over("Catatan item kelengkapan maksimal 4000 karakter")
        photos, documents = item.get("photos") or [], item.get("documents") or []
        if not isinstance(photos, list) or not isinstance(documents, list):
            raise HTTPException(400, "Foto dan dokumen kelengkapan harus berupa daftar")
        references = item.get("photo_gridfs_ids") or []
        if not isinstance(references, list):
            raise HTTPException(400, "Referensi foto harus berupa daftar")
        photo_count = max(len(photos), len(references))
        previous_count = max(len(before.get("photos") if isinstance(before.get("photos"), list) else []),
                             len(before.get("photo_gridfs_ids") if isinstance(before.get("photo_gridfs_ids"), list) else []))
        if photo_count > MAX_PHOTOS_PER_ITEM and photo_count > previous_count:
            _over("Maksimal 3 foto per item kelengkapan")
        if len(documents) > MAX_DOCUMENTS_PER_ITEM and len(documents) > len(before.get("documents") if isinstance(before.get("documents"), list) else []):
            _over("Maksimal 1 PDF per item kelengkapan")
        for index, photo in enumerate(photos):
            if isinstance(photo, str) and photo in known_photos:
                continue
            if photo in (None, "") and index < len(references) and str(references[index]) in known_photo_refs:
                continue  # Existing reference slot, never a new external blob.
            _image(photo)
        for gid in item.get("photo_gridfs_ids") or []:
            if not gid:
                continue  # Alignment placeholder accompanying an inline photo.
            if str(gid) not in known_photo_refs:
                raise HTTPException(400, "Referensi foto bukan milik aset ini")
        for document in documents:
            if not isinstance(document, dict):
                raise HTTPException(400, "Dokumen kelengkapan tidak valid")
            name = document.get("name", "document.pdf")
            if not isinstance(name, str) or not name.strip() or len(name) > 200:
                raise HTTPException(400, "Nama PDF tidak valid (maksimal 200 karakter)")
            if document.get("gridfs_id"):
                if str(document["gridfs_id"]) not in known_document_refs:
                    raise HTTPException(400, "Referensi PDF bukan milik aset ini")
                continue
            data = document.get("data")
            if isinstance(data, str) and data in known_documents:
                continue
            raw = _raw(data, MAX_PDF_BYTES, "PDF")
            if not raw.startswith(b"%PDF-"):
                raise HTTPException(400, "Dokumen kelengkapan harus berupa PDF")
    size = len(BSON.encode({"items": items}))
    previous_size = len(BSON.encode({"items": old}))
    if size > MAX_CHECKLIST_BSON_BYTES and (size > previous_size + 4096 or _media_bytes(items) > _media_bytes(old)):
        _over("Total lampiran kelengkapan maksimal 12 MB. Kurangi lampiran atau ukuran berkas.")


def validate_main_photos(photos, existing=None):
    old = existing if isinstance(existing, list) else []
    if len(photos) > MAX_MAIN_PHOTOS and len(photos) > len(old):
        _over("Maksimal 6 foto utama per aset")
    known = set(p for p in old if isinstance(p, str))
    for photo in photos:
        if not isinstance(photo, str) or photo not in known:
            _image(photo)


def validate_asset_document(document, existing=None):
    size = len(BSON.encode(document))
    old_size = len(BSON.encode(existing)) if existing else 0
    if size > ABSOLUTE_ASSET_BSON_BYTES:
        _over("Data aset mendekati batas penyimpanan. Kurangi lampiran sebelum menyimpan.")
    if size > MAX_ASSET_BSON_BYTES and (size > old_size + 4096 or _asset_media_bytes(document) > _asset_media_bytes(existing or {})):
        _over("Ukuran data aset maksimal 14 MB. Kurangi lampiran sebelum menyimpan.")


def resolve_checklist_for_validation(items, existing):
    """Preflight and writers share the same stable-ID/sentinel normalization."""
    from checklist_storage import normalize_checklist
    return normalize_checklist(items, existing)
