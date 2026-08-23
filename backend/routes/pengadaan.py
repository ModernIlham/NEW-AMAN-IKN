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
from pydantic import BaseModel, Field, field_validator

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from lpb_utils import (
    baris_lpb_dari_aset, baris_lpb_gabungan, is_persediaan, label_golongan,
    pilah_barang_perolehan, ringkas_pencatatan, total_nilai_lpb,
)
from persediaan_utils import KODE_PENUH_LEN, KODE_PREFIX_LEN
from db import db
from shared_utils import kode_satker_user, scope_query_field_satker, pastikan_akses_dok_satker, delete_document_from_gridfs, get_document_from_gridfs, log_audit
from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    build_asset_perolehan_projection, dokumen_kurang_perolehan,
    is_ekstrakomptabel, kunci_ubah_perolehan, nilai_perolehan, rekap_perolehan,
    snapshot_penganggaran, snapshot_ppk, validate_perolehan,
)
from pengadaan_dokumen import (
    baris_dokumen, bersihkan_dokumen, validate_dokumen,
)
from penandatangan_dokumen import (
    bersihkan_penandatangan, validate_penandatangan,
)

pengadaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


class BarangIn(BaseModel):
    uraian: str = Field(min_length=1)
    kode: str = ""                     # kode barang (opsional, utk ambang)
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)
    asset_id: str = ""                 # tautan ke aset master (opsional)

    @field_validator("jumlah", "harga_satuan")
    @classmethod
    def _terhingga(cls, v):
        # Token JSON `Infinity`/`NaN` di-parse Starlette menjadi float('inf')/
        # nan dan LOLOS gt/ge — lalu meracuni register: ekspor CSV & jurlah
        # nilai jadi tak terhitung, PDF 500, catat-semua setengah jalan. Tolak
        # nilai tak-hingga di gerbang.
        import math
        if not math.isfinite(v):
            raise ValueError("harus angka terhingga (Infinity/NaN ditolak)")
        return v


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
    # Dokumen pengadaan yang melekat pada register ini. `sifat` menentukan
    # kolom mana yang berlaku — SP/SPK milik jalur kontrak, UP/TUP & SPBy
    # milik jalur uang persediaan, dan keduanya TIDAK bertukar (lihat
    # pengadaan_dokumen.py). Kosong = belum ditetapkan; register lama tak
    # pernah dianggap bertentangan.
    sifat: str = ""
    no_sp_spk: str = ""
    jenis_up: str = ""
    no_spby: str = ""
    no_spp: str = ""
    no_spm: str = ""
    no_dokumen: str = ""
    barang: list[BarangIn] = Field(min_length=1, max_length=100)


class BarangUbahIn(BaseModel):
    """Baris barang saat register DIUBAH — tanpa `asset_id`, sengaja.

    Penautan ke aset master punya jalurnya sendiri (`POST .../tautkan`) yang
    memeriksa hak akses aset, dan daftar barang hanya boleh diubah selagi belum
    ada satu pun baris tertaut. Menerima `asset_id` di sini hanya akan menjadi
    pintu belakang yang melewati pemeriksaan itu.
    """
    uraian: str = Field(min_length=1)
    kode: str = ""
    jumlah: float = Field(gt=0)
    harga_satuan: float = Field(ge=0)

    @field_validator("jumlah", "harga_satuan")
    @classmethod
    def _terhingga(cls, v):
        import math
        if not math.isfinite(v):
            raise ValueError("harus angka terhingga (Infinity/NaN ditolak)")
        return v


