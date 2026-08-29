"""BAST SERAH TERIMA PENGGUNA — generator BA serah terima BMN lintas modul.

Format mengikuti contoh resmi satker (BAST Rumga & BA Robot Kit — dua docx
pemilik; intisari di scratchpad/format_bast.md) + PMK Nomor 40 Tahun 2024
(tata cara pelaksanaan penggunaan BMN — menggantikan PMK 246/2014 jo.
76/2019) & PMK 53/2023 (BMN di IKN):
kop → judul per jenis → nomor → narasi tanggal terbilang → identitas PIHAK
KESATU (penyerah) & PIHAK KEDUA (penerima) → dasar hukum → PASAL 1 + tabel
MULTI-ASET → pasal-pasal sesuai jenis → penutup → ttd 2 pihak → tembusan →
lampiran foto aset (opsional, sesuai setelan `sertakan_foto`).

Tujuh jenis serah terima (kebutuhan lapangan):
- penggunaan_melekat    : BAST ke pegawai (aset "Melekat ke" perorangan)
- mutasi_pengguna       : alih pemegang — PIHAK KESATU pemegang lama,
                          PIHAK KEDUA pemegang baru (opsional efek langsung
                          ke master aset via `terapkan_ke_aset`)
- operasional_unit      : penanggung jawab operasional per unit/tempat/tugas
                          (+ daftar penanggung jawab tambahan opsional)
- penggunaan_sementara  : pinjam pakai internal ber-jangka waktu
- pengembalian          : arah balik (PIHAK KEDUA mengembalikan ke satker)
- pengembalian_almarhum : pengembalian BMN pemegang MENINGGAL DUNIA —
                          penyerah ahli waris/atasan, wajib blok dasar
                          (akta kematian) + saksi min. 2 (pola BA pihak
                          berhalangan tetap)
- lainnya               : jenis bebas (judul manual)

Register `bast_serah_terima` menyimpan tiap BAST (riwayat per aset dan per
pengguna terlacak); PDF dirender ulang kapan pun dari register.
"""
import asyncio
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from bast_pasal import validate_pj_tambahan
from auth_utils import (
    require_user, require_user_or_query_token, require_writer,
    require_writer_satker,
)
from db import db
from shared_utils import (
    cek_magic_gambar, get_idempotent_response, kode_satker_user, kunci_idem,
    log_audit, pastikan_akses_aset, pastikan_akses_dok_satker,
    reserve_idempotency_key, scope_query_field_satker, store_idempotent_response,
)

logger = logging.getLogger(__name__)

bast_router = APIRouter()

_PROJ = {"_id": 0}

JENIS_BAST = {
    "penggunaan_melekat": "Penggunaan Barang Milik Negara (Melekat ke Pengguna)",
    "mutasi_pengguna": "Mutasi/Alih Pemegang Barang Milik Negara",
    "operasional_unit": "Operasional Penggunaan Barang Milik Negara pada Unit/Tempat/Tugas",
    "penggunaan_sementara": "Operasional Penggunaan Sementara Barang Milik Negara",
    "pengembalian": "Pengembalian Barang Milik Negara",
    "pengembalian_almarhum": ("Pengembalian Barang Milik Negara — "
                              "Pemegang Meninggal Dunia"),
    "lainnya": "Serah Terima Barang Milik Negara",
}

# Jenis ber-ARAH BALIK (PIHAK KEDUA menyerahkan, PIHAK KESATU menerima).
# `pengembalian_almarhum` ikut keluarga ini: yang menyerahkan bukan almarhum
# melainkan AHLI WARIS/ATASAN LANGSUNG — karena itu ia butuh blok dasar
# (akta kematian) dan SAKSI, pola berita acara "pihak berhalangan tetap".
_JENIS_PENGEMBALIAN = frozenset({"pengembalian", "pengembalian_almarhum"})

# Celah tanda tangan basah BAST (mm) — dokumen ber-batas 2 halaman sehingga
# tak bisa memakai default _signature_block yang lebih lega. Ruang tambahan
# celah diambil dari jarak antar-baris blok TTD (pemisah visual, bukan area
# pena): pasangan ini yang terbesar yang masih lolos uji batas 2 halaman
# pada muatan terberat (test_semua_jenis_bast_maksimal_dua_halaman).
_CELAH_TTD_BAST = 14
_JARAK_BARIS_TTD_BAST = 3

# Dasar hukum BAST penggunaan BMN — dimutakhirkan (audit resmi): rezim
# PMK 246/PMK.06/2014 jo. 76/2019 telah DICABUT dan digantikan PMK Nomor 40
# Tahun 2024 tentang Tata Cara Pelaksanaan Penggunaan BMN.
DASAR_HUKUM = (
    "Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;",
    "Peraturan Pemerintah Nomor 27 Tahun 2014 tentang Pengelolaan Barang "
    "Milik Negara/Daerah jo. PP Nomor 28 Tahun 2020;",
    "Peraturan Presiden Nomor 62 Tahun 2022 tentang Otorita Ibu Kota "
    "Nusantara;",
    "Peraturan Menteri Keuangan Nomor 40 Tahun 2024 tentang Tata Cara "
    "Pelaksanaan Penggunaan Barang Milik Negara;",
    "Peraturan Menteri Keuangan Nomor 53 Tahun 2023 tentang Pengelolaan "
    "Barang Milik Negara dan Aset Dalam Penguasaan di Ibu Kota Nusantara.",
)

# Bentuk RINGKAS dasar hukum untuk badan naskah — satu kalimat mengalir,
# rujukan hukum yang sama persis dengan DASAR_HUKUM di atas (yang tetap
# dipertahankan sebagai rujukan lengkap/dokumentasi).
DASAR_HUKUM_RINGKAS = (
    "Undang-Undang Nomor 17 Tahun 2003; Peraturan Pemerintah Nomor 27 Tahun "
    "2014 jo. Peraturan Pemerintah Nomor 28 Tahun 2020; Peraturan Presiden "
    "Nomor 62 Tahun 2022; Peraturan Menteri Keuangan Nomor 40 Tahun 2024; dan "
    "Peraturan Menteri Keuangan Nomor 53 Tahun 2023"
)


class PihakIn(BaseModel):
    nama: str = ""
    nip: str = ""
    jabatan: str = ""
    alamat: str = ""


class PjTambahanIn(BaseModel):
    """Penanggung jawab tambahan pada BAST Operasional Unit/Tempat/Tugas.

    `nip` dan `asset_ids` ditambahkan atas permintaan pemilik: tanpa keduanya,
    Pasal 2 menamai orang tanpa pengenal yang bisa diverifikasi, dan tak
    pernah menyebut barang mana yang menjadi tanggung jawab siapa — padahal
    justru itu yang dicari orang saat membuka BAST setahun kemudian.
    """
    nama: str = ""
    # NIP (ASN) atau NIK (non-ASN) — satu kolom, karena dokumen ini dipakai
    # keduanya dan memisahkannya hanya melahirkan kolom yang selalu kosong.
    nip: str = ""
    unit_tempat_tugas: str = ""
    # Unit eselon TERDALAM tempat orang ini bekerja — terisi otomatis saat
    # namanya dipilih dari Master Pegawai. Tetap bisa diketik manual: tidak
    # semua penanggung jawab terdaftar di sana (tenaga alih daya, mitra).
    unit_eselon: str = ""
    # Bagian dari `asset_ids` BAST yang melekat pada orang ini. Bukan daftar
    # bebas: divalidasi harus termasuk aset yang diserahterimakan, dan satu
    # aset hanya boleh melekat pada satu orang.
    asset_ids: List[str] = []


class AlmarhumIn(BaseModel):
    """Identitas pemegang yang meninggal — DASAR berita acara pengembalian.
    Bukan penanda tangan; ia disebut di blok dasar bersama akta kematiannya."""
    nama: str = ""
    nip: str = ""
    tanggal_meninggal: str = ""
    nomor_akta_kematian: str = ""


class SaksiIn(BaseModel):
    """Saksi berita acara — WAJIB (min. 2) pada pengembalian almarhum, karena
    pihak yang seharusnya menyerahkan berhalangan tetap."""
    nama: str = ""
    jabatan: str = ""
    nip: str = ""


class BastIn(BaseModel):
    jenis: str
    judul_lainnya: Optional[str] = ""
    asset_ids: List[str]
    pihak_kedua: PihakIn
    pihak_pertama: Optional[PihakIn] = None   # default: kasatker/KPB pengaturan
    # Penyerah (Pihak Kesatu) adalah pejabat pengelola BMN yang bertindak
    # ATAS NAMA KPB (mis. Petugas Penatausahaan/Pengelola BMN Satker) — bila
    # true, dokumen ditandai "a.n. Kuasa Pengguna Barang" + baris "Mengetahui,
    # KPB" (kaidah pendelegasian penyerahan internal — riset regulasi §11B).
    penyerah_atas_nama_kpb: Optional[bool] = False
    nomor: Optional[str] = ""                 # bisa dari Booking Nomor persuratan
    tanggal: Optional[str] = ""               # default hari ini
    jangka_dari: Optional[str] = ""           # khusus penggunaan_sementara
    jangka_sampai: Optional[str] = ""
    penanggung_jawab_tambahan: Optional[List[PjTambahanIn]] = None
    # Khusus `pengembalian_almarhum`: identitas almarhum (dasar BA) + saksi.
    almarhum: Optional[AlmarhumIn] = None
    saksi: Optional[List[SaksiIn]] = None
    tembusan: Optional[str] = ""              # override; default pengaturan
    sertakan_foto: Optional[bool] = False
    # Tampilkan kolom Nilai Perolehan pada PDF? None = ikut KEBIJAKAN satker
    # (Pengaturan/Master Satker); True/False = keputusan dokumen ini sendiri —
    # banyak satker menutup nilai pada naskah yang dipegang pegawai.
    tampilkan_nilai: Optional[bool] = None
    keterangan: Optional[str] = ""
    # Handover langsung: BAST sekaligus MENERAPKAN perubahan ke master aset
    # (mutasi → pengguna beralih ke PIHAK KEDUA; pengembalian → pengguna
    # dikosongkan). Ber-audit + $inc version.
    terapkan_ke_aset: Optional[bool] = False
    # Pesan nomor otomatis dari Registrasi Persuratan (tercatat di buku
    # agenda berstatus dibooking).
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
    booking_otomatis: Optional[bool] = False
    # Lampiran Surat Pernyataan Tanggung Jawab (opsional) — satu lembar per
    # penanggung jawab individual, ditandatangani orangnya sendiri.
    surat_pernyataan: Optional[bool] = False
    # ── REVISI BAST (mandat SURAT-3C) ──────────────────────────────────────
    # BAST yang sudah sah TIDAK PERNAH diedit: revisi = BAST BARU bernomor
    # baru yang menggantikan yang lama. `revisi_dari` = id BAST yang
    # digantikan; mode "mengubah" (koreksi isi, serah terima tetap terjadi)
    # atau "mencabut" (serah terimanya sendiri dibatalkan). Arsip lama utuh
    # dan PDF-nya diberi penanda telah direvisi; nomor agenda lama otomatis
    # ber-status keberlakuan lewat relasi antar surat (SURAT-3B).
    revisi_dari: Optional[str] = ""
    revisi_mode: Optional[str] = "mengubah"
    revisi_alasan: Optional[str] = ""


@bast_router.get("/bast/referensi")
async def referensi_bast(_user: dict = Depends(require_user)):
    return {"jenis": [{"kode": k, "uraian": v} for k, v in JENIS_BAST.items()]}


@bast_router.get("/bast")
async def daftar_bast(asset_id: str = "", q: str = "", nip: str = "",
                      page: int = 1, page_size: int = 30,
                      _user: dict = Depends(require_user)):
    """Riwayat BAST (filter per aset / cari nama penerima & nomor).

    `nip` mengunci hasil pada identitas penerima (pihak_kedua.nip) — riwayat
    per pemegang tidak lagi tercampur nama mirip (audit G2 #7).
    """
    page, page_size = max(1, page), min(max(1, page_size), 100)
    query = {}
    if asset_id.strip():
        query["asset_ids"] = asset_id.strip()
    if nip.strip():
        query["pihak_kedua.nip"] = nip.strip()
    if q.strip():
        import re as _re
        rx = {"$regex": _re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"nomor": rx}, {"pihak_kedua.nama": rx}, {"jenis": rx}]
    from shared_utils import scope_query_field_satker
    query = scope_query_field_satker(_user, query)
    total = await db.bast_serah_terima.count_documents(query)
    items = await (db.bast_serah_terima.find(query, _PROJ)
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    # STATUS TTD ELEKTRONIK ikut, satu kueri untuk sehalaman. Tanpa ini
    # Riwayat BAST tak punya cara menjawab "sudah ditandatangani belum?" —
    # dan tombol "Kirim ke TTD" tampak seperti satu-satunya jalan, sehingga
    # ditekan lagi dan lagi sementara permintaan yang lama menua sampai
    # tautannya mati.
    from ttd_penautan import lampirkan_status_ttd
    await lampirkan_status_ttd(db, "bast", items)
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "label_jenis": JENIS_BAST}


