"""BAST SERAH TERIMA PENGGUNA — generator BA serah terima BMN lintas modul.

Format mengikuti contoh resmi satker (BAST Rumga & BA Robot Kit — dua docx
pemilik; intisari di scratchpad/format_bast.md) + PMK 246/PMK.06/2014 jo.
76/PMK.06/2019 (penggunaan BMN) & PMK 53/2023 (BMN di IKN):
kop → judul per jenis → nomor → narasi tanggal terbilang → identitas PIHAK
KESATU (penyerah) & PIHAK KEDUA (penerima) → dasar hukum → PASAL 1 + tabel
MULTI-ASET → pasal-pasal sesuai jenis → penutup → ttd 2 pihak → tembusan →
lampiran foto aset (opsional, sesuai setelan `sertakan_foto`).

Jenis serah terima (kebutuhan lapangan):
- penggunaan_melekat   : BAST ke pegawai (aset "Melekat ke" perorangan)
- operasional_unit     : penanggung jawab operasional per unit/tempat/tugas
                         (+ daftar penanggung jawab tambahan opsional)
- penggunaan_sementara : pinjam pakai internal ber-jangka waktu
- pengembalian         : arah balik (PIHAK KEDUA mengembalikan ke satker)
- lainnya              : jenis bebas (judul manual)

Register `bast_serah_terima` menyimpan tiap BAST (riwayat per aset dan per
pengguna terlacak); PDF dirender ulang kapan pun dari register.
"""
import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import (
    require_user, require_user_or_query_token, require_writer,
)
from db import db
from shared_utils import kode_satker_user, log_audit

bast_router = APIRouter()

_PROJ = {"_id": 0}

JENIS_BAST = {
    "penggunaan_melekat": "Penggunaan Barang Milik Negara (Melekat ke Pengguna)",
    "mutasi_pengguna": "Mutasi/Alih Pemegang Barang Milik Negara",
    "operasional_unit": "Operasional Penggunaan Barang Milik Negara pada Unit/Tempat/Tugas",
    "penggunaan_sementara": "Operasional Penggunaan Sementara Barang Milik Negara",
    "pengembalian": "Pengembalian Barang Milik Negara",
    "lainnya": "Serah Terima Barang Milik Negara",
}

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


class PihakIn(BaseModel):
    nama: str = ""
    nip: str = ""
    jabatan: str = ""
    alamat: str = ""


class PjTambahanIn(BaseModel):
    nama: str = ""
    unit_tempat_tugas: str = ""


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
    tembusan: Optional[str] = ""              # override; default pengaturan
    sertakan_foto: Optional[bool] = False
    keterangan: Optional[str] = ""
    # Handover langsung: BAST sekaligus MENERAPKAN perubahan ke master aset
    # (mutasi → pengguna beralih ke PIHAK KEDUA; pengembalian → pengguna
    # dikosongkan). Ber-audit + $inc version.
    terapkan_ke_aset: Optional[bool] = False
    # Pesan nomor otomatis dari Registrasi Persuratan (tercatat di buku
    # agenda berstatus dibooking).
    booking_otomatis: Optional[bool] = False


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
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "label_jenis": JENIS_BAST}