class PerolehanUbahIn(BaseModel):
    """Perbaikan register perolehan.

    `penganggaran_id`/`ppk_pejabat_id` sengaja TIDAK di sini: keduanya punya
    endpoint sendiri yang menulis snapshot beku, dan menerimanya di sini
    membuat form ubah tanpa sadar mengosongkan PPK yang sudah ditetapkan.

    `barang = null` berarti "jangan sentuh daftar barang" — itulah yang dikirim
    klien saat daftarnya terkunci.
    """
    jenis: str
    pihak: str = Field(min_length=1)
    nomor_kontrak: str = ""
    nomor_bast: str = Field(min_length=1)
    tanggal_bast: str = Field(min_length=10, max_length=10)
    keterangan: str = ""
    # Dokumen pengadaan yang melekat pada register ini. `sifat` menentukan
    # kolom mana yang berlaku — SP/SPK milik jalur kontrak, UP/TUP & SPBy
    # milik jalur uang persediaan, dan keduanya TIDAK bertukar (lihat
    # pengadaan_dokumen.py). Kosong = belum ditetapkan; register lama tak
    # pernah dianggap bertentangan.
    sifat: str = ""
    no_sp_spk: str = ""
    jenis_up: str = ""
    no_spby: str = ""
    no_spp: str = ""
    no_spm: str = ""
    no_dokumen: str = ""
    barang: list[BarangUbahIn] | None = Field(default=None, max_length=100)


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
    # Status "sejauh mana masih boleh diubah" dihitung SEKALI untuk seluruh
    # halaman: satu query LPB untuk semua id, bukan satu query per baris.
    # Tanpa ini, register 500 baris = 500 round-trip hanya untuk menentukan
    # tombol ubah aktif atau tidak.
    ids = [p["id"] for p in items]
    tertunjuk_lpb = set()
    if ids:
        async for l in db.lpb.find(
                {"$or": [{"perolehan_id": {"$in": ids}},
                         {"perolehan_ids": {"$in": ids}}]},
                {"_id": 0, "perolehan_id": 1, "perolehan_ids": 1}):
            if l.get("perolehan_id"):
                tertunjuk_lpb.add(l["perolehan_id"])
            tertunjuk_lpb.update(l.get("perolehan_ids") or [])
    for p in items:
        p["ubah"] = kunci_ubah_perolehan(p, p["id"] in tertunjuk_lpb)
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
    for idx_baris, row in enumerate(barang):
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
        jumlah_asli = float(row.get("jumlah") or 0)
        # Stok persediaan hanya menerima BILANGAN BULAT POSITIF. Dulu kode
        # memaksa `max(1, int(jumlah_asli))` LALU tetap memposting: 2,5 →
        # tercatat 2 (0,5 lenyap), 0,5 → dibulatkan NAIK jadi 1 (mengarang
        # stok) — dan pesan "dibulatkan ke bawah" bahkan salah untuk kasus
        # naik. Angka yang diposting jadi tak cocok dengan register/LPB.
        # Kini baris pecahan/nol DILEWATI (tidak diposting) dan dilaporkan
        # sebagai gagal sungguhan; operator memecah baris atau mengubah satuan.
        if jumlah_asli <= 0 or not float(jumlah_asli).is_integer():
            gagal.append(
                f"{row.get('uraian')}: jumlah {jumlah_asli:g} bukan bilangan "
                "bulat positif — stok persediaan hanya menerima bilangan bulat. "
                "Baris DILEWATI (tak dicatat); pecah barisnya atau ubah satuannya.")
            continue
        jumlah = int(jumlah_asli)
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
        # Penanda "sudah masuk stok" dipersist SEGERA per baris — bukan sekali
        # di akhir loop. Dulu seluruh array `barang` baru ditulis setelah loop
        # selesai; bila proses mati / permintaan diulang di tengah, transaksi
        # persediaan yang SUDAH terposting tak punya `psd_item_id` di DB,
        # sehingga jalankan-ulang mempostingnya LAGI → stok dobel. Update
        # posisional per-baris membuat tiap baris yang sukses langsung
        # ber-penanda dan dilewati pada pengulangan (guard di atas).
        row["psd_item_id"] = it["id"]
        await db.pengadaan.update_one(
            {"id": perolehan_id},
            {"$set": {f"barang.{idx_baris}.psd_item_id": it["id"],
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        masuk += 1
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
    # Hari-ini dalam WIB, bukan UTC: batas "tanggal BAST tak boleh di masa
    # depan" dulu memakai tanggal UTC yang TERTINGGAL 7 jam dari WIB — sehingga
    # tiap pagi pukul 00:00–06:59 WIB, BAST bertanggal hari ini (WIB) ditolak
    # keliru sebagai "masa depan". Register lain (persediaan) sudah memakai
    # today_wib; disamakan di sini.
    from persediaan_utils import today_wib
    today_iso = today_wib()
    data = payload.model_dump()
    errors = (validate_perolehan(data, today_iso)
              + validate_dokumen(data.get("sifat"), data))
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
        "sifat": str(data.get("sifat") or "").strip(),
        **bersihkan_dokumen(data),
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


async def _ada_lpb_menunjuk(perolehan_id: str) -> bool:
    """Adakah LPB yang menunjuk register ini (tunggal maupun gabungan)?"""
    return bool(await db.lpb.find_one(
        {"$or": [{"perolehan_id": perolehan_id},
                 {"perolehan_ids": perolehan_id}]}, {"_id": 0, "id": 1}))


@pengadaan_router.put("/pengadaan/{perolehan_id}")
async def ubah_perolehan(perolehan_id: str, payload: PerolehanUbahIn,
                         user: dict = Depends(require_writer)):
    """Perbaiki register perolehan yang salah input.

    Sebelum ini satu-satunya jalan memperbaiki salah ketik nomor BAST atau
    harga satuan adalah **menghapus lalu mencatat ulang** — dan penjaga hapus
    justru menolak begitu barangnya sudah tercatat, sehingga registernya
    terkunci salah selamanya.

    Seberapa jauh boleh diubah ditentukan `kunci_ubah_perolehan` (lihat
    docstring-nya). Yang terkunci ditolak **dengan 409 dan alasannya**, bukan
    diterima lalu diabaikan diam-diam: klien harus tahu bahwa yang diketiknya
    tidak tersimpan.
    """
    from persediaan_utils import today_wib
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)

    kunci = kunci_ubah_perolehan(p, await _ada_lpb_menunjuk(perolehan_id))
    data = payload.model_dump()

    # 1. Daftar barang — null berarti "biarkan apa adanya".
    if data.get("barang") is None:
        barang_rows = p.get("barang") or []
    elif not kunci["barang"]:
        raise HTTPException(status_code=409, detail=kunci["alasan"])
    else:
        # Semua baris masih bebas (kunci["barang"] True berarti tak satu pun
        # tertaut aset/persediaan), jadi daftarnya disusun ulang utuh — tak ada
        # tautan yang bisa hilang karenanya.
        barang_rows = [{"uraian": b["uraian"].strip(),
                        "kode": str(b.get("kode") or "").strip(),
                        "jumlah": float(b["jumlah"]),
                        "harga_satuan": float(b["harga_satuan"]),
                        "asset_id": "", "asset_code": "", "NUP": "",
                        "asset_name": ""}
                       for b in data["barang"]]

    # 2. Identitas dokumen — dibandingkan, bukan dipercaya. Klien lama yang
    #    tidak tahu kunci ini tetap tak bisa menembusnya.
    if not kunci["identitas"]:
        berubah = [f for f in ("jenis", "pihak", "nomor_kontrak", "nomor_bast",
                               "tanggal_bast")
                   if str(data.get(f) or "").strip() != str(p.get(f) or "").strip()]
        if berubah:
            raise HTTPException(status_code=409, detail=(
                f"{kunci['alasan']} (yang ditolak: {', '.join(berubah)})"))

    errors = (validate_perolehan({**data, "barang": barang_rows}, today_wib())
              + validate_dokumen(data.get("sifat"), data))
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    now = datetime.now(timezone.utc).isoformat()
    ubah = {
        "jenis": data["jenis"],
        "pihak": data["pihak"].strip(),
        "nomor_kontrak": str(data.get("nomor_kontrak") or "").strip(),
        "sifat": str(data.get("sifat") or "").strip(),
        **bersihkan_dokumen(data),
        "nomor_bast": data["nomor_bast"].strip(),
        "tanggal_bast": data["tanggal_bast"].strip()[:10],
        "keterangan": str(data.get("keterangan") or "").strip(),
        "barang": barang_rows,
        "updated_at": now,
        "updated_by": user.get("username"),
    }
    # Checklist dokumen sengaja TIDAK ikut disentuh: ia menyatakan "berkasnya
    # ada di tangan", dan itu tidak berubah hanya karena nomornya diperbaiki.
    perubahan = [{"field": f, "from": str(p.get(f) or ""), "to": str(ubah[f] or "")}
                 for f in ("jenis", "pihak", "nomor_kontrak", "nomor_bast",
                           "tanggal_bast", "keterangan")
                 if str(p.get(f) or "") != str(ubah[f] or "")]
    nilai_lama, nilai_baru = nilai_perolehan(p), nilai_perolehan(ubah)
    if nilai_lama != nilai_baru or len(p.get("barang") or []) != len(barang_rows):
        perubahan.append({"field": "barang",
                          "from": f"{len(p.get('barang') or [])} baris · {nilai_lama:.0f}",
                          "to": f"{len(barang_rows)} baris · {nilai_baru:.0f}"})
    if not perubahan:
        return _enrich({**p, "ubah": kunci})   # tak ada yang berubah — jangan mengotori jejak audit

    await db.pengadaan.update_one({"id": perolehan_id}, {"$set": ubah})
    p.update(ubah)
    # Snapshot perolehan yang menempel di aset tertaut ikut disegarkan, kalau
    # tidak identitas dokumen di kartu aset tetap menyebut nomor BAST lama.
    await _proyeksi_perolehan_ke_aset(p)
    await log_audit("pengadaan_ubah", "", perolehan_id,
                    username=user.get("username", "system"),
                    changes=perubahan,
                    detail=(f"Register perolehan {p.get('nomor_bast') or perolehan_id[:8]} "
                            f"diubah ({len(perubahan)} field)"))
    p["ubah"] = kunci_ubah_perolehan(p, await _ada_lpb_menunjuk(perolehan_id))
    return _enrich(p)


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
        # PINTU MANUAL KE PENCATATAN GANDA. Jalur otomatis
        # (`buat_draft_aset_dari_perolehan` / `catat-semua`) sudah dijaga penjaga
        # golongan, tetapi tombol "Tautkan" di layar tidak — dan ia menulis ke
        # baris yang sama. Satu rim kertas HVS bisa berdiri di kartu stok DAN
        # sebagai BMN ber-NUP sekaligus, keduanya berjurnal ke Neraca.
        # Melepas tautan (`asset_id` kosong) tetap boleh: data lama yang telanjur
        # salah harus bisa dibetulkan.
        if str(row.get("psd_item_id") or "").strip():
            raise HTTPException(
                status_code=400,
                detail=("Baris ini sudah tercatat sebagai persediaan (kartu "
                        "stok). Menautkannya ke aset membuat barang yang sama "
                        "terhitung dua kali di Neraca."))
        if is_persediaan(row.get("kode")):
            raise HTTPException(
                status_code=400,
                detail=(f"Kode {str(row.get('kode') or '').strip()} bergolongan 1 "
                        "= barang persediaan, bukan aset tetap. Catat lewat "
                        "\"Catat Semua Barang\" agar masuk ke kartu stok."))
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
    # Kode klasifikasi arsip PILIHAN OPERATOR untuk dokumen ini.
    #
    # Keluhan pemilik: *"ketika buat BAST dan klik nomor otomatis dari
    # registrasi persuratan, bagian klasifikasi arsip tidak ada dan tidak ada
    # pilihan memilih klasifikasi arsip yang ada"*. Memang: jalur otomatis
    # lintas modul hanya pernah punya SATU sumber kode — aturan pemetaan
    # (modul + jenis naskah). Tak ada aturan yang cocok berarti slot
    # {kode_klasifikasi} pada nomor terbit KOSONG, tanpa satu pun galat, dan
    # tanpa cara memperbaikinya dari layar tempat dokumennya dibuat.
    kode_klasifikasi: str = ""



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
        # Satker DOKUMEN dibekukan dari perolehannya, bukan dari pemanggil:
        # super-admin yang mencatat BAST satker lain tak boleh menstempel LPB
        # & nomor suratnya "" (yang membuatnya tampil di SEMUA satker) —
        # pola sama dengan bast.py yang memakai kode_satker milik dokumen.
        ks_dok = str(p.get("kode_satker") or "").strip() or kode_satker_user(user)
        surat_id = ""
        if payload.booking_nomor:
            from routes.persuratan import booking_nomor_lpb
            nomor_lpb, surat_id = await booking_nomor_lpb(
                user, tgl,
                perihal=("Laporan Penerimaan Barang (LPB) — BMN "
                         f"{p.get('nomor_bast') or ''}".strip()),
                tujuan=str(p.get("pihak") or "").strip(),
                keterangan=f"booking otomatis dari pencatatan BAST {p.get('nomor_bast') or '-'}",
                kode_satker=ks_dok,
                kode_klasifikasi=payload.kode_klasifikasi)
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
            # Status ikut disalin: `_baris_nip_ppk` di LPB memakainya untuk
            # menegakkan aturan privasi Non-ASN. Tanpa ini NIP tercetak mentah.
            "ppk_status_kepegawaian": str(p.get("ppk_status_kepegawaian") or "").strip(),
            "keterangan": (f"Penerimaan BMN dari BAST "
                           f"{p.get('nomor_bast') or '-'}"),
            "items": items, "total_nilai": total_nilai_lpb(items),
            "jumlah_barang": len(items),
            "kode_satker": ks_dok,
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


# ============================================================================
# BAST PPK → KPB — serah terima LANJUTAN hasil pengadaan.
#
# Rantainya dua tahap: (1) Penyedia menyerahkan kepada PPK — BAST-nya dibuat
# dan dinomori PPK sendiri, register ini hanya MENCATAT nomornya (field
# `nomor_bast`); (2) PPK menyerahkan hasil pengadaan itu kepada Kuasa
# Pengguna Barang untuk ditatausahakan sebagai BMN — dokumen tahap kedua
# inilah yang DITERBITKAN aplikasi: nomor Berita Acara dipesan dari
# Persuratan (deret yang sama dengan generator BAST modul Penggunaan) dan
# PDF resminya dirender dari snapshot yang dibekukan saat terbit.
# ============================================================================

# Dasar hukum naskah BAST hasil pengadaan (rezim pengadaan + penatausahaan,
# BUKAN rezim penggunaan yang dipakai bast.py — dokumen ini lahir dari
# Perpres 16/2018, bukan PMK 40/2024).
_DASAR_BAST_PPK = (
    "Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;",
    "Peraturan Pemerintah Nomor 27 Tahun 2014 tentang Pengelolaan Barang "
    "Milik Negara/Daerah jo. PP Nomor 28 Tahun 2020;",
    "Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa "
    "Pemerintah jo. Perpres Nomor 46 Tahun 2025;",
    "Peraturan Menteri Keuangan Nomor 181/PMK.06/2016 tentang Penatausahaan "
    "Barang Milik Negara;",
    "Peraturan Menteri Keuangan Nomor 53 Tahun 2023 tentang Pengelolaan "
    "Barang Milik Negara dan Aset Dalam Penguasaan di Ibu Kota Nusantara.",
)


def _tgl_iso_atau_hari_ini(v: str) -> str:
    """Tanggal ISO tervalidasi; kosong/cacat → hari ini (bukan 400 — tombol
    satu-klik tak menyediakan input tanggal, jadi cacat berarti bug klien)."""
    from datetime import date
    s = str(v or "").strip()[:10]
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).date().isoformat()


class BastPpkIn(BaseModel):
    tanggal: str = ""                  # default hari ini (YYYY-MM-DD)
    booking_nomor: bool = True         # pesan nomor Berita Acara (Persuratan)
    # Kode klasifikasi arsip PILIHAN OPERATOR untuk dokumen ini.
    #
    # Keluhan pemilik: *"ketika buat BAST dan klik nomor otomatis dari
    # registrasi persuratan, bagian klasifikasi arsip tidak ada dan tidak ada
    # pilihan memilih klasifikasi arsip yang ada"*. Memang: jalur otomatis
    # lintas modul hanya pernah punya SATU sumber kode — aturan pemetaan
    # (modul + jenis naskah). Tak ada aturan yang cocok berarti slot
    # {kode_klasifikasi} pada nomor terbit KOSONG, tanpa satu pun galat, dan
    # tanpa cara memperbaikinya dari layar tempat dokumennya dibuat.
    kode_klasifikasi: str = ""



@pengadaan_router.post("/pengadaan/{perolehan_id}/bast-ppk-kpb")
async def terbitkan_bast_ppk_kpb(perolehan_id: str, payload: BastPpkIn,
                                 user: dict = Depends(require_writer)):
    """Terbitkan BAST PPK → KPB untuk satu perolehan (idempoten).

    Identitas kedua pihak DIBEKUKAN saat terbit: PIHAK KESATU dari snapshot
    PPK perolehan (bukan registry hari ini), PIHAK KEDUA dari resolver KPB
    pada tanggal dokumen. Klik kedua mengembalikan rekaman yang sudah ada —
    nomor Berita Acara tak boleh terpesan dua kali untuk dokumen yang sama.
    """
    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)  # isolasi satker (REVIEW-9 R8)
    lama = p.get("bast_ppk") or {}
    if lama:
        return {"bast_ppk": lama, "sudah_ada": True}
    if not str(p.get("ppk_nama") or "").strip():
        raise HTTPException(status_code=400, detail=(
            "PPK belum ditetapkan pada perolehan ini — PIHAK KESATU dokumen "
            "adalah PPK. Ketuk baris PPK pada register untuk mengisinya dari "
            "Referensi Pejabat, lalu coba lagi."))

    from shared_utils import resolve_penandatangan_kpb
    tgl = _tgl_iso_atau_hari_ini(payload.tanggal)
    settings = await db.report_settings.find_one(
        {"type": "global"}, {"_id": 0}) or {}
    kode = str(p.get("kode_satker") or "").strip() or kode_satker_user(user)
    kpb = await resolve_penandatangan_kpb(settings, per_iso=tgl,
                                          kode_satker=kode) or {}
    if not str(kpb.get("nama") or "").strip():
        raise HTTPException(status_code=400, detail=(
            "Kuasa Pengguna Barang belum terdaftar — isi peran KPB di "
            "Referensi Pejabat (atau nama Kasatker di Pengaturan Laporan) "
            "supaya PIHAK KEDUA dokumen ini punya identitas."))

    now = datetime.now(timezone.utc)
    nomor, surat_id = "", ""
    if payload.booking_nomor:
        # Deret nomor yang SAMA dengan generator BAST Penggunaan (bast.py):
        # buku agenda keluar per satker + PER PERIODE (bulanan/tahunan sesuai
        # setelan) — jalur otomatis sedertan dengan booking manual.
        from persuratan_utils import bangun_nomor, periode_urut, pilih_klasifikasi
        from routes.persuratan import _no_agenda_berikut, _pengaturan
        atur = await _pengaturan(kode)
        kode_klas = pilih_klasifikasi(
            atur["peta_klasifikasi"], "pengadaan", "Berita Acara",
            eksplisit=payload.kode_klasifikasi)
        tahun = int(tgl[:4]) if tgl[:4].isdigit() else now.year
        periode = (periode_urut(atur.get("reset_urut"), tgl)
                   or periode_urut(atur.get("reset_urut"),
                                   now.date().isoformat()))
        no_agenda = await _no_agenda_berikut("keluar", periode, kode)
        nomor = bangun_nomor(atur["format_nomor"], no_agenda, tgl,
                             kode_klasifikasi=kode_klas,
                             kode_unit=atur["kode_unit"],
                             kode_bawaan=atur["kode_klasifikasi_default"])
        surat_id = str(uuid.uuid4())
        await db.surat.insert_one({
            "id": surat_id, "jenis": "keluar", "no_agenda": no_agenda,
            "sisipan": 0,
            "tahun": tahun, "nomor": nomor, "status": "dibooking",
            "kode_satker": kode,
            "perihal": ("BAST Hasil Pengadaan PPK-KPB — "
                        f"{p.get('nomor_bast') or perolehan_id[:8]}"),
            "tujuan": str(kpb.get("nama") or "").strip(),
            "jenis_naskah": "Berita Acara", "modul": "pengadaan",
            "kegiatan_id": "", "nama_kegiatan": "",
            "kode_klasifikasi": kode_klas, "kode_keamanan": "B",
            "tanggal_surat": tgl, "referensi": "BAST PPK-KPB",
            "nomor_eksternal": "",
            "keterangan": "booking otomatis dari BAST PPK-KPB",
            "dibuat_oleh": user.get("username", "system"),
            "riwayat": [{"status": "dibooking", "tanggal": now.isoformat(),
                         "oleh": user.get("username", "system"),
                         "catatan": "booking otomatis dari BAST PPK-KPB"}],
            "created_at": now.isoformat(), "updated_at": now.isoformat(),
        })

    rekaman = {
        "nomor": nomor, "surat_id": surat_id, "tanggal": tgl,
        # Snapshot KPB dibekukan DI SINI: dokumen historis tak boleh berganti
        # penanda tangan hanya karena registry pejabat berubah kemudian.
        "kpb_nama": str(kpb.get("nama") or "").strip(),
        "kpb_nip": str(kpb.get("nip") or "").strip(),
        # Kapasitas mengikuti kop dokumen: pada BAST PPK→KPB ia menerima
        # SEBAGAI Kuasa Pengguna Barang — jabatan strukturalnya disimpan
        # terpisah untuk arsip, tidak dicetak sebagai jabatan penandatangan.
        "kpb_jabatan": "Kuasa Pengguna Barang",
        "kpb_jabatan_struktural": str(kpb.get("jabatan") or "").strip(),
        "kpb_status_kepegawaian": str(kpb.get("status_kepegawaian") or "").strip(),
        "kpb_jenis_pelaksana": str(kpb.get("jenis_pelaksana") or "").strip(),
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
    }
    # Filter "$exists: False" menutup celah klik-ganda di antara pemeriksaan
    # `lama` di atas dan tulisan ini: yang kalah balapan TIDAK menimpa rekaman
    # pemenang (nomor booking-nya sendiri dibiarkan berstatus dibooking di
    # buku agenda — nomor memang tak pernah dipakai ulang).
    res = await db.pengadaan.update_one(
        {"id": perolehan_id, "bast_ppk": {"$exists": False}},
        {"$set": {"bast_ppk": rekaman, "updated_at": now.isoformat()}})
    if not res.modified_count:
        segar = await db.pengadaan.find_one(
            {"id": perolehan_id}, {"_id": 0, "bast_ppk": 1}) or {}
        return {"bast_ppk": segar.get("bast_ppk") or rekaman, "sudah_ada": True}
    await log_audit("pengadaan_bast_ppk_terbit", "", perolehan_id,
                    username=user.get("username", "system"),
                    detail=(f"BAST PPK-KPB {nomor or '(tanpa nomor)'} untuk "
                            f"BAST {p.get('nomor_bast') or perolehan_id[:8]}"))
    return {"bast_ppk": rekaman, "sudah_ada": False}