async def _penanda_tangan_bast(b: dict, user: dict) -> list:
    """Daftar penanda tangan BAST untuk e-sign — SINKRON dengan blok TTD
    yang dicetak `bast_pdf`: Pihak Pertama & Kedua, lalu "Mengetahui" KPB
    (pada mutasi pengguna / penyerah a.n. KPB — kaidah §11B), lalu seluruh
    saksi. Kondisi & resolver KPB-nya SAMA dengan cetakan; bila blok TTD
    PDF berubah, fungsi ini wajib ikut — tautan TTD yang lebih sedikit dari
    kolom di kertasnya membuat dokumen tak pernah bisa lengkap diteken.

    → list[dict {nama, nip, jabatan}] terurut sesuai dokumen.
    """
    hasil = []
    for p, peran in ((b.get("pihak_pertama") or {}, "Pihak Pertama"),
                     (b.get("pihak_kedua") or {}, "Pihak Kedua")):
        nama = str((p or {}).get("nama") or "").strip()
        if not nama:
            continue
        hasil.append({"nama": nama,
                      "nip": str((p or {}).get("nip") or "").strip(),
                      "jabatan": str((p or {}).get("jabatan") or peran).strip()})

    jenis = str(b.get("jenis") or "")
    an_kpb = bool(b.get("penyerah_atas_nama_kpb")) and jenis != "mutasi_pengguna"
    if jenis == "mutasi_pengguna" or an_kpb:
        from pejabat_utils import jabatan_kapasitas_kpb
        from shared_utils import pengaturan_kop, resolve_penandatangan_kpb
        settings = await pengaturan_kop(kode_satker=b.get("kode_satker")) or {}
        kpb = await resolve_penandatangan_kpb(
            settings, b.get("tanggal"),
            str(b.get("kode_satker") or "").strip() or kode_satker_user(user)) or {}
        nama_kpb = str(kpb.get("nama") or "").strip()
        nip_kpb = str(kpb.get("nip") or "").strip()

        def _orang_sama(s):
            # KPB yang juga tercantum sebagai pihak (mis. PIHAK KESATU default
            # = KPB sendiri) cukup SATU tautan — NIP pembanding utama, nama
            # fallback saat salah satunya tak ber-NIP.
            if nip_kpb and s.get("nip"):
                return s["nip"] == nip_kpb
            return s["nama"].casefold() == nama_kpb.casefold()

        if nama_kpb and nama_kpb != "-" and not any(map(_orang_sama, hasil)):
            hasil.append({"nama": nama_kpb, "nip": nip_kpb,
                          "jabatan": f"Mengetahui — {jabatan_kapasitas_kpb(kpb)}"})

    for i, s in enumerate(
            [s for s in (b.get("saksi") or [])
             if str((s or {}).get("nama") or "").strip()], 1):
        hasil.append({"nama": str(s.get("nama")).strip(),
                      "nip": str(s.get("nip") or "").strip(),
                      "jabatan": str(s.get("jabatan") or "").strip()
                      or f"Saksi {i}"})
    return hasil


