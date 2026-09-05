"""Master Satker — satker sebagai ENTITAS KELAS SATU (Mandat-2, M-SATKER).

Sebelumnya identitas satker hanya field flat pada kegiatan (kode_satker,
nama_satker, …) dan kop laporan sepenuhnya GLOBAL (`report_settings`), sehingga
aplikasi multi-satker ber-database bersama memakai satu kop untuk semua.
Koleksi `satker` menampung profil + KOP PER-SATKER; resolusi nilai laporan:

    kegiatan (paling spesifik) → master satker → report_settings global

Master diregistrasi otomatis dari kegiatan (sinkron) dan dirawat admin.
Koleksi ini KONFIGURASI: masuk RESET_KEEP (selamat reset), tetap ikut backup.
"""
import re
from penandatangan_dokumen import bersihkan_penandatangan, validate_penandatangan
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pymongo.errors import DuplicateKeyError

from auth_utils import is_super_admin, require_admin, require_super_admin, require_user
import organisasi_utils as org
from db import db
from shared_utils import kode_satker_user, log_audit

satker_router = APIRouter()

_PROJ = {"_id": 0}

# Field kop yang boleh dioverride per satker (subset report_settings + identitas)
FIELD_KOP_SATKER = (
    "nama_satker", "nama_unit_organisasi", "nama_sub_unit", "alamat",
    "tempat_laporan", "tembusan_laporan", "telepon", "email",
    "kode_satker_lengkap",
    # Ditambahkan REVIEW-9 R15b. Sebelumnya field-field ini HANYA ada pada
    # dokumen global `report_settings`, sehingga ketika penulisan global
    # dibatasi super-admin, admin satker kehilangan cara mengatur kop laporan
    # miliknya sendiri (pada deployment satu-satker, itu berarti TIDAK ADA yang
    # bisa memasang logo/judul). Kini tiap satker punya salinannya sendiri yang
    # di-overlay di atas default global oleh `gabung_kop`.
    "logo_url", "judul_laporan", "subjudul_laporan", "tahun_anggaran",
    "catatan_kaki",
    # Kebijakan nilai perolehan pada surat serah terima ("" = ikut global).
    "nilai_dokumen",
)


def _pastikan_satker_sendiri(admin: dict, kode: str) -> None:
    """403 bila admin SATKER menyentuh master/KOP satker LAIN (REVIEW-9 R9).

    `require_admin` hanya cek role, sehingga tanpa guard ini admin satker A
    dapat menimpa KOP satker B — dan KOP master itu dipakai `pengaturan_kop`
    untuk SELURUH laporan/PDF/stiker/BAST satker B — atau menghapus master
    satker B (bila belum punya kegiatan) beserta profil yang diisi manual."""
    if is_super_admin(admin):
        return
    milik = kode_satker_user(admin)
    if not milik or str(kode or "").strip() != milik:
        raise HTTPException(
            status_code=403,
            detail=("Master & kop satker lain hanya dapat diubah super-admin "
                    "pusat — akun Anda terikat satker " + (milik or "-")))


