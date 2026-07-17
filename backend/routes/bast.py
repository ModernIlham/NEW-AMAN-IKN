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

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import require_user
from db import db
from shared_utils import log_audit

bast_router = APIRouter()

_PROJ = {"_id": 0}

JENIS_BAST = {
    "penggunaan_melekat": "Penggunaan Barang Milik Negara (Melekat ke Pengguna)",
    "operasional_unit": "Operasional Penggunaan Barang Milik Negara pada Unit/Tempat/Tugas",
    "penggunaan_sementara": "Operasional Penggunaan Sementara Barang Milik Negara",
    "pengembalian": "Pengembalian Barang Milik Negara",
    "lainnya": "Serah Terima Barang Milik Negara",
}

DASAR_HUKUM = (
    "Undang-Undang Republik Indonesia Nomor 17 Tahun 2003 tentang Keuangan Negara;",
    "Peraturan Pemerintah Republik Indonesia Nomor 27 Tahun 2014 tentang "
    "Pengelolaan Barang Milik Negara/Daerah serta perubahannya;",
    "Peraturan Presiden Republik Indonesia Nomor 62 Tahun 2022 tentang "
    "Otorita Ibu Kota Nusantara;",
    "Peraturan Menteri Keuangan Republik Indonesia Nomor 246/PMK.06/2014 "
    "tentang Tata Cara Pelaksanaan Penggunaan Barang Milik Negara;",
    "Peraturan Menteri Keuangan Republik Indonesia Nomor 76/PMK.06/2019 "
    "tentang Perubahan Kedua atas PMK Nomor 246/PMK.06/2014;",
    "Peraturan Menteri Keuangan Republik Indonesia Nomor 53 Tahun 2023 "
    "tentang Pengelolaan Barang Milik Negara dan Aset Dalam Penguasaan "
    "di Ibu Kota Nusantara;",
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
    nomor: Optional[str] = ""                 # bisa dari Booking Nomor persuratan
    tanggal: Optional[str] = ""               # default hari ini
    jangka_dari: Optional[str] = ""           # khusus penggunaan_sementara
    jangka_sampai: Optional[str] = ""
    penanggung_jawab_tambahan: Optional[List[PjTambahanIn]] = None
    tembusan: Optional[str] = ""              # override; default pengaturan
    sertakan_foto: Optional[bool] = False
    keterangan: Optional[str] = ""


@bast_router.get("/bast/referensi")
async def referensi_bast(_user: dict = Depends(require_user)):
    return {"jenis": [{"kode": k, "uraian": v} for k, v in JENIS_BAST.items()]}


@bast_router.get("/bast")
async def daftar_bast(asset_id: str = "", q: str = "", page: int = 1,
                      page_size: int = 30, _user: dict = Depends(require_user)):
    """Riwayat BAST (filter per aset / cari nama penerima & nomor)."""
    page, page_size = max(1, page), min(max(1, page_size), 100)
    query = {}
    if asset_id.strip():
        query["asset_ids"] = asset_id.strip()
    if q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"nomor": rx}, {"pihak_kedua.nama": rx}, {"jenis": rx}]
    total = await db.bast_serah_terima.count_documents(query)
    items = await (db.bast_serah_terima.find(query, _PROJ)
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "label_jenis": JENIS_BAST}


@bast_router.post("/bast")
async def buat_bast(payload: BastIn, user: dict = Depends(require_user)):
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
         "brand": 1, "model": 1, "condition": 1, "purchase_date": 1,
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
    now = datetime.now(timezone.utc)
    record = {
        "id": str(uuid.uuid4()),
        "jenis": payload.jenis,
        "judul_lainnya": str(payload.judul_lainnya or "").strip(),
        "nomor": str(payload.nomor or "").strip(),
        "tanggal": (str(payload.tanggal or "").strip()[:10]
                    or now.date().isoformat()),
        "pihak_pertama": pihak_pertama,
        "pihak_kedua": payload.pihak_kedua.model_dump(),
        "asset_ids": [a["id"] for a in aset],
        # Snapshot identitas utk dokumen (foto TIDAK disnapshot — diambil
        # saat render bila sertakan_foto).
        "aset": [{k: a.get(k) for k in ("id", "asset_code", "NUP", "asset_name",
                                        "brand", "model", "condition",
                                        "purchase_date")} for a in aset],
        "jangka_dari": str(payload.jangka_dari or "").strip()[:10],
        "jangka_sampai": str(payload.jangka_sampai or "").strip()[:10],
        "penanggung_jawab_tambahan": [
            p.model_dump() for p in (payload.penanggung_jawab_tambahan or [])
            if str(p.nama or "").strip()],
        "tembusan": str(payload.tembusan or "").strip(),
        "sertakan_foto": bool(payload.sertakan_foto),
        "keterangan": str(payload.keterangan or "").strip(),
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
    }
    await db.bast_serah_terima.insert_one({**record})
    await log_audit("buat_bast", "", username=user.get("username", "system"),
                    detail=(f"BAST {JENIS_BAST[payload.jenis]} — "
                            f"{len(aset)} aset → {record['pihak_kedua']['nama']}"))
    return record


