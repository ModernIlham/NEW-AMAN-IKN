"""Read-time SIMAN provenance, shared by asset and synchronization endpoints.

Stored import evidence remains an audit record. It may only describe the
current asset while its source and recorded owner still agree with the
authoritative activity/master identity. Sanitizing a response never updates
the asset, its native fields, or its version in MongoDB.
"""

from db import db
from siman_satker import identitas_satker, kode_satker_sama


def _kode_skalar(value):
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _id_aset(asset):
    value = asset.get("id")
    return value if isinstance(value, (str, int)) and not isinstance(value, bool) else None


def _pemilik(asset, kegiatan):
    """Malformed stored identifiers are unknown, never opaque repr aliases."""
    activity_id = asset.get("activity_id")
    if activity_id is not None and not isinstance(activity_id, str):
        return None
    activity = kegiatan.get(activity_id) or {}
    owner_fields = ("kode_satker", "kode_satker_lengkap")
    has_activity_owner = any(
        activity.get(field) is not None
        and not (isinstance(activity.get(field), str) and not activity[field].strip())
        for field in owner_fields)
    owner = activity if has_activity_owner else asset
    if any(owner.get(field) is not None and not _kode_skalar(owner[field]) for field in owner_fields):
        return None
    return owner


async def identitas_satker_aset(assets, *, database=None):
    """Resolve owner identities in batches; activity ownership is authoritative.

    The activity's full code wins, with its master completing an absent full
    code. Flat asset stamps are only a fallback when its activity supplies no
    owner identity. Global report settings never identify an asset's owner.
    """
    database = database if database is not None else db
    kegiatan, master = {}, {}
    ids = sorted({a["activity_id"] for a in assets
                  if isinstance(a.get("activity_id"), str) and a["activity_id"]})
    for awal in range(0, len(ids), 1000):
        async for item in database.inventory_activities.find(
                {"id": {"$in": ids[awal:awal + 1000]}},
                {"_id": 0, "id": 1, "kode_satker": 1, "kode_satker_lengkap": 1}):
            if isinstance(item.get("id"), str):
                kegiatan[item["id"]] = item
    owners = [(_id_aset(asset), _pemilik(asset, kegiatan)) for asset in assets]
    kode = sorted({str(owner.get("kode_satker") or "").strip()
                   for _, owner in owners if owner is not None} - {""})
    for awal in range(0, len(kode), 1000):
        async for item in database.satker.find(
                {"kode_satker": {"$in": kode[awal:awal + 1000]}},
                {"_id": 0, "kode_satker": 1, "kode_satker_lengkap": 1}):
            if isinstance(item.get("kode_satker"), str):
                master[item["kode_satker"]] = item
    hasil = {}
    for asset_id, owner in owners:
        if asset_id is None:
            continue
        if owner is None:
            hasil[asset_id] = ""
            continue
        pendek = owner.get("kode_satker")
        master_owner = master.get(str(pendek or "").strip()) or {}
        lengkap = owner.get("kode_satker_lengkap") or master_owner.get("kode_satker_lengkap")
        if lengkap is not None and not _kode_skalar(lengkap):
            hasil[asset_id] = ""
            continue
        hasil[asset_id] = identitas_satker(pendek, lengkap)
    return hasil


def referensi_siman_terverifikasi(sub, identity):
    """Both recorded identities must agree with each other and today's owner.

    Six/full matching is not transitive: two distinct full codes can share a
    six-digit owner. Checking the recorded pair as well prevents that short
    owner from legitimizing contradictory full source/snapshot identities.
    Legacy records without either provenance field are unverified.
    """
    if not isinstance(sub, dict) or not _kode_skalar(identity):
        return False
    source = sub.get("kode_satker")
    snapshot = sub.get("kode_satker_aset")
    return bool(_kode_skalar(source) and _kode_skalar(snapshot)
                and kode_satker_sama(identity, source)
                and kode_satker_sama(identity, snapshot)
                and kode_satker_sama(source, snapshot))


async def bersihkan_referensi_siman(assets, *, database=None):
    """Expose only verified references, using explicit null to clear old clients.

    Rows without a reference also include ``siman: None``: omitting the key
    would let clients merge an old cached match back into an authoritative
    response. Only response dictionaries are changed; no database writes occur.
    """
    referenced = [a for a in assets if a.get("siman") is not None]
    identities = (await identitas_satker_aset(referenced, database=database)
                  if referenced else {})
    for asset in assets:
        if not referensi_siman_terverifikasi(asset.get("siman"), identities.get(_id_aset(asset))):
            asset["siman"] = None
    return assets