class SatkerIn(BaseModel):
    kode_satker: str
    nama_satker: str
    nama_unit_organisasi: str = ""
    nama_sub_unit: str = ""
    alamat: str = ""
    tempat_laporan: str = ""
    tembusan_laporan: str = ""
    telepon: str = ""
    email: str = ""
    # Kode satker LENGKAP registrasi BMN (±20 digit, mis.
    # 126011600691778000KP) — dipakai a.l. baris kedua header stiker.
    kode_satker_lengkap: str = ""
    # Kop laporan milik satker (REVIEW-9 R15b) — kosong = pakai default global.
    logo_url: str = ""
    judul_laporan: str = ""
    subjudul_laporan: str = ""
    tahun_anggaran: str = ""
    catatan_kaki: str = ""
    # Kebijakan NILAI PEROLEHAN pada surat serah terima satker ini:
    # "" = ikut setelan universal · "tampilkan" · "sembunyikan".
    nilai_dokumen: str = ""
    # Penanda tangan pilihan SATKER per slot dokumen (slot → id pejabat).
    # Lapis KEDUA dari tiga: pilihan dokumen menang di atasnya, resolusi peran
    # pada Referensi Pejabat tetap jadi jaring terakhir. Rumahnya di sini —
    # bukan di setelan global — karena penanda tangan memang milik satker, dan
    # setelan global hanya boleh disentuh super-admin pusat.
    penandatangan: Optional[dict] = None
    # Menerima KEDUA bentuk yang benar-benar ada di basis data — daftar string
    # (tulisan PUT lama) dan daftar dict bersarang (auto-registrasi kegiatan).
    # Menuntut `List[str]` saja membuat satker hasil auto-registrasi ditolak
    # 422 begitu profilnya disunting, dan yang menyuntingnya tak melakukan
    # apa-apa yang salah. Disimpan dalam SATU bentuk (lihat `normalkan_eselon_teks`).
    eselon1: Optional[List[Union[str, dict]]] = None
    aktif: bool = True


def _valid_kode(kode: str) -> str:
    k = str(kode or "").strip()
    if not k or len(k) > 30 or not re.fullmatch(r"[\w.\-]+", k):
        raise HTTPException(status_code=400,
                            detail="Kode satker wajib (huruf/angka/titik/strip, maks 30)")
    return k


@satker_router.get("/satker")
async def daftar_satker(_user: dict = Depends(require_user)):
    """Master satker + jumlah kegiatan per satker (agar terlihat mana yang
    dipakai). Termasuk satker yang BELUM terdaftar di master tetapi muncul di
    kegiatan (status 'belum terdaftar') — kandidat sinkron 1-klik."""
    # Isolasi satker (REVIEW-9 R10): user terikat hanya melihat barisnya
    # sendiri; super-admin pusat tetap melihat seluruh master (dipakai untuk
    # mengelola & mengikat akun antar satker).
    #
    # SATKER AKTIF (temuan tinjauan): saat super-admin ber-"act-as" satker X,
    # kode_satker-nya tersuntik X sehingga daftar ini akan menciut jadi HANYA X
    # — padahal bilah pemilih satker justru butuh daftar PENUH agar bisa pindah
    # X→Y langsung. `is_super_admin` menghormati penanda `_super_admin_asli`,
    # jadi super-admin asli tetap melihat seluruh master meski sedang act-as.
    _milik = kode_satker_user(_user)
    _lihat_semua = is_super_admin(_user)
    _q_master = {} if _lihat_semua else ({"kode_satker": _milik} if _milik else {})
    master = {m["kode_satker"]: m async for m in db.satker.find(_q_master, _PROJ)}
    pakai = {}
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"}, "n": {"$sum": 1}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        pakai[g["_id"]] = g
    items = []
    for kode, m in master.items():
        items.append({**m, "jumlah_kegiatan": pakai.get(kode, {}).get("n", 0),
                      "terdaftar": True})
    for kode, g in pakai.items():
        if not _lihat_semua and _milik and kode != _milik:
            continue
        if kode not in master:
            items.append({"kode_satker": kode, "nama_satker": g.get("nama") or "",
                          "eselon1": org.normalkan_eselon_teks(g.get("eselon1")),
                          "aktif": True,
                          "jumlah_kegiatan": g.get("n", 0), "terdaftar": False})
    items.sort(key=lambda x: str(x.get("kode_satker")))
    return {"items": items, "jumlah": len(items),
            "field_kop": list(FIELD_KOP_SATKER)}