@bast_router.get("/bast/{bast_id}/pdf")
async def bast_pdf(bast_id: str, _user: dict = Depends(require_user)):
    """Render BAST 1-2 halaman + lampiran foto opsional."""
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, Image as RLImage

    from pelaporan_utils import narasi_hari_tanggal
    from routes.reports import (
        _blok_tembusan, _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _gridfs_photo_data_uri, _identity_table, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _tempat_tanggal_laporan, _title_block,
    )

    b = await db.bast_serah_terima.find_one({"id": bast_id}, _PROJ)
    if not b:
        raise HTTPException(status_code=404, detail="BAST tidak ditemukan")
    settings = await db.report_settings.find_one({"type": "global"}, _PROJ) or {}

    judul_jenis = (b.get("judul_lainnya") or JENIS_BAST.get(b.get("jenis"), "")
                   if b.get("jenis") == "lainnya"
                   else JENIS_BAST.get(b.get("jenis"), ""))
    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    body, bold = st['Body'], st['Heading']
    tengah = st['Signature']

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("BERITA ACARA SERAH TERIMA\n" + judul_jenis.upper(),
                           nomor=b.get("nomor") or "......./......./........"))

    nar = narasi_hari_tanggal(b.get("tanggal"))
    frasa = (f"Pada hari ini, {nar['hari']}, tanggal {nar['tanggal_terbilang']} "
             f"bulan {nar['bulan']} tahun {nar['tahun_terbilang']} "
             f"({_fmt_tanggal_id(b.get('tanggal'))})" if nar else "Pada hari ini")
    el.append(Paragraph(f"{frasa}, yang bertanda tangan di bawah ini:", body))
    el.append(Spacer(1, 2 * rl_mm))

    p1, p2 = b.get("pihak_pertama") or {}, b.get("pihak_kedua") or {}
    el.append(_identity_table([("Nama", p1.get("nama") or "-"),
                               ("NIP", p1.get("nip") or "-"),
                               ("Jabatan", p1.get("jabatan") or "-"),
                               ("Alamat", p1.get("alamat") or "-")]))
    el.append(Paragraph("Yang selanjutnya disebut <b>PIHAK KESATU</b>", body))
    el.append(Spacer(1, 2 * rl_mm))
    el.append(_identity_table([("Nama", p2.get("nama") or "-"),
                               ("NIP/NIK", p2.get("nip") or "-"),
                               ("Jabatan", p2.get("jabatan") or "-"),
                               ("Alamat", p2.get("alamat") or "-")]))
    el.append(Paragraph("Yang selanjutnya disebut <b>PIHAK KEDUA</b>", body))
    el.append(Spacer(1, 2 * rl_mm))
    arah = ("PIHAK KEDUA mengembalikan kepada PIHAK KESATU"
            if b.get("jenis") == "pengembalian"
            else "PARA PIHAK sepakat untuk melakukan serah terima")
    el.append(Paragraph(
        f"PIHAK KESATU dan PIHAK KEDUA selanjutnya disebut PARA PIHAK. "
        f"{arah} {judul_jenis} sebagaimana daftar terlampir, dengan dasar hukum:",
        body))
    for i, d in enumerate(DASAR_HUKUM, 1):
        el.append(Paragraph(f"{i}. {d}", st['BodyIndent']))
    el.append(Spacer(1, 3 * rl_mm))

    # PASAL 1 — objek serah terima (tabel multi-aset)
    el.append(Paragraph("<b>PASAL 1 — OBJEK SERAH TERIMA</b>", tengah))
    kalimat1 = ("PIHAK KEDUA menyerahkan kembali dan PIHAK KESATU menerima"
                if b.get("jenis") == "pengembalian"
                else "PIHAK KESATU menyerahkan dan PIHAK KEDUA menerima dengan baik")
    el.append(Paragraph(
        f"{kalimat1} Barang Milik Negara sebagai berikut:", body))
    data = [["No", "Nama Barang", "Kode Barang", "NUP",
             "Merk/Type/Spesifikasi", "Tahun", "Kondisi"]]
    for i, a in enumerate(b.get("aset") or [], 1):
        merk = " ".join(x for x in (a.get("brand"), a.get("model")) if x) or "-"
        tahun = str(a.get("purchase_date") or "")[:4] or "-"
        data.append([str(i), Paragraph(a.get("asset_name") or "-", st['Cell']),
                     a.get("asset_code") or "-", str(a.get("NUP") or "-"),
                     Paragraph(merk, st['Cell']), tahun,
                     a.get("condition") or "-"])
    t = Table(data, colWidths=_fit_col_widths([22, 120, 72, 30, 120, 34, 52],
                                              doc.width), repeatRows=1)
    t.setStyle(_std_table_style(zebra=True))
    el.append(t)
    el.append(Spacer(1, 3 * rl_mm))

    # PASAL 2+ — ketentuan sesuai jenis
    nomor_pasal = 2
    def pasal(judul, isi_list):
        nonlocal nomor_pasal
        el.append(Paragraph(f"<b>PASAL {nomor_pasal} — {judul}</b>", tengah))
        for i, isi in enumerate(isi_list, 1):
            el.append(Paragraph(
                (f"{i}. {isi}" if len(isi_list) > 1 else isi), st['BodyIndent']))
        el.append(Spacer(1, 2 * rl_mm))
        nomor_pasal += 1

    jenis = b.get("jenis")
    if jenis in ("penggunaan_melekat", "operasional_unit", "lainnya"):
        pasal("TANGGUNG JAWAB", [
            "Dengan ditandatanganinya Berita Acara ini, PIHAK KEDUA bertanggung "
            "jawab penuh atas penggunaan, pengamanan, dan pemeliharaan BMN tersebut.",
            "Apabila PIHAK KEDUA tidak lagi menjabat, berpindah tugas, atau "
            "berhenti berdasarkan ketentuan yang berlaku, BMN wajib dikembalikan "
            "kepada PIHAK KESATU dalam kondisi baik.",
            "PIHAK KEDUA dilarang mengalihkan dan/atau menyerahkan BMN kepada "
            "pihak lain tanpa sepengetahuan dan persetujuan tertulis PIHAK KESATU.",
        ])
    if jenis == "operasional_unit" and b.get("penanggung_jawab_tambahan"):
        baris = [f"{p.get('nama')} — {p.get('unit_tempat_tugas') or '-'}"
                 for p in b["penanggung_jawab_tambahan"]]
        pasal("PENANGGUNG JAWAB PENGGUNAAN",
              ["Pembagian penanggung jawab penggunaan pada unit/tempat/tugas:"]
              + baris)
    if jenis == "penggunaan_sementara":
        pasal("STATUS ASET", [
            "BMN tetap tercatat pada PIHAK KESATU; penggunaan sementara ini "
            "tidak mengakibatkan beralihnya hak kepemilikan.",
            "Aset tetap berada dalam pengawasan dan pengendalian PIHAK KESATU.",
        ])
        pasal("JANGKA WAKTU DAN PENGEMBALIAN", [
            f"Penggunaan sementara berlaku sejak {_fmt_tanggal_id(b.get('jangka_dari')) or '…'} "
            f"sampai dengan {_fmt_tanggal_id(b.get('jangka_sampai')) or '…'} atau "
            "sampai adanya pemberitahuan lain dari PIHAK KESATU.",
            "Setelah jangka waktu berakhir atau sewaktu-waktu diperlukan, PIHAK "
            "KEDUA wajib mengembalikan BMN dalam kondisi baik.",
        ])
    if jenis == "pengembalian":
        pasal("PERNYATAAN", [
            "PIHAK KEDUA menyatakan telah mengembalikan seluruh BMN tersebut dan "
            "PIHAK KESATU menyatakan menerima dalam kondisi sebagaimana tercantum "
            "pada tabel objek serah terima.",
        ])
    if b.get("keterangan"):
        pasal("KETERANGAN LAIN", [b["keterangan"]])
    pasal("PENUTUP", [
        "Apabila di kemudian hari terdapat kekeliruan dalam Berita Acara ini, "
        "akan diadakan perbaikan sebagaimana mestinya.",
        "Demikian Berita Acara Serah Terima ini dibuat dan ditandatangani oleh "
        "PARA PIHAK untuk dipergunakan sebagaimana mestinya.",
    ])

    el.append(Spacer(1, 4 * rl_mm))
    el.extend(_signature_block([
        {'header': 'PIHAK KEDUA,', 'role': 'Yang Menerima' if jenis != 'pengembalian' else 'Yang Menyerahkan',
         'nama': p2.get("nama") or "________________",
         'after': [f"NIP/NIK. {p2.get('nip') or '…'}"]},
        {'pre': [_tempat_tanggal_laporan(settings, b.get("tanggal"))],
         'header': 'PIHAK KESATU,', 'role': 'Yang Menyerahkan' if jenis != 'pengembalian' else 'Yang Menerima',
         'nama': p1.get("nama") or "________________",
         'after': [f"NIP. {p1.get('nip') or '…'}"]},
    ], doc.width))
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
                foto_el.append(Paragraph(
                    f"<b>{a.get('asset_code')} · NUP {a.get('NUP')}</b> — {a.get('asset_name')}",
                    body))
                foto_el.append(img)
                foto_el.append(Spacer(1, 4 * rl_mm))
            except Exception:
                continue
        if foto_el:
            el.append(PageBreak())
            el.extend(_title_block("LAMPIRAN\nFOTO BUKTI SERAH TERIMA BARANG"))
            el.extend(foto_el)

    footer = _page_footer_factory(f"BAST — {judul_jenis}")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="BAST_{bast_id[:8]}.pdf"'})