@bast_router.post("/bast/{bast_id}/kirim-ttd")
async def kirim_bast_ke_ttd(bast_id: str, user: dict = Depends(require_writer)):
    """Buat permintaan TTD elektronik untuk sebuah BAST — dengan penaut
    TERSTRUKTUR (`doc_ref` = id BAST) + penanda tangan otomatis dari SEMUA
    kolom TTD dokumen (`_penanda_tangan_bast`: pihak, Mengetahui KPB, saksi).
    Ini titik masuk yang menautkan dunia BAST ke dunia e-sign secara
    terstruktur (fondasi propagasi otomatis: back-link signature_request_id
    ke BAST saat selesai, lalu cascade saat dibatalkan)."""
    from shared_utils import scope_query_field_satker
    b = await db.bast_serah_terima.find_one(
        scope_query_field_satker(user, {"id": bast_id}), _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    from routes.ttd import PermintaanIn, SignerIn, buat_permintaan
    # SURAT PERNYATAAN TANGGUNG JAWAB MENAMBAH TEMPAT TEKEN.
    #
    # BAST ber-SPTJ mencetak SATU LEMBAR TERSENDIRI untuk tiap penyata, dan
    # lembar itu menuntut tanda tangan orangnya sendiri. Selama `jumlah_ttd`
    # selalu 1, lembar pernyataan terbit KOSONG — dokumen resmi yang tampak
    # lengkap padahal belum diteken.
    #
    # Jumlahnya diturunkan dari `daftar_penyata`, fungsi YANG SAMA yang
    # dipakai `bast_pdf` mencetak lembarnya; menghitung sendiri di sini akan
    # melahirkan dua pendapat tentang "berapa lembar".
    _penyata = []
    if b.get("surat_pernyataan"):
        from bast_pasal import daftar_penyata
        _penyata = daftar_penyata(
            str(b.get("jenis") or ""), b.get("pihak_kedua") or {},
            b.get("pihak_pertama") or {},
            b.get("penanggung_jawab_tambahan"), b.get("aset"))
    from ttd_lembar_pernyataan import terapkan_lembar_pernyataan
    signers = [SignerIn(**s) for s in terapkan_lembar_pernyataan(
        await _penanda_tangan_bast(b, user), _penyata)]
    if not signers:
        raise HTTPException(
            status_code=400,
            detail="BAST belum memiliki pihak yang dapat menandatangani")
    judul = f"BAST {b.get('nomor') or bast_id}".strip()
    payload = PermintaanIn(judul=judul, doc_type="bast", doc_ref=str(bast_id),
                           mode="paralel", signers=signers)
    # buat_permintaan mengembalikan {id, judul, mode, links:[...]} + mencatat audit.
    hasil = await buat_permintaan(payload=payload, user=user)

    # LAMPIRKAN PDF BAST-nya (pola sama dengan LPB): tanpa ini penanda tangan
    # hanya melihat kanvas kosong — tak bisa MEMBACA yang ditandatanganinya
    # dan tak bisa MENGATUR letak pembubuhannya, dan dokumen ber-TTD tak bisa
    # diunduh sama sekali. PDF DIBEKUKAN sekarang (bukan dibangun ulang saat
    # diteken) supaya kop/pejabat/nomor tak berubah di antara "dikirim" dan
    # "diteken" — yang bersangkutan meneken persis dokumen yang ia baca.
    try:
        _resp = await bast_pdf(bast_id, _user=user)
        _buf = io.BytesIO()
        async for _potong in _resp.body_iterator:
            _buf.write(_potong if isinstance(_potong, bytes) else _potong.encode())
        _data = _buf.getvalue()
        from pypdf import PdfReader
        _n_hal = len(PdfReader(io.BytesIO(_data)).pages)
        _nama = f"BAST_{str(b.get('nomor') or bast_id)[:40].replace('/', '_')}.pdf"
        # GERBANG KOMPRESI. Sama seperti LPB: ditulis SEBELUM QR & spesimen
        # dibubuhkan, jadi yang dikompres masih naskah vektor polos.
        from gerbang_media import tulis_media as _tulis
        _fid, _ = await _tulis(_data, nama=_nama, content_type="application/pdf",
                               metadata={"kind": "bast", "bast_id": bast_id})
        await db.signature_requests.update_one(
            {"id": hasil["id"]},
            {"$set": {"dok_file_id": str(_fid), "dok_nama": _nama,
                      "dok_halaman": _n_hal}})
        hasil = {**hasil, "dok_nama": _nama, "dok_halaman": _n_hal}
    except HTTPException:
        raise
    except Exception:
        # Lampiran gagal (mis. render PDF) TIDAK menggugurkan permintaan yang
        # sudah terbit + link yang sudah dikirim — penanda tangan tetap bisa
        # meneken (mode tanpa dokumen, perilaku lama).
        logger.warning("Lampiran PDF BAST %s ke permintaan TTD gagal", bast_id,
                       exc_info=True)
    return hasil


@bast_router.post("/bast")
async def buat_bast(payload: BastIn, request: Request = None,
                    user: dict = Depends(require_writer_satker)):
    """Simpan BAST ke register (multi-aset; snapshot identitas aset dibekukan
    agar dokumen historis tak berubah saat master aset berubah).
    Idempotency-Key opsional: klik ganda / retry jaringan tidak menggandakan
    BAST + nomor booking otomatis (pola sama dengan PATCH aset)."""
    idem_key = kunci_idem(
        request.headers.get("Idempotency-Key", "") if request else "", user)
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            return cached["response"]
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return cached["response"]
        elif _idem == "pending":
            raise HTTPException(
                status_code=409,
                detail="Permintaan dengan kunci idempotensi ini sedang "
                       "diproses, coba lagi sebentar")
    if payload.jenis not in JENIS_BAST:
        raise HTTPException(status_code=400,
                            detail=f"Jenis BAST tidak dikenal: {payload.jenis}")
    # ── Validasi REVISI (SURAT-3C): rantai lurus, beralasan, satu pengganti ─
    sumber_revisi = None
    if str(payload.revisi_dari or "").strip():
        sumber_revisi = await db.bast_serah_terima.find_one(
            {"id": str(payload.revisi_dari).strip()}, _PROJ)
        if not sumber_revisi:
            raise HTTPException(status_code=404,
                                detail="BAST yang direvisi tidak ditemukan")
        await pastikan_akses_dok_satker(user, sumber_revisi)
        if str(payload.revisi_mode or "") not in ("mengubah", "mencabut"):
            raise HTTPException(status_code=400, detail=(
                "Mode revisi tidak dikenal (pilihan: mengubah, mencabut)"))
        if not str(payload.revisi_alasan or "").strip():
            raise HTTPException(status_code=400, detail=(
                "Alasan revisi wajib diisi — tercatat pada dokumen pengganti "
                "dan jejak audit"))
        if sumber_revisi.get("direvisi_oleh"):
            # Rantai revisi harus LURUS: BAST yang sudah punya pengganti tak
            # boleh direvisi lagi (dua pengganti = dua kebenaran). Revisi
            # berikutnya dibuat dari pengganti TERBARU.
            raise HTTPException(status_code=409, detail=(
                "BAST ini sudah punya pengganti — buat revisi dari BAST "
                "penggantinya (revisi terbaru), bukan dari arsip lama"))
    if not payload.asset_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu aset")
    if not str(payload.pihak_kedua.nama or "").strip():
        raise HTTPException(status_code=400, detail="Nama PIHAK KEDUA wajib diisi")
    if payload.jenis == "penggunaan_sementara" and not (
            str(payload.jangka_dari or "").strip()
            and str(payload.jangka_sampai or "").strip()):
        raise HTTPException(status_code=400, detail=(
            "Penggunaan sementara wajib ber-jangka waktu (dari & sampai)"))
    _saksi = [s for s in (payload.saksi or []) if str(s.nama or "").strip()]
    if payload.jenis == "pengembalian_almarhum":
        # Dasar BA: identitas almarhum WAJIB — tanpanya dokumen tak menjelaskan
        # mengapa yang menyerahkan bukan pemegang tercatat.
        if not str((payload.almarhum.nama if payload.almarhum else "") or "").strip():
            raise HTTPException(status_code=400, detail=(
                "Nama pemegang yang meninggal wajib diisi (dasar berita acara)"))
        if not str((payload.almarhum.tanggal_meninggal if payload.almarhum else "")
                   or "").strip():
            raise HTTPException(status_code=400, detail=(
                "Tanggal meninggal wajib diisi (dasar berita acara)"))
        # Saksi WAJIB min. 2 — pihak yang seharusnya menyerahkan berhalangan
        # tetap, sehingga keabsahan bertumpu pada kesaksian (pola BA berhalangan
        # tetap; tak diatur norma nasional → dikodifikasi di sini).
        if len(_saksi) < 2:
            raise HTTPException(status_code=400, detail=(
                "Pengembalian BMN almarhum wajib disaksikan minimal 2 saksi"))

    aset = await db.assets.find(
        {"id": {"$in": payload.asset_ids}, "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "brand": 1, "model": 1, "serial_number": 1, "condition": 1,
         "purchase_date": 1, "purchase_price": 1, "activity_id": 1,
         "photos": 1, "photo_gridfs_ids": 1, "thumbnail_index": 1},
    ).to_list(500)
    _galat_pj = validate_pj_tambahan(
        [p.model_dump() for p in (payload.penanggung_jawab_tambahan or [])],
        payload.asset_ids)
    if _galat_pj:
        raise HTTPException(status_code=400, detail="; ".join(_galat_pj))
    if len(aset) != len(set(payload.asset_ids)):
        raise HTTPException(status_code=404,
                            detail="Sebagian aset tidak ditemukan/terhapus")
    for a in aset:
        await pastikan_akses_aset(user, a)

    # Stempel efektif SATU kali untuk BAST + surat booking + default pihak
    # pertama: dokumen buatan super-admin pusat ikut satker aset yang
    # diserahterimakan — stempel "" tampil di riwayat & buku agenda SEMUA
    # satker (kebocoran yang dilaporkan pemilik).
    from shared_utils import (kode_satker_efektif_dari_aset, pengaturan_kop,
                              resolve_penandatangan_kpb)
    from satker_utils import tampilkan_nilai_dokumen
    ks_efektif = await kode_satker_efektif_dari_aset(
        user, [a["id"] for a in aset])
    settings = await pengaturan_kop(kode_satker=ks_efektif) or {}
    p1 = payload.pihak_pertama
    # Default alamat pihak = SEMUA baris alamat kantor digabung "; " — setelan
    # multi-baris (2+ alamat kantor) tidak boleh terpotong ke baris pertama
    # saja pada identitas pihak; isian manual dari form selalu menang.
    alamat_p1 = (p1.alamat.strip() if p1 and p1.alamat.strip()
                 else "; ".join(
                     ln.strip() for ln in
                     str(settings.get("alamat_instansi") or "").splitlines()
                     if ln.strip()))
    if p1 and p1.nama.strip():
        # Identitas diketik di form (pemegang lama mutasi / pejabat penyerah)
        # dipakai APA ADANYA — NIP/jabatan kosong tidak boleh diisi silang
        # dengan data KPB (identitas campur-aduk pada dokumen resmi).
        pihak_pertama = {"nama": p1.nama.strip(), "nip": p1.nip.strip(),
                         "jabatan": p1.jabatan.strip(), "alamat": alamat_p1}
    else:
        # Kosong = otomatis KPB aktif dari REFERENSI PEJABAT satker aset pada
        # tanggal BAST (fallback setelan kasatker) — bukan setelan mentah yang
        # bisa kosong/kedaluwarsa. Placeholder "-" dinormalkan ke "" agar PDF
        # tetap mencetak garis titik untuk diisi manual.
        from pejabat_utils import jabatan_kapasitas_kpb
        _kpb_def = await resolve_penandatangan_kpb(
            settings, str(payload.tanggal or "").strip()[:10] or None,
            ks_efektif)

        def _isi(v):
            v = str(v or "").strip()
            return "" if v == "-" else v

        pihak_pertama = {
            "nama": _isi(_kpb_def["nama"]),
            "nip": _isi(_kpb_def["nip"]),
            # Kapasitas mengikuti KOP dokumen: BAST ber-kop KPB → ia bertindak
            # "(Plt./Plh.) Kuasa Pengguna Barang", bukan jabatan strukturalnya
            # (mis. "Direktur ...") yang berlaku pada naskah kop unitnya sendiri.
            "jabatan": jabatan_kapasitas_kpb(_kpb_def),
            "alamat": alamat_p1,
        }
    if payload.jenis == "mutasi_pengguna" and not (
            payload.pihak_pertama and str(payload.pihak_pertama.nama or "").strip()):
        raise HTTPException(status_code=400, detail=(
            "Mutasi pemegang: isi PIHAK KESATU (pemegang lama) — "
            "PIHAK KEDUA adalah pemegang baru"))
    # PIHAK KESATU meninggal dunia → TOLAK untuk SEMUA jenis: almarhum tak
    # dapat menandatangani penyerahan. Termasuk pengembalian_almarhum — di
    # sana penyerah justru ahli waris/atasan (yang hidup); identitas almarhum
    # dicatat di blok `almarhum`, bukan sebagai PIHAK KESATU.
    nip1 = str(pihak_pertama.get("nip") or "").strip()
    if nip1:
        from pegawai_utils import is_meninggal
        # Scope satker (REVIEW-9 R15): Master Pegawai per-satker. Tanpa scope,
        # validasi ini membaca — dan pesan galatnya MEMBOCORKAN nama — pegawai
        # satker lain hanya dari tebakan NIP.
        peg1 = await db.pegawai.find_one(
            scope_query_field_satker(user, {"nip": nip1}),
            {"_id": 0, "nama": 1, "status": 1})
        if peg1 and is_meninggal(peg1):
            raise HTTPException(status_code=400, detail=(
                f"{peg1.get('nama') or nip1} berstatus Meninggal Dunia di "
                "Master Pegawai — tidak dapat menjadi PIHAK KESATU/"
                "penanda tangan. Gunakan BAST Pengembalian (Pemegang Wafat) "
                "dengan penyerah ahli waris/atasan; identitas almarhum diisi "
                "pada bagian dasar berita acara."))

    now = datetime.now(timezone.utc)
    nomor_final = str(payload.nomor or "").strip()
    surat_id = ""
    if payload.booking_otomatis and not nomor_final:
        # Booking nomor otomatis lewat modul Persuratan (buku agenda keluar).
        # Periode deret mengikuti setelan satker (bulanan/tahunan) — jalur
        # otomatis WAJIB sedertan dengan booking manual; dua deret yang
        # diam-diam berbeda tak bisa diperbaiki tanpa menomori ulang arsip.
        from persuratan_utils import bangun_nomor, periode_urut, pilih_klasifikasi
        from routes.persuratan import _no_agenda_berikut, _pengaturan
        tgl_surat = (str(payload.tanggal or "").strip()[:10]
                     or now.date().isoformat())
        _ks = ks_efektif
        atur = await _pengaturan(_ks)
        kode_klas = pilih_klasifikasi(
            atur["peta_klasifikasi"], "penggunaan", "Berita Acara",
            eksplisit=payload.kode_klasifikasi)
        tahun = int(tgl_surat[:4]) if tgl_surat[:4].isdigit() else now.year
        periode = (periode_urut(atur.get("reset_urut"), tgl_surat)
                   or periode_urut(atur.get("reset_urut"),
                                   now.date().isoformat()))
        no_agenda = await _no_agenda_berikut("keluar", periode, _ks)
        nomor_final = bangun_nomor(
            atur["format_nomor"], no_agenda, tgl_surat,
            kode_klasifikasi=kode_klas, kode_unit=atur["kode_unit"],
            kode_bawaan=atur["kode_klasifikasi_default"])
        surat_id = str(uuid.uuid4())
        await db.surat.insert_one({
            "id": surat_id, "jenis": "keluar", "no_agenda": no_agenda,
            "sisipan": 0,
            "tahun": tahun, "nomor": nomor_final, "status": "dibooking",
            # Stempel satker (REVIEW-9 R10): tanpa ini surat booking otomatis
            # muncul di buku agenda & arsip SEMUA satker, dan tak terhitung saat
            # counter per-satker di-seed.
            "kode_satker": _ks,
            "perihal": f"BAST {JENIS_BAST[payload.jenis]} — {payload.pihak_kedua.nama}",
            "tujuan": payload.pihak_kedua.nama, "jenis_naskah": "Berita Acara",
            "modul": "penggunaan", "kegiatan_id": "", "nama_kegiatan": "",
            "kode_klasifikasi": kode_klas, "kode_keamanan": "B",
            "tanggal_surat": tgl_surat, "referensi": "BAST",
            "nomor_eksternal": "", "keterangan": "booking otomatis dari BAST",
            "dibuat_oleh": user.get("username", "system"),
            "riwayat": [{"status": "dibooking", "tanggal": now.isoformat(),
                         "oleh": user.get("username", "system"),
                         "catatan": "booking otomatis dari BAST"}],
            "created_at": now.isoformat(), "updated_at": now.isoformat(),
        })

    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": ks_efektif,
        "jenis": payload.jenis,
        "judul_lainnya": str(payload.judul_lainnya or "").strip(),
        "nomor": nomor_final,
        "surat_id": surat_id,
        "tanggal": (str(payload.tanggal or "").strip()[:10]
                    or now.date().isoformat()),
        "pihak_pertama": pihak_pertama,
        "pihak_kedua": payload.pihak_kedua.model_dump(),
        "asset_ids": [a["id"] for a in aset],
        # Snapshot identitas utk dokumen (foto TIDAK disnapshot — diambil
        # saat render bila sertakan_foto).
        "aset": [{k: a.get(k) for k in ("id", "asset_code", "NUP", "asset_name",
                                        "brand", "model", "serial_number",
                                        "condition", "purchase_date",
                                        "purchase_price")} for a in aset],
        "jangka_dari": str(payload.jangka_dari or "").strip()[:10],
        "jangka_sampai": str(payload.jangka_sampai or "").strip()[:10],
        "penanggung_jawab_tambahan": [
            p.model_dump() for p in (payload.penanggung_jawab_tambahan or [])
            if str(p.nama or "").strip()],
        # Pilihan lampiran DIBEKUKAN pada dokumen, bukan dibaca dari kebijakan
        # saat mencetak: BAST yang sudah ditandatangani harus tercetak sama
        # persis kapan pun diunduh ulang.
        "surat_pernyataan": bool(payload.surat_pernyataan),
        # Dasar & saksi (khusus pengembalian almarhum; kosong utk jenis lain)
        "almarhum": (payload.almarhum.model_dump()
                     if payload.jenis == "pengembalian_almarhum" and payload.almarhum
                     else {}),
        "saksi": [s.model_dump() for s in _saksi],
        "tembusan": str(payload.tembusan or "").strip(),
        # Delegasi penyerahan a.n. KPB hanya relevan pada non-mutasi (mutasi
        # sudah otomatis ber-"Mengetahui KPB").
        "penyerah_atas_nama_kpb": (bool(payload.penyerah_atas_nama_kpb)
                                   and payload.jenis != "mutasi_pengguna"),
        "sertakan_foto": bool(payload.sertakan_foto),
        # Keputusan penyajian nilai DIBEKUKAN bersama dokumen: kebijakan satker
        # boleh berubah kemudian, tetapi BAST yang sudah ditandatangani harus
        # tercetak ulang persis seperti saat diterbitkan.
        "tampilkan_nilai": tampilkan_nilai_dokumen(settings,
                                                   payload.tampilkan_nilai),
        "terapkan_ke_aset": bool(payload.terapkan_ke_aset),
        "keterangan": str(payload.keterangan or "").strip(),
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
    }
    if sumber_revisi:
        record.update({
            "revisi_dari": sumber_revisi["id"],
            "revisi_dari_nomor": sumber_revisi.get("nomor") or "",
            "revisi_ke": int(sumber_revisi.get("revisi_ke") or 0) + 1,
            "revisi_mode": str(payload.revisi_mode),
            "revisi_alasan": str(payload.revisi_alasan).strip(),
        })
    # Validasi LUNAK penerima ke Master Pegawai (non-blocking): NIP tak
    # terdaftar hanya diberi peringatan — BAST tetap tersimpan.
    peringatan_pegawai = ""
    nip2 = str(record["pihak_kedua"].get("nip") or "").strip()
    if nip2:
        # Scope satker (REVIEW-9 R15): flag "terdaftar" + nama penerima harus
        # dari Master Pegawai SATKER INI, bukan seluruh instansi.
        peg = await db.pegawai.find_one(
            scope_query_field_satker(user, {"nip": nip2}),
            {"_id": 0, "nama": 1, "status": 1})
        record["pihak_kedua_terdaftar"] = bool(peg)
        if not peg:
            peringatan_pegawai = (f"NIP {nip2} belum terdaftar di Master "
                                  "Pegawai — periksa ejaan atau daftarkan dulu")
        else:
            from pegawai_utils import is_aktif, is_meninggal
            # Penerima MENINGGAL DUNIA → TOLAK (bukan sekadar peringatan):
            # secara hukum mustahil almarhum menerima serah terima. BAST lama
            # atas namanya tetap sah; yang diperlukan adalah serah terima BMN
            # almarhum kepada ahli waris/pengurus barang, bukan BAST baru
            # kepadanya.
            if is_meninggal(peg):
                raise HTTPException(
                    status_code=400,
                    detail=(f"{peg.get('nama') or nip2} berstatus Meninggal "
                            "Dunia di Master Pegawai — tidak dapat dijadikan "
                            "penerima serah terima. Gunakan alur pengembalian "
                            "BMN almarhum (penyerah: ahli waris/atasan) atau "
                            "pilih penerima lain."))
            # Pegawai pensiun/mutasi/nonaktif → peringatan lunak (tak memblokir).
            if not is_aktif(peg):
                st = str(peg.get("status") or "").strip() or "nonaktif"
                peringatan_pegawai = (f"Penerima ({peg.get('nama') or nip2}) "
                                      f"berstatus {st} di Master Pegawai — "
                                      "pastikan serah terima ini memang tepat")
    await db.bast_serah_terima.insert_one({**record})

    if sumber_revisi:
        # BAST lama ditandai TERGANTIKAN (arsipnya utuh; PDF-nya kelak
        # mencetak penanda telah direvisi/dicabut) — rantai versi lurus.
        await db.bast_serah_terima.update_one(
            {"id": sumber_revisi["id"]},
            {"$set": {"direvisi_oleh": record["id"],
                      "direvisi_oleh_nomor": record["nomor"],
                      "direvisi_pada": now.isoformat(),
                      "direvisi_mode": record["revisi_mode"]}})
        # Tautkan NOMOR AGENDA lewat relasi antar surat (SURAT-3B): nomor
        # lama otomatis ber-status "Berlaku dengan perubahan" (mengubah) atau
        # "Tidak Berlaku" (mencabut) di buku agenda — tanpa diketik siapa pun.
        if record.get("surat_id") and sumber_revisi.get("surat_id"):
            from routes.persuratan import catat_relasi_surat
            s_baru = await db.surat.find_one({"id": record["surat_id"]}, _PROJ)
            s_lama = await db.surat.find_one(
                {"id": sumber_revisi["surat_id"]}, _PROJ)
            if s_baru and s_lama:
                await catat_relasi_surat(
                    s_baru, s_lama, record["revisi_mode"],
                    f"Revisi BAST ke-{record['revisi_ke']}: "
                    f"{record['revisi_alasan']}",
                    user.get("username", "system"))
        await log_audit(
            "revisi_bast", "", username=user.get("username", "system"),
            detail=(f"BAST {sumber_revisi.get('nomor') or sumber_revisi['id']} "
                    f"di-{record['revisi_mode']} oleh {record['nomor'] or record['id']} "
                    f"(revisi ke-{record['revisi_ke']}: {record['revisi_alasan']})"))

    # Jejak BAST terakhir pada tiap aset (badge riwayat di UI) + efek data
    # handover langsung bila diminta.
    set_aset = {"bast_terakhir": {
        "id": record["id"], "jenis": payload.jenis, "nomor": nomor_final,
        "tanggal": record["tanggal"],
        "penerima": record["pihak_kedua"]["nama"]}}
    if payload.terapkan_ke_aset and payload.jenis == "mutasi_pengguna":
        set_aset.update({
            "user": record["pihak_kedua"]["nama"],
            "pengguna_nip": record["pihak_kedua"].get("nip", ""),
            "pengguna_jabatan": record["pihak_kedua"].get("jabatan", ""),
        })
    elif payload.terapkan_ke_aset and payload.jenis in _JENIS_PENGEMBALIAN:
        set_aset.update({"user": "", "pengguna_nip": "",
                         "pengguna_jabatan": "", "pengguna_melekat_ke": ""})
    await db.assets.update_many(
        {"id": {"$in": record["asset_ids"]}, "dihapus": {"$ne": True}},
        {"$set": {**set_aset, "updated_at": now.isoformat()},
         "$inc": {"version": 1}})

    efek = ""
    if payload.terapkan_ke_aset and payload.jenis == "mutasi_pengguna":
        efek = f" (pengguna aset dialihkan ke {record['pihak_kedua']['nama']})"
    elif payload.terapkan_ke_aset and payload.jenis in _JENIS_PENGEMBALIAN:
        efek = " (pengguna aset dikosongkan)"
    await log_audit("buat_bast", "", username=user.get("username", "system"),
                    detail=(f"BAST {JENIS_BAST[payload.jenis]} — "
                            f"{len(aset)} aset → {record['pihak_kedua']['nama']}"
                            f"{efek}"
                            + (f"; nomor otomatis {nomor_final}" if surat_id else "")))
    respons = {**record, "peringatan_pegawai": peringatan_pegawai}
    if idem_key:
        await store_idempotent_response(idem_key, respons)
    return respons