@satker_router.get("/satker/{kode}")
async def detail_satker(kode: str, _user: dict = Depends(require_user)):
    # Isolasi satker (REVIEW-9 R10): profil satker memuat alamat, telepon,
    # email, dan kode registrasi BMN 20 digit — bukan referensi publik.
    _milik = kode_satker_user(_user)
    if _milik and str(kode or "").strip() != _milik:
        raise HTTPException(status_code=403, detail="Profil satker lain")
    doc = await db.satker.find_one({"kode_satker": kode}, _PROJ)
    if not doc:
        raise HTTPException(status_code=404, detail="Satker belum terdaftar di master")
    return doc


@satker_router.put("/satker/{kode}")
async def simpan_satker(kode: str, payload: SatkerIn,
                        admin: dict = Depends(require_admin)):
    """Daftarkan/perbarui profil & kop satu satker (admin). Upsert by kode —
    kode pada path menang atas body (path = identitas)."""
    k = _valid_kode(kode)
    _pastikan_satker_sendiri(admin, k)  # isolasi satker (REVIEW-9 R9)
    if not str(payload.nama_satker or "").strip():
        raise HTTPException(status_code=400, detail="Nama satker wajib diisi")
    # Kebijakan nilai dokumen: kosong = ikut setelan universal. Nilai asing
    # ditolak agar tidak diam-diam jatuh ke bawaan "tampilkan" — satker yang
    # bermaksud menyembunyikan nilai berhak tahu setelannya tak tersimpan.
    from satker_utils import NILAI_DOKUMEN
    _nd = str(payload.nilai_dokumen or "").strip().lower()
    if _nd and _nd not in NILAI_DOKUMEN:
        raise HTTPException(status_code=400, detail=(
            "Kebijakan nilai dokumen harus kosong (ikut universal), "
            "'tampilkan', atau 'sembunyikan'"))
    payload.nilai_dokumen = _nd
    # Peta penanda tangan: slot asing ditolak, bukan diam-diam dibuang. Admin
    # yang salah ketik nama slot berhak tahu setelannya tak akan berlaku.
    _galat_ttd = validate_penandatangan(payload.penandatangan)
    if _galat_ttd:
        raise HTTPException(status_code=400, detail="; ".join(_galat_ttd))
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "kode_satker": k,
        "nama_satker": payload.nama_satker.strip(),
        "aktif": bool(payload.aktif),
        "updated_at": now, "updated_by": admin.get("username", "system"),
    }
    for f in FIELD_KOP_SATKER:
        if f in ("nama_satker",):
            continue
        doc[f] = str(getattr(payload, f, "") or "").strip()
    # `None` berarti "jangan sentuh"; peta kosong berarti "kembalikan ke
    # resolusi peran". Keduanya beda maksud, jadi dibedakan di sini.
    if payload.penandatangan is not None:
        doc["penandatangan"] = bersihkan_penandatangan(payload.penandatangan)
    # Aturan yang SAMA berlaku untuk struktur eselon, dan dulu tidak: `doc`
    # menulisnya tanpa syarat, sementara layar Satker tak pernah mengirimnya
    # sama sekali (tak ada `eselon1` pada FORM_KOSONG). Akibatnya setiap kali
    # profil satker disimpan — mengganti alamat, telepon, apa pun — struktur
    # Eselon I/II-nya terhapus diam-diam, dan kegiatan baru kehilangan
    # isian otomatisnya tanpa satu pun pesan.
    if payload.eselon1 is not None:
        doc["eselon1"] = org.normalkan_eselon_teks(payload.eselon1)
    try:
        await db.satker.update_one(
            {"kode_satker": k},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True)
    except DuplicateKeyError:
        # C32: dua upsert balapan melawan indeks unik — Mongo mengulang sekali
        # sendiri, tapi sisa kemungkinannya jatuh sebagai 500 tepat di tombol
        # Simpan admin. Dokumen kini pasti ada → cukup $set murni.
        await db.satker.update_one({"kode_satker": k}, {"$set": doc})
    await log_audit("simpan_satker", "", k, username=admin.get("username", "system"),
                    detail=f"Master satker {k} — {doc['nama_satker']}")
    return {"ok": True, "kode_satker": k}


