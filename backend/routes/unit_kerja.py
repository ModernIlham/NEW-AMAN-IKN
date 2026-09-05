"""Master Unit Kerja berjenjang (Eselon I–V) — adopsi KERJA-BARENG.

Menyediakan struktur organisasi hierarkis utk pilihan bertingkat di form
pegawai & rekap laporan BMN per unit resmi. Semua user melihat; admin
mengelola. Ter-scope satker (pola master lain). Endpoint bangun-dari-pegawai
menderivasi master otomatis dari eselon1–5 data pegawai yang sudah ada/impor.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user, require_admin_satker
from db import db
from shared_utils import (kode_satker_user, log_audit, scope_query_aset,
                          scope_query_field_satker)
import organisasi_utils as org
from unit_kerja_utils import unit_dari_pegawai

unit_kerja_router = APIRouter()

_PROJ = {"_id": 0}


class UnitIn(BaseModel):
    nama_unit: str
    eselon: str
    parent_id: Optional[str] = ""


class UnitUbah(BaseModel):
    """Penyuntingan satu unit. Ketiganya opsional — yang tak dikirim tetap.

    `parent_id` dibedakan antara "tak dikirim" (None → biarkan) dan
    "dikosongkan" (string kosong → jadikan puncak). Tanpa pembedaan itu,
    mengganti nama saja akan diam-diam melepaskan unitnya dari induknya.
    """
    nama_unit: Optional[str] = None
    eselon: Optional[str] = None
    parent_id: Optional[str] = None


@unit_kerja_router.get("/unit-kerja")
async def daftar_unit_kerja(_user: dict = Depends(require_user)):
    """Seluruh unit kerja satker (terurut eselon lalu nama)."""
    items = await db.unit_kerja.find(
        scope_query_field_satker(_user), _PROJ).to_list(5000)
    items.sort(key=lambda u: (str(u.get("eselon")), str(u.get("nama_unit", "")).lower()))
    return {"items": items, "jumlah": len(items)}


@unit_kerja_router.post("/unit-kerja")
async def buat_unit_kerja(payload: UnitIn,
                          user: dict = Depends(require_admin_satker)):
    """Tambah unit (admin). Eselon >1 wajib induk eselon tepat di atasnya."""
    doc = {"nama_unit": str(payload.nama_unit or "").strip(),
           "eselon": str(payload.eselon or "").strip(),
           "parent_id": str(payload.parent_id or "").strip()}
    induk = None
    if doc["parent_id"]:
        induk = await db.unit_kerja.find_one({"id": doc["parent_id"]}, _PROJ)
        if not induk:
            raise HTTPException(status_code=400, detail="Induk tidak ditemukan")
    ok, pesan = org.validasi_unit(doc, induk)
    if not ok:
        raise HTTPException(status_code=400, detail=pesan)
    kode = kode_satker_user(user)
    dup = await db.unit_kerja.find_one(
        {"nama_unit": doc["nama_unit"], "eselon": doc["eselon"],
         "parent_id": doc["parent_id"] or None,
         "kode_satker": {"$in": [kode, "", None]}}, _PROJ)
    if dup:
        raise HTTPException(status_code=400,
                            detail=f"Unit {doc['nama_unit']} sudah terdaftar")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "parent_id": doc["parent_id"] or None,
                "kode_satker": kode, "created_at": now, "updated_at": now})
    await db.unit_kerja.insert_one(dict(doc))
    await log_audit("buat_unit_kerja", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah unit Eselon {doc['eselon']}: {doc['nama_unit']}")
    return {"ok": True, "id": doc["id"]}


async def _rambatkan_nama(user, fe_lama, fe_baru, level_lama, level_baru):
    """Ikutkan pegawai dan aset saat nama/jalur unitnya berubah.

    `pegawai` dan `assets` menyimpan unitnya sebagai NAMA, bukan sebagai id.
    Mengganti nama di master saja membuat keduanya berselisih diam-diam: master
    menyebut "Biro Umum dan Keuangan" sementara seluruh pegawainya masih
    tertulis "Biro Umum", dan pilihan bertingkat pada form pegawai — yang
    mencocokkan lewat nama — mendadak tak menemukan satu pun anak. Penggantian
    nama yang tak ikut merambat bukan penggantian nama, melainkan penambahan
    unit kembar.

    Barisnya dicari lewat jalur lama LENGKAP (leluhur beserta namanya sendiri),
    bukan lewat namanya saja — dua Bagian Tata Usaha di bawah dua Biro berbeda
    tak boleh ikut terbawa.

    `assets` hanya punya kolom eselon1 dan eselon2. Unit Eselon III ke bawah
    karenanya tak dapat dikenali di sana, dan asetnya sengaja TIDAK disentuh:
    menebaknya dari eselon2 akan mengubah aset milik unit saudaranya.
    """
    saring = org.filter_jalur(fe_lama, level_lama)
    if not saring:
        return {"pegawai": 0, "aset": 0}
    setel, hapus = org.perubahan_jalur(fe_lama, fe_baru,
                                       max(level_lama, level_baru))
    if not setel and not hapus:
        return {"pegawai": 0, "aset": 0}
    ubah = {}
    if setel:
        ubah["$set"] = dict(setel)
    if hapus:
        ubah["$unset"] = {k: "" for k in hapus}

    hasil = await db.pegawai.update_many(
        scope_query_field_satker(user, dict(saring)), ubah)
    n_aset = 0
    if max(level_lama, level_baru) <= 2:
        saring_aset = {k: v for k, v in saring.items() if k in ("eselon1",
                                                                "eselon2")}
        setel_aset = {k: v for k, v in setel.items() if k in ("eselon1",
                                                              "eselon2")}
        hapus_aset = [k for k in hapus if k in ("eselon1", "eselon2")]
        if saring_aset and (setel_aset or hapus_aset):
            ubah_aset = {}
            if setel_aset:
                ubah_aset["$set"] = setel_aset
            if hapus_aset:
                ubah_aset["$unset"] = {k: "" for k in hapus_aset}
            # `assets` TIDAK membawa kode_satker; ia di-scope lewat kegiatan
            # induknya. Memakai penyaring berbasis field akan mencocokkan
            # dokumen yang field-nya TIDAK ADA — yaitu seluruh aset satker
            # mana pun — dan penulisan ini akan merambat ke luar satker.
            r = await db.assets.update_many(
                await scope_query_aset(user, saring_aset), ubah_aset)
            n_aset = getattr(r, "modified_count", 0) or 0
    return {"pegawai": getattr(hasil, "modified_count", 0) or 0,
            "aset": n_aset}


@unit_kerja_router.put("/unit-kerja/{unit_id}")
async def ubah_unit_kerja(unit_id: str, payload: UnitUbah,
                          user: dict = Depends(require_admin_satker)):
    """Perbaiki satu unit: ganti nama, pindahkan induk, atau ubah eselonnya.

    Sebelum ada rute ini, unit yang salah ketik dan sudah punya anak tak dapat
    diperbaiki sama sekali — menghapusnya ditolak karena masih membawahi, dan
    tak ada jalan lain selain membongkar seluruh cabangnya lalu menyusunnya
    ulang. Organisasi yang berkembang justru sering berganti nama dan berpindah
    induk; struktur yang hanya bisa ditambah dan dihapus memaksa penggunanya
    membuat unit kembar.
    """
    from shared_utils import pastikan_akses_dok_satker
    u = await db.unit_kerja.find_one({"id": unit_id}, _PROJ)
    if not u:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    await pastikan_akses_dok_satker(user, u)

    baru = dict(u)
    if payload.nama_unit is not None:
        baru["nama_unit"] = str(payload.nama_unit or "").strip()
    if payload.eselon is not None:
        baru["eselon"] = str(payload.eselon or "").strip()
    if payload.parent_id is not None:
        baru["parent_id"] = str(payload.parent_id or "").strip() or None

    induk = None
    if baru.get("parent_id"):
        induk = await db.unit_kerja.find_one({"id": baru["parent_id"]}, _PROJ)
        if not induk:
            raise HTTPException(status_code=400, detail="Induk tidak ditemukan")
        await pastikan_akses_dok_satker(user, induk)

    semua = await db.unit_kerja.find(
        scope_query_field_satker(user),
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1,
         "parent_id": 1}).to_list(5000)
    ok, pesan = org.validasi_perubahan(u, baru, induk, semua)
    if not ok:
        raise HTTPException(status_code=400, detail=pesan)

    kembar = await db.unit_kerja.find_one(
        {"id": {"$ne": unit_id}, "nama_unit": baru["nama_unit"],
         "eselon": baru["eselon"], "parent_id": baru.get("parent_id"),
         "kode_satker": {"$in": [kode_satker_user(user), "", None]}}, _PROJ)
    if kembar:
        raise HTTPException(
            status_code=400,
            detail=f"Unit {baru['nama_unit']} sudah terdaftar di induk itu")

    # Jalur nama SEBELUM dan SESUDAH, dihitung dari pohon yang sama supaya
    # keduanya sebanding. Pohon "sesudah" adalah salinan dengan satu unit
    # diganti — bukan hasil pembacaan ulang setelah menulis, yang akan
    # kehilangan jalur lamanya justru saat ia masih dibutuhkan.
    peta_unit = {x["id"]: x for x in semua}
    peta_parent = {x["id"]: x.get("parent_id") for x in semua}
    fe_lama = org.field_eselon(unit_id, peta_unit, peta_parent)
    peta_unit_baru = dict(peta_unit, **{unit_id: baru})
    peta_parent_baru = dict(peta_parent, **{unit_id: baru.get("parent_id")})
    fe_baru = org.field_eselon(unit_id, peta_unit_baru, peta_parent_baru)
    lv_lama = int(str(u.get("eselon") or "1"))
    lv_baru = int(str(baru.get("eselon") or "1"))

    await db.unit_kerja.update_one({"id": unit_id}, {"$set": {
        "nama_unit": baru["nama_unit"], "eselon": baru["eselon"],
        "parent_id": baru.get("parent_id"),
        "updated_at": datetime.now(timezone.utc).isoformat()}})
    rambat = await _rambatkan_nama(user, fe_lama, fe_baru, lv_lama, lv_baru)

    await log_audit("ubah_unit_kerja", "", unit_id,
                    username=user.get("username", "system"),
                    detail=(f"Ubah unit Eselon {lv_lama}→{lv_baru}: "
                            f"{u.get('nama_unit')} → {baru['nama_unit']}; "
                            f"pegawai {rambat['pegawai']}, aset {rambat['aset']}"))
    return {"ok": True, "id": unit_id, "jalur": org.jalur_nama(
        unit_id, peta_unit_baru, peta_parent_baru), "ikut_diperbarui": rambat}


@unit_kerja_router.delete("/unit-kerja/{unit_id}")
async def hapus_unit_kerja(unit_id: str, user: dict = Depends(require_admin)):
    """Hapus unit (admin). Ditolak bila masih punya anak atau dipakai pegawai."""
    u = await db.unit_kerja.find_one({"id": unit_id}, _PROJ)
    if not u:
        raise HTTPException(status_code=404, detail="Unit tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(user, u)
    # Cacah di-scope (REVIEW-9 R10): tanpa itu unit satker ini tak bisa
    # dihapus hanya karena satker LAIN punya anak/pegawai bernama sama, dan
    # angkanya membocorkan volume satker lain.
    from shared_utils import scope_query_field_satker
    anak = await db.unit_kerja.count_documents(
        scope_query_field_satker(user, {"parent_id": unit_id}))
    if anak:
        raise HTTPException(status_code=409, detail=(
            f"Unit masih punya {anak} sub-unit — hapus/pindahkan dulu"))
    nama = str(u.get("nama_unit") or "")
    es = str(u.get("eselon") or "1")
    dipakai = await db.pegawai.count_documents(
        scope_query_field_satker(user, {f"eselon{es}": nama}))
    if dipakai:
        raise HTTPException(status_code=409, detail=(
            f"Unit dipakai {dipakai} pegawai — perbarui unit pegawai dulu"))
    await db.unit_kerja.delete_one({"id": unit_id})
    await log_audit("hapus_unit_kerja", "", unit_id,
                    username=user.get("username", "system"),
                    detail=f"Hapus unit Eselon {es}: {nama}")
    return {"ok": True, "id": unit_id}


class LingkupTeksIn(BaseModel):
    """Lingkup kegiatan bentuk LAMA: `[{nama, eselon2: [nama, …]}, …]`."""
    eselon1: Optional[list] = []


@unit_kerja_router.post("/unit-kerja/cocokkan-lingkup")
async def cocokkan_lingkup(payload: LingkupTeksIn,
                           user: dict = Depends(require_user)):
    """Ubah lingkup yang DIKETIK menjadi rujukan ke master unit.

    Kegiatan lama mencatat lingkupnya sebagai teks bebas dua tingkat, tak
    pernah dihubungkan dengan master unit mana pun. Rute ini mencocokkannya
    sekali supaya kegiatan lama tak perlu diisi ulang tangan.

    Yang TIDAK cocok ikut dikembalikan, bukan dibuang diam-diam: salah ketik
    pada data lama justru yang perlu dilihat orang yang memperbaikinya, dan
    daftar yang menyusut tanpa keterangan terbaca sebagai data yang hilang.

    Hanya MENGUSULKAN — penyimpanannya lewat rute kegiatan seperti biasa,
    sehingga tetap satu jalur tulis.
    """
    semua = await db.unit_kerja.find(
        scope_query_field_satker(user),
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1,
         "parent_id": 1}).to_list(5000)
    ids, tak_cocok = org.cocokkan_lingkup_teks(payload.eselon1 or [], semua)
    peta_unit = {u["id"]: u for u in semua}
    peta_parent = {u["id"]: u.get("parent_id") for u in semua}
    return {
        "lingkup_unit": ids,
        "tak_cocok": tak_cocok,
        "unit": [{"id": i, "eselon": str(peta_unit[i].get("eselon") or ""),
                  "jalur": org.jalur_nama(i, peta_unit, peta_parent)}
                 for i in ids],
    }


@unit_kerja_router.post("/unit-kerja/bangun-dari-pegawai")
async def bangun_dari_pegawai(user: dict = Depends(require_admin_satker)):
    """Bangun/lengkapi master unit OTOMATIS dari jalur eselon1–5 seluruh
    pegawai satker (idempoten — hanya menambah yang belum ada). Berguna
    pasca impor massal: master langsung terisi tanpa entri manual."""
    kode = kode_satker_user(user)
    pegawai = await db.pegawai.find(
        scope_query_field_satker(user),
        {"_id": 0, "eselon1": 1, "eselon2": 1, "eselon3": 1,
         "eselon4": 1, "eselon5": 1}).to_list(20000)
    kandidat = unit_dari_pegawai(pegawai)
    ada = await db.unit_kerja.find(
        scope_query_field_satker(user),
        {"_id": 0, "id": 1, "nama_unit": 1, "eselon": 1, "parent_id": 1}
    ).to_list(5000)
    # peta (eselon, nama) → id utk resolusi induk; nama unik per level cukup
    # praktis utk data organisasi nyata.
    peta = {(str(u["eselon"]), u["nama_unit"]): u["id"] for u in ada}
    now = datetime.now(timezone.utc).isoformat()
    dibuat = 0
    # urut per eselon agar induk selalu dibuat lebih dulu
    for k in sorted(kandidat, key=lambda x: x["eselon"]):
        kunci = (k["eselon"], k["nama_unit"])
        if kunci in peta:
            continue
        parent_id = None
        if k["induk_nama"]:
            parent_id = peta.get((str(int(k["eselon"]) - 1), k["induk_nama"]))
            if not parent_id:
                continue  # induk tak dikenal — jalur tak utuh, lewati
        doc = {"id": str(uuid.uuid4()), "nama_unit": k["nama_unit"],
               "eselon": k["eselon"], "parent_id": parent_id,
               "kode_satker": kode, "sumber": "derivasi pegawai",
               "created_at": now, "updated_at": now}
        await db.unit_kerja.insert_one(dict(doc))
        peta[kunci] = doc["id"]
        dibuat += 1
    await log_audit("bangun_unit_kerja", "", "derivasi",
                    username=user.get("username", "system"),
                    detail=f"Bangun master unit dari pegawai: {dibuat} unit baru")
    return {"ok": True, "dibuat": dibuat, "total_kandidat": len(kandidat)}
