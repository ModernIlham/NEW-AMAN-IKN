"""Proyeksi amanah BAST sah ke master administratif dan BMN Saya.

Satu CAS pada aset adalah pagar perpindahan tanggung jawab. Koleksi portal
merupakan proyeksi idempoten, bukan transaksi lintas-dokumen semu. Kegagalan
sesudah CAS dapat dipulihkan dengan ID penugasan deterministik; setiap akses
tetap memeriksa pointer aset dan sumber BAST saat ini. Tidak menulis jurnal.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from portal_auth import (email_normal, identitas_portal_hash,
                         pegawai_email_tunggal, pegawai_layak_portal)
from portal_pemegang_utils import alias_identitas_aset, ikatan_sumber, teks

logger = logging.getLogger(__name__)
SERAH = frozenset({"penggunaan_melekat", "mutasi_pengguna", "operasional_unit",
                   "penggunaan_sementara"})
KEMBALI = frozenset({"pengembalian", "pengembalian_almarhum"})


def _now():
    return datetime.now(timezone.utc).isoformat()


def _nama(value):
    return " ".join(teks(value).split()).casefold()


async def _segarkan_aset(asset, oleh):
    """Notifikasi proyeksi; bukan otorisasi atau bagian commit administratif."""
    from meili_utils import jadwalkan_sync_id
    from routes.websocket import notify_asset_change
    from shared_utils import invalidate_asset_cache

    invalidate_asset_cache()
    jadwalkan_sync_id("assets", [asset["id"]])
    payload = {k: asset.get(k) for k in ("id", "activity_id", "version", "updated_at",
        "user", "pengguna_nip", "pengguna_jabatan", "pengguna_melekat_ke", "bast_terakhir")}
    try:
        await notify_asset_change(asset.get("activity_id", ""), "asset_updated", payload, oleh)
    except Exception:
        logger.warning("Notifikasi perubahan amanah tertunda; sumber database tetap berlaku")


async def _pegawai(database, pihak, kode):
    """FK eksplisit atau nomor identitas unik, tidak pernah menebak dari nama."""
    nip, pid = teks(pihak.get("nip")), teks(pihak.get("pegawai_id"))
    if not nip:
        return None, "Lengkapi identitas penerima di Master Pegawai dan BAST"
    query = {"kode_satker": kode, "nip": nip}
    rows = await database.pegawai.find(query, {"_id": 0}).limit(2).to_list(2)
    if len(rows) != 1:
        return None, "Identitas penerima belum terdaftar unik pada Master Pegawai satker"
    peg = rows[0]
    if ((pid and pid != peg.get("id")) or _nama(peg.get("nama")) != _nama(pihak.get("nama"))):
        return None, "Identitas penerima BAST tidak cocok dengan Master Pegawai"
    pihak["pegawai_id"] = peg["id"]
    return peg, ""


async def siapkan_otomasi_bast(database, bast, assets):
    """Bekukan rencana saja; tidak memberi akses atau mengubah satu pun aset."""
    kode, jenis = teks(bast.get("kode_satker")), bast.get("jenis")
    aksi = "serah" if jenis in SERAH else "kembali" if jenis in KEMBALI else ""
    if bast.get("revisi_mode") == "mencabut":
        aksi = "cabut"
    p2 = bast.get("pihak_kedua") or {}
    pjs = bast.get("penanggung_jawab_tambahan") or []
    resolved = {}
    if aksi == "serah":
        for pihak in [p2, *pjs]:
            peg, alasan = await _pegawai(database, pihak, kode)
            resolved[id(pihak)] = (peg, alasan)
    items, used_aliases = [], set()
    for asset in assets:
        pihak = p2
        if jenis == "operasional_unit":
            # Pembagian sama dengan daftar_penyata: PJ eksplisit, sisanya p2.
            pihak = next((p for p in pjs if asset["id"] in (p.get("asset_ids") or [])), p2)
        peg, alasan = resolved.get(id(pihak), (None, ""))
        try:
            aliases = alias_identitas_aset(asset, kode)
        except ValueError as exc:
            aliases, alasan = [], str(exc)
        if used_aliases.intersection(aliases):
            raise HTTPException(409, "BAST memuat duplikat barang fisik lintas baris/kegiatan; pilih satu baris induk")
        used_aliases.update(aliases)
        if not aksi:
            alasan = "Jenis BAST lainnya perlu penetapan tanggung jawab oleh petugas"
        items.append({
            "asset_id": asset["id"], "aksi": aksi or "tinjau",
            "penerima": {"pegawai_id": teks((peg or {}).get("id")),
                          **{k: teks(pihak.get(k)) for k in ("nama", "nip", "jabatan")}},
            "ikatan_awal": ikatan_sumber(asset, kode), "alias": aliases,
            "identitas_pegawai": identitas_portal_hash(peg) if peg else "",
            "alasan_awal": alasan,
        })
    return {"version": 1, "status": "menunggu_keabsahan", "items": items,
            "hasil": [], "alasan": "Menunggu BAST lengkap dan tervalidasi", "ever_applied": False}


def _id_penugasan(bast_id, asset_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"aman:bast:amanah:{bast_id}:{asset_id}"))


async def _asset(database, asset_id, kode):
    asset = await database.assets.find_one({"id": asset_id}, {"_id": 0, **{k: 1 for k in (
        "id", "activity_id", "asset_code", "NUP", "kode_register", "asset_name", "user",
        "pengguna_nip", "pengguna_jabatan", "pengguna_melekat_ke", "bast_terakhir",
        "location", "condition", "inventory_status", "dihapus", "category", "amanah_bast",
        "version", "updated_at")}})
    if not asset or asset.get("dihapus") is True or "dummy" in teks(asset.get("category")).lower():
        raise HTTPException(409, "Barang tidak tersedia")
    activity = await database.inventory_activities.find_one({"id": asset.get("activity_id")})
    if not kode or teks((activity or {}).get("kode_satker")) != kode:
        raise HTTPException(409, "Satker barang berubah atau belum lengkap")
    return asset


async def _akses_awal(database, peg, bast, oleh):
    """Hanya insert pertama; revokasi/restore/email berubah tidak direset."""
    if not pegawai_layak_portal(peg):
        return "Amanah tercatat; lengkapi email/status pegawai untuk login BMN Saya"
    tunggal = await pegawai_email_tunggal(peg.get("email"), database)
    if not tunggal or tunggal.get("id") != peg["id"]:
        return "Amanah tercatat; email dipakai lebih dari satu pegawai, perlu koreksi"
    await database.portal_pemegang_akses.update_one({"id": peg["id"]}, {"$setOnInsert": {
        "_id": peg["id"], "id": peg["id"], "kode_satker": bast["kode_satker"], "aktif": True,
        "email_verified": email_normal(peg["email"]), "identitas_hash": identitas_portal_hash(peg),
        "epoch": 1, "version": 1, "verified_by": oleh, "verified_at": _now(),
        "sumber_bast_id": bast["id"], "catatan": "Akses awal berdasarkan BAST lengkap tervalidasi",
    }}, upsert=True)
    akses = await database.portal_pemegang_akses.find_one({"id": peg["id"]})
    if (not akses or akses.get("aktif") is not True
            or akses.get("identitas_hash") != identitas_portal_hash(peg)
            or akses.get("email_verified") != email_normal(peg["email"])):
        return "Amanah tercatat; akses/email pernah berubah atau dicabut, admin perlu verifikasi ulang"
    return ""


async def _tutup_lama(database, asset, item, pid, oleh, now):
    """Tutup generasi lebih tua saja; retry terlambat tak menyentuh yang baru."""
    urutan = asset["amanah_bast"]["urutan"]
    old = await database.portal_penugasan.find({
        "asset_id": asset["id"], "slot_aktif": {"$in": item["alias"]}, "id": {"$ne": pid},
        "$or": [{"amanah_urutan": {"$lt": urutan}}, {"amanah_urutan": {"$exists": False}}],
    }, {"_id": 0}).to_list(None)
    for p in old:
        catat = {"catatan": "Digantikan oleh BAST sah; riwayat tetap disimpan",
                 "tanggal": now, "oleh": oleh, "bast_id": asset["amanah_bast"]["bast_id"]}
        res = await database.portal_penugasan.update_one(
            {"id": p["id"], "version": p["version"], "status": {"$ne": "dicabut"},
             "$or": [{"laporan_aktif": {"$exists": False}},
                     {"laporan_aktif.expires_at": {"$lte": datetime.now(timezone.utc)}}]},
            {"$set": {"status": "dicabut", "updated_at": now, "pencabutan": catat},
             "$inc": {"version": 1}, "$unset": {"slot_aktif": "", "laporan_aktif": ""},
             "$push": {"riwayat": {"status": "dicabut", **catat}}})
        if not res.matched_count:
            raise HTTPException(409, "Penugasan lama sedang berubah/menyimpan laporan; coba sinkronkan kembali")


async def _terapkan_item(database, bast, item, bukti, oleh):
    from portal_bast_validitas import evaluasi_bast_sah

    if item.get("alasan_awal"):
        raise HTTPException(409, item["alasan_awal"])
    kode, aid = bast["kode_satker"], item["asset_id"]
    pid, now = _id_penugasan(bast["id"], aid), _now()
    asset = await _asset(database, aid, kode)
    peg = None
    if item["aksi"] == "serah":
        pihak = dict(item["penerima"])
        peg, alasan = await _pegawai(database, pihak, kode)
        if not peg or peg["id"] != item["penerima"]["pegawai_id"]:
            raise HTTPException(409, alasan or "Identitas penerima berubah")
        # Email/status boleh diperbaiki setelah dokumen, namun akses tidak
        # otomatis diaktifkan jika snapshot identitas saat pembuatan berubah.
    other = await database.portal_penugasan.find_one({
        "slot_aktif": {"$in": item["alias"]}, "asset_id": {"$ne": aid}})
    if other:
        raise HTTPException(409, "Barang fisik masih terikat pada baris/kegiatan lain; rekonsiliasi baris induk dahulu")
    pointer = asset.get("amanah_bast") or {}
    sudah = pointer.get("id") == pid and pointer.get("kunci_bukti") == bukti["kunci_bukti"]
    if pointer.get("id") == pid and not sudah:
        raise HTTPException(409, "Bukti BAST berubah setelah penerapan; gunakan revisi resmi")
    if sudah:
        expected = {**item["ikatan_awal"], "bast_id": bast["id"]}
        if item["aksi"] == "serah":
            expected.update({"user": _nama(item["penerima"]["nama"]), "pengguna_nip": item["penerima"]["nip"]})
        elif item["aksi"] == "kembali":
            expected.update({"user": "", "pengguna_nip": ""})
        if ikatan_sumber(asset, kode) != expected:
            raise HTTPException(409, "Data induk berubah setelah penerapan BAST; akses tidak diperbarui diam-diam")
    if not sudah:
        if ikatan_sumber(asset, kode) != item["ikatan_awal"]:
            raise HTTPException(409, "Pemegang/dokumen/identitas aset berubah sejak BAST dibuat; tinjau BAST, jangan timpa data terbaru")
        # Pembatalan yang mendahului CAS tidak boleh diterapkan.
        latest = await database.bast_serah_terima.find_one({"id": bast["id"]}, {"_id": 0})
        sah = await evaluasi_bast_sah(database, latest or {})
        if not sah.get("sah") or sah.get("kunci_bukti") != bukti["kunci_bukti"]:
            raise HTTPException(409, sah.get("alasan") or "Keabsahan BAST berubah")
        pointer = {"id": pid, "bast_id": bast["id"], "pegawai_id": (peg or {}).get("id", ""),
                   "kunci_bukti": bukti["kunci_bukti"], "aksi": item["aksi"],
                   "urutan": int((asset.get("amanah_bast") or {}).get("urutan") or 0) + 1,
                   "diterapkan_pada": now, "oleh": oleh}
        update = {"amanah_bast": pointer, "updated_at": now,
                  "bast_terakhir": {"id": bast["id"], "jenis": bast["jenis"],
                    "nomor": bast.get("nomor", ""), "tanggal": bast.get("tanggal", ""),
                    "penerima": item["penerima"].get("nama", ""), "tt_dicabut": False}}
        if item["aksi"] == "serah":
            update.update({"user": item["penerima"]["nama"],
                           "pengguna_nip": item["penerima"]["nip"],
                           "pengguna_jabatan": item["penerima"].get("jabatan", "")})
        elif item["aksi"] == "kembali":
            update.update({"user": "", "pengguna_nip": "", "pengguna_jabatan": "",
                           "pengguna_melekat_ke": ""})
        # 'cabut' tidak menyatakan barang sudah kembali secara fisik.
        if bukti["jenis"] == "basah" and item["aksi"] != "cabut":
            from penggunaan_utils import snapshot_bast
            update.update({"bast_file_id": bukti["file_id"], "bast_snapshot": snapshot_bast(asset)})
        query = {"id": aid, "version": asset.get("version")}
        # Beberapa data lama belum memiliki versi; equality null mencakup missing.
        perubahan = {
            "$set": update,
            "$push": {"amanah_riwayat": {"bast_id": bast["id"], "aksi": item["aksi"],
                "sebelum": ikatan_sumber(asset, kode), "sesudah": ikatan_sumber({**asset, **update}, kode),
                "oleh": oleh, "tanggal": now, "kunci_bukti": bukti["kunci_bukti"]}}}
        if asset.get("version") is None:
            perubahan["$set"]["version"] = 1
        else:
            perubahan["$inc"] = {"version": 1}
        res = await database.assets.update_one(query, perubahan)
        if not res.matched_count:
            raise HTTPException(409, "Aset berubah saat penerapan; sinkronkan kembali")
        await database.bast_serah_terima.update_one({"id": bast["id"]},
            {"$set": {"portal_otomasi.ever_applied": True}})
        asset = {**asset, **update}
    # Bila worker lain sudah membawa aset ke BAST berikutnya, tidak menulis
    # proyeksi lama. Guard portal juga membandingkan pointer setiap akses.
    terkini = await _asset(database, aid, kode)
    if terkini.get("amanah_bast") != pointer:
        raise HTTPException(409, "Amanah sudah berubah lagi; proyeksi lama tidak diaktifkan")
    await _segarkan_aset(terkini, oleh)
    await _tutup_lama(database, asset, item, pid, oleh, now)
    if item["aksi"] in {"kembali", "cabut"}:
        return {"asset_id": aid, "status": "ditutup", "alasan": (
            "Akses ditutup; penyelesaian tanggung jawab perlu petugas" if item["aksi"] == "cabut" else "Pengembalian tercatat")}
    doc = {
        "_id": pid, "id": pid, "version": 1, "status": "diterima", "penerimaan_otomatis": True,
        "pegawai_id": peg["id"], "pegawai_nama": item["penerima"]["nama"], "kode_satker": kode,
        "asset_id": aid, "amanah_urutan": pointer["urutan"],
        **{k: asset.get(k, "") for k in ("asset_name", "asset_code", "NUP", "location", "condition")},
        "ikatan_sumber": ikatan_sumber(asset, kode), "slot_aktif": item["alias"],
        "sumber_bast": {"id": bast["id"], "nomor": bast.get("nomor", ""),
                         "tanggal": bast.get("tanggal", ""), "jenis": bast["jenis"],
                         "jangka_sampai": bast.get("jangka_sampai", ""),
                         "kunci_bukti": bukti["kunci_bukti"]},
        "dasar_penugasan": f"BAST {bast.get('nomor') or bast['id']} tanggal {bast.get('tanggal', '')}",
        "catatan": "Penerimaan tercatat melalui BAST lengkap tervalidasi",
        "created_by": oleh, "created_at": now, "updated_at": now,
        "riwayat": [{"status": "diterima", "tanggal": now, "oleh": oleh,
                     "catatan": "Otomatis berdasarkan BAST; bukan konfirmasi ulang pemegang"}],
    }
    try:
        await database.portal_penugasan.update_one({"id": pid}, {"$setOnInsert": doc}, upsert=True)
    except DuplicateKeyError:
        raise HTTPException(409, "Penugasan lain masih aktif; sinkronkan kembali setelah ditinjau")
    stored = await database.portal_penugasan.find_one({"id": pid})
    if stored.get("status") == "dicabut":
        raise HTTPException(409, "Akses penugasan ini pernah dicabut; tidak diaktifkan ulang otomatis")
    warning = ""
    if bast["portal_otomasi"].get("akses_otomatis_ditahan"):
        warning = "Amanah dipulihkan dari backup; admin perlu memverifikasi ulang akses"
    elif identitas_portal_hash(peg) == item["identitas_pegawai"]:
        warning = await _akses_awal(database, peg, bast, oleh)
    else:
        warning = "Amanah tercatat; identitas/email berubah sejak BAST dibuat, admin perlu verifikasi akses"
    return {"asset_id": aid, "pegawai_id": peg["id"], "status": "aktif", "alasan": warning}


async def _finalisasi_agenda(database, bast, oleh):
    now = _now()
    if bast.get("surat_id"):
        await database.surat.update_one({"id": bast["surat_id"], "kode_satker": bast["kode_satker"],
                                        "status": "dibooking", "dihapus": {"$ne": True}},
            {"$set": {"status": "disahkan", "disahkan_pada": now, "disahkan_oleh": oleh, "updated_at": now},
             "$push": {"riwayat": {"status": "disahkan", "tanggal": now, "oleh": oleh,
                                     "catatan": "BAST lengkap tervalidasi dan amanah direkonsiliasi"}}})
    if not bast.get("revisi_dari"):
        return
    sumber = await database.bast_serah_terima.find_one({"id": bast["revisi_dari"], "kode_satker": bast["kode_satker"]})
    if not sumber or sumber.get("direvisi_oleh") not in (None, "", bast["id"]):
        raise HTTPException(409, "BAST sumber sudah digantikan revisi lain")
    res = await database.bast_serah_terima.update_one(
        {"id": sumber["id"], "direvisi_oleh": sumber.get("direvisi_oleh")},
        {"$set": {"direvisi_oleh": bast["id"], "direvisi_oleh_nomor": bast.get("nomor", ""),
                  "direvisi_pada": now, "direvisi_mode": bast["revisi_mode"]}})
    if not res.matched_count:
        raise HTTPException(409, "Revisi sumber berubah; tinjau kembali")
    if bast.get("surat_id") and sumber.get("surat_id"):
        # Identitas deterministik; tidak membuat panah ganda saat callback diulang.
        relid = _id_penugasan(bast["id"], "relasi-surat")
        baru = await database.surat.find_one({"id": bast["surat_id"]}) or {}
        lama = await database.surat.find_one({"id": sumber["surat_id"]}) or {}
        await database.surat_relasi.update_one({"id": relid}, {"$setOnInsert": {
            "id": relid, "dari_id": bast["surat_id"], "ke_id": sumber["surat_id"],
            "jenis": bast["revisi_mode"], "kode_satker": bast["kode_satker"],
            "catatan": f"Revisi BAST sah ke-{bast.get('revisi_ke', 1)}: {bast.get('revisi_alasan', '')}",
            "dari_nomor": baru.get("nomor", ""), "dari_perihal": baru.get("perihal", ""),
            "ke_nomor": lama.get("nomor", ""), "ke_perihal": lama.get("perihal", ""),
            "created_at": now, "oleh": oleh,
        }}, upsert=True)
        for surat, arah, tujuan in ((baru, "aktif", lama), (lama, "pasif", baru)):
            if surat:
                await database.surat.update_one({"id": surat["id"], "riwayat.relasi_id": {"$ne": relid}},
                    {"$push": {"riwayat": {"relasi_id": relid, "status": surat.get("status"),
                        "tanggal": now, "oleh": oleh,
                        "catatan": f"Relasi {bast['revisi_mode']} ({arah}) — {tujuan.get('nomor', '')}"}}})


async def _klaim_revisi(database, bast, bukti, token):
    if not bast.get("revisi_dari"):
        return
    res = await database.bast_serah_terima.update_one({
        "id": bast["revisi_dari"], "kode_satker": bast["kode_satker"],
        "$and": [
            {"$or": [{"direvisi_oleh": None}, {"direvisi_oleh": ""}, {"direvisi_oleh": bast["id"]}]},
            {"$or": [{"amanah_revisi_klaim.id": None}, {"amanah_revisi_klaim.id": bast["id"]}]},
        ]}, {"$set": {"amanah_revisi_klaim": {
            "id": bast["id"], "token": token, "kunci_bukti": bukti["kunci_bukti"], "pada": _now()}}})
    if not res.matched_count:
        raise HTTPException(409, "BAST sumber sedang/telah diterapkan oleh revisi lain; lanjutkan revisi yang sudah diproses")


async def sinkronkan_bast(database, bast_id, oleh="sistem"):
    """Dipanggil finalisasi/QR atau retry eksplisit petugas; tidak ada cron."""
    from portal_bast_validitas import evaluasi_bast_sah

    bast = await database.bast_serah_terima.find_one({"id": bast_id}, {"_id": 0})
    plan = (bast or {}).get("portal_otomasi") or {}
    if not plan.get("items"):
        return {"status": "perlu_tinjauan", "alasan": "BAST lama belum memiliki rencana amanah terikat; gunakan penugasan terverifikasi atau revisi resmi", "hasil": []}
    token, now = str(uuid.uuid4()), datetime.now(timezone.utc)
    claim = await database.bast_serah_terima.update_one(
        {"id": bast_id, "$or": [{"portal_otomasi.lease": {"$exists": False}},
                                  {"portal_otomasi.lease.expires_at": {"$lte": now}}]},
        {"$set": {"portal_otomasi.lease": {"id": token, "expires_at": now + timedelta(minutes=5)}}})
    if not claim.matched_count:
        raise HTTPException(409, "Sinkronisasi BAST sedang berjalan; coba kembali sebentar lagi")
    try:
        bast = await database.bast_serah_terima.find_one({"id": bast_id}, {"_id": 0})
        bukti = await evaluasi_bast_sah(database, bast)
        hasil = []
        if not bukti.get("sah"):
            status = "perlu_tinjauan" if bast["portal_otomasi"].get("ever_applied") else "menunggu_keabsahan"
            alasan = bukti.get("alasan", "BAST belum sah")
        else:
            # Jangan berjalan bila indeks unik gagal disiapkan server.
            await database.portal_penugasan.create_index([("slot_aktif", 1)], unique=True,
                name="portal_penugasan_slot_aktif", partialFilterExpression={"slot_aktif": {"$exists": True}})
            blokir = ""
            try:
                # Reservasi garis revisi hanya setelah bukti sah, bukan saat
                # draf. Dua revisi tak boleh masing-masing mengambil subset.
                await _klaim_revisi(database, bast, bukti, token)
            except HTTPException as exc:
                blokir = str(exc.detail)
            for item in bast["portal_otomasi"]["items"]:
                try:
                    if blokir:
                        raise HTTPException(409, blokir)
                    hasil.append(await _terapkan_item(database, bast, item, bukti, oleh))
                except HTTPException as exc:
                    hasil.append({"asset_id": item["asset_id"], "status": "perlu_tinjauan", "alasan": str(exc.detail)})
            jumlah = sum(h["status"] in {"aktif", "ditutup"} for h in hasil)
            status = "selesai" if jumlah == len(hasil) else "sebagian" if jumlah else "perlu_tinjauan"
            alasan = "Amanah mengikuti BAST sah" if status == "selesai" else "Ada barang yang perlu ditinjau petugas; hasil yang sudah diterapkan tetap tercatat"
            if status == "selesai":
                latest = await database.bast_serah_terima.find_one({"id": bast_id}, {"_id": 0})
                final = await evaluasi_bast_sah(database, latest or {})
                if not final.get("sah") or final.get("kunci_bukti") != bukti["kunci_bukti"]:
                    status, alasan = "perlu_tinjauan", "Keabsahan BAST berubah selama sinkronisasi; akses ditahan, agenda/revisi belum difinalisasi"
                else:
                    await _finalisasi_agenda(database, latest, oleh)
        result = {"status": status, "alasan": alasan, "hasil": hasil}
        await database.bast_serah_terima.update_one({"id": bast_id, "portal_otomasi.lease.id": token},
            {"$set": {**{f"portal_otomasi.{k}": v for k, v in result.items()},
                      "portal_otomasi.diperiksa_pada": _now(), "portal_otomasi.diperiksa_oleh": oleh},
             "$inc": {"portal_otomasi.version": 1}})
        return {**result, "version": int(bast["portal_otomasi"].get("version") or 1) + 1}
    finally:
        if bast.get("revisi_dari"):
            # Klaim tetap melekat sesudah SATU barang diterapkan (termasuk
            # crash sebelum flag ever_applied tersimpan). Hanya percobaan
            # tanpa efek yang boleh melepas garis revisinya.
            terpakai = await database.assets.find_one({"amanah_bast.bast_id": bast_id}, {"_id": 1})
            akhir = await database.bast_serah_terima.find_one({"id": bast_id}, {"portal_otomasi.ever_applied": 1}) or {}
            if not terpakai and not (akhir.get("portal_otomasi") or {}).get("ever_applied"):
                await database.bast_serah_terima.update_one({
                    "id": bast["revisi_dari"], "amanah_revisi_klaim.id": bast_id,
                    "amanah_revisi_klaim.token": token}, {"$unset": {"amanah_revisi_klaim": ""}})
        await database.bast_serah_terima.update_one({"id": bast_id, "portal_otomasi.lease.id": token},
            {"$unset": {"portal_otomasi.lease": ""}})


async def periksa_sumber_bast(database, penugasan, asset, cache=None):
    """Pagar baca/tulis/unduh: callback atau proyeksi usang bukan otorisasi."""
    from portal_bast_validitas import evaluasi_bast_sah

    sumber = penugasan.get("sumber_bast") or {}
    pointer = asset.get("amanah_bast") or {}
    if (pointer.get("id") != penugasan.get("id") or pointer.get("aksi") != "serah"
            or pointer.get("kunci_bukti") != sumber.get("kunci_bukti")
            or pointer.get("pegawai_id") != penugasan.get("pegawai_id")):
        raise HTTPException(403, "Amanah telah berubah; akses lama tidak berlaku")
    key = sumber.get("id")
    entry = (cache or {}).get(key)
    if entry is None:
        bast = await database.bast_serah_terima.find_one({"id": key}, {"_id": 0})
        sah = await evaluasi_bast_sah(database, bast or {})
        if cache is not None:
            cache[key] = (bast, sah)
    else:
        bast, sah = entry
    if not bast or bast.get("kode_satker") != penugasan.get("kode_satker"):
        raise HTTPException(403, "Sumber BAST tidak tersedia dalam satker")
    if not sah.get("sah") or sah.get("kunci_bukti") != sumber.get("kunci_bukti"):
        raise HTTPException(403, "BAST sumber berubah/dicabut; petugas perlu meninjau amanah")