@satker_router.delete("/satker/{kode}")
async def hapus_satker(kode: str, admin: dict = Depends(require_admin)):
    """Hapus satker dari master — DITOLAK bila masih dipakai kegiatan
    (hapus/madah kegiatannya dulu; master bukan tempat menghilangkan jejak)."""
    _pastikan_satker_sendiri(admin, kode)  # isolasi satker (REVIEW-9 R9)
    n = await db.inventory_activities.count_documents({"kode_satker": kode})
    if n:
        raise HTTPException(status_code=409,
                            detail=f"Satker dipakai {n} kegiatan — tidak dapat dihapus")
    res = await db.satker.delete_one({"kode_satker": kode})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Satker tidak ditemukan")
    await log_audit("hapus_satker", "", kode,
                    username=admin.get("username", "system"),
                    detail=f"Hapus master satker {kode}")
    return {"ok": True}


@satker_router.post("/satker/sinkron")
async def sinkron_satker(admin: dict = Depends(require_super_admin)):
    """Registrasi otomatis: setiap satker yang muncul di kegiatan tetapi belum
    ada di master → didaftarkan (kode+nama+eselon1). Idempoten; profil kop
    yang sudah diisi admin TIDAK ditimpa."""
    now = datetime.now(timezone.utc).isoformat()
    baru = 0
    pipeline = [
        {"$match": {"kode_satker": {"$exists": True, "$ne": ""}}},
        {"$group": {"_id": "$kode_satker", "nama": {"$first": "$nama_satker"},
                    "eselon1": {"$first": "$eselon1"},
                    "alamat": {"$first": "$alamat_satker"}}},
    ]
    async for g in db.inventory_activities.aggregate(pipeline):
        # C32: satu upsert $setOnInsert menggantikan find_one+insert_one —
        # check-then-act lama bisa melahirkan dua master satu kode saat dua
        # pemanggil balapan, dan dengan indeks unik menyala insert kalah
        # balapan berubah jadi 500. Pola sama dengan auto-registrasi di
        # routes/activities.py. Dokumen yang sudah ada TIDAK ditimpa.
        res = await db.satker.update_one(
            {"kode_satker": g["_id"]},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()), "kode_satker": g["_id"],
                "nama_satker": str(g.get("nama") or "").strip(),
                "nama_unit_organisasi": "", "nama_sub_unit": "",
                "alamat": str(g.get("alamat") or "").strip(),
                "tempat_laporan": "", "tembusan_laporan": "",
                "telepon": "", "email": "",
                "eselon1": org.normalkan_eselon_teks(g.get("eselon1")),
                "aktif": True,
                "created_at": now, "updated_at": now,
                "updated_by": admin.get("username", "system"),
            }},
            upsert=True)
        if res.upserted_id is not None:
            baru += 1
    await log_audit("sinkron_satker", "", "master",
                    username=admin.get("username", "system"),
                    detail=f"Sinkron master satker: {baru} satker baru terdaftar")
    return {"ok": True, "baru": baru}


