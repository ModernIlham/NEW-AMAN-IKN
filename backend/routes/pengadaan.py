"""PENGADAAN — Fase 4 tahap awal: register perolehan per dokumen.

Perpres 16/2018 jo. 46/2025 (pustaka §10): satu entri per BAST/kontrak,
checklist kelengkapan dokumen sumber, daftar barang dengan tautan ke aset
master (cegah entri ganda) + penanda ekstrakomptabel PMK 181. Pencatatan
resmi tetap di SAKTI; kanal pengadaan tetap SiRUP/SPSE/e-Katalog — AMAN
alat bantu tertib dokumen satker. Barang perolehan yang belum tertaut
dapat dibuatkan draft aset otomatis (buat-draft-aset, NUP berurut).
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from lpb_utils import (
    baris_lpb_dari_aset, is_persediaan, pilah_barang_perolehan,
    ringkas_pencatatan, total_nilai_lpb,
)
from persediaan_utils import KODE_PENUH_LEN, KODE_PREFIX_LEN
from db import db, fs_bucket
from shared_utils import kode_satker_user, scope_query_field_satker, pastikan_akses_dok_satker, delete_document_from_gridfs, get_document_from_gridfs, log_audit
from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    build_asset_perolehan_projection, dokumen_kurang_perolehan,
    is_ekstrakomptabel, nilai_perolehan, rekap_perolehan,
    snapshot_penganggaran, snapshot_ppk, validate_perolehan,
)

pengadaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


class BarangIn(BaseModel):
    uraian: str = Field(min_length=1)
    kode: str = ""                     # kode barang (opsional, utk ambang)
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)
    asset_id: str = ""                 # tautan ke aset master (opsional)


class PerolehanIn(BaseModel):
    jenis: str
    pihak: str = Field(min_length=1)   # penyedia / pemberi hibah / pengirim
    nomor_kontrak: str = ""
    nomor_bast: str = Field(min_length=1)
    tanggal_bast: str = Field(min_length=10, max_length=10)
    keterangan: str = ""
    penganggaran_id: str = ""          # tautan usulan Penganggaran (opsional)
    # PPK penanggung jawab komitmen. Kosong = resolusi otomatis dari Referensi
    # Pejabat menurut tanggal BAST (lihat `_ambil_snapshot_ppk`).
    ppk_pejabat_id: str = ""
    barang: list[BarangIn] = Field(min_length=1, max_length=100)


class TautkanPenganggaranIn(BaseModel):
    penganggaran_id: str = ""          # kosong = lepaskan tautan


class TetapkanPpkIn(BaseModel):
    # "" = kosongkan penetapan; "auto" = resolusi ulang dari Referensi Pejabat.
    ppk_pejabat_id: str = ""


async def _ambil_snapshot_penganggaran(penganggaran_id: str, user=None) -> dict:
    """Cari usulan penganggaran (bila id diisi) → snapshot; 404 bila hilang.

    Isolasi satker (REVIEW-9 R9): pencarian di-scope ke satker pemanggil —
    tanpa itu writer satker A dapat menautkan perolehannya ke usulan satker B
    dan ikut membaca uraian/nomor DIPA/tahun anggaran milik B.
    """
    pid = str(penganggaran_id or "").strip()
    if not pid:
        return snapshot_penganggaran(None)
    u = await db.penganggaran.find_one(
        scope_query_field_satker(user, {"id": pid}),
        {"_id": 0, "id": 1, "uraian": 1, "nomor_dipa": 1, "tahun_anggaran": 1})
    if not u:
        raise HTTPException(status_code=404,
                            detail="Usulan penganggaran tidak ditemukan")
    return snapshot_penganggaran(u)


async def _ambil_snapshot_ppk(ppk_pejabat_id: str, tanggal_bast: str,
                              user=None) -> dict:
    """Tentukan PPK dokumen ini → snapshot beku.

    DUA jalur, sengaja:

    - **id diisi** → pejabat itu yang dipakai, apa pun perannya di registry.
      Operator kadang tahu lebih tepat daripada tabel (mis. PPK pengganti yang
      SK-nya belum sempat direkam). 404 bila id tak ada.
    - **id kosong** → resolusi otomatis peran `ppk` yang BERLAKU pada tanggal
      BAST. Tanggal BAST, bukan hari ini: register perolehan sering diisi
      belakangan, dan PPK hari ini belum tentu PPK yang menandatangani.

    Ter-scope satker (pola resolve_pejabat_peran): dokumen satker ini hanya
    boleh menyebut pejabat satker ini — tanpa itu, id pejabat satker lain bisa
    dijadikan PPK dan namanya ikut tercetak di BAST/LPB kita.
    """
    from shared_utils import _q_pejabat_satker, resolve_pejabat_peran
    pid = str(ppk_pejabat_id or "").strip()
    kode = kode_satker_user(user)
    per_iso = str(tanggal_bast or "").strip()[:10] or None
    if pid:
        pj = await db.pejabat.find_one(
            {**_q_pejabat_satker(kode), "id": pid}, {"_id": 0})
        if not pj:
            raise HTTPException(status_code=404,
                                detail="Pejabat PPK tidak ditemukan")
        return snapshot_ppk(pj)
    return snapshot_ppk(await resolve_pejabat_peran(
        "ppk", per_iso=per_iso, kode_satker=kode))


async def _proyeksi_perolehan_ke_aset(perolehan: dict) -> None:
    """Proyeksi BALIK dokumen sumber (§5A gap #6): stamp `perolehan_id` +
    snapshot ke tiap aset yang tertaut di baris barang. Best-effort — perolehan
    (jurnal) sudah tersimpan; kegagalan tak menggagalkan pencatatan. Tanpa
    `$inc version` (provenance) agar tak memicu OCC 409 palsu pada form aset.
    """
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_perolehan_projection(perolehan, now)
    for b in perolehan.get("barang") or []:
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            await db.assets.update_one({"id": aid}, {"$set": proj})


async def _lepas_perolehan_dari_aset(asset_id: str, perolehan_id: str) -> None:
    """Lepas back-link perolehan pada aset saat baris di-untautkan — HANYA bila
    `perolehan_id` cocok (jangan hapus tautan milik perolehan lain)."""
    aid = str(asset_id or "").strip()
    if not aid:
        return
    await db.assets.update_one(
        {"id": aid, "perolehan_id": perolehan_id},
        {"$set": {"perolehan_id": "", "perolehan": {}}})


class DokumenIn(BaseModel):
    dokumen: dict[str, bool]


class TautkanIn(BaseModel):
    index: int = Field(ge=0)
    asset_id: str = ""                 # kosong = lepaskan tautan


def _enrich(p: dict) -> dict:
    p["dokumen_kurang"] = dokumen_kurang_perolehan(p)
    p["nilai"] = nilai_perolehan(p)
    for b in p.get("barang") or []:
        b["ekstrakomptabel"] = is_ekstrakomptabel(b)
    return p


@pengadaan_router.get("/pengadaan")
async def list_pengadaan(_user: dict = Depends(require_user)):
    """Register perolehan (BAST terbaru dulu) + ringkasan + label."""
    items = [_enrich(p) async for p in db.pengadaan.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("tanggal_bast", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_perolehan(items),
            "label_jenis": {k: v[0] for k, v in JENIS_PEROLEHAN.items()},
            "kode_jenis": {k: v[1] for k, v in JENIS_PEROLEHAN.items()},
            "label_dokumen": LABEL_DOKUMEN_SUMBER,
            "dokumen_wajib": {k: list(v) for k, v in DOKUMEN_PEROLEHAN.items()},
            "catatan": (
                "Register pendamping tertib dokumen: pencatatan BMN resmi di "
                "SAKTI (BAST = pemicu, tanpa menunggu SP2D); kanal pengadaan "
                "resmi SiRUP/SPSE/e-Katalog. Penanda ekstrakomptabel memakai "
                "ambang PMK 181/2016 (peralatan-mesin Rp1 jt, gedung Rp25 jt).")}


@pengadaan_router.post("/pengadaan/{perolehan_id}/daftarkan-persediaan")
async def daftarkan_persediaan(perolehan_id: str, user: dict = Depends(require_writer)):
    """Barang perolehan ber-kode persediaan (awalan '1') → master persediaan
    + transaksi masuk berjurnal FIFO (audit G4 #6 — jalur BAST konsumsi).

    Master dicari per kode; bila belum ada dibuat otomatis (kode 10 digit
    dilengkapi nomor urut, NUP otomatis). Transaksi memakai jalur
    `transaksi_masuk` yang sudah atomik + berjurnal + ber-FK dokumen sumber.
    Baris yang sudah pernah didaftarkan (psd_item_id) dilewati.
    """
    from routes.persediaan import (PersediaanCreate, TransaksiMasukIn,
                                   create_persediaan, transaksi_masuk)

    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)
    barang = list(p.get("barang") or [])
    dibuat_master = masuk = dilewati_nonpsd = dilewati_terdaftar = 0
    gagal = []
    for row in barang:
        kode = str(row.get("kode") or "").strip()
        if not is_persediaan(kode):
            dilewati_nonpsd += 1
            continue
        if str(row.get("psd_item_id") or "").strip():
            dilewati_terdaftar += 1
            continue
        # Sisi kembar dari penjaga di `buat_draft_aset_dari_perolehan`: baris
        # yang TERLANJUR jadi aset (data lama, sebelum penjaga golongan ada)
        # tak boleh ditambahkan lagi ke stok persediaan.
        if str(row.get("asset_id") or "").strip():
            dilewati_terdaftar += 1
            continue
        jumlah_asli = float(row.get("jumlah") or 1)
        jumlah = max(1, int(jumlah_asli))
        if jumlah != jumlah_asli:
            # Pemotongan pecahan JANGAN senyap: 2,5 liter tercatat 2 dan
            # setengahnya lenyap dari stok tanpa jejak (temuan audit).
            gagal.append(
                f"{row.get('uraian')}: jumlah {jumlah_asli:g} dibulatkan ke "
                f"bawah menjadi {jumlah} — stok persediaan hanya menerima "
                f"bilangan bulat; pecah barisnya atau ubah satuannya.")
        # Lookup master DALAM LINGKUP SATKER (REVIEW-9 R3): tanpa scope,
        # master satker lain yang kebetulan ber-kode sama terpilih → jalur
        # create terlewati → transaksi_masuk 403 dan baris macet permanen.
        #
        # COCOKKAN PER-AWALAN **DAN NAMA** (dua temuan audit berturut-turut).
        #
        # Ronde 1: `create_persediaan` menyimpan kode 16 digit (`next_kode_penuh`:
        # 10 digit kodefikasi + 6 digit nomor urut) sedangkan baris BAST membawa
        # 10 digit, jadi pencocokan PERSIS selalu meleset → master baru dibuat
        # setiap kali barang yang sama dibeli, dan satu jenis kertas HVS pecah
        # jadi puluhan kartu stok.
        #
        # Ronde 2: mencocokkan per-awalan SAJA lebih buruk lagi. Enam digit
        # terakhir itu justru yang MEMBEDAKAN barang berbeda pada kodefikasi
        # 10-digit yang sama ("Kertas HVS A4" vs "Kertas HVS F4"). Mengambil
        # nomor urut terkecil membuang stok & layer FIFO ke kartu barang yang
        # SALAH — lebih merusak daripada kartu yang pecah.
        #
        # Karena itu: awalan kode + nama barang yang sama (abaikan kapital &
        # spasi berlebih). Tak ada yang cocok → master baru, sebagaimana
        # mestinya. Kode yang lebih pendek dari awalan baku (mis. "1") tak
        # pernah dicocokkan per-awalan — dulu ditolak, dan tetap harus ditolak.
        from shared_utils import scope_query_field_satker
        nama_row = str(row.get("uraian") or "").strip()
        if len(kode) == KODE_PENUH_LEN:
            q_kode = {"kode_barang": kode}
        elif len(kode) >= KODE_PREFIX_LEN:
            q_kode = {"kode_barang": {"$regex": f"^{re.escape(kode)}"},
                      "nama_barang": {"$regex": f"^{re.escape(nama_row)}$",
                                      "$options": "i"}}
        else:
            q_kode = {"kode_barang": kode}     # kode cacat: jangan menebak
        it = await db.persediaan.find_one(
            scope_query_field_satker(user, q_kode),
            {"_id": 0, "id": 1}, sort=[("kode_barang", 1)])
        if not it:
            try:
                it = await create_persediaan(PersediaanCreate(
                    kode_barang=kode,
                    nama_barang=str(row.get("uraian") or "Barang persediaan").strip()[:300],
                ), _user=user)
                dibuat_master += 1
            except HTTPException as e:
                gagal.append(f"{row.get('uraian')}: {e.detail}")
                continue
        try:
            await transaksi_masuk(it["id"], TransaksiMasukIn(
                jenis="pembelian", jumlah=jumlah,
                harga_satuan=float(row.get("harga_satuan") or 0),
                no_bukti=str(p.get("nomor_bast") or ""), jenis_dokumen="BAST",
                tgl_dokumen=str(p.get("tanggal_bast") or ""),
                no_kontrak=str(p.get("nomor_kontrak") or ""),
                penyedia=str(p.get("pihak") or ""), perolehan_id=perolehan_id,
                keterangan="Didaftarkan dari perolehan Pengadaan",
            ), user=user)
        except HTTPException as e:
            gagal.append(f"{row.get('uraian')}: {e.detail}")
            continue
        row["psd_item_id"] = it["id"]
        masuk += 1
    if masuk:
        await db.pengadaan.update_one(
            {"id": perolehan_id},
            {"$set": {"barang": barang,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_audit("pengadaan_daftarkan_persediaan", "", perolehan_id,
                    username=user.get("username", "system"),
                    detail=(f"BAST {p.get('nomor_bast') or perolehan_id[:8]}: "
                            f"{masuk} barang masuk persediaan "
                            f"({dibuat_master} master baru)"))
    return {"masuk": masuk, "dibuat_master": dibuat_master,
            "dilewati_bukan_persediaan": dilewati_nonpsd,
            "dilewati_sudah_terdaftar": dilewati_terdaftar,
            "gagal": gagal[:20]}


@pengadaan_router.get("/pengadaan/export")
async def export_pengadaan(_user: dict = Depends(require_user)):
    """Ekspor CSV register perolehan (pola #158)."""
    import csv as csv_module
    import io

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["jenis", "pihak", "nomor_kontrak", "nomor_bast", "tanggal_bast",
                "ppk_nama", "ppk_nip", "ppk_jabatan",
                "jumlah_barang", "nilai", "dokumen_kurang", "penganggaran",
                "nomor_dipa", "keterangan", "jumlah_lampiran", "dibuat_oleh"])
    async for p in db.pengadaan.find(scope_query_field_satker(_user), {"_id": 0}).sort("tanggal_bast", -1):
        w.writerow([
            JENIS_PEROLEHAN.get(p.get("jenis"), (p.get("jenis"),))[0],
            p.get("pihak"), p.get("nomor_kontrak"), p.get("nomor_bast"),
            p.get("tanggal_bast"),
            p.get("ppk_nama"), p.get("ppk_nip"), p.get("ppk_jabatan"),
            len(p.get("barang") or []),
            int(nilai_perolehan(p)),
            "; ".join(dokumen_kurang_perolehan(p)),
            p.get("penganggaran_uraian"), p.get("penganggaran_nomor_dipa"),
            p.get("keterangan"), len(p.get("lampiran_berkas") or []),
            p.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_pengadaan.csv"'})


@pengadaan_router.post("/pengadaan")
async def buat_perolehan(payload: PerolehanIn, user: dict = Depends(require_writer)):
    """Catat perolehan baru (barang boleh ditautkan ke aset master)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    data = payload.model_dump()
    errors = validate_perolehan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    barang_rows = []
    for b in data["barang"]:
        row = {"uraian": b["uraian"].strip(),
               "kode": str(b.get("kode") or "").strip(),
               "jumlah": float(b["jumlah"]),
               "harga_satuan": float(b["harga_satuan"]),
               "asset_id": "", "asset_code": "", "NUP": "", "asset_name": ""}
        aid = str(b.get("asset_id") or "").strip()
        if aid:
            a = await db.assets.find_one(
                {"id": aid}, {**_PROJ_ASET, "activity_id": 1})
            if not a:
                raise HTTPException(status_code=404,
                                    detail=f"Aset {aid} tidak ditemukan")
            # Guard aset (REVIEW-9 R15b): tanpa ini identitas aset satker lain
            # terbaca DAN `_proyeksi_perolehan_ke_aset` menulis back-link
            # perolehan ke dokumen aset mereka — sama persis dengan lubang yang
            # ditutup di `tautkan_barang` di bawah.
            from shared_utils import pastikan_akses_aset as _paa
            await _paa(user, a)
            row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                        "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
        barang_rows.append(row)
    snap = await _ambil_snapshot_penganggaran(data.get("penganggaran_id"), user)
    snap_ppk = await _ambil_snapshot_ppk(
        data.get("ppk_pejabat_id"), data["tanggal_bast"], user)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": kode_satker_user(user),
        "jenis": data["jenis"],
        "pihak": data["pihak"].strip(),
        "nomor_kontrak": str(data.get("nomor_kontrak") or "").strip(),
        "nomor_bast": data["nomor_bast"].strip(),
        "tanggal_bast": data["tanggal_bast"].strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        **snap,
        **snap_ppk,
        # Checklist mulai kosong; BAST & kontrak otomatis tercentang bila
        # nomornya sudah diisi saat pencatatan.
        "dokumen": {"bast": True,
                    **({"kontrak": True} if str(data.get("nomor_kontrak") or "").strip() else {})},
        "barang": barang_rows,
        "lampiran_berkas": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pengadaan.insert_one({**record})
    # Back-link dokumen sumber (§5A gap #6): stamp perolehan_id ke aset tertaut.
    await _proyeksi_perolehan_ke_aset(record)
    return _enrich(record)


@pengadaan_router.put("/pengadaan/{perolehan_id}/dokumen")
async def perbarui_dokumen(perolehan_id: str, payload: DokumenIn,
                           _user: dict = Depends(require_writer)):
    """Perbarui checklist dokumen sumber (kunci di luar daftar diabaikan)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, p)  # isolasi satker (REVIEW-9 R8)
    wajib = set(DOKUMEN_PEROLEHAN.get(p.get("jenis"), ()))
    dokumen = {**(p.get("dokumen") or {}),
               **{k: bool(v) for k, v in payload.dokumen.items() if k in wajib}}
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"dokumen": dokumen, "updated_at": now}})
    p["dokumen"] = dokumen
    return _enrich(p)