async def bangun_bast_ppk_pdf(perolehan_id: str, _user: dict) -> bytes:
    """Susun PDF BAST PPK → KPB → bytes (naskah resmi ber-pasal, pola
    bast.py). Dipisah dari route-nya mengikuti `bangun_lpb_pdf` supaya jalur
    TTD elektronik kelak bisa membekukan berkas yang sama persis."""
    import asyncio
    from io import BytesIO
    from xml.sax.saxutils import escape as _esc

    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import (
        KeepTogether, Paragraph, Spacer, Table, TableStyle,
    )

    from pegawai_utils import (
        baris_identitas_ttd, deteksi_identitas, label_nomor_identitas,
    )
    from pejabat_utils import prefiks_pelaksana
    from pelaporan_utils import narasi_hari_tanggal
    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _tempat_tanggal_laporan, _title_block,
    )
    from shared_utils import pengaturan_kop

    p = await db.pengadaan.find_one({"id": perolehan_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, p)  # isolasi satker (REVIEW-9 R8)
    bp = p.get("bast_ppk") or {}
    if not bp:
        raise HTTPException(status_code=400, detail=(
            "BAST PPK-KPB belum diterbitkan untuk perolehan ini — tekan "
            "tombol \"BAST PPK → KPB\" pada barisnya dulu."))
    settings = await pengaturan_kop(kode_satker=p.get("kode_satker"))

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    body = st['Body']
    # Gaya naskah resmi yang sama dengan bast.py: isi pasal hitam rata
    # kiri-kanan, judul pasal tebal-tengah.
    isi = ParagraphStyle('BastPpkIsi', parent=body, fontSize=8.6, leading=11.6,
                         alignment=TA_JUSTIFY, textColor=HexColor("#111827"),
                         spaceAfter=1.5)
    lbl_pasal = ParagraphStyle('BastPpkPasal', parent=body, fontSize=9,
                               leading=11.5, alignment=TA_CENTER,
                               spaceBefore=5, spaceAfter=2.5,
                               textColor=HexColor("#111827"))
    ket = ParagraphStyle('BastPpkKet', parent=isi, fontSize=8.2, leading=10.8)
    _garis = HexColor("#9aa5b1")

    def fmt_rp(v):
        try:
            return f"{int(round(float(v))):,}".replace(",", ".")
        except (ValueError, TypeError):
            return "0"

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block(
        "BERITA ACARA SERAH TERIMA HASIL PENGADAAN\n"
        "DARI PEJABAT PEMBUAT KOMITMEN KEPADA KUASA PENGGUNA BARANG",
        nomor=bp.get("nomor") or "......./......./........"))

    nar = narasi_hari_tanggal(bp.get("tanggal"))
    tempat = str(settings.get("tempat_laporan")
                 or settings.get("alamat_instansi") or "").strip()
    frasa = (f"Pada hari ini, {nar['hari']}, tanggal {nar['tanggal_terbilang']}, "
             f"bulan {nar['bulan']}, tahun {nar['tahun_terbilang']} "
             f"({_fmt_tanggal_id(bp.get('tanggal'))})" if nar else "Pada hari ini")
    if tempat:
        frasa += f", bertempat di {_esc(tempat.splitlines()[0])}"
    el.append(Paragraph(f"{frasa}, kami yang bertanda tangan di bawah ini:", isi))
    el.append(Spacer(1, 1.5 * rl_mm))

    p1 = {"nama": p.get("ppk_nama"), "nip": p.get("ppk_nip"),
          "jabatan": p.get("ppk_jabatan") or "Pejabat Pembuat Komitmen"}
    # Jabatan dicetak = KAPASITAS dokumen ("Kuasa Pengguna Barang" ber-awalan
    # Plt./Plh.), bukan snapshot jabatan struktural — BAST lama yang terlanjur
    # menyimpan "Direktur ..." di kpb_jabatan ikut ternormalkan saat render.
    p2 = {"nama": bp.get("kpb_nama"), "nip": bp.get("kpb_nip"),
          "jabatan": (prefiks_pelaksana(bp.get("kpb_jenis_pelaksana"))
                      + "Kuasa Pengguna Barang")}

    def _kolom_pihak(peran, sebutan, ph):
        """Identitas satu pihak (pola bast.py, tanpa alamat): NIK Non-ASN
        tidak dicetak (privasi); label nomor pintar (NIP/NRP)."""
        nomor_id = str(ph.get("nip") or "").strip()
        det = deteksi_identitas(nomor_id)
        pasangan = [("Nama", ph.get("nama"))]
        if det["jenis"] != "nik" and nomor_id:
            # Label netral bila formatnya tak dikenal — bukan tebakan "NIP".
            pasangan.append((label_nomor_identitas(nomor_id) or det["label"],
                             nomor_id))
        pasangan.append(("Jabatan", ph.get("jabatan")))
        rows = [[Paragraph(lbl, ket),
                 Paragraph(f": <b>{_esc(str(val or '-'))}</b>", ket)]
                for lbl, val in pasangan]
        dalam = Table(rows, colWidths=[46, doc.width * 0.5 - 46 - 14])
        dalam.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5)]))
        return [Paragraph(f"<b>{peran}</b>", ket), dalam,
                Paragraph(f"<i>— selanjutnya disebut <b>{sebutan}</b> —</i>",
                          ket)]

    tp = Table([[
        _kolom_pihak("PIHAK KESATU (yang menyerahkan)", "PIHAK KESATU", p1),
        _kolom_pihak("PIHAK KEDUA (yang menerima)", "PIHAK KEDUA", p2),
    ]], colWidths=[doc.width * 0.5, doc.width * 0.5])
    tp.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('LEFTPADDING', (1, 0), (1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.4, _garis),
        ('LINEBEFORE', (1, 0), (1, -1), 0.4, _garis),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    el.append(tp)
    el.append(Spacer(1, 1.5 * rl_mm))

    el.append(Paragraph(
        "PIHAK KESATU dan PIHAK KEDUA sepakat melakukan serah terima hasil "
        "pengadaan barang untuk ditatausahakan sebagai Barang Milik Negara, "
        "berdasarkan:", isi))
    dasar = list(_DASAR_BAST_PPK)
    if str(p.get("nomor_kontrak") or "").strip():
        dasar.append(f"Kontrak/SPK Nomor {_esc(p['nomor_kontrak'].strip())};")
    dasar.append(
        "Berita Acara Serah Terima dari Penyedia/Pemberi kepada PPK Nomor "
        f"{_esc(str(p.get('nomor_bast') or '-').strip())} tanggal "
        f"{_fmt_tanggal_id(p.get('tanggal_bast')) or '-'}.")
    for i, d in enumerate(dasar, 1):
        el.append(Paragraph(f"{i}. {d}", ket))
    el.append(Spacer(1, 1.5 * rl_mm))

    # ── Dokumen pengadaan yang melekat pada register ini ──────────────────
    # Dicetak SEBELUM Pasal 1 karena ia menerangkan dasar perolehannya —
    # pembaca perlu tahu ini kontrak atau uang persediaan sebelum membaca
    # barang apa yang diserahkan. Kolom kosong tidak dicetak: blok yang
    # separuhnya bertanda hubung membuat pembaca menghitung apa yang tak ada
    # alih-alih membaca apa yang ada.
    _brs_dok = baris_dokumen(p.get("sifat"), p)
    if _brs_dok:
        el.append(Paragraph("<b>DASAR DAN DOKUMEN PENGADAAN</b>", lbl_pasal))
        _t_dok = Table(
            [[Paragraph(_esc(lbl), ket),
              Paragraph(f": <b>{_esc(str(val))}</b>", ket)]
             for lbl, val in _brs_dok],
            colWidths=[110, doc.width - 110])
        _t_dok.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5)]))
        el.append(_t_dok)
        el.append(Spacer(1, 1.5 * rl_mm))

    # PASAL 1 — objek serah terima: seluruh baris barang perolehan apa adanya
    # (aset maupun persediaan — pemilahan buku terjadi di pencatatan, bukan
    # pada serah terimanya).
    el.append(Paragraph("<b>PASAL 1 — OBJEK SERAH TERIMA</b>", lbl_pasal))
    el.append(Paragraph(
        "PIHAK KESATU menyerahkan dan PIHAK KEDUA menerima hasil pengadaan "
        "dengan rincian sebagai berikut:", isi))
    data = [[Paragraph(h, st['TableHeader']) for h in
             ("No", "Kode Barang", "Uraian Barang", "Golongan", "Jumlah",
              "Harga Satuan (Rp)", "Jumlah Harga (Rp)")]]
    total = 0.0
    for i, b in enumerate(p.get("barang") or [], 1):
        row = b or {}
        harga = float(row.get("harga_satuan") or 0)
        jml = float(row.get("jumlah") or 0)
        tot = harga * jml
        total += tot
        jml_txt = str(int(jml)) if float(jml).is_integer() else f"{jml:g}"
        data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(_esc(str(row.get("kode") or "-").strip()), st['CellCenter']),
            Paragraph(_esc(str(row.get("uraian") or "-").strip()), st['Cell']),
            Paragraph(label_golongan(row.get("kode")) or "-", st['CellCenter']),
            Paragraph(jml_txt, st['CellCenter']),
            Paragraph(fmt_rp(harga), st['CellRight']),
            Paragraph(fmt_rp(tot), st['CellRight']),
        ])
    data.append([Paragraph("", st['Cell']),
                 Paragraph("<b>JUMLAH</b>", st['Cell']),
                 Paragraph("", st['Cell']), Paragraph("", st['Cell']),
                 Paragraph("", st['Cell']), Paragraph("", st['Cell']),
                 Paragraph(f"<b>{fmt_rp(total)}</b>", st['CellRight'])])
    t = Table(data, colWidths=_fit_col_widths([24, 84, 148, 86, 40, 80, 84],
                                              doc.width), repeatRows=1)
    t.setStyle(_std_table_style(zebra=True, total_row=True))
    el.append(t)

    nomor_pasal = 2

    def pasal(judul, isi_list):
        nonlocal nomor_pasal
        blok = [Paragraph(f"<b>PASAL {nomor_pasal} — {judul}</b>", lbl_pasal)]
        for i, teks in enumerate(isi_list, 1):
            blok.append(Paragraph(
                (f"({i}) {teks}" if len(isi_list) > 1 else teks), isi))
        el.append(KeepTogether(blok))
        nomor_pasal += 1

    label_jenis = JENIS_PEROLEHAN.get(p.get("jenis"),
                                      (p.get("jenis") or "perolehan",))[0]
    pasal("DASAR SERAH TERIMA", [
        f"Barang pada Pasal 1 diperoleh melalui {_esc(str(label_jenis).lower())} "
        f"dari {_esc(str(p.get('pihak') or '-').strip())} dan telah diterima "
        "PIHAK KESATU dari penyedia/pemberi berdasarkan Berita Acara Serah "
        f"Terima Nomor {_esc(str(p.get('nomor_bast') or '-').strip())} "
        f"tanggal {_fmt_tanggal_id(p.get('tanggal_bast')) or '-'}.",
        "PIHAK KESATU menyatakan barang tersebut telah diperiksa jumlah, "
        "spesifikasi, dan kelengkapannya serta diterima dalam keadaan baik "
        "sebagaimana mestinya.",
    ])
    pasal("PENATAUSAHAAN DAN TANGGUNG JAWAB", [
        "Terhitung sejak ditandatanganinya Berita Acara ini, barang beralih "
        "kepada PIHAK KEDUA untuk ditatausahakan sebagai Barang Milik Negara "
        "pada satuan kerja sesuai ketentuan peraturan perundang-undangan.",
        "Barang golongan aset tetap dicatat ke Daftar Barang Pengguna dengan "
        "Nomor Urut Pendaftaran (NUP), dan barang persediaan dicatat ke "
        "kartu/kartu kendali persediaan satuan kerja.",
    ])
    pasal("PENUTUP", [
        "Demikian Berita Acara Serah Terima ini dibuat dengan sebenarnya "
        "dalam rangkap 2 (dua) — 1 (satu) rangkap untuk PIHAK KESATU dan "
        "1 (satu) rangkap untuk PIHAK KEDUA — yang masing-masing mempunyai "
        "kekuatan hukum yang sama; apabila di kemudian hari terdapat "
        "kekeliruan akan diadakan perbaikan sebagaimana mestinya.",
    ])

    el.append(Spacer(1, 3 * rl_mm))
    from shared_utils import status_kepegawaian_by_nip
    el.extend(_signature_block([
        {'header': 'PIHAK KEDUA,', 'role': 'Yang Menerima,',
         'nama': p2.get("nama") or "................................",
         'after': baris_identitas_ttd(
             p2.get("nip"), bp.get("kpb_status_kepegawaian"))},
        {'pre': [_tempat_tanggal_laporan(settings, bp.get("tanggal"))],
         'header': 'PIHAK KESATU,', 'role': 'Yang Menyerahkan,',
         'nama': p1.get("nama") or "................................",
         'after': baris_identitas_ttd(
             p1.get("nip"), str(p.get("ppk_status_kepegawaian") or "").strip()
             or await status_kepegawaian_by_nip(p1.get("nip")))},
    ], doc.width))

    footer = _page_footer_factory("BAST Hasil Pengadaan PPK-KPB")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    return buffer.getvalue()