@bast_router.post("/bast")
async def buat_bast(payload: BastIn, user: dict = Depends(require_writer)):
    """Simpan BAST ke register (multi-aset; snapshot identitas aset dibekukan
    agar dokumen historis tak berubah saat master aset berubah)."""
    if payload.jenis not in JENIS_BAST:
        raise HTTPException(status_code=400,
                            detail=f"Jenis BAST tidak dikenal: {payload.jenis}")
    if not payload.asset_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu aset")
    if not str(payload.pihak_kedua.nama or "").strip():
        raise HTTPException(status_code=400, detail="Nama PIHAK KEDUA wajib diisi")
    if payload.jenis == "penggunaan_sementara" and not (
            str(payload.jangka_dari or "").strip()
            and str(payload.jangka_sampai or "").strip()):
        raise HTTPException(status_code=400, detail=(
            "Penggunaan sementara wajib ber-jangka waktu (dari & sampai)"))

    aset = await db.assets.find(
        {"id": {"$in": payload.asset_ids}, "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "brand": 1, "model": 1, "serial_number": 1, "condition": 1,
         "purchase_date": 1, "purchase_price": 1,
         "photos": 1, "photo_gridfs_ids": 1, "thumbnail_index": 1},
    ).to_list(500)
    if len(aset) != len(set(payload.asset_ids)):
        raise HTTPException(status_code=404,
                            detail="Sebagian aset tidak ditemukan/terhapus")

    settings = await db.report_settings.find_one({"type": "global"}, _PROJ) or {}
    p1 = payload.pihak_pertama
    pihak_pertama = {
        "nama": (p1.nama if p1 and p1.nama.strip() else settings.get("kasatker_nama", "")),
        "nip": (p1.nip if p1 and p1.nip.strip() else settings.get("kasatker_nip", "")),
        "jabatan": (p1.jabatan if p1 and p1.jabatan.strip()
                    else settings.get("kasatker_jabatan", "Kuasa Pengguna Barang")),
        "alamat": (p1.alamat if p1 and p1.alamat.strip()
                   else str(settings.get("alamat_instansi") or "").splitlines()[0]
                   if str(settings.get("alamat_instansi") or "").strip() else ""),
    }
    if payload.jenis == "mutasi_pengguna" and not (
            payload.pihak_pertama and str(payload.pihak_pertama.nama or "").strip()):
        raise HTTPException(status_code=400, detail=(
            "Mutasi pemegang: isi PIHAK KESATU (pemegang lama) — "
            "PIHAK KEDUA adalah pemegang baru"))

    now = datetime.now(timezone.utc)
    nomor_final = str(payload.nomor or "").strip()
    surat_id = ""
    if payload.booking_otomatis and not nomor_final:
        # Booking nomor otomatis lewat modul Persuratan (buku agenda keluar).
        from persuratan_utils import bangun_nomor, pilih_klasifikasi
        from routes.persuratan import _no_agenda_berikut, _pengaturan
        tgl_surat = (str(payload.tanggal or "").strip()[:10]
                     or now.date().isoformat())
        atur = await _pengaturan()
        kode_klas = pilih_klasifikasi(atur["peta_klasifikasi"], "penggunaan",
                                      "Berita Acara",
                                      default=atur["kode_klasifikasi_default"])
        tahun = int(tgl_surat[:4]) if tgl_surat[:4].isdigit() else now.year
        no_agenda = await _no_agenda_berikut("keluar", tahun)
        nomor_final = bangun_nomor(atur["format_nomor"], no_agenda, tgl_surat,
                                   kode_klasifikasi=kode_klas,
                                   kode_unit=atur["kode_unit"])
        surat_id = str(uuid.uuid4())
        await db.surat.insert_one({
            "id": surat_id, "jenis": "keluar", "no_agenda": no_agenda,
            "tahun": tahun, "nomor": nomor_final, "status": "dibooking",
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
        "kode_satker": kode_satker_user(user),
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
                                        "condition", "purchase_date")} for a in aset],
        "jangka_dari": str(payload.jangka_dari or "").strip()[:10],
        "jangka_sampai": str(payload.jangka_sampai or "").strip()[:10],
        "penanggung_jawab_tambahan": [
            p.model_dump() for p in (payload.penanggung_jawab_tambahan or [])
            if str(p.nama or "").strip()],
        "tembusan": str(payload.tembusan or "").strip(),
        # Delegasi penyerahan a.n. KPB hanya relevan pada non-mutasi (mutasi
        # sudah otomatis ber-"Mengetahui KPB").
        "penyerah_atas_nama_kpb": (bool(payload.penyerah_atas_nama_kpb)
                                   and payload.jenis != "mutasi_pengguna"),
        "sertakan_foto": bool(payload.sertakan_foto),
        "terapkan_ke_aset": bool(payload.terapkan_ke_aset),
        "keterangan": str(payload.keterangan or "").strip(),
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
    }
    # Validasi LUNAK penerima ke Master Pegawai (non-blocking): NIP tak
    # terdaftar hanya diberi peringatan — BAST tetap tersimpan.
    peringatan_pegawai = ""
    nip2 = str(record["pihak_kedua"].get("nip") or "").strip()
    if nip2:
        peg = await db.pegawai.find_one({"nip": nip2}, {"_id": 0, "nama": 1, "status": 1})
        record["pihak_kedua_terdaftar"] = bool(peg)
        if not peg:
            peringatan_pegawai = (f"NIP {nip2} belum terdaftar di Master "
                                  "Pegawai — periksa ejaan atau daftarkan dulu")
        else:
            # Pegawai pensiun/mutasi/nonaktif → peringatan lunak (tak memblokir).
            from pegawai_utils import is_aktif
            if not is_aktif(peg):
                st = str(peg.get("status") or "").strip() or "nonaktif"
                peringatan_pegawai = (f"Penerima ({peg.get('nama') or nip2}) "
                                      f"berstatus {st} di Master Pegawai — "
                                      "pastikan serah terima ini memang tepat")
    await db.bast_serah_terima.insert_one({**record})

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
    elif payload.terapkan_ke_aset and payload.jenis == "pengembalian":
        set_aset.update({"user": "", "pengguna_nip": "",
                         "pengguna_jabatan": "", "pengguna_melekat_ke": ""})
    await db.assets.update_many(
        {"id": {"$in": record["asset_ids"]}, "dihapus": {"$ne": True}},
        {"$set": {**set_aset, "updated_at": now.isoformat()},
         "$inc": {"version": 1}})

    efek = ""
    if payload.terapkan_ke_aset and payload.jenis == "mutasi_pengguna":
        efek = f" (pengguna aset dialihkan ke {record['pihak_kedua']['nama']})"
    elif payload.terapkan_ke_aset and payload.jenis == "pengembalian":
        efek = " (pengguna aset dikosongkan)"
    await log_audit("buat_bast", "", username=user.get("username", "system"),
                    detail=(f"BAST {JENIS_BAST[payload.jenis]} — "
                            f"{len(aset)} aset → {record['pihak_kedua']['nama']}"
                            f"{efek}"
                            + (f"; nomor otomatis {nomor_final}" if surat_id else "")))
    return {**record, "peringatan_pegawai": peringatan_pegawai}