@pengadaan_router.post("/pengadaan/{perolehan_id}/tautkan")
async def tautkan_barang(perolehan_id: str, payload: TautkanIn,
                         _user: dict = Depends(require_writer)):
    """Tautkan/lepaskan baris barang ke aset master (cegah entri ganda)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, p)  # isolasi satker (REVIEW-9 R8)
    barang = p.get("barang") or []
    if payload.index >= len(barang):
        raise HTTPException(status_code=400, detail="Baris barang tidak ada")
    row = barang[payload.index]
    prev_aid = str(row.get("asset_id") or "").strip()   # aset lama (lepas back-link)
    aid = str(payload.asset_id or "").strip()
    if aid:
        a = await db.assets.find_one({"id": aid}, {**_PROJ_ASET, "activity_id": 1})
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        # Guard aset (REVIEW-9 R15): register perolehan sudah ber-guard, tetapi
        # ASET yang ditautkan belum — tanpa ini identitas aset satker lain
        # terbaca dan back-link perolehan tertulis ke aset mereka.
        from shared_utils import pastikan_akses_aset as _paa
        await _paa(_user, a)
        row.update({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                    "NUP": a.get("NUP"), "asset_name": a.get("asset_name")})
    else:
        row.update({"asset_id": "", "asset_code": "", "NUP": "",
                    "asset_name": ""})
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id},
        {"$set": {"barang": barang, "updated_at": now}})
    # Back-link dokumen sumber (§5A gap #6): lepas dari aset lama bila berganti,
    # lalu stamp perolehan_id + snapshot ke aset baru.
    if prev_aid and prev_aid != aid:
        await _lepas_perolehan_dari_aset(prev_aid, perolehan_id)
    if aid:
        await db.assets.update_one(
            {"id": aid}, {"$set": build_asset_perolehan_projection(p, now)})
    p["barang"] = barang
    return _enrich(p)


class BuatDraftAsetIn(BaseModel):
    activity_id: str = Field(min_length=1)   # kegiatan tujuan (dipilih saat aksi)


@pengadaan_router.post("/pengadaan/{perolehan_id}/buat-draft-aset")
async def buat_draft_aset_dari_perolehan(perolehan_id: str,
                                         payload: BuatDraftAsetIn,
                                         user: dict = Depends(require_writer)):
    """Buat aset draft dari baris barang perolehan yang BELUM bertaut (evaluasi #5).

    Untuk tiap baris `barang[]` tanpa `asset_id`: buat aset draft di kegiatan
    inventarisasi terpilih lewat jalur create aset yang ada (`buat_aset_draft`
    — registry/keunikan/kunci-kegiatan/audit tetap berlaku), NUP dinomori
    otomatis per (kode, kegiatan), lalu tautkan balik `barang[].asset_id` +
    proyeksi dokumen sumber. Baris tanpa kode barang DILEWATI (isi kode dulu).
    Satu baris = satu aset draft (harga = harga satuan; jumlah BAST dicatat).
    """
    from models import AssetCreate
    from routes.assets import buat_aset_draft

    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)
    act = await db.inventory_activities.find_one(
        {"id": payload.activity_id},
        {"_id": 0, "id": 1, "nama_kegiatan": 1, "kode_satker": 1})
    if not act:
        raise HTTPException(status_code=404,
                            detail="Kegiatan inventarisasi tidak ditemukan")
    # Isolasi satker (REVIEW-9 R8): kegiatan TUJUAN juga wajib milik satker
    # kita — tanpa ini aset draft bisa dijejalkan ke kegiatan satker lain.
    await pastikan_akses_dok_satker(user, act)
    kategori_by_kode = {
        c["kode_aset"]: c.get("label", "")
        async for c in db.categories.find({}, {"_id": 0, "kode_aset": 1, "label": 1})
        if c.get("kode_aset")}

    barang = p.get("barang") or []
    now = datetime.now(timezone.utc).isoformat()
    dibuat, dilewati_tertaut, dilewati_tanpa_kode = 0, 0, 0
    dilewati_persediaan = 0
    aset_dibuat = []      # bahan baris LPB (satu entri = satu NUP nyata)
    gagal = []
    next_nup = {}   # kode → NUP numerik terakhir dalam kegiatan tujuan

    async def _nup_berikut(kode: str) -> str:
        if kode not in next_nup:
            res = await db.assets.aggregate([
                {"$match": {"activity_id": payload.activity_id, "asset_code": kode}},
                {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
                    "input": "$NUP", "to": "int", "onError": None, "onNull": None}}}}},
            ]).to_list(1)
            next_nup[kode] = int((res[0].get("max_nup") if res else None) or 0)
        next_nup[kode] += 1
        return str(next_nup[kode])

    for row in barang:
        if str(row.get("asset_id") or "").strip():
            dilewati_tertaut += 1
            continue
        kode = str(row.get("kode") or "").strip()
        if not kode:
            dilewati_tanpa_kode += 1
            continue
        # BARANG PERSEDIAAN BUKAN ASET TETAP (temuan saat menyatukan dua jalur
        # pencatatan). Dulu jalur ini menerima SEMUA kode: menekan "Daftarkan
        # ke Persediaan" lalu "Buat Draft Aset" atas BAST yang sama membuat
        # satu rim kertas HVS tercatat DUA KALI — sekali di kartu stok, sekali
        # sebagai BMN ber-NUP — dan keduanya berjurnal ke Neraca. Golongan 1
        # kini ditolak di sini, bukan diserahkan pada kedisiplinan operator.
        if is_persediaan(kode) or str(row.get("psd_item_id") or "").strip():
            dilewati_persediaan += 1
            continue
        jumlah = float(row.get("jumlah") or 1)
        # BMN ber-jumlah N = N unit ber-NUP masing-masing (audit G4 #10):
        # pecah jadi N draft ber-NUP berurut bila jumlah bulat 2..50; di luar
        # itu (pecahan/ekstrem) tetap 1 draft + catatan jumlah.
        n_unit = int(jumlah) if jumlah == int(jumlah) and 2 <= jumlah <= 50 else 1
        catatan_jumlah = (f" — jumlah pada BAST: {jumlah:g} unit"
                          if jumlah != 1 and n_unit == 1 else "")
        gagal_baris = False
        for unit_ke in range(1, n_unit + 1):
            sub = (f" (unit {unit_ke}/{n_unit})" if n_unit > 1 else "")
            draft = AssetCreate(
                asset_code=kode,
                NUP=await _nup_berikut(kode),
                asset_name=str(row.get("uraian") or "").strip(),
                category=kategori_by_kode.get(kode, ""),
                purchase_date=str(p.get("tanggal_bast") or "").strip()[:10],
                purchase_price=str(int(round(float(row.get("harga_satuan") or 0)))),
                nomor_bast=str(p.get("nomor_bast") or "").strip(),
                nomor_kontrak=str(p.get("nomor_kontrak") or "").strip(),
                perolehan_dari_nama=str(p.get("pihak") or "").strip(),
                supplier=str(p.get("pihak") or "").strip(),
                notes=(f"Draft otomatis dari perolehan Pengadaan "
                       f"(BAST {p.get('nomor_bast')}){sub}{catatan_jumlah}"),
                activity_id=payload.activity_id,
            )
            try:
                doc = await buat_aset_draft(
                    draft, audit_user=user.get("name") or user.get("username") or "system")
            except HTTPException as e:
                gagal.append(f"{row.get('uraian')}{sub}: {e.detail}")
                gagal_baris = True
                break
            if unit_ke == 1:
                row.update({"asset_id": doc["id"], "asset_code": doc["asset_code"],
                            "NUP": doc["NUP"], "asset_name": doc["asset_name"]})
            # Back-link dokumen sumber (§5A gap #6) ke aset draft yang baru dibuat.
            await db.assets.update_one(
                {"id": doc["id"]}, {"$set": build_asset_perolehan_projection(p, now)})
            # Jurnal Buku Barang (G7): perolehan → kode 101/102/103/105.
            from shared_utils import catat_mutasi_bmn
            kode_trx = str(JENIS_PEROLEHAN.get(p.get("jenis"), ("", "101"))[1]).split("/")[0]
            await catat_mutasi_bmn({
                "asset_id": doc["id"], "kode_transaksi": kode_trx or "101",
                "kode_barang": doc["asset_code"], "nup": str(doc["NUP"]),
                "tanggal_buku": (str(p.get("tanggal_bast") or "").strip()[:10]
                                 or now[:10]),
                "jumlah": 1, "nilai": float(row.get("harga_satuan") or 0),
                "sumber_modul": "pengadaan", "ref_id": perolehan_id,
                "keterangan": f"Draft aset dari BAST {p.get('nomor_bast') or '-'}",
                "oleh": user.get("username", "system")})
            # HANYA field yang dibutuhkan LPB — JANGAN pernah menyalin dokumen
            # aset mentah (temuan audit adversarial). `buat_aset_draft`
            # mengembalikan dict YANG SAMA yang dioper ke `insert_one()`, dan
            # Motor menyisipkan `_id: ObjectId` ke dalamnya IN-PLACE. Dokumen
            # itu ikut jadi nilai balik route; `jsonable_encoder` FastAPI tak
            # bisa membuat serial ObjectId → HTTP 500, padahal aset, back-link,
            # jurnal, dan audit SUDAH tertulis. Uji unit tak menangkapnya karena
            # memanggil handler langsung, melewati lapisan serialisasi.
            #
            # `jumlah_bast` menjaga LPB tetap jujur saat satu draft mewakili
            # SELURUH baris (jumlah > 50 atau pecahan — lihat n_unit di atas).
            aset_dibuat.append({
                "id": doc.get("id"),
                "asset_code": doc.get("asset_code"),
                "NUP": doc.get("NUP"),
                "asset_name": doc.get("asset_name"),
                "harga_satuan": float(row.get("harga_satuan") or 0),
                "jumlah_bast": 1 if n_unit > 1 else jumlah,
            })
            dibuat += 1
        if gagal_baris:
            continue

    if dibuat:
        await db.pengadaan.update_one(
            {"id": perolehan_id},
            {"$set": {"barang": barang,
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
    p["barang"] = barang
    return {"dibuat": dibuat, "dilewati_tertaut": dilewati_tertaut,
            "dilewati_tanpa_kode": dilewati_tanpa_kode,
            "dilewati_persediaan": dilewati_persediaan,
            "aset_dibuat": aset_dibuat, "gagal": gagal[:20],
            "kegiatan": act.get("nama_kegiatan") or act.get("id"),
            "perolehan": _enrich(p)}


class CatatSemuaIn(BaseModel):
    # Kegiatan tujuan draft aset. BOLEH kosong bila BAST-nya persediaan
    # semua — menuntut kegiatan inventarisasi untuk satu rim kertas adalah
    # syarat yang tak ada gunanya (divalidasi di handler, bukan di sini,
    # karena baru diketahui setelah barangnya dipilah).
    activity_id: str = ""
    booking_nomor: bool = True               # terbitkan nomor LPB dari Persuratan


@pengadaan_router.post("/pengadaan/{perolehan_id}/catat-semua")
async def catat_semua_barang(perolehan_id: str, payload: CatatSemuaIn,
                             user: dict = Depends(require_writer)):
    """SATU tombol: seluruh barang BAST masuk ke buku yang benar + LPB terbit.

    Sebelum ini operator harus tahu sendiri bahwa golongan 1 pergi ke
    Persediaan dan golongan 2–8 jadi aset, lalu menekan dua tombol berbeda
    dalam urutan yang benar. Pengetahuan itu tak pernah tertulis di layar mana
    pun — dan menekan keduanya justru MENCATAT GANDA barang persediaan
    (lihat penjaga golongan di `buat_draft_aset_dari_perolehan`).

    Endpoint ini memakai kembali kedua jalur apa adanya — keunikan, penomoran
    NUP, jurnal Buku Barang, dan FIFO persediaan semuanya tetap dijalankan
    oleh pemiliknya masing-masing. Yang baru hanya: pemilahan otomatis, satu
    laporan hasil, dan penerbitan LPB untuk sisi ASET (sisi persediaan sudah
    punya LPB sendiri lewat transaksi massal).

    TIDAK transaksional — Mongo standalone tak menyediakannya, dan jalur massal
    di aplikasi ini memang melaporkan kegagalan per baris apa adanya alih-alih
    berpura-pura semua atau tak sama sekali.
    """
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)

    pilah = pilah_barang_perolehan(p.get("barang") or [])
    hasil_aset = {}
    if pilah["aset"]:
        if not str(payload.activity_id or "").strip():
            raise HTTPException(
                status_code=400,
                detail=(f"BAST ini memuat {len(pilah['aset'])} barang golongan "
                        "aset tetap — pilih kegiatan inventarisasi tujuannya."))
        hasil_aset = await buat_draft_aset_dari_perolehan(
            perolehan_id, BuatDraftAsetIn(activity_id=payload.activity_id),
            user=user)
    hasil_psd = {}
    if pilah["persediaan"]:
        hasil_psd = await daftarkan_persediaan(perolehan_id, user=user)

    # LPB sisi ASET — satu baris per NUP nyata. Inilah bukti terima BMN yang
    # selama ini hanya dipunyai persediaan.
    lpb_id, nomor_lpb = "", ""
    aset_dibuat = hasil_aset.get("aset_dibuat") or []
    if aset_dibuat:
        items = baris_lpb_dari_aset(aset_dibuat)
        tgl = str(p.get("tanggal_bast") or "").strip()[:10] or \
            datetime.now(timezone.utc).date().isoformat()
        surat_id = ""
        if payload.booking_nomor:
            from routes.persuratan import booking_nomor_lpb
            nomor_lpb, surat_id = await booking_nomor_lpb(
                user, tgl,
                perihal=("Laporan Penerimaan Barang (LPB) — BMN "
                         f"{p.get('nomor_bast') or ''}".strip()),
                tujuan=str(p.get("pihak") or "").strip(),
                keterangan=f"booking otomatis dari pencatatan BAST {p.get('nomor_bast') or '-'}")
        lpb_id = str(uuid.uuid4())
        await db.lpb.insert_one({
            "id": lpb_id, "nomor": nomor_lpb, "surat_id": surat_id,
            # Pembeda kolom & judul dokumen: NUP hanya bermakna untuk BMN.
            "kategori": "aset",
            "tanggal": tgl,
            "jenis": p.get("jenis") or "pembelian",
            "jenis_dokumen": "BAST",
            "penyedia": str(p.get("pihak") or "").strip(),
            "perolehan_id": perolehan_id,
            "ppk_nama": str(p.get("ppk_nama") or "").strip(),
            "ppk_nip": str(p.get("ppk_nip") or "").strip(),
            "keterangan": (f"Penerimaan BMN dari BAST "
                           f"{p.get('nomor_bast') or '-'}"),
            "items": items, "total_nilai": total_nilai_lpb(items),
            "jumlah_barang": len(items),
            "kode_satker": kode_satker_user(user),
            "created_by": user.get("username", "system"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    ringkas = ringkas_pencatatan(hasil_aset, hasil_psd,
                                 tanpa_kode=len(pilah["tanpa_kode"]))
    await log_audit("pengadaan_catat_semua", "", perolehan_id,
                    username=user.get("username", "system"),
                    detail=(f"BAST {p.get('nomor_bast') or perolehan_id[:8]}: "
                            f"{ringkas['aset_dibuat']} aset + "
                            f"{ringkas['persediaan_masuk']} persediaan"))
    segar = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    return {**ringkas, "lpb_id": lpb_id, "nomor_lpb": nomor_lpb,
            "baris_tanpa_kode": [i + 1 for i, _ in pilah["tanpa_kode"]],
            "kegiatan": hasil_aset.get("kegiatan", ""),
            "perolehan": _enrich(segar or p)}


@pengadaan_router.put("/pengadaan/{perolehan_id}/ppk")
async def tetapkan_ppk(perolehan_id: str, payload: TetapkanPpkIn,
                       user: dict = Depends(require_writer)):
    """Tetapkan / ganti / kosongkan PPK pada register perolehan.

    Register lama (sebelum field ini ada) tak punya PPK sama sekali; endpoint
    ini jalan untuk melengkapinya tanpa membuat ulang dokumen. Kirim `"auto"`
    agar server mencari sendiri PPK yang berlaku pada tanggal BAST-nya.

    Perubahan diproyeksikan ULANG ke aset yang tertaut — kalau tidak, aset
    yang sudah dicatat akan selamanya menyebut PPK yang sudah diperbaiki.
    """
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)
    pid = str(payload.ppk_pejabat_id or "").strip()
    if pid.lower() == "auto":
        snap_ppk = await _ambil_snapshot_ppk("", p.get("tanggal_bast"), user)
    elif pid:
        snap_ppk = await _ambil_snapshot_ppk(pid, p.get("tanggal_bast"), user)
    else:
        snap_ppk = snapshot_ppk(None)
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id}, {"$set": {**snap_ppk, "updated_at": now}})
    p.update(snap_ppk)
    await _proyeksi_perolehan_ke_aset(p)
    await log_audit("pengadaan_tetapkan_ppk", "", perolehan_id,
                    username=user.get("username", "system"),
                    detail=(f"BAST {p.get('nomor_bast') or perolehan_id[:8]}: "
                            f"PPK → {snap_ppk.get('ppk_nama') or '(dikosongkan)'}"))
    return _enrich(p)


@pengadaan_router.post("/pengadaan/{perolehan_id}/penganggaran")
async def tautkan_penganggaran(perolehan_id: str,
                               payload: TautkanPenganggaranIn,
                               _user: dict = Depends(require_writer)):
    """Tautkan/lepaskan perolehan ke usulan Penganggaran (#117 ↔ #115)."""
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, p)  # isolasi satker (REVIEW-9 R8)
    snap = await _ambil_snapshot_penganggaran(payload.penganggaran_id, _user)
    now = datetime.now(timezone.utc).isoformat()
    await db.pengadaan.update_one(
        {"id": perolehan_id}, {"$set": {**snap, "updated_at": now}})
    p.update(snap)
    return _enrich(p)


# Lampiran berkas per perolehan (scan kontrak/BAPHP/BAST/kuitansi/SP2D
# — melengkapi checklist dokumen sumber). Pola sama dengan #131/#132/#134.
_LAMPIRAN_MEDIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
_MAX_LAMPIRAN_BYTES = 10 * 1024 * 1024
_MAX_LAMPIRAN = 10


def _lampiran_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _LAMPIRAN_MEDIA:
        if name.endswith(ext):
            return ext
    return ""


@pengadaan_router.post("/pengadaan/{perolehan_id}/lampiran")
async def unggah_lampiran_perolehan(perolehan_id: str,
                                    file: UploadFile = File(...),
                                    user: dict = Depends(require_writer)):
    """Unggah scan dokumen sumber (PDF/gambar, maks 10MB, 10 berkas)."""
    p = await db.pengadaan.find_one(
        {"id": perolehan_id},
        {"_id": 0, "id": 1, "lampiran_berkas": 1, "kode_satker": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    if len(p.get("lampiran_berkas") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per perolehan")
    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    ext = _lampiran_ext(filename)
    if not ext:
        raise HTTPException(status_code=400,
                            detail="Lampiran harus PDF atau gambar (JPG/PNG/WEBP)")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > _MAX_LAMPIRAN_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran lampiran maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    from bson import ObjectId
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=filename,
        metadata={"content_type": _LAMPIRAN_MEDIA[ext], "size": len(file_bytes),
                  "kind": "pengadaan", "perolehan_id": perolehan_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pengadaan.find_one_and_update(
        {"id": perolehan_id},
        {"$push": {"lampiran_berkas": entri},
         "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran_berkas": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    return {"message": "Lampiran terunggah",
            "lampiran_berkas": res.get("lampiran_berkas") or []}


@pengadaan_router.get("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def unduh_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   request: Request,
                                   _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran perolehan (menerima header ATAU ?token)."""
    p = await db.pengadaan.find_one(
        scope_query_field_satker(
            _user, {"id": perolehan_id, "lampiran_berkas.file_id": file_id}),
        {"_id": 0, "lampiran_berkas.$": 1})
    if not p or not p.get("lampiran_berkas"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = p["lampiran_berkas"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "dokumen"}"'})


@pengadaan_router.delete("/pengadaan/{perolehan_id}/lampiran/{file_id}")
async def hapus_lampiran_perolehan(perolehan_id: str, file_id: str,
                                   _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pengadaan.update_one(
        scope_query_field_satker(_admin, {"id": perolehan_id}),
        {"$pull": {"lampiran_berkas": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pengadaan_router.delete("/pengadaan/{perolehan_id}")
async def hapus_perolehan(perolehan_id: str,
                          _admin: dict = Depends(require_admin)):
    """Hapus register perolehan salah input (admin) + berkas lampirannya.

    Back-link `perolehan_id`/snapshot di aset tertaut DILEPAS dulu (temuan
    review #11 — dulu menggantung menunjuk perolehan yang sudah tidak ada).
    """
    p = await db.pengadaan.find_one(
        {"id": perolehan_id},
        {"_id": 0, "kode_satker": 1, "lampiran_berkas": 1, "barang": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_admin, p)  # 403 bila register milik satker lain
    res = await db.pengadaan.delete_one({"id": perolehan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    for b in (p or {}).get("barang") or []:
        if b.get("asset_id"):
            await _lepas_perolehan_dari_aset(b["asset_id"], perolehan_id)
    for lamp in (p or {}).get("lampiran_berkas") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": perolehan_id}