@pengadaan_router.get("/pengadaan/{perolehan_id}/bast-ppk-kpb/pdf")
async def bast_ppk_kpb_pdf(perolehan_id: str,
                           _user: dict = Depends(require_user_or_query_token)):
    """Unduh dokumen resmi BAST PPK → KPB (PDF naskah ber-pasal)."""
    from io import BytesIO

    from fastapi.responses import StreamingResponse

    data = await bangun_bast_ppk_pdf(perolehan_id, _user)
    return StreamingResponse(
        BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="BAST_PPK_KPB_{perolehan_id[:8]}.pdf"'})


class LpbGabunganIn(BaseModel):
    perolehan_ids: list[str] = Field(min_length=1, max_length=100)
    tanggal: str = ""                  # default hari ini
    booking_nomor: bool = True
    # Penanda tangan KHUSUS dokumen ini (slot → id pejabat) — menimpa setelan
    # satker. Dibekukan pada rekamannya: dokumen yang sudah terbit tak boleh
    # berganti nama penanda tangan hanya karena setelan satker kelak diubah.
    penandatangan: dict | None = None
    # Kode klasifikasi arsip PILIHAN OPERATOR untuk dokumen ini.
    #
    # Keluhan pemilik: *"ketika buat BAST dan klik nomor otomatis dari
    # registrasi persuratan, bagian klasifikasi arsip tidak ada dan tidak ada
    # pilihan memilih klasifikasi arsip yang ada"*. Memang: jalur otomatis
    # lintas modul hanya pernah punya SATU sumber kode — aturan pemetaan
    # (modul + jenis naskah). Tak ada aturan yang cocok berarti slot
    # {kode_klasifikasi} pada nomor terbit KOSONG, tanpa satu pun galat, dan
    # tanpa cara memperbaikinya dari layar tempat dokumennya dibuat.
    kode_klasifikasi: str = ""



@pengadaan_router.post("/pengadaan/lpb-gabungan")
async def buat_lpb_gabungan(payload: LpbGabunganIn,
                            user: dict = Depends(require_writer)):
    """SATU Laporan Penerimaan Barang yang merangkum BANYAK BAST PPK → KPB —
    aset maupun persediaan dalam satu surat laporan (permintaan pemilik).

    Semua perolehan terpilih WAJIB sudah menerbitkan BAST PPK → KPB: LPB
    gabungan didefinisikan sebagai rekap dokumen serah terima itu, dan baris
    yang tak bisa dirunut ke BAST PPK-KPB mana pun membuat rekapnya bohong.
    Nomornya dipesan dari deret LPB yang sama dengan kedua jalur lain
    (`booking_nomor_lpb`), dan hasilnya tampil di Riwayat LPB seperti biasa.
    """
    ids = sorted({str(i or "").strip() for i in payload.perolehan_ids
                  if str(i or "").strip()})
    if not ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu perolehan")
    rows = await db.pengadaan.find(
        scope_query_field_satker(user, {"id": {"$in": ids}}),
        {"_id": 0}).to_list(len(ids))
    if len(rows) != len(ids):
        raise HTTPException(status_code=404,
                            detail="Sebagian perolehan tidak ditemukan")
    tanpa = [str(r.get("nomor_bast") or r.get("id", "")[:8]) for r in rows
             if not (r.get("bast_ppk") or {})]
    if tanpa:
        raise HTTPException(status_code=400, detail=(
            "Terbitkan BAST PPK-KPB dulu untuk: " + ", ".join(tanpa[:10])
            + ("…" if len(tanpa) > 10 else "")))
    # SATU satker per LPB gabungan. Untuk operator satker-tunggal, scope query
    # sudah menjamin ini; tetapi super-admin (lintas-satker) bisa memilih
    # perolehan dari beberapa satker sekaligus — satu surat laporan yang
    # mencampur BMN dua satker adalah dokumen yang tak bisa ditandatangani
    # KPB mana pun dan bocor ke keduanya. Tolak tegas.
    satker_set = {str(r.get("kode_satker") or "").strip() for r in rows}
    satker_set.discard("")
    if len(satker_set) > 1:
        raise HTTPException(status_code=400, detail=(
            "Perolehan terpilih berasal dari lebih dari satu satker "
            f"({', '.join(sorted(satker_set))}). LPB gabungan harus satu satker."))
    ks_dok = (next(iter(satker_set)) if satker_set
              else kode_satker_user(user))

    # Urutan dokumen mengikuti tanggal BAST (kronologis), bukan urutan klik.
    rows.sort(key=lambda r: (str(r.get("tanggal_bast") or ""),
                             str(r.get("nomor_bast") or "")))
    items = baris_lpb_gabungan(rows)
    if not items:
        raise HTTPException(status_code=400, detail=(
            "Perolehan terpilih tidak memuat baris barang sama sekali"))

    _galat_ttd = validate_penandatangan(payload.penandatangan)
    if _galat_ttd:
        raise HTTPException(status_code=400, detail="; ".join(_galat_ttd))
    tgl = _tgl_iso_atau_hari_ini(payload.tanggal)
    nomor_ppk = [str((r.get("bast_ppk") or {}).get("nomor") or "").strip()
                 or f"(tanpa nomor — BAST {r.get('nomor_bast') or '-'})"
                 for r in rows]
    nomor, surat_id = "", ""
    if payload.booking_nomor:
        from routes.persuratan import booking_nomor_lpb
        nomor, surat_id = await booking_nomor_lpb(
            user, tgl,
            perihal=(f"Laporan Penerimaan Barang (LPB) Gabungan — "
                     f"{len(rows)} BAST PPK-KPB"),
            tujuan="",
            keterangan="booking otomatis dari LPB gabungan Pengadaan",
            kode_satker=ks_dok,
            kode_klasifikasi=payload.kode_klasifikasi)

    # PPK di header LPB: satu nama bila seragam; beberapa nama digabung tanpa
    # NIP (baris NIP hanya bermakna untuk satu orang).
    ppk_unik = {(str(r.get("ppk_nama") or "").strip(),
                 str(r.get("ppk_nip") or "").strip(),
                 str(r.get("ppk_status_kepegawaian") or "").strip())
                for r in rows if str(r.get("ppk_nama") or "").strip()}
    if len(ppk_unik) == 1:
        ppk_nama, ppk_nip, ppk_status = next(iter(ppk_unik))
    else:
        ppk_nama = ", ".join(sorted(n for n, _, _ in ppk_unik))[:300]
        ppk_nip, ppk_status = "", ""
    penyedia_unik = sorted({str(r.get("pihak") or "").strip()
                            for r in rows if str(r.get("pihak") or "").strip()})
    penyedia = "; ".join(penyedia_unik[:5]) + (
        f"; +{len(penyedia_unik) - 5} lainnya" if len(penyedia_unik) > 5 else "")

    lpb_id = str(uuid.uuid4())
    await db.lpb.insert_one({
        "id": lpb_id, "nomor": nomor, "surat_id": surat_id,
        "kategori": "gabungan",
        "tanggal": tgl,
        "jenis": "gabungan",
        "jenis_dokumen": "BAST PPK-KPB",
        "penyedia": penyedia,
        "perolehan_id": "",
        "perolehan_ids": ids,
        "jumlah_bast": len(rows),
        "ppk_nama": ppk_nama, "ppk_nip": ppk_nip,
        "ppk_status_kepegawaian": ppk_status,
        "keterangan": ("Gabungan seluruh BAST PPK-KPB: "
                       + "; ".join(nomor_ppk))[:500],
        "items": items, "total_nilai": total_nilai_lpb(items),
        "jumlah_barang": len(items),
        # Penanda tangan khusus dokumen ini — DIBEKUKAN di sini. Kosong =
        # ikut setelan satker, lalu resolusi peran.
        "penandatangan": bersihkan_penandatangan(payload.penandatangan),
        "kode_satker": ks_dok,
        "created_by": user.get("username", "system"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await log_audit("pengadaan_lpb_gabungan", "", lpb_id,
                    username=user.get("username", "system"),
                    detail=(f"LPB gabungan {nomor or '(tanpa nomor)'}: "
                            f"{len(rows)} BAST PPK-KPB, {len(items)} baris"))
    return {"lpb_id": lpb_id, "nomor": nomor,
            "jumlah_bast": len(rows), "jumlah_barang": len(items),
            "total_nilai": total_nilai_lpb(items)}


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

    # GERBANG KOMPRESI — satu aturan untuk satu aplikasi utuh. Lampiran modul
    # siklus dulu ditulis apa adanya, jadi PDF hasil pindai dan foto bukti
    # masuk GridFS tanpa pernah menyentuh rantai berjenjang.
    #
    # `content_type` DAN `filename` entri diambil dari metadata yang
    # DIKEMBALIKAN gerbang, bukan dari ekstensi: rantai gambar mengembalikan
    # JPEG walau masukannya PNG, dan entri yang tetap menyebut `.png` membuat
    # pengguna mengunduh berkas yang isinya tak sesuai namanya.
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        file_bytes, nama=filename, content_type=_LAMPIRAN_MEDIA[ext],
        metadata={"kind": "pengadaan", "perolehan_id": perolehan_id})

    entri = {"file_id": file_id, "filename": _meta["filename"],
             "content_type": _meta["content_type"],
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
    """Hapus register perolehan SALAH INPUT (admin) + berkas lampirannya.

    HANYA register yang BELUM melahirkan apa pun. Begitu barangnya sudah
    dicatat (masuk stok persediaan / jadi draft aset), atau BAST PPK-KPB sudah
    terbit, atau ada LPB yang menunjuknya, menghapus registernya meninggalkan
    stok, jurnal Buku Barang, dokumen resmi, dan nomor surat sebagai anak
    yatim yang menunjuk induk yang tak ada lagi — kerusakan data yang jauh
    lebih mahal daripada satu register salah. Operator harus membalik
    pencatatannya lebih dulu (pola sama dengan penjaga hapus master
    persediaan). Back-link `perolehan_id`/snapshot di aset tertaut DILEPAS
    setelah lolos penjaga (temuan review #11).
    """
    p = await db.pengadaan.find_one(
        {"id": perolehan_id},
        {"_id": 0, "kode_satker": 1, "lampiran_berkas": 1, "barang": 1,
         "bast_ppk": 1, "nomor_bast": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Perolehan tidak ditemukan")
    await pastikan_akses_dok_satker(_admin, p)  # 403 bila register milik satker lain

    # Penjaga anti-yatim: register yang sudah "hidup" tak boleh dihapus.
    tercatat = [b for b in (p.get("barang") or [])
                if str(b.get("psd_item_id") or "").strip()
                or str(b.get("asset_id") or "").strip()]
    if tercatat:
        raise HTTPException(status_code=409, detail=(
            f"{len(tercatat)} barang sudah tercatat ke stok/aset dari perolehan "
            "ini — batalkan/keluarkan pencatatannya dulu sebelum menghapus "
            "register (jika tidak, stok & jurnal menjadi yatim)."))
    if p.get("bast_ppk"):
        raise HTTPException(status_code=409, detail=(
            "BAST PPK→KPB sudah diterbitkan untuk perolehan ini — dokumen resmi "
            "& nomor suratnya akan menggantung. Tidak dapat dihapus."))
    lpb_terkait = await db.lpb.find_one(
        {"$or": [{"perolehan_id": perolehan_id},
                 {"perolehan_ids": perolehan_id}]},
        {"_id": 0, "id": 1})
    if lpb_terkait:
        raise HTTPException(status_code=409, detail=(
            "Ada Laporan Penerimaan Barang (LPB) yang menunjuk perolehan ini — "
            "menghapusnya membuat LPB menunjuk data yang tak ada. Tidak dapat "
            "dihapus."))

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