@bast_router.post("/bast/{bast_id}/bukti")
async def unggah_bukti_bast(bast_id: str, file: UploadFile = File(...),
                            user: dict = Depends(require_writer)):
    """Unggah scan BAST bertanda tangan (PDF/gambar ≤10MB) → tersimpan di
    GridFS; bila nomor BAST berasal dari booking otomatis, nomor agenda di
    Registrasi Persuratan langsung DISAHKAN (menutup siklus dua langkah)."""
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    nama = str(file.filename or "").lower()
    if not nama.endswith((".pdf", ".jpg", ".jpeg", ".png")):
        raise HTTPException(status_code=400,
                            detail="Berkas harus PDF/JPG/PNG")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 10MB")

    from bson import ObjectId
    from db import fs_bucket
    tipe = "application/pdf" if nama.endswith(".pdf") else "image/jpeg"
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=file.filename,
        metadata={"content_type": tipe, "size": len(data)})
    await grid_in.write(data)
    await grid_in.close()

    now = datetime.now(timezone.utc).isoformat()
    bukti_lama = (b.get("bukti") or {}).get("file_id")
    res = await db.bast_serah_terima.update_one(
        {"id": bast_id},
        {"$set": {"bukti": {"file_id": str(file_id), "filename": file.filename,
                            "content_type": tipe,
                            "diunggah_pada": now,
                            "oleh": user.get("username", "system")}}})
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
    await db.assets.update_many(
        {"id": {"$in": b.get("asset_ids") or []}, "dihapus": {"$ne": True}},
        {"$set": {"bast_file_id": str(file_id), "updated_at": now},
         "$inc": {"version": 1}})

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


@bast_router.get("/bast/{bast_id}/bukti")
async def unduh_bukti_bast(bast_id: str,
                           _user: dict = Depends(require_user_or_query_token)):
    """Stream scan bukti ttd (dipakai pratinjau window.open ber-token)."""
    from shared_utils import get_document_from_gridfs
    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b or not (b.get("bukti") or {}).get("file_id"):
        raise HTTPException(status_code=404, detail="Bukti belum diunggah")
    data = await get_document_from_gridfs(b["bukti"]["file_id"])
    if not data:
        raise HTTPException(status_code=404, detail="Berkas bukti tidak ditemukan")
    return StreamingResponse(
        io.BytesIO(data), media_type=b["bukti"].get("content_type", "application/pdf"),
        headers={"Content-Disposition":
                 f'inline; filename="{b["bukti"].get("filename", "bukti.pdf")}"',
                 "X-Content-Type-Options": "nosniff"})