@bast_router.post("/bast/{bast_id}/bukti")
async def unggah_bukti_bast(bast_id: str, file: UploadFile = File(...),
                            user: dict = Depends(require_writer)):
    """Unggah scan BAST bertanda tangan (PDF/gambar ≤10MB) → tersimpan di
    GridFS; bila nomor BAST berasal dari booking otomatis, nomor agenda di
    Registrasi Persuratan langsung DISAHKAN (menutup siklus dua langkah)."""
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    await pastikan_akses_dok_satker(user, b)
    nama = str(file.filename or "").lower()
    if not nama.endswith((".pdf", ".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400,
                            detail="Berkas harus PDF/JPG/PNG")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 10MB")

    tipe = "application/pdf" if nama.endswith(".pdf") else "image/jpeg"
    # GERBANG KOMPRESI — bukti serah terima (pindaian PDF atau foto).
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        data, nama=file.filename, content_type=tipe)

    now = datetime.now(timezone.utc).isoformat()
    bukti_lama = (b.get("bukti") or {}).get("file_id")
    res = await db.bast_serah_terima.update_one(
        {"id": bast_id},
        {"$set": {"bukti": {"file_id": str(file_id), "filename": file.filename,
                            "content_type": tipe,
                            "diunggah_pada": now,
                            "oleh": user.get("username", "system")},
                  # Bukti ttd baru = serah terima sah kembali → cabut penanda
                  # "TTD dibatalkan" dari pembatalan e-sign sebelumnya (sejajar
                  # jalur re-sign). Tanpa ini, unggah bukti valid justru
                  # membalik metrik jadi "TTD BAST dibatalkan".
                  "tt_dicabut": False}})
    if res.matched_count == 0:
        # BAST terhapus di sela — jangan tinggalkan blob yatim di GridFS.
        from shared_utils import delete_document_from_gridfs
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    # Bukti lama diganti → hapus blob lama (cegah orphan GridFS).
    if bukti_lama and str(bukti_lama) != str(file_id):
        from shared_utils import delete_document_from_gridfs
        await delete_document_from_gridfs(str(bukti_lama))

    # Bukti ttd = BAST sah → tautkan ke SEMUA aset objeknya (bast_file_id)
    # sehingga metrik kelengkapan pemegang ("BAST x/y", badge Lengkap) naik —
    # sebelumnya generator BAST tak pernah mengisi field ini (audit G2 #1).
    # Snapshot kode+nama per aset → deteksi BAST usang bila berubah kemudian.
    from pymongo import UpdateOne

    from penggunaan_utils import snapshot_bast
    _aset_bast = await db.assets.find(
        {"id": {"$in": b.get("asset_ids") or []}, "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_code": 1, "asset_name": 1}).to_list(100000)
    if _aset_bast:
        await db.assets.bulk_write([
            UpdateOne({"id": a["id"]},
                      {"$set": {"bast_file_id": str(file_id), "updated_at": now,
                                "bast_snapshot": snapshot_bast(a)},
                       "$inc": {"version": 1}})
            for a in _aset_bast], ordered=False)
    # Cabut penanda "TTD dibatalkan" pada aset yang BAST-terakhirnya BAST ini
    # (presisi — tak menyentuh aset dgn BAST lebih baru). Sejajar jalur re-sign.
    await db.assets.update_many(
        {"bast_terakhir.id": bast_id, "bast_terakhir.tt_dicabut": True},
        {"$set": {"bast_terakhir.tt_dicabut": False}})

    # Nomor agenda dibooking → otomatis disahkan (bukti ttd = pengesahan).
    disahkan = False
    if str(b.get("surat_id") or "").strip():
        res = await db.surat.find_one_and_update(
            {"id": b["surat_id"], "status": "dibooking"},
            {"$set": {"status": "disahkan", "disahkan_pada": now,
                      "disahkan_oleh": user.get("username", "system"),
                      "updated_at": now},
             "$push": {"riwayat": {"status": "disahkan", "tanggal": now,
                                   "oleh": user.get("username", "system"),
                                   "catatan": "bukti ttd BAST diunggah"}}})
        disahkan = res is not None
    await log_audit("bukti_bast", "", username=user.get("username", "system"),
                    detail=(f"Unggah bukti ttd BAST {b.get('nomor') or bast_id[:8]}"
                            + (" — nomor agenda disahkan" if disahkan else "")))
    return {"ok": True, "nomor_agenda_disahkan": disahkan}


