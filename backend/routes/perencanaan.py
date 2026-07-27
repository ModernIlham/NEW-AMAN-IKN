"""PERENCANAAN — Fase 4 tahap awal: kandidat RKBMN pemeliharaan.

PMK 153/PMK.06/2021: satker menyusun usulan RKBMN pemeliharaan dari
daftar barang + hasil pemeliharaan. Modul ini menyaring aset yang LAYAK
diusulkan (Baik/Rusak Ringan, dioperasikan) vs yang tidak (rusak berat,
idle, nonaktif) + riwayat biaya pemeliharaan sebagai bahan pertimbangan.
RKBMN pengadaan + sanding SBSK menyusul sesuai masterplan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_writer
from db import db
from pemeliharaan_utils import rekap_pemeliharaan
from shared_utils import (kode_satker_user, scope_query_aset,
                          scope_query_field_satker, pastikan_akses_dok_satker)
from perencanaan_utils import (
    JENIS_USULAN_RKBMN, STATUS_USULAN_RKBMN, TRANSISI_USULAN_RKBMN,
    rekap_rkbmn, rekap_usulan_rkbmn, validate_transisi_rkbmn,
    validate_usulan_rkbmn,
)

perencanaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "condition": 1, "status": 1, "location": 1}
_PROJ_BIAYA = {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
               "asset_name": 1, "tanggal": 1, "jenis": 1, "biaya": 1}
_MAKS_BARIS = 1000  # daftar dipangkas untuk UI; ringkasan tetap utuh


async def _data_rkbmn(tahun: int, user=None):
    """Kumpulkan kandidat RKBMN (dipakai endpoint JSON & XLSX).

    ISOLASI SATKER (REVIEW-9 R10): `filter_aset_perhitungan` TIDAK men-scope
    satker, jadi tanpa `scope_query_aset` kertas kerja RKBMN satu satker berisi
    aset + biaya pemeliharaan SELURUH satker.
    """
    from shared_utils import (filter_aset_perhitungan, scope_query_aset,
                              scope_query_field_satker)
    assets = [a async for a in db.assets.find(
        await filter_aset_perhitungan(await scope_query_aset(user, {})),
        _PROJ_ASET)]
    records = [r async for r in db.pemeliharaan.find(
        scope_query_field_satker(user), _PROJ_BIAYA)]
    per_aset = rekap_pemeliharaan(records, tahun=tahun)["per_aset"]
    biaya_map = {p["asset_id"]: p for p in per_aset if p.get("asset_id")}
    return rekap_rkbmn(assets, biaya_map)


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan-xlsx")
async def rkbmn_pemeliharaan_xlsx(
    tahun: int = Query(None, ge=2000, le=2100),
    _user: dict = Depends(require_user),
):
    """Kertas kerja usulan RKBMN pemeliharaan (XLSX) — siap diisi satker.

    Sheet "Layak Diusulkan" menambahkan kolom kosong Usulan Pekerjaan &
    Perkiraan Biaya untuk diisi lalu dibawa ke SIMAN; sheet "Tidak Layak"
    memuat alasan + jalur yang benar (jejak keputusan untuk auditor).
    """
    import io as io_module

    import xlsxwriter
    from fastapi.responses import StreamingResponse

    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun, _user)
    buffer = io_module.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    f_judul = wb.add_format({"bold": True})
    f_kepala = wb.add_format({"bold": True, "bg_color": "#DDE6F2", "border": 1})
    f_isi = wb.add_format({"bold": True, "bg_color": "#FFF6DD", "border": 1})
    f_sel = wb.add_format({"border": 1})
    f_angka = wb.add_format({"border": 1, "num_format": "#,##0"})

    s1 = wb.add_worksheet("Layak Diusulkan")
    s1.write(0, 0, f"Kertas kerja usulan RKBMN pemeliharaan TA {tahun + 1} "
                   f"(PMK 153/2021) — riwayat biaya TA {tahun}; kolom kuning diisi satker",
             f_judul)
    kolom1 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status",
              "Lokasi", "Riwayat (x)", "Riwayat Biaya (Rp)"]
    for c, h in enumerate(kolom1):
        s1.write(2, c, h, f_kepala)
    s1.write(2, len(kolom1), "Usulan Pekerjaan", f_isi)
    s1.write(2, len(kolom1) + 1, "Perkiraan Biaya (Rp)", f_isi)
    for i, a in enumerate(hasil["layak"], start=3):
        s1.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s1.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s1.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s1.write(i, 3, str(a.get("condition") or ""), f_sel)
        s1.write(i, 4, str(a.get("status") or ""), f_sel)
        s1.write(i, 5, str(a.get("location") or ""), f_sel)
        s1.write_number(i, 6, a["riwayat_jumlah"], f_angka)
        s1.write_number(i, 7, a["riwayat_biaya"], f_angka)
        s1.write(i, 8, "", f_sel)
        s1.write(i, 9, "", f_angka)
    s1.set_column(0, 0, 14)
    s1.set_column(2, 2, 36)
    s1.set_column(3, 5, 14)
    s1.set_column(6, 7, 14)
    s1.set_column(8, 8, 32)
    s1.set_column(9, 9, 18)

    s2 = wb.add_worksheet("Tidak Layak")
    kolom2 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status", "Alasan / Jalur yang Benar"]
    for c, h in enumerate(kolom2):
        s2.write(0, c, h, f_kepala)
    for i, a in enumerate(hasil["tidak"], start=1):
        s2.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s2.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s2.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s2.write(i, 3, str(a.get("condition") or ""), f_sel)
        s2.write(i, 4, str(a.get("status") or ""), f_sel)
        s2.write(i, 5, a.get("alasan") or "", f_sel)
    s2.set_column(0, 0, 14)
    s2.set_column(2, 2, 36)
    s2.set_column(5, 5, 60)

    wb.close()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="Usulan_RKBMN_Pemeliharaan_TA{tahun + 1}.xlsx"'})


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan")
async def rkbmn_pemeliharaan(
    tahun: int = Query(None, ge=2000, le=2100,
                       description="Tahun anggaran riwayat biaya (default: berjalan)"),
    _user: dict = Depends(require_user),
):
    """Kandidat usulan RKBMN pemeliharaan + riwayat biaya per aset."""
    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun, _user)
    dipangkas = {
        "layak": len(hasil["layak"]) > _MAKS_BARIS,
        "tidak": len(hasil["tidak"]) > _MAKS_BARIS,
    }
    hasil["layak"] = hasil["layak"][:_MAKS_BARIS]
    hasil["tidak"] = hasil["tidak"][:_MAKS_BARIS]
    hasil["tahun"] = tahun
    hasil["dipangkas"] = dipangkas
    hasil["catatan"] = (
        "Kriteria PMK 153/2021: hanya kondisi Baik/Rusak Ringan yang layak "
        "diusulkan; rusak berat = jalur penghapusan; BMN idle = penetapan "
        "status (PMK 120/2024). Riwayat biaya dari modul Pemeliharaan TA "
        f"{tahun}."
    )
    return hasil


class UsulanRkbmnIn(BaseModel):
    tahun_rkbmn: str = Field(min_length=4, max_length=4)
    jenis: str
    unit_pengusul: str = Field(min_length=1)
    uraian: str = Field(min_length=1)
    volume: float = Field(gt=0)
    satuan: str = Field(min_length=1)
    asset_id: str = ""                 # opsional (pemeliharaan/eksisting)
    keterangan: str = ""


class TransisiRkbmnIn(BaseModel):
    status: str
    catatan: str = ""
    sptjm: bool | None = None          # penanda SPTJM ditandatangani
    reviu_apip: bool | None = None     # penanda sudah direviu APIP


@perencanaan_router.get("/perencanaan/usulan")
async def list_usulan_rkbmn(_user: dict = Depends(require_user)):
    """Register usulan RKBMN per unit (terbaru dulu) + ringkasan."""
    items = [u async for u in db.perencanaan_usulan.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_usulan_rkbmn(items),
            "label_jenis": JENIS_USULAN_RKBMN,
            "label_status": STATUS_USULAN_RKBMN,
            "transisi": {k: sorted(v) for k, v in TRANSISI_USULAN_RKBMN.items()},
            "catatan": (
                "Register pendamping rantai usulan RKBMN internal (PMK "
                "153/2021 + KMK 128/KM.6/2022) — usulan resmi tetap via "
                "SIMAN V2; status di sini tak berkekuatan hukum dan bukan "
                "cetakan RKBMN/SPTJM/Hasil Penelaahan.")}


@perencanaan_router.get("/perencanaan/usulan/export")
async def export_usulan_rkbmn(_user: dict = Depends(require_user)):
    """Ekspor CSV register usulan RKBMN (pola #158 — audit G4 #11)."""
    import csv as csv_module
    import io

    from fastapi import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["tahun_rkbmn", "jenis", "unit_pengusul", "uraian", "volume",
                "satuan", "status", "sptjm", "reviu_apip", "kode_barang",
                "nup", "nama_aset", "keterangan", "dibuat_oleh"])
    async for u in db.perencanaan_usulan.find(scope_query_field_satker(_user), {"_id": 0}).sort("updated_at", -1):
        w.writerow([
            u.get("tahun_rkbmn"), JENIS_USULAN_RKBMN.get(u.get("jenis"), u.get("jenis")),
            u.get("unit_pengusul"), u.get("uraian"), u.get("volume"), u.get("satuan"),
            STATUS_USULAN_RKBMN.get(u.get("status"), u.get("status")),
            "ya" if u.get("sptjm") else "belum",
            "ya" if u.get("reviu_apip") else "belum",
            u.get("asset_code"), u.get("NUP"), u.get("asset_name"),
            u.get("keterangan"), u.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_usulan_rkbmn.csv"'})


@perencanaan_router.post("/perencanaan/usulan")
async def buat_usulan_rkbmn(payload: UsulanRkbmnIn,
                            user: dict = Depends(require_writer)):
    """Buat usulan RKBMN baru (status awal draft; aset opsional)."""
    data = payload.model_dump()
    errors = validate_usulan_rkbmn(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_snapshot = {}
    aid = str(data.get("asset_id") or "").strip()
    if aid:
        a = await db.assets.find_one(
            {"id": aid}, {**_PROJ_ASET, "activity_id": 1})
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        from shared_utils import pastikan_akses_aset
        await pastikan_akses_aset(user, a)  # isolasi satker (REVIEW-9 R10)
        aset_snapshot = {"asset_id": a["id"], "asset_code": a.get("asset_code"),
                         "NUP": a.get("NUP"), "asset_name": a.get("asset_name")}
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": kode_satker_user(user),
        "tahun_rkbmn": data["tahun_rkbmn"].strip(),
        "jenis": data["jenis"],
        "unit_pengusul": data["unit_pengusul"].strip(),
        "uraian": data["uraian"].strip(),
        "volume": float(data["volume"]),
        "satuan": data["satuan"].strip(),
        **aset_snapshot,
        "status": "draft",
        "sptjm": False,
        "reviu_apip": False,
        "keterangan": str(data.get("keterangan") or "").strip(),
        "riwayat": [{"status": "draft", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.perencanaan_usulan.insert_one({**record})
    return record


@perencanaan_router.post("/perencanaan/usulan/{usulan_id}/status")
async def transisi_usulan_rkbmn(usulan_id: str, payload: TransisiRkbmnIn,
                                user: dict = Depends(require_writer)):
    """Pindahkan status usulan (anti-race; dikembalikan wajib catatan)."""
    u = await db.perencanaan_usulan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(user, u)
    ke = payload.status
    errors = validate_transisi_rkbmn(u, ke, payload.catatan)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": ke, "updated_at": now}
    if payload.sptjm is not None:
        set_fields["sptjm"] = bool(payload.sptjm)
    if payload.reviu_apip is not None:
        set_fields["reviu_apip"] = bool(payload.reviu_apip)
    entri = {"status": ke, "tanggal": now, "oleh": user.get("username"),
             "catatan": str(payload.catatan or "").strip()}
    res = await db.perencanaan_usulan.find_one_and_update(
        {"id": usulan_id, "status": u["status"]},
        {"$set": set_fields, "$push": {"riwayat": entri}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Status usulan berubah di perangkat lain — muat ulang")
    res.update(set_fields)
    return res


@perencanaan_router.delete("/perencanaan/usulan/{usulan_id}")
async def hapus_usulan_rkbmn(usulan_id: str,
                             _admin: dict = Depends(require_admin)):
    """Hapus satu usulan dari register (admin)."""
    res = await db.perencanaan_usulan.delete_one(
        scope_query_field_satker(_admin, {"id": usulan_id}))
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    return {"ok": True}


# ============================================================================
# SBSK (PMK 138/2024) — tabel standar konfigurabel + SANDING usulan (M-MODUL)
# ============================================================================

class SbskIn(BaseModel):
    kategori: str
    peruntukan: str
    satuan: str
    standar: float
    keterangan: str = ""


@perencanaan_router.get("/perencanaan/sbsk")
async def daftar_sbsk(_user: dict = Depends(require_user)):
    """Tabel Standar Barang & Standar Kebutuhan (PMK 138/2024) — dirawat
    admin dari Lampiran PMK; seed default dimuat OTOMATIS saat kosong."""
    from perencanaan_utils import SBSK_SEED_DEFAULT
    if await db.sbsk_standar.estimated_document_count() == 0:
        now = datetime.now(timezone.utc).isoformat()
        for s in SBSK_SEED_DEFAULT:
            await db.sbsk_standar.insert_one(
                {**s, "id": str(uuid.uuid4()), "sumber": "seed",
                 "created_at": now})
    items = await db.sbsk_standar.find({}, {"_id": 0}).sort(
        [("kategori", 1), ("peruntukan", 1)]).to_list(1000)
    return {"items": items, "jumlah": len(items),
            "dasar": "PMK 138/2024 — Standar Barang & Standar Kebutuhan BMN"}


@perencanaan_router.post("/perencanaan/sbsk")
async def tambah_sbsk(payload: SbskIn, admin: dict = Depends(require_admin)):
    """Tambah/rawat baris standar SBSK (admin — angka dari Lampiran PMK 138)."""
    from perencanaan_utils import validate_sbsk
    data = payload.model_dump()
    errors = validate_sbsk(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    record = {**{k: (str(v).strip() if isinstance(v, str) else v)
                 for k, v in data.items()},
              "id": str(uuid.uuid4()), "sumber": "input satker",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "created_by": admin.get("username", "system")}
    await db.sbsk_standar.insert_one({**record})
    return record


@perencanaan_router.delete("/perencanaan/sbsk/{sbsk_id}")
async def hapus_sbsk(sbsk_id: str, _admin: dict = Depends(require_admin)):
    res = await db.sbsk_standar.delete_one({"id": sbsk_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Baris standar tidak ditemukan")
    return {"ok": True}


@perencanaan_router.get("/perencanaan/usulan/{usulan_id}/sanding")
async def sanding_usulan(usulan_id: str, kode_barang: str = "",
                         _user: dict = Depends(require_user)):
    """SANDING usulan RKBMN vs aset EKSISTING sejenis + standar SBSK:
    jumlah/kondisi/umur rata-rata/nilai aset ber-prefix `kode_barang`
    (param menimpa snapshot aset usulan) + baris standar relevan + catatan
    analisis untuk reviewer (PMK 153/2021 jo. PMK 138/2024)."""
    from perencanaan_utils import sanding_usulan_aset
    from shared_utils import kode_satker_user, scope_query_field_satker, scope_query_aset
    usulan = await db.perencanaan_usulan.find_one({"id": usulan_id}, {"_id": 0})
    if not usulan:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, usulan)
    prefix = (str(kode_barang or "").strip()
              or str(usulan.get("asset_code") or "")[:3])
    usulan_sanding = {**usulan, "kode_barang": prefix}
    from shared_utils import filter_aset_perhitungan
    q = await filter_aset_perhitungan(await scope_query_aset(_user, {}))
    assets = await db.assets.find(
        q, {"_id": 0, "asset_code": 1, "condition": 1,
            "purchase_date": 1, "purchase_price": 1}).to_list(200000)
    standar = await db.sbsk_standar.find({}, {"_id": 0}).to_list(1000)
    hasil = sanding_usulan_aset(
        usulan_sanding, assets,
        datetime.now(timezone.utc).date().isoformat(), standar)
    return {"usulan": {k: usulan.get(k) for k in
                       ("id", "uraian", "jenis", "volume", "satuan", "tahun_rkbmn")},
            "kode_barang": prefix, **hasil}


# ═══════════════════════════════════════════════════════════════════════════
# SBSK BERBASIS RUANG NYATA (Spasial Fase 15)
#
# Sampai fase ini, standar "247 m² untuk pimpinan" tak punya lawan bicara:
# tak ada satu pun luas ruangan NYATA di sistem untuk dibandingkan. Denah
# poligon Fase 3–7 menyediakannya — luas dihitung DARI GAMBARNYA, bukan dari
# angka yang diketik ulang seseorang ke dalam formulir.
#
# LUAS DIHITUNG ULANG DI SINI, tidak membaca `metrik.luas_m2` yang tersimpan.
# Nilai tersimpan itu ditulis saat geometri terakhir disimpan, bisa jadi oleh
# RUMUS VERSI LAMA (proyeksi bola, yang melebihkan luas ~0,45% di lintang IKN).
# Untuk peringkat area bias seragam tak berpengaruh; untuk angka yang masuk
# dokumen perencanaan, membaca nilai basi berarti melaporkan luas yang tak bisa
# dipertanggungjawabkan asal-usulnya.
# ═══════════════════════════════════════════════════════════════════════════

_MAKS_RUANGAN_SBSK = 800
# Nama pemegang yang ditampilkan per ruangan. Gudang bisa punya ratusan; yang
# dibaca petugas di layar cuma beberapa.
_MAKS_PEMEGANG_SBSK = 20


@perencanaan_router.get("/perencanaan/sbsk-ruang")
async def sbsk_ruang(node_id: str = Query(...), dalam: bool = Query(True),
                     tipe: str = Query("RUANGAN"),
                     _user: dict = Depends(require_user)):
    """Sanding LUAS RUANGAN NYATA (dari poligon denah) vs standar SBSK.

    Yang paling berguna di sini bukan kolom "sesuai", melainkan dua kolom yang
    biasanya tak ada di mana pun: ruangan yang sudah tergambar tetapi BELUM
    ditetapkan peruntukannya, dan ruangan yang tak berperuntukan SEKALIGUS tak
    berisi aset apa pun — ruang menganggur. Itulah bukti yang menahan usulan
    pengadaan ruang baru.
    """
    import spasial_utils as su
    import sbsk_ruang_utils as sru

    node = await db.spasial_node.find_one(
        scope_query_field_satker(_user, {"id": str(node_id or "").strip()}),
        {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "status": 1})
    if not node or node.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node denah tidak ditemukan")

    lingkup = {"status": {"$ne": "dihapus"}}
    if dalam:
        lingkup["$or"] = [{"id": node["id"]}, {"ancestors": node["id"]}]
    else:
        lingkup["parent_id"] = node["id"]
    tipe_pilih = str(tipe or "").strip().upper()
    if tipe_pilih:
        lingkup["tipe"] = tipe_pilih

    rows_node = await db.spasial_node.find(
        scope_query_field_satker(_user, lingkup),
        {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "peruntukan": 1,
         "ancestors_nama": 1, "geometry": 1}).to_list(_MAKS_RUANGAN_SBSK)

    # Isi ruangan (jumlah aset + pemegang) dalam SATU agregasi, bukan satu
    # kueri per ruangan: gedung berisi 200 ruangan akan berarti 200 bolak-balik
    # jaringan untuk satu halaman yang sama.
    #
    # DUA HAL YANG DIPERBAIKI SETELAH AUDIT ADVERSARIAL:
    #
    # 1. ISOLASI SATKER. `ids` memang ter-scope satker, tetapi node ERA LAMA
    #    tanpa `kode_satker` terbuka untuk semua satker (lihat
    #    scope_query_field_satker) — sehingga aset satker LAIN yang menempati
    #    node semacam itu ikut terhitung, lengkap dengan NAMA PEMEGANGNYA.
    #    `scope_query_aset` menutupnya lewat kegiatan induk, jalur guard baku
    #    modul aset. Agregasi tak bisa memakai `pastikan_akses_aset` per dokumen,
    #    dan justru karena itu ia gampang lolos dari penjagaan — filternya harus
    #    ikut masuk ke `$match`.
    #
    # 2. `$limit` DIPINDAH KE SETELAH `$group`. Sebelumnya ia memotong ASET
    #    sebelum pengelompokan, sehingga ruangan yang asetnya kebetulan berada
    #    di luar potongan HILANG UTUH dari peta `isi` — lalu dilaporkan
    #    "menganggur" karena jumlah asetnya 0. Persis kebalikan dari tujuan
    #    laporan ini: bukti palsu untuk menghentikan pengadaan. Setelah `$group`,
    #    plafonnya membatasi jumlah RUANGAN (yang sudah ≤ len(ids)), bukan aset.
    ids = [r["id"] for r in rows_node]
    isi = {}
    if ids:
        q_isi = await scope_query_aset(
            _user, {"lokasi_spasial.node_id": {"$in": ids}})
        async for g in db.assets.aggregate([
            {"$match": q_isi},
            {"$group": {"_id": "$lokasi_spasial.node_id",
                        "jumlah": {"$sum": 1},
                        "pemegang": {"$addToSet": "$user"}}},
            {"$limit": _MAKS_RUANGAN_SBSK},
        ]):
            isi[g["_id"]] = {
                "jumlah": int(g.get("jumlah") or 0),
                # Daftar pemegang dipotong di Python, bukan di pipeline: ruangan
                # gudang bisa punya ratusan pemegang berbeda dan seluruhnya tak
                # berguna di layar — yang dibaca petugas cuma beberapa nama.
                "pemegang": [p for p in (g.get("pemegang") or []) if p][:_MAKS_PEMEGANG_SBSK],
            }

    standar = await db.sbsk_standar.find({}, {"_id": 0}).to_list(1000)
    baris = []
    for n in rows_node:
        jalur = " / ".join([str(x) for x in (n.get("ancestors_nama") or []) if x]
                           + [str(n.get("nama") or "")])
        luas = su.luas_kasar_m2(n.get("geometry"))
        baris.append(sru.baris_ruang({**n, "jalur_nama": jalur}, luas,
                                     isi.get(n["id"]), standar))
    baris.sort(key=lambda b: (-(b.get("luas_m2") or 0), b.get("nama") or ""))

    return {
        "node": {"id": node["id"], "nama": node.get("nama"),
                 "tipe": node.get("tipe")},
        "termasuk_keturunan": bool(dalam),
        "tipe": tipe_pilih,
        "items": baris,
        "rekap": sru.rekap_sbsk_ruang(baris),
        "sebaran": sru.sebaran_per_induk(baris),
        "toleransi_persen": sru.TOLERANSI_PERSEN,
        "terpotong": len(rows_node) >= _MAKS_RUANGAN_SBSK,
        "catatan": ("Luas dihitung dari poligon denah (proyeksi lokal WGS84), "
                    "bukan angka ketikan. Untuk poligon seluas kawasan, "
                    "gunakan pustaka geodesi bila angkanya masuk dokumen resmi."),
    }