@satker_router.post("/satker/backfill")
async def backfill_kode_satker(payload: dict = None,
                               admin: dict = Depends(require_super_admin)):
    """BACKFILL kode_satker untuk DATA LAMA (sekali jalan, idempoten — hanya
    dokumen yang kode_satker-nya kosong/hilang yang diisi):

    1. Register ber-relasi aset (asset_id / asset_ids / aset[]): kode
       diturunkan dari aset → kegiatan → kode_satker.
    2. Sisanya (persediaan, pengadaan, penganggaran, usulan RKBMN,
       pengamanan, insidentil, dst.) TANPA relasi kegiatan: diisi
       `kode_satker_sisa` bila diberikan (use-case: satker tunggal lama
       mengklaim seluruh data historisnya sebelum satker kedua bergabung).

    Kembalikan laporan jumlah terisi per koleksi."""
    payload = payload or {}
    kode_sisa = str(payload.get("kode_satker_sisa") or "").strip()
    if kode_sisa:
        ada = await db.satker.find_one({"kode_satker": kode_sisa}, {"_id": 1})
        if not ada:
            raise HTTPException(
                status_code=400,
                detail=f"Satker {kode_sisa} belum terdaftar di master")

    # Peta aset → kode satker (via kegiatan) — sekali bangun.
    act_satker = {}
    async for a in db.inventory_activities.find(
            {"kode_satker": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "kode_satker": 1}):
        act_satker[a["id"]] = a["kode_satker"]
    aset_satker = {}
    async for a in db.assets.find(
            {}, {"_id": 0, "id": 1, "activity_id": 1}):
        k = act_satker.get(a.get("activity_id"))
        if k:
            aset_satker[a["id"]] = k

    def _kode_dari_dok(d):
        aid = d.get("asset_id")
        if aid and aset_satker.get(aid):
            return aset_satker[aid]
        for lid in (d.get("asset_ids") or []):
            if aset_satker.get(lid):
                return aset_satker[lid]
        for ar in (d.get("aset") or []):
            k = aset_satker.get((ar or {}).get("asset_id"))
            if k:
                return k
        return ""

    KOSONG = {"$in": ["", None]}
    _q_kosong = {"$or": [{"kode_satker": KOSONG},
                         {"kode_satker": {"$exists": False}}]}
    # Klaim-sisa TIDAK boleh menyentuh kode_satker == "" — string kosong
    # adalah stempel sengaja "lintas-satker" oleh super-admin; hanya dokumen
    # yang benar-benar belum pernah distempel (None / field absen) yang sah
    # diklaim massal.
    _q_belum_distempel = {"$or": [{"kode_satker": None},
                                  {"kode_satker": {"$exists": False}}]}
    laporan = {}

    # 1) Koleksi ber-relasi aset.
    RELASI = ("psp", "bmn_idle", "penggunaan_proses", "usulan_penghapusan",
              "pemusnahan", "pemindahtanganan", "pemanfaatan", "penertiban",
              "bast_serah_terima")
    for nama in RELASI:
        coll = db[nama]
        terisi = 0
        async for d in coll.find(_q_kosong, {"_id": 0, "id": 1, "asset_id": 1,
                                             "asset_ids": 1, "aset.asset_id": 1}):
            k = _kode_dari_dok(d)
            if k and d.get("id"):
                await coll.update_one({"id": d["id"]},
                                      {"$set": {"kode_satker": k}})
                terisi += 1
        laporan[nama] = terisi

    # 2) Sisanya diisi kode_satker_sisa bila diberikan.
    if kode_sisa:
        # Koleksi yang BARU distempel di REVIEW-9 R9/R10 ikut di sini, supaya
        # baris lama (yang terlanjur tanpa stempel dan karenanya terlihat
        # lintas satker lewat kelonggaran era-lama) bisa ditutup sekali jalan:
        # lpb, ruangan, surat, mutasi_bmn, pengamanan_checklist.
        SISA = ("persediaan", "pengadaan", "penganggaran", "perencanaan_usulan",
                "pemantauan_insidentil", "pengamanan_kasus",
                "pengamanan_dokumen", "pengamanan_polis",
                "pengamanan_checklist", "lpb", "ruangan", "surat",
                "mutasi_bmn") + RELASI
        for nama in SISA:
            res = await db[nama].update_many(
                _q_belum_distempel, {"$set": {"kode_satker": kode_sisa}})
            laporan[nama] = laporan.get(nama, 0) + res.modified_count

    total = sum(laporan.values())
    await log_audit("backfill_kode_satker", "", "backfill",
                    username=admin.get("username", "system"),
                    detail=(f"Backfill kode_satker: {total} dokumen"
                            + (f" (sisa → {kode_sisa})" if kode_sisa else "")))
    return {"ok": True, "total": total, "per_koleksi": laporan,
            "kode_satker_sisa": kode_sisa}