@bast_router.post("/bast/{bast_id}/foto-serah-terima")
async def unggah_foto_serah_terima(bast_id: str, file: UploadFile = File(...),
                                   asset_id: str = Form(default=""),
                                   berlaku_semua: bool = Form(default=False),
                                   user: dict = Depends(require_writer)):
    """Unggah FOTO dokumentasi serah terima barang untuk lampiran BAST.

    Dua mode, sesuai kenyataan di lapangan:

    - **Per barang** (`asset_id` diisi) — tiap aset punya fotonya sendiri;
      di lampiran, foto ini berdampingan dengan foto sampul aset tersebut.
    - **Satu untuk semua** (`berlaku_semua=true`) — satu foto perwakilan
      mewakili seluruh barang dalam BAST ini; dicetak SEKALI di akhir
      lampiran, bukan diulang pada tiap aset.

    Berbeda dari `/bukti` yang menyimpan SCAN BAST BERTANDA TANGAN (dan
    karenanya mengesahkan nomor agenda), endpoint ini murni dokumentasi foto
    dan TIDAK menyentuh status persuratan.
    """
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    await pastikan_akses_dok_satker(user, b)

    aid = str(asset_id or "").strip()
    if not aid and not berlaku_semua:
        raise HTTPException(
            status_code=400,
            detail="Pilih barangnya, atau tandai berlaku untuk semua barang")
    if aid and aid not in (b.get("asset_ids") or []):
        raise HTTPException(status_code=400,
                            detail="Aset itu bukan objek BAST ini")

    nama = str(file.filename or "").lower()
    if not nama.endswith((".jpg", ".jpeg", ".png", ".webp")):
        raise HTTPException(status_code=400,
                            detail="Foto harus JPG/PNG/WebP")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 10MB")
    # `cek_magic_gambar(data, ext)` — WAJIB dua argumen (lihat shared_utils);
    # memanggilnya dengan satu argumen membuat SETIAP unggahan 500.
    import os as _os
    if not cek_magic_gambar(data, _os.path.splitext(nama)[1]):
        raise HTTPException(status_code=400,
                            detail="Berkas bukan gambar yang sah")

    tipe = "image/png" if nama.endswith(".png") else (
        "image/webp" if nama.endswith(".webp") else "image/jpeg")
    # GERBANG KOMPRESI — foto serah terima ikut rantai berjenjang.
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        data, nama=file.filename, content_type=tipe,
        metadata={"kind": "foto_serah_terima", "bast_id": bast_id,
                  "asset_id": aid})

    lama = (str(b.get("foto_serah_terima_bersama") or "") if berlaku_semua
            else str((b.get("foto_serah_terima") or {}).get(aid) or ""))
    kunci = ("foto_serah_terima_bersama" if berlaku_semua
             else f"foto_serah_terima.{aid}")
    res = await db.bast_serah_terima.update_one(
        {"id": bast_id},
        {"$set": {kunci: str(file_id),
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        from shared_utils import delete_document_from_gridfs
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    # Ganti foto → buang blob lama supaya GridFS tidak menumpuk yatim.
    if lama and lama != str(file_id):
        from shared_utils import delete_document_from_gridfs
        await delete_document_from_gridfs(lama)

    await log_audit("foto_serah_terima_bast", "",
                    username=user.get("username", "system"),
                    detail=(f"Foto serah terima BAST {b.get('nomor') or bast_id[:8]}"
                            + (" (berlaku semua barang)" if berlaku_semua
                               else f" — aset {aid[:8]}")))
    return {"ok": True, "file_id": str(file_id),
            "berlaku_semua": bool(berlaku_semua), "asset_id": aid}


@bast_router.delete("/bast/{bast_id}/foto-serah-terima")
async def hapus_foto_serah_terima(bast_id: str, asset_id: str = "",
                                  berlaku_semua: bool = False,
                                  user: dict = Depends(require_writer)):
    """Hapus foto serah terima (per barang atau yang berlaku untuk semua)."""
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    await pastikan_akses_dok_satker(user, b)
    aid = str(asset_id or "").strip()
    lama = (str(b.get("foto_serah_terima_bersama") or "") if berlaku_semua
            else str((b.get("foto_serah_terima") or {}).get(aid) or ""))
    if not lama:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    kunci = ("foto_serah_terima_bersama" if berlaku_semua
             else f"foto_serah_terima.{aid}")
    await db.bast_serah_terima.update_one({"id": bast_id}, {"$unset": {kunci: ""}})
    from shared_utils import delete_document_from_gridfs
    await delete_document_from_gridfs(lama)
    return {"ok": True}


@bast_router.get("/bast/{bast_id}/foto-serah-terima/{file_id}")
async def lihat_foto_serah_terima(bast_id: str, file_id: str,
                                  user: dict = Depends(require_user_or_query_token)):
    """Stream satu foto serah terima (pratinjau di UI)."""
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    await pastikan_akses_dok_satker(user, b)
    sah = set(str(v) for v in (b.get("foto_serah_terima") or {}).values() if v)
    if str(b.get("foto_serah_terima_bersama") or ""):
        sah.add(str(b["foto_serah_terima_bersama"]))
    if str(file_id) not in sah:
        # Cegah endpoint ini jadi pembaca GridFS serba-guna.
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    from shared_utils import get_document_from_gridfs
    data = await get_document_from_gridfs(str(file_id))
    if not data:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return StreamingResponse(io.BytesIO(data), media_type="image/jpeg",
                             headers={"Cache-Control": "private, max-age=3600",
                                      "X-Content-Type-Options": "nosniff"})


@bast_router.get("/bast/{bast_id}/bukti")
async def unduh_bukti_bast(bast_id: str,
                           _user: dict = Depends(require_user_or_query_token)):
    """Stream scan bukti ttd (dipakai pratinjau window.open ber-token)."""
    from shared_utils import get_document_from_gridfs
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b or not (b.get("bukti") or {}).get("file_id"):
        raise HTTPException(status_code=404, detail="Bukti belum diunggah")
    await pastikan_akses_dok_satker(_user, b)
    data = await get_document_from_gridfs(b["bukti"]["file_id"])
    if not data:
        raise HTTPException(status_code=404, detail="Berkas bukti tidak ditemukan")
    return StreamingResponse(
        io.BytesIO(data), media_type=b["bukti"].get("content_type", "application/pdf"),
        headers={"Content-Disposition":
                 f'inline; filename="{b["bukti"].get("filename", "bukti.pdf")}"',
                 "X-Content-Type-Options": "nosniff"})


@bast_router.get("/bast/{bast_id}/pdf")
async def bast_pdf(bast_id: str, nilai: str = "",
                   _user: dict = Depends(require_user_or_query_token)):
    """Render BAST 1-2 halaman + lampiran foto opsional.

    `?nilai=0/1` mencetak salinan TANPA/DENGAN kolom Nilai Perolehan tanpa
    mengubah data — satu BAST bisa dicetak dua versi (arsip ber-nilai,
    salinan pegawai tanpa nilai). Tanpa parameter: ikut pilihan yang
    dibekukan pada dokumen, lalu kebijakan satker."""
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, Image as RLImage

    from pelaporan_utils import narasi_hari_tanggal
    from kodefikasi_utils import kelompokkan_per_bidang as _kelompokkan_per_bidang
    from routes.reports import (
        _baris_sekat_bidang, _blok_tembusan, _fit_col_widths, _fmt_tanggal_id,
        _get_report_styles, _gaya_sekat_bidang, _gridfs_photo_data_uri,
        _identity_table, _kop_surat_flowables, _page_footer_factory,
        _peta_subsub_kelompok, _peta_uraian_bidang, _sel_identitas_barang,
        _sel_uraian_barang, _signature_block, _std_doc, _std_table_style,
        _tempat_tanggal_laporan, _title_block,
    )

    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker, pengaturan_kop
    await pastikan_akses_dok_satker(_user, b)
    # Kop mengikuti SATKER pembuat BAST (resolusi satker → global).
    settings = await pengaturan_kop(kode_satker=b.get("kode_satker"))
    # Nilai perolehan: parameter unduhan → pilihan yang dibekukan pada dokumen
    # → kebijakan satker.
    from satker_utils import pilihan_nilai_dari_query, tampilkan_nilai_dokumen
    _pilihan = pilihan_nilai_dari_query(nilai)
    if _pilihan is None and b.get("tampilkan_nilai") is not None:
        _pilihan = bool(b.get("tampilkan_nilai"))
    tampil_nilai = tampilkan_nilai_dokumen(settings, _pilihan)

    from xml.sax.saxutils import escape as _esc
    judul_jenis = (b.get("judul_lainnya") or JENIS_BAST.get(b.get("jenis"), "")
                   if b.get("jenis") == "lainnya"
                   else JENIS_BAST.get(b.get("jenis"), ""))
    # Baris kedua judul: hindari dobel "SERAH TERIMA SERAH TERIMA ..." bila
    # judul kustom sudah diawali frasa itu.
    judul_baris2 = judul_jenis
    if judul_baris2.lower().startswith("serah terima"):
        judul_baris2 = judul_baris2[len("serah terima"):].strip() or judul_jenis
    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    body = st['Body']

    # Gaya khusus naskah BAST: isi pasal HITAM rata kiri-kanan (bukan Small
    # abu-abu metadata) + judul pasal tebal-tengah ber-jarak — resmi & lega.
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    # Kerapatan naskah: jarak antar butir/pasal dipadatkan (bukan ukuran
    # huruf — keterbacaan dokumen resmi dijaga) agar seluruh jenis BAST muat
    # 2 halaman termasuk tanda tangan.
    isi = ParagraphStyle('BastIsi', parent=body, fontSize=8.6, leading=11.0,
                         alignment=TA_JUSTIFY, textColor=HexColor("#111827"),
                         spaceAfter=0.6)
    lbl_pasal = ParagraphStyle('BastPasal', parent=body, fontSize=9,
                               leading=11.0, alignment=TA_CENTER,
                               spaceBefore=2.5, spaceAfter=1.0,
                               textColor=HexColor("#111827"))
    ket = ParagraphStyle('BastKet', parent=isi, fontSize=8.2, leading=10.4)

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("BERITA ACARA SERAH TERIMA\n"
                           + _esc(judul_baris2.upper()),
                           nomor=b.get("nomor") or "......./......./........"))

    # ── Penanda RANTAI REVISI (SURAT-3C) — dokumen bercerita jujur ─────────
    # BAST tergantikan mencetak peringatan (cetakan lama yang beredar tak
    # boleh dikira masih berlaku); BAST pengganti menyebut revisi ke-berapa
    # atas nomor lama beserta alasannya.
    if b.get("direvisi_oleh"):
        _mode_lbl = ("DICABUT" if b.get("direvisi_mode") == "mencabut"
                     else "DIREVISI")
        el.append(Paragraph(
            f"<b>DOKUMEN INI TELAH {_mode_lbl}</b> — digantikan oleh BAST "
            f"Nomor {_esc(b.get('direvisi_oleh_nomor') or '(tanpa nomor)')} "
            f"tanggal {_esc(_fmt_tanggal_id(str(b.get('direvisi_pada') or '')[:10]) or '-')}. "
            "Gunakan dokumen penggantinya.",
            ParagraphStyle('BastRevisiWarn', parent=isi,
                           textColor=HexColor("#b91c1c"),
                           alignment=TA_CENTER, spaceAfter=3)))
    if b.get("revisi_dari"):
        el.append(Paragraph(
            f"Revisi ke-{int(b.get('revisi_ke') or 1)} — "
            f"{'mencabut' if b.get('revisi_mode') == 'mencabut' else 'mengubah'} "
            f"BAST Nomor {_esc(b.get('revisi_dari_nomor') or '(tanpa nomor)')}"
            + (f". Alasan: {_esc(b.get('revisi_alasan'))}"
               if b.get("revisi_alasan") else ""),
            ParagraphStyle('BastRevisiInfo', parent=ket,
                           alignment=TA_CENTER, spaceAfter=3)))

    jenis_awal = b.get("jenis")
    nar = narasi_hari_tanggal(b.get("tanggal"))
    tempat = str(settings.get("tempat_laporan")
                 or settings.get("alamat_instansi") or "").strip()
    frasa = (f"Pada hari ini, {nar['hari']}, tanggal {nar['tanggal_terbilang']}, "
             f"bulan {nar['bulan']}, tahun {nar['tahun_terbilang']} "
             f"({_fmt_tanggal_id(b.get('tanggal'))})" if nar else "Pada hari ini")
    if tempat:
        frasa += f", bertempat di {_esc(tempat.splitlines()[0])}"
    el.append(Paragraph(f"{frasa}, kami yang bertanda tangan di bawah ini:", isi))
    el.append(Spacer(1, 1.5 * rl_mm))

    p1, p2 = b.get("pihak_pertama") or {}, b.get("pihak_kedua") or {}
    from reportlab.platypus import TableStyle as _TS
    _garis = HexColor("#9aa5b1")

    def _kolom_pihak(peran, sebutan, ph):
        """Identitas satu pihak: label SEJAJAR (tabel label:nilai) + baris
        'selanjutnya disebut ...' — mengikuti anatomi BAST resmi.

        Label nomor identitas PINTAR: NRP terdeteksi → 'NRP'; NIK Non-ASN
        TIDAK dicetak (baris dilewati — privasi, permintaan pemilik)."""
        from pegawai_utils import deteksi_identitas, label_nomor_identitas
        nomor = str(ph.get("nip") or "").strip()
        det = deteksi_identitas(nomor)
        if det["jenis"] == "nik":
            baris_nomor = None  # NIK tidak dicetak di BAST
        else:
            lbl_pintar = label_nomor_identitas(nomor) if nomor else ""
            # Nomor berformat TAK DIKENAL tak lagi ditebak "NIP": deteksinya
            # sendiri menyediakan label netral ("No. Identitas"). Menebak di
            # sini berarti dokumen resmi menamai nomor orang dengan nama yang
            # bukan namanya — cacat yang sama dengan garis tanda tangan kosong.
            baris_nomor = (lbl_pintar or det["label"], ph.get("nip"))
        rows = []
        pasangan = [("Nama", ph.get("nama"))]
        if baris_nomor:
            pasangan.append(baris_nomor)
        pasangan += [("Jabatan", ph.get("jabatan")),
                     ("Alamat", ph.get("alamat"))]
        for lbl, val in pasangan:
            rows.append([Paragraph(lbl, ket),
                         Paragraph(f": <b>{_esc(str(val or '-'))}</b>", ket)])
        dalam = Table(rows, colWidths=[46, doc.width * 0.5 - 46 - 14])
        dalam.setStyle(_TS([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5)]))
        return [Paragraph(f"<b>{peran}</b>", ket), dalam,
                Paragraph(f"<i>— selanjutnya disebut <b>{sebutan}</b> —</i>", ket)]

    tp = Table([[
        _kolom_pihak("PIHAK KESATU (yang menyerahkan)"
                     if jenis_awal not in _JENIS_PENGEMBALIAN
                     else "PIHAK KESATU (yang menerima)", "PIHAK KESATU", p1),
        _kolom_pihak("PIHAK KEDUA (yang menerima)"
                     if jenis_awal not in _JENIS_PENGEMBALIAN
                     else "PIHAK KEDUA (yang menyerahkan)", "PIHAK KEDUA", p2),
    ]], colWidths=[doc.width * 0.5, doc.width * 0.5])
    tp.setStyle(_TS([
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
    arah = ("PIHAK KEDUA mengembalikan kepada PIHAK KESATU"
            if jenis_awal in _JENIS_PENGEMBALIAN
            else "PIHAK KESATU dan PIHAK KEDUA — secara bersama-sama disebut "
                 "PARA PIHAK — sepakat melakukan serah terima")
    # Dasar hukum dirapatkan menjadi SATU paragraf mengalir (dulu daftar
    # bernomor 5 baris): isi hukumnya sama persis, ruang yang dihemat dipakai
    # agar seluruh naskah muat 2 halaman.
    el.append(Paragraph(
        f"{arah} {_esc(judul_jenis)}, berdasarkan {DASAR_HUKUM_RINGKAS}.",
        isi))
    el.append(Spacer(1, 1.2 * rl_mm))

    # PASAL 1 — objek serah terima (tabel multi-aset + nilai + total)
    el.append(Paragraph("<b>PASAL 1 — OBJEK SERAH TERIMA</b>", lbl_pasal))
    kalimat1 = ("PIHAK KEDUA menyerahkan kembali dan PIHAK KESATU menerima"
                if b.get("jenis") in _JENIS_PENGEMBALIAN
                else "PIHAK KESATU menyerahkan dan PIHAK KEDUA menerima penyerahan")
    el.append(Paragraph(
        f"{kalimat1} Barang Milik Negara dengan rincian sebagai berikut:", isi))
    # Sekat pembagi per BIDANG kode barang; di dalam kelompok barang terurut
    # menurut kode barang lalu NUP TERKECIL (dulu urutan pilih pengguna).
    # Uraian SUB-SUB KELOMPOK ditampilkan hanya bila TABEL masih pendek —
    # diukur dari jumlah BARIS (aset + sekat), bukan jumlah aset saja. Kalau
    # diukur dari aset saja, BAST 4 barang di 4 bidang (8 baris) justru lebih
    # tinggi daripada BAST 6 barang di 2 bidang dan menembus halaman ketiga.
    # Maknanya TIDAK hilang saat dilepas: sub-sub kelompok adalah turunan
    # (lookup) kode barang yang tetap tercetak pada tiap baris.
    # Ambang ini DIUKUR, bukan dikira-kira: dengan sub-sub kelompok tercetak
    # pada tiap baris, BAST 13 aset lintas 5 bidang (18 baris) masih dua
    # halaman; 14 aset (19 baris) menembus halaman ketiga. Muatan wajib mandat
    # 12 aset karena itu SELALU membawa sub-sub kelompoknya.
    #
    # Sebelumnya ambangnya 6 baris — jauh lebih ketat daripada yang sebenarnya
    # muat, sehingga BAST 6 aset satu bidang (7 baris) sudah kehilangan nama
    # sub-sub kelompoknya sementara JUDUL KOLOMNYA tetap menjanjikannya.
    # Itulah yang dilaporkan pemilik.
    _AMBANG_BARIS_SUBSUB = 18
    from kodefikasi_utils import normalize_kode as _norm
    from pembukuan_utils import parse_harga as _ph
    # Gaya SEL KHUSUS tabel BAST: sedikit lebih kecil & rapat dari gaya
    # laporan umum (8.5/11 → 7.8/9.6). Hanya berlaku pada tabel objek serah
    # terima dokumen ini — laporan lain tak tersentuh — dan inilah yang
    # membuat BAST ber-banyak aset tetap 2 halaman tanpa membuang kolom.
    st = dict(st)
    # BAST yang membawa tabel penanggung jawab tambahan (Pasal 2) merapatkan
    # tabel asetnya SATU TAKIK lagi. Alasannya diukur, bukan dikira-kira: pada
    # muatan wajib 12 aset, sisa ruang di kaki halaman kedua hanya ~25 pt —
    # tak cukup bahkan untuk kepala tabel plus satu baris. Merapatkan tabel
    # aset mendorong satu butir Pasal 2 naik ke halaman pertama, dan ruang
    # yang ditinggalkannya di halaman kedua itulah tempat tabel penanggung
    # jawab berdiri. Inilah "memaksimalkan kekosongan yang ada" yang diminta.
    _rapat_pj = bool(b.get("penanggung_jawab_tambahan"))
    _ukuran_sel = 7.2 if _rapat_pj else 7.8
    _leading_sel = 8.7 if _rapat_pj else 9.6
    for _k in ('Cell', 'CellCenter', 'CellRight'):
        if _k in st:
            st[_k] = ParagraphStyle(f'BastSel{_k}', parent=st[_k],
                                    fontSize=_ukuran_sel, leading=_leading_sel)
    st['TableHeader'] = ParagraphStyle('BastSelHead', parent=st['TableHeader'],
                                       fontSize=_ukuran_sel,
                                       leading=_leading_sel)
    # Baris sekat kelompok bidang: satu baris pendek, tak boleh memakan ruang
    # sebesar baris barang (batas 2 halaman).
    st['CellSekat'] = ParagraphStyle('BastSekat', parent=st['Cell'],
                                     fontSize=7.4, leading=8.8)
    async def _tabel_objek(daftar):
        """Tabel objek BMN berkelompok per BIDANG → (flowable, peta_urut).

        SATU pembangun untuk dua tempat: tabel Pasal 1 dan daftar BMN pada
        lampiran Surat Pernyataan Tanggung Jawab. Menyalinnya berarti dua
        tabel yang menyusut berbeda saat kolom berubah — dan yang membaca
        pernyataan tak punya cara tahu tabel mana yang benar.

        `peta_urut` memetakan id aset → nomor urut SEBAGAIMANA TERCETAK pada
        tabel itu; kolom "No. BMN" tabel penanggung jawab memakainya supaya
        cukup menulis "1, 4, 7". Direkam di dalam loop yang benar-benar
        mencetak nomornya — menghitung ulang urutan pengelompokan bidang di
        tempat kedua adalah cara paling pasti melahirkan rujukan yang menunjuk
        barang yang SALAH tanpa satu pun galat.
        """
        daftar = list(daftar or [])
        _klp = _kelompokkan_per_bidang(daftar)
        # Uraian SUB-SUB KELOMPOK hanya bila TABEL masih pendek — diukur dari
        # jumlah BARIS (aset + sekat), bukan jumlah aset saja. Kalau diukur
        # dari aset saja, BAST 4 barang di 4 bidang (8 baris) justru lebih
        # tinggi daripada BAST 6 barang di 2 bidang dan menembus halaman
        # ketiga. Maknanya TIDAK hilang saat dilepas: sub-sub kelompok adalah
        # turunan (lookup) kode barang yang tetap tercetak pada tiap baris.
        _kode = [x.get("asset_code") for x in daftar]
        _subsub = ({} if len(daftar) + len(_klp) > _AMBANG_BARIS_SUBSUB
                   else await _peta_subsub_kelompok(_kode))
        _uraian_bidang = await _peta_uraian_bidang(_kode)
        # JUDUL kolom mengikuti isi tabel INI, bukan janji tetap. Judul yang
        # menyebut "Sub-sub Kelompok" di atas kolom yang tak memuatnya membuat
        # pembaca mengira datanya hilang — dan pada dokumen resmi, mengira
        # data hilang sama buruknya dengan data yang benar-benar hilang.
        # Dihitung di DALAM sini karena lampiran Surat Pernyataan memakai
        # pembangun yang sama dengan daftar yang lebih pendek: satu tabel bisa
        # memuat sub-sub sementara tabel lain di dokumen yang sama tidak.
        kepala = ["No",
                  ("Identitas Barang<br/>(Sub-sub Kelompok · Kode · NUP)"
                   if _subsub else "Identitas Barang<br/>(Kode · NUP)"),
                  "Uraian Barang<br/>(Nama · Merk/Tipe/Spesifikasi)", "Tahun",
                  "Kondisi"]
        lebar = [24, 130, 168, 36, 50]
        if tampil_nilai:
            kepala.append("Nilai Perolehan (Rp)")
            lebar.append(78)
        data = [[Paragraph(h, st['TableHeader']) for h in kepala]]
        total_nilai = 0.0
        _baris_sekat, urut, i = [], {}, 0
        for _kode_bidang, _isi in _klp:
            _baris_sekat.append(len(data))
            data.append(_baris_sekat_bidang(_kode_bidang,
                                            _uraian_bidang.get(_kode_bidang, ""),
                                            len(_isi), len(kepala), st))
            for a in _isi:
                i += 1
                urut[str(a.get("id") or "")] = i
                tgl = str(a.get("purchase_date") or "")
                tahun = tgl[:4] if len(tgl) >= 4 and tgl[:4].isdigit() else (
                    tgl[-4:] if len(tgl) >= 4 and tgl[-4:].isdigit() else "-")
                nilai = _ph(a.get("purchase_price"))
                total_nilai += nilai
                baris = [
                    Paragraph(str(i), st['CellCenter']),
                    _sel_identitas_barang(
                        a, _subsub.get(_norm(a.get("asset_code")), ""), st),
                    _sel_uraian_barang(a, st),
                    Paragraph(tahun, st['CellCenter']),
                    Paragraph(a.get("condition") or "-", st['CellCenter']),
                ]
                if tampil_nilai:
                    baris.append(Paragraph(
                        f"{nilai:,.0f}".replace(",", ".") if nilai else "-",
                        st['CellRight'] if 'CellRight' in st else st['CellCenter']))
                data.append(baris)
        if tampil_nilai:
            data.append([Paragraph("", st['Cell']),
                         Paragraph("<b>JUMLAH</b>", st['Cell']), Paragraph("", st['Cell']),
                         Paragraph("", st['Cell']), Paragraph("", st['Cell']),
                         Paragraph(f"<b>{total_nilai:,.0f}</b>".replace(",", "."),
                                   st['CellRight'] if 'CellRight' in st else st['CellCenter'])])
        t = Table(data, colWidths=_fit_col_widths(lebar, doc.width), repeatRows=1)
        # Padding baris dirapatkan KHUSUS tabel BAST (3 → 1.5) — tiap baris
        # aset hemat ~1,5 mm sehingga BAST ber-banyak aset tetap muat 2 halaman.
        _pad_sel = 0.4 if _rapat_pj else 1.2
        t.setStyle(_std_table_style(zebra=True, total_row=tampil_nilai, extra=[
            ('TOPPADDING', (0, 0), (-1, -1), _pad_sel),
            ('BOTTOMPADDING', (0, 0), (-1, -1), _pad_sel),
        ] + _gaya_sekat_bidang(_baris_sekat, padding=0.3)))
        return t, urut

    _t_objek, _urut_cetak = await _tabel_objek(b.get("aset") or [])
    el.append(_t_objek)
    if not tampil_nilai:
        # Nyatakan terus terang MENGAPA kolom nilai absen — pembaca dokumen
        # resmi tak boleh menduga-duga apakah nilainya nihil atau disembunyikan.
        el.append(Paragraph(
            "Nilai perolehan BMN tidak ditampilkan pada salinan ini sesuai "
            "kebijakan penyajian dokumen satuan kerja; data nilai tetap "
            "tercatat pada Daftar Barang Kuasa Pengguna.", ket))

    # PASAL 2+ — ketentuan sesuai jenis. Tiap pasal dibungkus KeepTogether
    # agar judul tidak yatim terpisah dari isinya saat pecah halaman.
    from reportlab.platypus import KeepTogether
    nomor_pasal = 2

    def pasal(judul, isi_list, tambahan=None):
        """`tambahan`: flowable yang IKUT ke dalam KeepTogether pasal ini.

        Ikut, bukan ditempel sesudahnya — tabel yang terpisah dari pasalnya
        saat pecah halaman akan berdiri sendiri tanpa judul, dan pembaca
        dokumen resmi tak punya cara tahu tabel itu milik pasal mana.
        """
        nonlocal nomor_pasal
        butir = [Paragraph((f"({i}) {teks}" if len(isi_list) > 1 else teks), isi)
                 for i, teks in enumerate(isi_list, 1)]
        # Yang WAJIB menyatu hanya judul dengan butir PERTAMANYA — judul pasal
        # yang yatim di kaki halaman memang tak boleh terjadi. Mengunci
        # SELURUH pasal justru mahal: satu pasal berbutir panjang yang tak
        # muat di sisa halaman melompat utuh ke halaman berikutnya dan
        # meninggalkan ruang kosong sebesar apa pun sisa itu. Pada naskah yang
        # dibatasi dua halaman, ruang terbuang itulah yang lebih dulu habis.
        el.append(KeepTogether(
            [Paragraph(f"<b>PASAL {nomor_pasal} — {judul}</b>", lbl_pasal)]
            + butir[:1]))
        el.extend(butir[1:])
        el.extend(tambahan or [])
        nomor_pasal += 1

    jenis = b.get("jenis")
    # ── PASAL 2 — TANGGUNG JAWAB DAN PENGGUNAAN ────────────────────────────
    # Gabungan dari lima pasal lama yang bermakna sama/bersambung: keadaan
    # barang, tanggung jawab per jenis, status pencatatan, jangka waktu, dan
    # konteks waktu penggunaan. Isi hukumnya utuh; yang dibuang hanya
    # pengulangan — syarat agar seluruh naskah muat 2 halaman.
    from bast_pasal import (baris_pj_tambahan, bmn_tanpa_pj, butir_khusus_bidang,
                            butir_risiko, butir_waktu, label_unit,
                            rujukan_pasal1, sisa_bidang)

    _pj_baris, _ada_bmn = [], False
    tj = ["Serah terima meliputi fisik barang beserta kelengkapan/dokumen "
          "pendukungnya dalam keadaan sebagaimana kolom Kondisi pada Pasal 1, "
          "yang telah diperiksa bersama oleh PARA PIHAK sebelum Berita Acara "
          "ini ditandatangani."]
    if jenis == "mutasi_pengguna":
        tj.append(
            "Terhitung sejak penandatanganan, tanggung jawab penggunaan, "
            "pengamanan, dan pemeliharaan BMN beralih dari PIHAK KESATU "
            "kepada PIHAK KEDUA; BMN tetap tercatat sebagai Barang Milik "
            "Negara pada satuan kerja dan mutasi ini hanya mengubah "
            "pencatatan pemegang pada daftar barang/DBR/KIB.")
    elif jenis == "operasional_unit":
        # Dulu daftar penanggung jawab dirangkai jadi ekor kalimat ini —
        # tanpa NIP/NIK dan tanpa menyebut barang siapa yang mana. Kini ia
        # tabel tersendiri (dirakit di bawah, ikut ke dalam pasal yang sama).
        _pj_baris = baris_pj_tambahan(b.get("penanggung_jawab_tambahan"),
                                      b.get("aset"))
        _ada_bmn = any(r["aset"] for r in _pj_baris)
        tj.append(
            "Terhitung sejak penandatanganan, PIHAK KEDUA selaku penanggung "
            "jawab unit bertanggung jawab atas penggunaan, pengamanan, dan "
            "pemeliharaan BMN yang dipakai bersama; BMN tetap berada pada "
            "unit/tempat kerja, pemakaian bergilir diatur PIHAK KEDUA dengan "
            "kejelasan penguasa barang pada satu waktu, dan pergantian "
            "penanggung jawab dilakukan melalui serah terima baru."
            + ("" if not _pj_baris else
               " Penanggung jawab pada unit/tempat tugas tercantum dalam "
               "tabel berikut" + ("; kolom No. BMN merujuk nomor urut BMN "
                                  "pada Pasal 1." if _ada_bmn else ".")))
    elif jenis == "penggunaan_sementara":
        tj.append(
            "Penggunaan sementara TIDAK mengalihkan status penggunaan — BMN "
            "tetap tercatat pada Daftar Barang Pengguna PIHAK KESATU — "
            f"berlaku {_fmt_tanggal_id(b.get('jangka_dari')) or '…'} s.d. "
            f"{_fmt_tanggal_id(b.get('jangka_sampai')) or '…'} dan dapat "
            "diperpanjang atas persetujuan pejabat berwenang; biaya "
            "pemeliharaan dan pengamanan selama jangka waktu tersebut "
            "dibebankan kepada PIHAK KEDUA kecuali diperjanjikan lain, dan "
            "pada saat berakhir BMN diserahkan kembali dalam keadaan baik "
            "melalui Berita Acara pengembalian.")
    elif jenis in _JENIS_PENGEMBALIAN:
        tj.append(
            "PIHAK KEDUA menyatakan telah mengembalikan seluruh BMN tersebut "
            "dan PIHAK KESATU telah memeriksa fisiknya; terhitung sejak "
            "penandatanganan, tanggung jawab penggunaan, pengamanan, dan "
            "pemeliharaan beralih kepada PIHAK KESATU dan pencatatan pemegang "
            "pada daftar barang satuan kerja dimutakhirkan.")
    else:   # penggunaan_melekat & lainnya
        tj.append(
            "Terhitung sejak penandatanganan, PIHAK KEDUA bertanggung jawab "
            "penuh atas penggunaan, pengamanan, dan pemeliharaan BMN untuk "
            "kepentingan kedinasan, dan wajib mengembalikannya dalam kondisi "
            "baik apabila berpindah tugas/berhenti.")
    if jenis not in _JENIS_PENGEMBALIAN:
        tj.append(
            "PIHAK KEDUA dilarang memindahtangankan, mengubah bentuk, "
            "membebani, atau mengalihkan BMN kepada pihak lain tanpa "
            "persetujuan tertulis PIHAK KESATU.")
    tj.extend(butir_waktu(jenis))

    # ── Tabel penanggung jawab tambahan (khusus operasional unit) ──────────
    # Dirakit di sini supaya ikut MASUK ke dalam KeepTogether pasalnya. Gaya
    # selnya meminjam gaya sel BAST yang sudah dirapatkan untuk Pasal 1 —
    # naskah ini dibatasi dua halaman, dan tabel kedua dengan gaya laporan
    # umum akan memakan jatah baris tabel asetnya.
    _tabel_pj = []
    if jenis == "operasional_unit" and _pj_baris:
        # Sel tabel ini LEBIH RAPAT lagi daripada tabel aset (7,8 → 7,2).
        # Isinya nama, nomor, dan lokasi — pendek-pendek — sementara jatah
        # halamannya sisa dari tabel aset yang mana pun besarnya. Merapatkan
        # di sini jauh lebih murah daripada memotong barisnya.
        st_pj = ParagraphStyle('BastPjSel', parent=st['Cell'],
                               fontSize=7.2, leading=8.6)
        st_pj_c = ParagraphStyle('BastPjSelC', parent=st['CellCenter'],
                                 fontSize=7.2, leading=8.6)
        st_pj_h = ParagraphStyle('BastPjHead', parent=st['TableHeader'],
                                 fontSize=7.2, leading=8.6)
        # Kolom BMN hanya dipasang bila memang ADA yang dilekatkan. Kolom
        # berisi tanda hubung dari atas ke bawah cuma memakan lebar yang bisa
        # dipakai nama dan unit — inilah "memaksimalkan kekosongan yang ada".
        _kepala_pj = ["No.", "Nama", "NIP/NIK", "Unit/Tempat/Tugas"]
        _lebar_pj = [16, 92, 70, 222]
        if _ada_bmn:
            _kepala_pj.append("No. BMN")
            _lebar_pj = [16, 80, 66, 190, 48]
        _data_pj = [[Paragraph(h, st_pj_h) for h in _kepala_pj]]
        for r in _pj_baris:
            baris_pj = [
                Paragraph(str(r["no"]), st_pj_c),
                Paragraph(_esc(r["nama"]), st_pj),
                Paragraph(_esc(r["nip"]), st_pj_c),
                Paragraph(_esc(label_unit(r)), st_pj),
            ]
            if _ada_bmn:
                baris_pj.append(Paragraph(
                    _esc(rujukan_pasal1(r["aset"], _urut_cetak)) or "—",
                    st_pj_c))
            _data_pj.append(baris_pj)
        _t_pj = Table(_data_pj, colWidths=_fit_col_widths(_lebar_pj, doc.width),
                      repeatRows=1)
        _t_pj.setStyle(_std_table_style(zebra=True, extra=[
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        _tabel_pj.append(_t_pj)
        _sisa_bmn = (bmn_tanpa_pj(b.get("penanggung_jawab_tambahan"),
                                  b.get("aset")) if _ada_bmn else [])
        if _sisa_bmn:
            # Hanya bermakna bila SEBAGIAN barang memang dilekatkan: pembaca
            # yang melihat 3 dari 10 barang di tabel akan menduga-duga ke mana
            # 7 sisanya. Bila tak satu pun dilekatkan, kalimat ini hanya
            # mengulang isi pasal di atasnya — dan mengulang berarti membuang
            # baris pada naskah yang dibatasi dua halaman.
            _tabel_pj.append(Paragraph(
                f"{len(_sisa_bmn)} BMN Pasal 1 lainnya: tanggung jawab PIHAK "
                "KEDUA.", ket))
    pasal("TANGGUNG JAWAB DAN PENGGUNAAN", tj)
    if _tabel_pj:
        el.append(KeepTogether(_tabel_pj))

    # ── PASAL 3 — KETENTUAN KHUSUS SESUAI JENIS BARANG ─────────────────────
    # SATU pasal berisi satu butir per BIDANG kode barang (dulu satu pasal
    # per bidang) — sistem tetap membedakan aturan per jenis barang, tetapi
    # naskahnya jauh lebih ringkas.
    _MAKS_BIDANG = 4
    _kode_aset = [a.get("asset_code") for a in (b.get("aset") or [])]
    _btr_bidang = butir_khusus_bidang(_kode_aset, maks=_MAKS_BIDANG)
    if _btr_bidang:
        _dipakai, _sisa_nama = sisa_bidang(_kode_aset, maks=_MAKS_BIDANG)
        if _sisa_nama:
            # Pemotongan TIDAK senyap: naskah menyebut bidang yang tak dicetak.
            _btr_bidang.append(
                "Terhadap BMN bidang " + _esc(", ".join(_sisa_nama))
                + " pada Berita Acara ini berlaku pula ketentuan teknis "
                "pengelolaan masing-masing bidang tersebut.")
        pasal("KETENTUAN KHUSUS SESUAI JENIS BARANG", _btr_bidang)

    # ── PASAL 4 — dasar pengembalian almarhum (khusus) ─────────────────────
    if jenis == "pengembalian_almarhum":
        alm = b.get("almarhum") or {}
        _nm = _esc(str(alm.get("nama") or "-"))
        _nip = str(alm.get("nip") or "").strip()
        _tgl = str(alm.get("tanggal_meninggal") or "").strip()
        _akta = str(alm.get("nomor_akta_kematian") or "").strip()
        # Nomor identitas almarhum tunduk aturan privasi blok TTD: NIK Non-ASN
        # TIDAK dicetak; NIP/NRP dicetak dengan label pintar.
        from pegawai_utils import (
            deteksi_identitas as _dj, label_nomor_identitas as _lni,
        )
        _det_alm = _dj(_nip)
        _frasa_id = ("" if not _nip or _det_alm["jenis"] == "nik"
                     # Format tak dikenal → label netral dari deteksinya
                     # sendiri, bukan tebakan "NIP".
                     else f" ({_esc(_lni(_nip) or _det_alm['label'])} "
                          f"{_esc(_nip)})")
        pasal("DASAR PENGEMBALIAN (PEMEGANG MENINGGAL DUNIA)", [
            f"BMN ini sebelumnya tercatat pada pemegang <b>{_nm}</b>"
            + _frasa_id
            + (f" yang meninggal dunia pada {_esc(_fmt_tanggal_id(_tgl))}"
               if _tgl else " yang telah meninggal dunia")
            + (f", Akta/Surat Keterangan Kematian Nomor {_esc(_akta)}" if _akta else "")
            + ". Karena pemegang tercatat berhalangan tetap, penyerahan "
            "dilakukan PIHAK KEDUA selaku ahli waris/atasan langsung dan "
            "disaksikan para saksi yang menandatangani Berita Acara ini.",
            "Berita Acara Serah Terima terdahulu atas nama pemegang tersebut "
            "TETAP SAH sebagai bukti rantai penguasaan barang dan tidak "
            "dibatalkan oleh Berita Acara ini.",
        ])

    # ── PASAL 5 — KEHILANGAN, KERUSAKAN, DAN GANTI RUGI ────────────────────
    _btr_risiko = butir_risiko(jenis)
    if _btr_risiko:
        pasal("KEHILANGAN, KERUSAKAN, DAN GANTI RUGI", _btr_risiko)

    if b.get("keterangan"):
        # Isi dari textarea: tiap baris tak-kosong → satu butir pasal
        # (di-escape — teks bebas berkarakter '&'/'<' tak boleh merusak PDF).
        butir = [_esc(ln.strip())
                 for ln in str(b["keterangan"]).splitlines() if ln.strip()]
        pasal("KETENTUAN TAMBAHAN", butir or [_esc(str(b["keterangan"]))])
    pasal("PENUTUP", [
        "Demikian Berita Acara ini dibuat dengan sebenarnya dalam rangkap "
        "2 (dua) yang masing-masing mempunyai kekuatan hukum sama; apabila "
        "di kemudian hari terdapat kekeliruan akan diperbaiki sebagaimana "
        "mestinya.",
    ])

    el.append(Spacer(1, 1.5 * rl_mm))
    # Baris "Mengetahui, KPB": otomatis pada mutasi; juga pada non-mutasi bila
    # penyerah bertindak a.n. KPB (pendelegasian) — kaidah §11B.
    # SINKRON dengan _penanda_tangan_bast (daftar tautan e-sign): perubahan
    # susunan kolom TTD di sini wajib dicerminkan ke sana.
    an_kpb = bool(b.get("penyerah_atas_nama_kpb")) and jenis != "mutasi_pengguna"
    signers_mengetahui = []
    if jenis == "mutasi_pengguna" or an_kpb:
        # KPB dari REGISTRY pejabat yang berlaku pada tanggal BAST (bukan
        # setelan mentah yang bisa kedaluwarsa) — fallback ke setelan kasatker.
        # Spesimen TTD digital KPB ikut tersemat (konsisten laporan lain).
        from pegawai_utils import baris_identitas_ttd as _baris_ttd
        from shared_utils import ambil_ttd_img, resolve_penandatangan_kpb
        # KPB melekat ke SATKER DOKUMEN (kode_satker BAST-nya sendiri), bukan
        # satker peminta — kop di atas sudah ikut satker dokumen; kalau KPB
        # ikut peminta, unduhan super-admin/lintas-satker mencetak KPB satker
        # lain (atau "-" padahal Referensi Pejabat satker itu punya KPB).
        kpb = await resolve_penandatangan_kpb(
            settings, b.get("tanggal"),
            str(b.get("kode_satker") or "").strip() or kode_satker_user(_user))
        # Ia "Mengetahui" DALAM KAPASITAS KPB (dokumen ber-kop KPB) — jabatan
        # strukturalnya (mis. "Direktur ...") tidak dicetak di sini; kaidah
        # rangkap jabatan: kapasitas mengikuti kop surat.
        from pejabat_utils import jabatan_kapasitas_kpb
        signers_mengetahui = [{'header': 'Mengetahui,',
                               'role': f"{jabatan_kapasitas_kpb(kpb)},",
                               'nama': kpb["nama"],
                               # Non-ASN: baris NIP/NIK tidak dicetak
                               'after': _baris_ttd(
                                   kpb['nip'], kpb.get("status_kepegawaian")),
                               'ttd_img': await ambil_ttd_img(kpb.get("ttd_file_id"))}]
    peran_kesatu = ('Yang Menyerahkan,' if jenis not in _JENIS_PENGEMBALIAN
                    else 'Yang Menerima,')
    if an_kpb:
        peran_kesatu = peran_kesatu.rstrip(',') + ' a.n. Kuasa Pengguna Barang,'
    from pegawai_utils import baris_identitas_ttd
    from shared_utils import status_kepegawaian_by_nip
    el.extend(_signature_block([
        {'header': 'PIHAK KEDUA,',
         'role': ('Yang Menerima,' if jenis not in _JENIS_PENGEMBALIAN
                  else 'Yang Menyerahkan,'),
         'nama': p2.get("nama") or "................................",
         # Label pintar (NIP/NRP); Non-ASN/NIK/kosong → tak ada baris
         'after': baris_identitas_ttd(
             p2.get("nip"),
             await status_kepegawaian_by_nip(p2.get("nip")))},
        {'pre': [_tempat_tanggal_laporan(settings, b.get("tanggal"))],
         'header': 'PIHAK KESATU,', 'role': peran_kesatu,
         'nama': p1.get("nama") or "................................",
         'after': baris_identitas_ttd(
             p1.get("nip"), await status_kepegawaian_by_nip(p1.get("nip")))},
    ] + signers_mengetahui, doc.width, celah_mm=_CELAH_TTD_BAST,
        jarak_baris_mm=_JARAK_BARIS_TTD_BAST))
    # Blok SAKSI — wajib pada pengembalian almarhum (pihak yang seharusnya
    # menyerahkan berhalangan tetap), opsional bila diisi pada jenis lain.
    _saksi_doc = [s for s in (b.get("saksi") or [])
                  if str((s or {}).get("nama") or "").strip()]
    if _saksi_doc:
        el.append(Spacer(1, 2 * rl_mm))
        el.append(Paragraph("<b>SAKSI-SAKSI:</b>", isi))
        kolom_saksi = []
        for i, s in enumerate(_saksi_doc, 1):
            kolom_saksi.append({
                'header': f'Saksi {i}.',
                'role': _esc(str(s.get("jabatan") or "").strip()) or ' ',
                'nama': _esc(str(s.get("nama") or "").strip()),
                'after': baris_identitas_ttd(
                    s.get("nip"),
                    await status_kepegawaian_by_nip(s.get("nip")))})
        # Dirender BERPASANGAN (2 per baris): _signature_block hanya menangani
        # 1–3 penanda tangan dan MEMBUANG sisanya bila diberi ≥4 — memecah
        # sendiri memastikan seluruh saksi benar-benar tercetak.
        for i in range(0, len(kolom_saksi), 2):
            el.extend(_signature_block(kolom_saksi[i:i + 2], doc.width,
                                       celah_mm=_CELAH_TTD_BAST))
    el.extend(_blok_tembusan(
        {"tembusan_laporan": b.get("tembusan") or settings.get("tembusan_laporan", "")}))

    # ── LAMPIRAN: SURAT PERNYATAAN TANGGUNG JAWAB (opsional) ───────────────
    #
    # Terpisah dari Berita Acara dan ditandatangani SATU ORANG. Berita Acara
    # membuktikan serah terima terjadi dan ditandatangani dua pihak;
    # pernyataan ini mengikat orangnya sendiri. Pada BAST operasional dengan
    # lima penanggung jawab, tanpa lembar tersendiri empat di antaranya tak
    # pernah membubuhkan tanda tangan apa pun pada dokumen yang membebani
    # mereka.
    if b.get("surat_pernyataan"):
        from bast_pasal import butir_pernyataan, daftar_penyata
        _nomor_ba = str(b.get("nomor") or "").strip() or "…………"
        _tgl_ba = _fmt_tanggal_id(b.get("tanggal")) or "…………"
        for _pen in daftar_penyata(jenis, p2, p1,
                                   b.get("penanggung_jawab_tambahan"),
                                   b.get("aset")):
            el.append(PageBreak())
            el.extend(_title_block("SURAT PERNYATAAN TANGGUNG JAWAB\n"
                                   "BARANG MILIK NEGARA"))
            el.append(Paragraph("Yang bertanda tangan di bawah ini:", isi))
            _baris_id = [("Nama", _pen["nama"] or "…………………………")]
            if _pen["nip"]:
                _baris_id.append(("NIP/NIK", _pen["nip"]))
            if _pen["jabatan"]:
                _baris_id.append(("Jabatan", _pen["jabatan"]))
            if _pen["unit"]:
                _baris_id.append(("Unit/Tempat Tugas", _pen["unit"]))
            el.append(_identity_table(_baris_id))
            el.append(Spacer(1, 2 * rl_mm))
            el.append(Paragraph(
                "dengan ini menyatakan dengan sesungguhnya bahwa:", isi))
            for _i, _t in enumerate(butir_pernyataan(_pen["peran"],
                                                     _pen["unit"]), 1):
                el.append(Paragraph(f"({_i}) {_esc(_t)}", isi))
            el.append(Spacer(1, 2 * rl_mm))
            # Daftar BMN dibangun pembangun YANG SAMA dengan tabel Pasal 1 —
            # berkelompok per bidang, kolom identik. Yang menandatangani
            # pernyataan ini harus melihat barang yang sama persis dengan yang
            # tercantum pada Berita Acaranya.
            if _pen["aset"]:
                el.append(Paragraph(
                    "<b>Daftar Barang Milik Negara yang menjadi tanggung "
                    "jawab saya:</b>", isi))
                _t_pen, _ = await _tabel_objek(_pen["aset"])
                el.append(_t_pen)
            else:
                # Daftar kosong DINYATAKAN, bukan didiamkan: lembar tanpa
                # daftar dan lembar yang daftarnya lupa diisi terlihat sama.
                el.append(Paragraph(
                    "<i>Tidak ada BMN yang dilekatkan secara khusus kepada "
                    "saya; tanggung jawab saya mengikuti BMN pada unit/tempat "
                    "tugas tersebut sebagaimana Pasal 1 Berita Acara.</i>",
                    isi))
            el.append(Spacer(1, 2 * rl_mm))
            el.append(Paragraph(
                "Surat pernyataan ini saya buat dengan sebenar-benarnya tanpa "
                "paksaan dari pihak mana pun, dan merupakan bagian yang "
                "<b>TIDAK TERPISAHKAN</b> dari Berita Acara Serah Terima "
                f"Nomor {_esc(_nomor_ba)} tanggal {_esc(_tgl_ba)}.", isi))
            el.append(Spacer(1, 2 * rl_mm))
            el.extend(_signature_block([
                {'pre': [_tempat_tanggal_laporan(settings, b.get("tanggal"))],
                 'header': 'Yang Menyatakan,', 'role': ' ',
                 'nama': _pen["nama"] or "................................",
                 'after': baris_identitas_ttd(
                     _pen["nip"],
                     await status_kepegawaian_by_nip(_pen["nip"]))},
            ], doc.width, celah_mm=_CELAH_TTD_BAST,
                jarak_baris_mm=_JARAK_BARIS_TTD_BAST))
            el.append(Paragraph(
                "<i>Ditandatangani di atas meterai sesuai ketentuan peraturan "
                "perundang-undangan apabila dipersyaratkan.</i>", ket))

    # Lampiran foto (opsional): (A) foto BARANG (sampul tiap aset) + (B) foto
    # SERAH TERIMA (scan bukti ttd BAST). Sebelumnya hanya foto barang yang
    # disematkan sehingga bukti serah terima tak pernah ikut tercetak.
    if b.get("sertakan_foto"):
        import base64
        from reportlab.platypus import Table as _Tbl, TableStyle as _TS
        from lampiran_foto_utils import (
            KOLOM as _LK, bagi_baris, ringkas_lampiran, susun_sel_lampiran,
        )
        from shared_utils import get_document_from_gridfs

        aset_master = await db.assets.find(
            {"id": {"$in": b.get("asset_ids") or []}},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
             "photos": 1, "photo_gridfs_ids": 1, "thumbnail_index": 1},
        ).to_list(500)
        # Pertahankan urutan aset sesuai BAST (find() tidak menjamin urutan).
        _urut = {aid: i for i, aid in enumerate(b.get("asset_ids") or [])}
        aset_master.sort(key=lambda a: _urut.get(a.get("id"), 10**6))

        async def _bytes_sampul(a):
            """Foto sampul aset → bytes (inline base64 atau GridFS)."""
            photos = a.get("photos") or []
            idx = a.get("thumbnail_index", 0) or 0
            url = photos[idx] if photos and idx < len(photos) else (
                photos[0] if photos else None)
            if not url:
                gids = a.get("photo_gridfs_ids") or []
                if gids:
                    gidx = max(0, min(int(idx), len(gids) - 1))
                    url = await _gridfs_photo_data_uri(gids[gidx]) or None
            if not url or "base64," not in str(url):
                return None
            try:
                return base64.b64decode(str(url).split("base64,", 1)[1])
            except Exception:
                return None

        # Foto serah terima: (a) PER BARANG lewat `foto_serah_terima`
        # {asset_id: file_id}, dan/atau (b) SATU perwakilan untuk semua barang.
        # Bukti ttd lama yang berupa gambar tetap dihormati sebagai perwakilan
        # supaya BAST terdahulu tidak kehilangan lampirannya.
        foto_st = {k: v for k, v in (b.get("foto_serah_terima") or {}).items() if v}
        _bukti = b.get("bukti") or {}
        _bukti_gambar = bool(
            _bukti.get("file_id")
            and str(_bukti.get("content_type") or "").lower().startswith("image/"))
        st_bersama_id = str(b.get("foto_serah_terima_bersama") or "").strip()
        if not st_bersama_id and _bukti_gambar:
            st_bersama_id = str(_bukti["file_id"])

        # SELURUH aset dioper; yang tak punya foto sampul cukup tak
        # menghasilkan sel "sampul" — foto serah terimanya TETAP tercetak.
        # (Dulu aset tanpa sampul disaring lebih dulu sehingga foto serah
        # terima yang sudah diunggah untuknya lenyap tanpa pesan apa pun.)
        sampul_bytes = {}
        for a in aset_master:
            raw = await _bytes_sampul(a)
            if raw:
                sampul_bytes[str(a.get("id"))] = raw

        sel = susun_sel_lampiran(aset_master, foto_st,
                                 foto_st_bersama=bool(st_bersama_id),
                                 id_ber_sampul=set(sampul_bytes))
        # Bukti ttd berupa PDF tak bisa disematkan sebagai gambar, tetapi
        # keberadaannya tetap perlu dicatat — halaman lampiran harus terbit
        # walau TIDAK ada satu pun foto (dulu blok ini dilewati seluruhnya).
        _catatan_bukti_pdf = bool(_bukti.get("file_id")) and not _bukti_gambar
        if sel or _catatan_bukti_pdf:
            # Lebar/tinggi sel dihitung dari lebar dokumen supaya 2 kolom x 3
            # baris benar-benar muat satu halaman tanpa meluber.
            # Gaya keterangan sel: kecil & rata tengah, didefinisikan lokal
            # supaya tidak bergantung pada kunci gaya global yang bisa berubah.
            kecil = ParagraphStyle(
                "LampiranSel", parent=body, fontSize=7.5, leading=9.5,
                alignment=TA_CENTER, spaceAfter=2)
            _gap = 4 * rl_mm
            lebar_sel = (doc.width - _gap * (_LK - 1)) / _LK
            # Lebar yang benar-benar tersedia = lebar kolom dikurangi padding
            # kanan sel; menskala terhadap `lebar_sel` membuat foto landscape
            # meluber ~2 mm ke kolom sebelah.
            lebar_gambar = lebar_sel - _gap / 2
            tinggi_foto = 62 * rl_mm

            async def _bytes_serah(s):
                if s["jenis"] == "serah_bersama":
                    fid = st_bersama_id
                else:
                    fid = str(s.get("kunci") or "")
                if not fid:
                    return None
                try:
                    return await get_document_from_gridfs(fid)
                except Exception:
                    return None

            def _kotak(judul, raw):
                """Satu sel: keterangan + foto ter-skala di dalam batas sel."""
                isi = [Paragraph(f"<b>{_esc(judul)}</b>", kecil)]
                if raw:
                    try:
                        im = RLImage(io.BytesIO(raw))
                        sk = min(lebar_gambar / im.imageWidth,
                                 tinggi_foto / im.imageHeight)
                        im.drawWidth = im.imageWidth * sk
                        im.drawHeight = im.imageHeight * sk
                        im.hAlign = "CENTER"
                        isi.append(im)
                    except Exception:
                        isi.append(Paragraph("<i>Foto tidak terbaca.</i>", kecil))
                else:
                    isi.append(Paragraph("<i>Foto tidak tersedia.</i>", kecil))
                return isi

            data_sel = []
            for s in sel:
                if s is None:
                    data_sel.append(None)   # penyeimbang agar pasangan utuh
                    continue
                raw = (sampul_bytes.get(s["asset_id"]) if s["jenis"] == "sampul"
                       else await _bytes_serah(s))
                data_sel.append(_kotak(s["judul"], raw))

            el.append(PageBreak())
            el.extend(_title_block("LAMPIRAN\nFOTO BUKTI SERAH TERIMA BARANG"))
            r = ringkas_lampiran(sel)
            el.append(Paragraph(
                f"{r['aset']} barang · {r['foto_serah_terima']} foto serah terima"
                + (" · 1 foto perwakilan untuk seluruh barang"
                   if r["ada_foto_bersama"] else ""), kecil))
            el.append(Spacer(1, 3 * rl_mm))

            # Bukti ttd berupa PDF tidak bisa disematkan sebagai gambar;
            # catatannya DIPULIHKAN di sini (sempat hilang saat lampiran
            # dirombak) supaya pembaca tahu scan bertanda tangan itu ada
            # sebagai berkas terpisah.
            if _catatan_bukti_pdf:
                el.append(Paragraph(
                    "<i>Scan BAST bertanda tangan tersimpan sebagai berkas "
                    f"terpisah ({_esc(str(_bukti.get('filename') or 'bukti.pdf'))}).</i>",
                    kecil))
                el.append(Spacer(1, 2 * rl_mm))

            if data_sel:
                baris = bagi_baris(data_sel)
                tabel = _Tbl(
                    [[c if c is not None else "" for c in br] for br in baris],
                    colWidths=[lebar_sel] * _LK, hAlign="CENTER")
                tabel.setStyle(_TS([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), _gap / 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]))
                el.append(tabel)

    footer = _page_footer_factory(f"BAST — {judul_jenis[:60]}")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="BAST_{bast_id[:8]}.pdf"'})