@bast_router.get("/bast/{bast_id}/pdf")
async def bast_pdf(bast_id: str,
                   _user: dict = Depends(require_user_or_query_token)):
    """Render BAST 1-2 halaman + lampiran foto opsional."""
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, Image as RLImage

    from pelaporan_utils import narasi_hari_tanggal
    from routes.reports import (
        _blok_tembusan, _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _gridfs_photo_data_uri, _identity_table, _kop_surat_flowables,
        _page_footer_factory, _peta_subsub_kelompok, _sel_identitas_barang,
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
    isi = ParagraphStyle('BastIsi', parent=body, fontSize=8.6, leading=11.6,
                         alignment=TA_JUSTIFY, textColor=HexColor("#111827"),
                         spaceAfter=1.5)
    lbl_pasal = ParagraphStyle('BastPasal', parent=body, fontSize=9,
                               leading=11.5, alignment=TA_CENTER,
                               spaceBefore=5, spaceAfter=2.5,
                               textColor=HexColor("#111827"))
    ket = ParagraphStyle('BastKet', parent=isi, fontSize=8.2, leading=10.8)

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("BERITA ACARA SERAH TERIMA\n"
                           + _esc(judul_baris2.upper()),
                           nomor=b.get("nomor") or "......./......./........"))

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

    def _kolom_pihak(peran, sebutan, ph, label_nip):
        """Identitas satu pihak: label SEJAJAR (tabel label:nilai) + baris
        'selanjutnya disebut ...' — mengikuti anatomi BAST resmi."""
        rows = []
        for lbl, val in (("Nama", ph.get("nama")), (label_nip, ph.get("nip")),
                         ("Jabatan", ph.get("jabatan")),
                         ("Alamat", ph.get("alamat"))):
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
                     if jenis_awal != "pengembalian"
                     else "PIHAK KESATU (yang menerima)", "PIHAK KESATU", p1, "NIP"),
        _kolom_pihak("PIHAK KEDUA (yang menerima)"
                     if jenis_awal != "pengembalian"
                     else "PIHAK KEDUA (yang menyerahkan)", "PIHAK KEDUA", p2, "NIP/NIK"),
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
            if jenis_awal == "pengembalian"
            else "PIHAK KESATU dan PIHAK KEDUA — secara bersama-sama disebut "
                 "PARA PIHAK — sepakat melakukan serah terima")
    el.append(Paragraph(
        f"{arah} {_esc(judul_jenis)}, berdasarkan:", isi))
    for i, d in enumerate(DASAR_HUKUM, 1):
        el.append(Paragraph(f"{i}. {d}", ket))
    el.append(Spacer(1, 1.5 * rl_mm))

    # PASAL 1 — objek serah terima (tabel multi-aset + nilai + total)
    el.append(Paragraph("<b>PASAL 1 — OBJEK SERAH TERIMA</b>", lbl_pasal))
    kalimat1 = ("PIHAK KEDUA menyerahkan kembali dan PIHAK KESATU menerima"
                if b.get("jenis") == "pengembalian"
                else "PIHAK KESATU menyerahkan dan PIHAK KEDUA menerima penyerahan")
    el.append(Paragraph(
        f"{kalimat1} Barang Milik Negara dengan rincian sebagai berikut:", isi))
    subsub = await _peta_subsub_kelompok(
        [a.get("asset_code") for a in (b.get("aset") or [])])
    from kodefikasi_utils import normalize_kode as _norm
    from pembukuan_utils import parse_harga as _ph
    data = [[Paragraph(h, st['TableHeader']) for h in
             ("No", "Identitas Barang<br/>(Sub-sub Kelompok · Kode · NUP)",
              "Uraian Barang<br/>(Nama · Merk/Tipe/Spesifikasi)", "Tahun",
              "Kondisi", "Nilai Perolehan (Rp)")]]
    total_nilai = 0.0
    for i, a in enumerate(b.get("aset") or [], 1):
        tgl = str(a.get("purchase_date") or "")
        tahun = tgl[:4] if len(tgl) >= 4 and tgl[:4].isdigit() else (
            tgl[-4:] if len(tgl) >= 4 and tgl[-4:].isdigit() else "-")
        nilai = _ph(a.get("purchase_price"))
        total_nilai += nilai
        data.append([
            Paragraph(str(i), st['CellCenter']),
            _sel_identitas_barang(a, subsub.get(_norm(a.get("asset_code")), ""), st),
            _sel_uraian_barang(a, st),
            Paragraph(tahun, st['CellCenter']),
            Paragraph(a.get("condition") or "-", st['CellCenter']),
            Paragraph(f"{nilai:,.0f}".replace(",", ".") if nilai else "-",
                      st['CellRight'] if 'CellRight' in st else st['CellCenter']),
        ])
    data.append([Paragraph("", st['Cell']),
                 Paragraph("<b>JUMLAH</b>", st['Cell']), Paragraph("", st['Cell']),
                 Paragraph("", st['Cell']), Paragraph("", st['Cell']),
                 Paragraph(f"<b>{total_nilai:,.0f}</b>".replace(",", "."),
                           st['CellRight'] if 'CellRight' in st else st['CellCenter'])])
    t = Table(data, colWidths=_fit_col_widths([24, 130, 168, 36, 50, 78],
                                              doc.width), repeatRows=1)
    t.setStyle(_std_table_style(zebra=True, total_row=True))
    el.append(t)

    # PASAL 2+ — ketentuan sesuai jenis. Tiap pasal dibungkus KeepTogether
    # agar judul tidak yatim terpisah dari isinya saat pecah halaman.
    from reportlab.platypus import KeepTogether
    nomor_pasal = 2

    def pasal(judul, isi_list):
        nonlocal nomor_pasal
        blok = [Paragraph(f"<b>PASAL {nomor_pasal} — {judul}</b>", lbl_pasal)]
        for i, teks in enumerate(isi_list, 1):
            blok.append(Paragraph(
                (f"({i}) {teks}" if len(isi_list) > 1 else teks), isi))
        el.append(KeepTogether(blok))
        nomor_pasal += 1

    jenis = b.get("jenis")
    # Pasal umum: keadaan barang & kelengkapan — anatomi BAST resmi.
    pasal("KEADAAN BARANG DAN KELENGKAPAN", [
        "Serah terima meliputi fisik barang beserta kelengkapan/dokumen "
        "pendukungnya, dalam keadaan sebagaimana tercantum pada kolom "
        "Kondisi tabel Pasal 1; PARA PIHAK telah melakukan pengecekan "
        "bersama atas barang dimaksud sebelum menandatangani Berita Acara ini.",
    ])
    if jenis == "mutasi_pengguna":
        pasal("MUTASI PEMEGANG DAN TANGGUNG JAWAB", [
            "Terhitung sejak ditandatanganinya Berita Acara ini, tanggung "
            "jawab penggunaan, pengamanan, dan pemeliharaan BMN beralih dari "
            "PIHAK KESATU kepada PIHAK KEDUA.",
            "PIHAK KEDUA dilarang memindahtangankan, mengubah bentuk, atau "
            "mengalihkan BMN kepada pihak lain tanpa persetujuan tertulis, "
            "dan wajib mengembalikannya apabila berpindah tugas/berhenti.",
            "Kehilangan atau kerusakan akibat kelalaian PIHAK KEDUA wajib "
            "segera dilaporkan dan dapat dikenakan tuntutan ganti rugi "
            "sesuai ketentuan peraturan perundang-undangan.",
        ])
        pasal("STATUS PENCATATAN", [
            "BMN tetap tercatat sebagai Barang Milik Negara pada satuan "
            "kerja; mutasi ini hanya mengubah pencatatan pemegang pada "
            "daftar barang/Daftar Barang Ruangan/Kartu Identitas Barang.",
        ])
    if jenis in ("penggunaan_melekat", "operasional_unit", "lainnya"):
        pasal("TANGGUNG JAWAB", [
            "Terhitung sejak ditandatanganinya Berita Acara ini, PIHAK KEDUA "
            "bertanggung jawab penuh atas penggunaan, pengamanan, dan "
            "pemeliharaan BMN untuk kepentingan kedinasan.",
            "BMN wajib dikembalikan kepada PIHAK KESATU dalam kondisi baik "
            "apabila PIHAK KEDUA berpindah tugas/berhenti sesuai ketentuan.",
            "PIHAK KEDUA dilarang memindahtangankan atau mengalihkan BMN "
            "kepada pihak lain tanpa persetujuan tertulis PIHAK KESATU.",
            "Kehilangan atau kerusakan akibat kelalaian PIHAK KEDUA wajib "
            "segera dilaporkan kepada PIHAK KESATU dan dapat dikenakan "
            "tuntutan ganti rugi sesuai ketentuan peraturan "
            "perundang-undangan.",
        ])
    if jenis == "operasional_unit" and b.get("penanggung_jawab_tambahan"):
        baris = [f"{_esc(str(p.get('nama') or '-'))} — "
                 f"{_esc(str(p.get('unit_tempat_tugas') or '-'))}"
                 for p in b["penanggung_jawab_tambahan"]]
        pasal("PENANGGUNG JAWAB PENGGUNAAN",
              ["Pembagian penanggung jawab penggunaan pada unit/tempat/tugas:"]
              + baris)
    if jenis == "penggunaan_sementara":
        pasal("STATUS DAN JANGKA WAKTU", [
            "Penggunaan sementara tidak mengalihkan status penggunaan — BMN "
            "tetap tercatat pada Daftar Barang Pengguna PIHAK KESATU dan "
            "berada dalam pengawasannya; PIHAK KEDUA dilarang mengubah "
            "status, memindahtangankan, atau membebani BMN.",
            f"Jangka waktu penggunaan sementara terhitung sejak "
            f"{_fmt_tanggal_id(b.get('jangka_dari')) or '…'} sampai dengan "
            f"{_fmt_tanggal_id(b.get('jangka_sampai')) or '…'} dan dapat "
            "diperpanjang sesuai ketentuan dengan persetujuan pejabat yang "
            "berwenang.",
        ])
        pasal("BIAYA DAN PENGEMBALIAN", [
            "Biaya pemeliharaan dan pengamanan BMN selama jangka waktu "
            "penggunaan sementara dibebankan kepada PIHAK KEDUA, kecuali "
            "diperjanjikan lain.",
            "Pada saat jangka waktu berakhir atau sewaktu-waktu diperlukan, "
            "PIHAK KEDUA wajib menyerahkan kembali BMN kepada PIHAK KESATU "
            "dalam keadaan baik yang dituangkan dalam Berita Acara Serah "
            "Terima pengembalian.",
        ])
    if jenis == "pengembalian":
        pasal("PERNYATAAN DAN PEMERIKSAAN", [
            "PIHAK KEDUA menyatakan telah mengembalikan seluruh BMN tersebut "
            "dan PIHAK KESATU telah melakukan pemeriksaan fisik serta "
            "menerima BMN dalam keadaan sebagaimana tercantum pada tabel "
            "objek serah terima.",
            "Terhitung sejak ditandatanganinya Berita Acara ini, tanggung "
            "jawab penggunaan, pengamanan, dan pemeliharaan BMN kembali "
            "beralih kepada PIHAK KESATU; pencatatan pemegang pada daftar "
            "barang satuan kerja dimutakhirkan.",
        ])
    if b.get("keterangan"):
        # Isi dari textarea: tiap baris tak-kosong → satu butir pasal
        # (di-escape — teks bebas berkarakter '&'/'<' tak boleh merusak PDF).
        butir = [_esc(ln.strip())
                 for ln in str(b["keterangan"]).splitlines() if ln.strip()]
        pasal("KETENTUAN TAMBAHAN", butir or [_esc(str(b["keterangan"]))])
    pasal("PENUTUP", [
        "Demikian Berita Acara Serah Terima ini dibuat dengan sebenarnya "
        "dalam rangkap 2 (dua) — 1 (satu) rangkap untuk PIHAK KESATU dan "
        "1 (satu) rangkap untuk PIHAK KEDUA — yang masing-masing mempunyai "
        "kekuatan hukum yang sama; apabila di kemudian hari terdapat "
        "kekeliruan akan diadakan perbaikan sebagaimana mestinya.",
    ])

    el.append(Spacer(1, 3 * rl_mm))
    # Baris "Mengetahui, KPB": otomatis pada mutasi; juga pada non-mutasi bila
    # penyerah bertindak a.n. KPB (pendelegasian) — kaidah §11B.
    an_kpb = bool(b.get("penyerah_atas_nama_kpb")) and jenis != "mutasi_pengguna"
    signers_mengetahui = []
    if jenis == "mutasi_pengguna" or an_kpb:
        # KPB dari REGISTRY pejabat yang berlaku pada tanggal BAST (bukan
        # setelan mentah yang bisa kedaluwarsa) — fallback ke setelan kasatker.
        # Spesimen TTD digital KPB ikut tersemat (konsisten laporan lain).
        from pejabat_utils import penandatangan_kpb
        from shared_utils import ambil_ttd_img
        pj_list = await db.pejabat.find({}, _PROJ).to_list(2000)
        kpb = penandatangan_kpb(settings, pj_list, b.get("tanggal"))
        signers_mengetahui = [{'header': 'Mengetahui,',
                               'role': kpb["jabatan"],
                               'nama': kpb["nama"],
                               'after': [f"NIP. {kpb['nip']}"],
                               'ttd_img': await ambil_ttd_img(kpb.get("ttd_file_id"))}]
    peran_kesatu = ('Yang Menyerahkan,' if jenis != 'pengembalian' else 'Yang Menerima,')
    if an_kpb:
        peran_kesatu = peran_kesatu.rstrip(',') + ' a.n. Kuasa Pengguna Barang,'
    el.extend(_signature_block([
        {'header': 'PIHAK KEDUA,',
         'role': 'Yang Menerima,' if jenis != 'pengembalian' else 'Yang Menyerahkan,',
         'nama': p2.get("nama") or "................................",
         'after': [f"NIP/NIK. {p2.get('nip') or '-'}"]},
        {'pre': [_tempat_tanggal_laporan(settings, b.get("tanggal"))],
         'header': 'PIHAK KESATU,', 'role': peran_kesatu,
         'nama': p1.get("nama") or "................................",
         'after': [f"NIP. {p1.get('nip') or '-'}"]},
    ] + signers_mengetahui, doc.width))
    el.extend(_blok_tembusan(
        {"tembusan_laporan": b.get("tembusan") or settings.get("tembusan_laporan", "")}))

    # Lampiran foto (opsional): foto sampul tiap aset
    if b.get("sertakan_foto"):
        import base64
        foto_el = []
        aset_master = await db.assets.find(
            {"id": {"$in": b.get("asset_ids") or []}},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
             "photos": 1, "photo_gridfs_ids": 1, "thumbnail_index": 1},
        ).to_list(500)
        for a in aset_master:
            photos = a.get("photos") or []
            idx = a.get("thumbnail_index", 0) or 0
            url = photos[idx] if photos and idx < len(photos) else (photos[0] if photos else None)
            if not url:
                gids = a.get("photo_gridfs_ids") or []
                if gids:
                    gidx = max(0, min(int(idx), len(gids) - 1))
                    url = await _gridfs_photo_data_uri(gids[gidx]) or None
            if not url or "base64," not in str(url):
                continue
            try:
                img_bytes = base64.b64decode(str(url).split("base64,", 1)[1])
                img = RLImage(io.BytesIO(img_bytes))
                skala = min((doc.width * 0.6) / img.imageWidth, 80 * rl_mm / img.imageHeight)
                img.drawWidth, img.drawHeight = img.imageWidth * skala, img.imageHeight * skala
                img.hAlign = 'CENTER'
                from reportlab.platypus import KeepTogether as _KT
                foto_el.append(_KT([
                    Paragraph(
                        f"<b>{_esc(str(a.get('asset_code') or ''))} · NUP "
                        f"{_esc(str(a.get('NUP') or ''))}</b> — "
                        f"{_esc(str(a.get('asset_name') or ''))}", body),
                    img, Spacer(1, 4 * rl_mm)]))
            except Exception:
                continue
        if foto_el:
            el.append(PageBreak())
            el.extend(_title_block("LAMPIRAN\nFOTO BUKTI SERAH TERIMA BARANG"))
            el.extend(foto_el)

    footer = _page_footer_factory(f"BAST — {judul_jenis[:60]}")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="BAST_{bast_id[:8]}.pdf"'})
