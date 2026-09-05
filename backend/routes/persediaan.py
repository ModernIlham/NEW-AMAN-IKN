"""Modul Inventarisasi Persediaan — AKTIF (§7.4).

Master barang persediaan satker (aset lancar, kodefikasi berawalan '1')
beserta seluruh siklusnya: CRUD master (paging/pencarian), transaksi
masuk/keluar ber-layer FIFO + jurnal (jenis SAKTI lengkap), tautan dokumen
sumber Pengadaan (BAST), pindah gudang & transaksi massal, peringatan +
Nota Dinas, stock opname + BAOF, rincian layer FIFO, serta laporan Posisi
(kolom akun neraca 1171xx + rekap per akun) & Mutasi. Master lahir dengan
stok 0 & layer kosong; stok/`batches` hanya berubah lewat transaksi/opname;
hapus master hanya boleh saat stok 0.

Regulasi: docs/PUSTAKA-REGULASI-BMN.md §3 (perpetual + FIFO per layer,
kode golongan '1', batas kritis & kedaluwarsa untuk peringatan/nota dinas).
Referensi teknis: modul persediaan KERJA-BARENG (dipelajari menyeluruh).
"""
import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (APIRouter, Depends, File, Header, HTTPException, Query,
                     Request, UploadFile)
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
    require_writer_satker,
)
from db import db
from shared_utils import kunci_idem, limiter, log_audit
from meili_utils import jadwalkan_sync, jadwalkan_hapus, cari_id_persediaan
from pencarian_utils import klausa_teks, pecah_kata
from pegawai_utils import baris_identitas_isian, baris_identitas_ttd
from persediaan_akun_utils import akun_persediaan
from persediaan_fields import EDITABLE_FIELD_NAMES
from persediaan_utils import (
    tanggal_wib, today_wib,
    JENIS_KELUAR, JENIS_MASUK, KODE_PENUH_LEN, KODE_PREFIX_LEN, SATUAN_BAKU,
    baris_csv_transaksi, buat_layer, klasifikasi_kedaluwarsa, konsumsi_fifo,
    koreksi_nilai_layers, mutasi_periode, next_kode_penuh, next_nup,
    nilai_persediaan_dari_batches, parse_import_persediaan_rows,
    penyesuaian_opname, rekap_nonaktif, status_stok,
    validate_hapus_definitif, validate_kode_persediaan,
    validate_pindah_gudang, validate_transaksi_keluar,
    validate_transaksi_masuk,
)
from pengadaan_utils import JENIS_PEROLEHAN, snapshot_perolehan

persediaan_router = APIRouter()


async def _insert_jurnal(jurnal):
    """Tulis jurnal transaksi + stempel `kode_satker` dari master item.

    Jurnal lama tidak berstempel sehingga isolasi memakai relasi
    `persediaan_id` ($in id master) — mahal saat koleksi besar. Baris BARU
    kini berstempel; setelah backfill (scripts/backfill_kode_satker_
    transaksi_persediaan.py) `_scope_jurnal` dapat beralih ke
    `scope_query_field_satker` murni."""
    if not jurnal.get("kode_satker"):
        pid = jurnal.get("persediaan_id")
        if pid:
            m = await db.persediaan.find_one(
                {"id": pid}, {"_id": 0, "kode_satker": 1})
            jurnal["kode_satker"] = str((m or {}).get("kode_satker") or "")
    await db.transaksi_persediaan.insert_one(jurnal)


async def _scope_jurnal(user, query=None) -> dict:
    """Sisipkan isolasi satker ke query jurnal `transaksi_persediaan`.

    Jurnal sengaja RAMPING dan tidak membawa `kode_satker`, jadi isolasi
    ditegakkan lewat relasi `persediaan_id` → master persediaan yang memang
    berstempel (pola sama dipakai wasdal.py). Tanpa ini seluruh laporan/ekspor
    jurnal membocorkan mutasi stok satker lain — data yang justru ditolak 403
    saat diakses per-item. User lintas-satker (super-admin) apa adanya.
    """
    from shared_utils import kode_satker_user, scope_query_field_satker
    q = dict(query or {})
    if not kode_satker_user(user):
        return q
    ids = [p["id"] async for p in db.persediaan.find(
        scope_query_field_satker(user), {"_id": 0, "id": 1}) if p.get("id")]
    # Jangan MENIMPA filter per-item yang sudah ada di query — iris kan
    # (dulu q["persediaan_id"] ditulis tanpa syarat, filter apa pun hilang).
    ada = q.get("persediaan_id")
    if isinstance(ada, str):
        q["persediaan_id"] = ada if ada in set(ids) else "__tak-berhak__"
    elif isinstance(ada, dict) and isinstance(ada.get("$in"), list):
        irisan = [i for i in ada["$in"] if i in set(ids)]
        q["persediaan_id"] = {"$in": irisan}
    else:
        q["persediaan_id"] = {"$in": ids}
    return q


async def _kpb_signer(settings, per_iso=None, user=None):
    """Penanda tangan Kuasa Pengguna Barang untuk PDF persediaan — delegasi ke
    resolver bersama `shared_utils.resolve_penandatangan_kpb` (temuan #26/#41:
    default tanggal = hari ini sehingga rentang berlaku SK pejabat DICEK;
    fallback setelan kasatker). Kembalikan {nama, nip, jabatan, sumber}.

    `user` (opsional) membatasi kandidat KPB ke satker penerbit dokumen
    (isolasi M-SCOPE); tanpa user → semua pejabat (perilaku lama)."""
    from shared_utils import resolve_penandatangan_kpb, kode_satker_user
    return await resolve_penandatangan_kpb(settings, per_iso,
                                           kode_satker_user(user))


def _hdr_kpb(kpb, label="Kuasa Pengguna Barang"):
    """Baris jabatan KPB dengan awalan 'Plt./Plh.' bila dijabat pelaksana
    tugas/harian (rangkap jabatan). Selalu berakhiran koma."""
    from pejabat_utils import prefiks_pelaksana
    return f"{prefiks_pelaksana((kpb or {}).get('jenis_pelaksana'))}{label},"


class PersediaanCreate(BaseModel):
    kode_barang: str = Field(min_length=1, max_length=KODE_PENUH_LEN)
    nup: str = ""                     # kosong → otomatis
    nama_barang: str = Field(min_length=1, max_length=300)
    merk: str = ""
    tipe: str = ""
    satuan: str = "Buah"
    lokasi: str = ""
    batas_kritis: int = Field(0, ge=0)
    expired_default: str = ""         # YYYY-MM-DD; kedaluwarsa bawaan batch
    tahun_anggaran: str = ""
    keterangan: str = ""


class PersediaanUpdate(BaseModel):
    nama_barang: Optional[str] = Field(None, min_length=1, max_length=300)
    merk: Optional[str] = None
    tipe: Optional[str] = None
    satuan: Optional[str] = None
    lokasi: Optional[str] = None
    batas_kritis: Optional[int] = Field(None, ge=0)
    expired_default: Optional[str] = None
    tahun_anggaran: Optional[str] = None
    keterangan: Optional[str] = None


def _doc(item: dict) -> dict:
    stok = int(item.get("stok", 0) or 0)
    return {
        **{k: item.get(k) for k in (
            "id", "kode_barang", "nup", "nama_barang", "merk", "tipe", "satuan",
            "lokasi", "batas_kritis", "expired_default", "tahun_anggaran",
            "keterangan", "stok", "version", "created_at", "updated_at")},
        "status_stok": status_stok(stok, item.get("batas_kritis")),
    }


@persediaan_router.get("/persediaan/satuan-baku")
async def list_satuan(_user: dict = Depends(require_user)):
    """Daftar satuan baku untuk dropdown (referensi, bukan pembatasan keras)."""
    return list(SATUAN_BAKU)


# CATATAN URUTAN: route literal HARUS terdaftar sebelum GET /persediaan/{item_id}
# di bawah — kalau tidak, path literal tertelan sebagai item_id.
@persediaan_router.get("/persediaan/peringatan")
async def peringatan_persediaan(
    horizon_hari: int = Query(30, ge=1, le=365),
    _user: dict = Depends(require_user),
):
    """Daftar pantau (pustaka §3): stok habis/kritis + layer kedaluwarsa.

    Bahan banner peringatan & nota dinas — dihitung dari data nyata
    (stok vs batas kritis; expired layer vs hari ini + horizon).
    """
    today_iso = today_wib()   # tanggal lokal WIB (#25/#44)
    habis, kritis, lewat, segera = [], [], [], []
    # Isolasi satker (REVIEW-9 R9): dipakai juga oleh PDF Nota Dinas di bawah.
    from shared_utils import scope_query_field_satker
    cursor = db.persediaan.find(scope_query_field_satker(_user), {"_id": 0})
    async for item in cursor:
        stok = int(item.get("stok", 0) or 0)
        st = status_stok(stok, item.get("batas_kritis"))
        ringkas = {"id": item.get("id"), "kode_barang": item.get("kode_barang"),
                   "nup": item.get("nup"), "nama_barang": item.get("nama_barang"),
                   "satuan": item.get("satuan"), "stok": stok,
                   "batas_kritis": item.get("batas_kritis", 0)}
        if st == "habis":
            habis.append(ringkas)
        elif st == "kritis":
            kritis.append(ringkas)
        exp_lewat, exp_segera = klasifikasi_kedaluwarsa(
            item.get("batches"), today_iso, horizon_hari)
        for e in exp_lewat:
            lewat.append({**ringkas, **e})
        for e in exp_segera:
            segera.append({**ringkas, **e})
    return {"tanggal": today_iso, "horizon_hari": horizon_hari,
            "habis": habis, "kritis": kritis,
            "kedaluwarsa": lewat, "segera_kedaluwarsa": segera,
            "total_masalah": len(habis) + len(kritis) + len(lewat) + len(segera)}


async def bangun_nota_dinas_pdf(jenis, rows, tanggal, settings, kpb,
                                horizon_hari=30, seleksi=False, nomor="",
                                yth="") -> bytes:
    """Susun PDF Nota Dinas persediaan → bytes.

    Dipisah dari route-nya (pola `bangun_lpb_pdf`) karena berkasnya kini punya
    DUA pemanggil: pratinjau yang menghitung daftarnya saat itu juga, dan nota
    TERBIT yang mencetak ulang daftar beku dari register. Keduanya wajib
    menghasilkan dokumen yang bentuknya sama persis — kalau tidak, yang
    dipratinjau bukan yang terbit.

    `rows` sudah tersaring dan siap cetak; fungsi ini tidak menghitung ulang
    peringatan apa pun. `kpb` dibekukan oleh pemanggil supaya nota tahun lalu
    tetap menyebut pejabat yang menandatanganinya, bukan pejabat hari ini.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _identity_table,
        _kop_surat_flowables, _page_footer_factory, _signature_block, _std_doc,
        _std_table_style, _title_block,
    )
    import persediaan_nota_utils as pnu
    import persuratan_utils as psu

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    body = pnu.isi_tabel(jenis, rows, fmt_tanggal=_fmt_tanggal_id)

    # ── KEPALA NASKAH DINAS ─────────────────────────────────────────────
    #
    # Sebelumnya hanya judul lalu tabel: tanpa tujuan, tanpa pengirim, tanpa
    # nomor, tanpa hal. Dokumen yang tak menyebut kepada siapa ia ditujukan
    # tak dapat diagendakan, tak dapat ditindaklanjuti penerimanya, dan tak
    # dapat diarsipkan sebagai naskah dinas — ia hanya cetakan daftar.
    # Susunannya mengikuti PerANRI 5/2021 (lihat persuratan_utils).
    elements.extend(_title_block(pnu.judul(jenis)))
    elements.append(_identity_table(psu.kepala_nota_dinas(
        yth=(str(yth or "").strip() or "Pejabat Pengadaan Barang/Jasa"),
        dari=_hdr_kpb(kpb).rstrip(","),
        nomor=nomor,
        hal=pnu.hal(jenis),
        lampiran=("1 (satu) berkas" if body else "-"),
        tanggal_iso=tanggal)))
    elements.append(Spacer(1, 3 * rl_mm))
    elements.append(Paragraph(
        pnu.pengantar(jenis, horizon_hari=horizon_hari, seleksi=seleksi),
        st['Meta']))
    elements.append(Paragraph(
        f"Data per {_fmt_tanggal_id(tanggal)}.", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    if not body:
        elements.append(Paragraph(
            "Tidak ada barang yang memenuhi kriteria saat ini.", st['Cell']))
    else:
        table_data = [[Paragraph(h, st['TableHeader'])
                       for h in pnu.headers(jenis)]]
        for r in body:
            table_data.append([Paragraph(str(c), st['Cell']) for c in r])
        table = Table(table_data,
                      colWidths=_fit_col_widths(pnu.widths(jenis), doc.width),
                      repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [psu.tempat_tanggal(settings, tanggal)],
         'header': _hdr_kpb(kpb),
         'nama': kpb["nama"],
         # Non-ASN: baris NIP/NIK tidak dicetak (privasi)
         'after': baris_identitas_ttd(kpb['nip'],
                                      kpb.get("status_kepegawaian"))},
    ], doc.width))

    footer = _page_footer_factory("Nota Dinas Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return buffer.getvalue()


@persediaan_router.get("/persediaan/nota-dinas")
async def nota_dinas_persediaan(
    jenis: str = Query(..., pattern="^(kritis|kedaluwarsa)$"),
    horizon_hari: int = Query(30, ge=1, le=365),
    ids: str = Query("", max_length=8000),
    _user: dict = Depends(require_user),
):
    """PRATINJAU nota dinas PDF (pustaka §3): stok kritis/habis ATAU layer
    kedaluwarsa — kop surat + kepala naskah + tabel + tanda tangan KPB.

    TANPA NOMOR dan tanpa jejak: daftarnya dihitung saat ini juga, sehingga
    dua unduhan pada hari yang sama bisa berbeda isi bila stok bergerak di
    antaranya. Untuk naskah yang benar-benar terbit — bernomor, dibekukan,
    dan dapat ditemukan lagi — pakai `POST /persediaan/nota-dinas/terbitkan`.

    `ids` (id barang dipisah koma) menyaring ke barang TERPILIH saja —
    tidak semua yang habis/kritis otomatis diusulkan pengadaan ulang;
    kandidatnya tetap dihitung ulang dari peringatan (id di luar daftar
    peringatan diabaikan, bukan disisipkan). Kosong = semua (perilaku lama).
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from shared_utils import kode_satker_user, pengaturan_kop

    import persediaan_nota_utils as pnu

    data = await peringatan_persediaan(horizon_hari=horizon_hari, _user=_user)
    # Kop dari MASTER SATKER pemakai, bukan setelan global apa adanya —
    # sumber yang sama dengan nota terbit. Dua sumber kop yang berbeda
    # membuat pratinjau dan naskah yang benar-benar terbit berkop berlainan
    # pada satker yang punya kop sendiri, dan tak ada yang menyebutkannya.
    settings = await pengaturan_kop(kode_satker=kode_satker_user(_user))
    terpilih = {s for s in (x.strip() for x in ids.split(",")) if s}
    rows = pnu.baris_terpilih(jenis, data, terpilih)
    kpb = await _kpb_signer(settings, user=_user)

    isi = await bangun_nota_dinas_pdf(
        jenis, rows, data["tanggal"], settings, kpb,
        horizon_hari=data["horizon_hari"], seleksi=bool(terpilih),
        yth=str(settings.get("nota_dinas_yth") or "").strip())
    fname = pnu.nama_berkas(jenis)
    return StreamingResponse(BytesIO(isi), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


class TerbitNotaDinasIn(BaseModel):
    jenis: str = Field(pattern="^(kritis|kedaluwarsa)$")
    horizon_hari: int = Field(30, ge=1, le=365)
    ids: list[str] = Field(default_factory=list, max_length=2000)
    yth: str = ""
    kode_klasifikasi: str = ""


@persediaan_router.post("/persediaan/nota-dinas/terbitkan")
async def terbitkan_nota_dinas(payload: TerbitNotaDinasIn,
                               user: dict = Depends(require_writer_satker)):
    """TERBITKAN nota dinas: booking nomor ke buku agenda Persuratan, bekukan
    daftar barangnya, simpan ke register.

    Kenapa penerbitan berdiri sendiri, bukan nomor yang dibooking saat unduh:
    nomor surat adalah deret yang tak pernah dipakai ulang, sementara tombol
    unduh ditekan berkali-kali — sekali untuk melihat, sekali untuk dicetak,
    sekali lagi karena berkasnya terselip. Membooking di jalur unduh berarti
    buku agenda penuh nomor yang tak pernah menjadi naskah apa pun.

    Daftarnya DIBEKUKAN pada saat terbit (pola LPB). Nota bernomor yang
    dicetak ulang dari peringatan yang dihitung ulang akan berubah isi tiap
    kali stok bergerak, sementara nomornya tetap sama — dokumen yang beredar
    dan dokumen yang tercetak lalu berselisih tanpa satu pun tanda.

    Gagal booking TIDAK membatalkan penerbitan (pola BAST/Surat Persetujuan):
    notanya tetap tercatat, nomornya tampil sebagai titik-titik, dan dapat
    dilengkapi kemudian dari Registrasi Persuratan.
    """
    import persediaan_nota_utils as pnu
    from shared_utils import kode_satker_user, pengaturan_kop

    data = await peringatan_persediaan(horizon_hari=payload.horizon_hari,
                                       _user=user)
    terpilih = {s.strip() for s in (payload.ids or []) if str(s).strip()}
    rows = pnu.baris_terpilih(payload.jenis, data, terpilih)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail=("Tidak ada barang yang memenuhi kriteria — nota dinas "
                    "kosong tidak diterbitkan"))

    ks = kode_satker_user(user)
    settings = await pengaturan_kop(kode_satker=ks)
    kpb = await _kpb_signer(settings, per_iso=data["tanggal"], user=user)
    now = datetime.now(timezone.utc).isoformat()

    nomor, surat_id = "", ""
    try:
        from routes.persuratan import booking_nomor_otomatis
        nomor, surat_id = await booking_nomor_otomatis(
            user, data["tanggal"],
            perihal=pnu.perihal_agenda(payload.jenis),
            tujuan=(str(payload.yth or "").strip()
                    or str(settings.get("nota_dinas_yth") or "").strip()),
            keterangan="booking otomatis dari nota dinas persediaan",
            kode_satker=ks, kode_klasifikasi=payload.kode_klasifikasi,
            jenis_naskah="Nota Dinas", referensi="NOTA-PERSEDIAAN")
    except Exception:
        nomor, surat_id = "", ""

    nid = str(uuid.uuid4())
    await db.persediaan_nota.insert_one({
        "id": nid, "kode_satker": ks,
        "jenis": payload.jenis, "tanggal": data["tanggal"],
        "horizon_hari": data["horizon_hari"],
        # `seleksi` dibekukan, bukan disimpulkan belakangan dari jumlah baris:
        # daftar yang kebetulan memuat SEMUA barang kritis saat terbit akan
        # tampak "tersaring" begitu satu barang kritis baru muncul, dan
        # kalimat "sengaja tidak disertakan" lalu muncul pada nota yang
        # sebenarnya lengkap.
        "seleksi": bool(terpilih),
        "yth": str(payload.yth or "").strip()
               or str(settings.get("nota_dinas_yth") or "").strip(),
        "hal": pnu.hal(payload.jenis),
        "items": pnu.bekukan(payload.jenis, rows),
        "jumlah_barang": len(rows),
        "nomor": nomor, "surat_id": surat_id,
        # KPB dibekukan — pejabat berganti, nota tahun lalu harus tetap
        # menyebut yang menandatanganinya (pola `ppk_nama` pada LPB).
        "kpb_nama": str((kpb or {}).get("nama") or ""),
        "kpb_nip": str((kpb or {}).get("nip") or ""),
        "kpb_jenis_pelaksana": str((kpb or {}).get("jenis_pelaksana") or ""),
        "kpb_status_kepegawaian": str(
            (kpb or {}).get("status_kepegawaian") or ""),
        "created_by": user.get("username", "system"),
        "created_at": now, "updated_at": now,
    })
    await log_audit("persediaan_nota_terbit", "", nid,
                    username=user.get("username", "system"),
                    detail=f"{payload.jenis} — {len(rows)} barang — "
                           f"{nomor or 'tanpa nomor'}")
    return {"id": nid, "nomor": nomor, "surat_id": surat_id,
            "jumlah_barang": len(rows),
            "message": ("Nota dinas terbit"
                        + (f" dengan nomor {nomor}" if nomor
                           else " tanpa nomor — buku agenda tidak merespons"))}


@persediaan_router.get("/persediaan/nota-dinas/register")
async def daftar_nota_dinas(page: int = Query(1, ge=1),
                            page_size: int = Query(30, ge=1, le=100),
                            jenis: str = Query("", pattern="^(|kritis|kedaluwarsa)$"),
                            _user: dict = Depends(require_user)):
    """Riwayat nota dinas persediaan yang TERBIT.

    Tanpa layar ini nota bernomor hanya hidup di dialog tempat ia dibuat:
    begitu ditutup, satu-satunya jejaknya adalah nomor di buku agenda yang
    tak menunjuk balik ke daftar barangnya.
    """
    from shared_utils import scope_query_field_satker
    q = scope_query_field_satker(_user)
    if str(jenis or "").strip():
        q = {**q, "jenis": jenis}
    total = await db.persediaan_nota.count_documents(q)
    items = await (db.persediaan_nota.find(q, {"_id": 0, "items": 0})
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    # Status TTD elektronik ikut — potongan yang SAMA dengan Riwayat LPB dan
    # Riwayat BAST (lihat `ttd_penautan`), bukan salinan keenam.
    from ttd_penautan import lampirkan_status_ttd
    await lampirkan_status_ttd(db, "nota_persediaan", items)
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size))}


async def bangun_nota_register_pdf(nid: str, _user: dict) -> tuple:
    """Ambil nota terbit + susun PDF-nya → `(bytes, nota)`.

    Dipisah dari route-nya (pola `bangun_lpb_pdf`) karena jalur TTD elektronik
    membutuhkan berkasnya sebagai BYTE untuk dibekukan ke GridFS — penanda
    tangan meneken dokumen yang benar-benar ia baca, bukan yang dibangun ulang
    belakangan. Gerbang kepemilikan satkernya ikut di sini supaya kedua
    pemanggil tak bisa lupa memasangnya.
    """
    from shared_utils import pastikan_akses_dok_satker, pengaturan_kop

    nota = await db.persediaan_nota.find_one({"id": nid}, {"_id": 0})
    if not nota:
        raise HTTPException(status_code=404, detail="Nota dinas tidak ditemukan")
    await pastikan_akses_dok_satker(_user, nota)

    settings = await pengaturan_kop(kode_satker=str(nota.get("kode_satker") or ""))
    kpb = {"nama": nota.get("kpb_nama") or "",
           "nip": nota.get("kpb_nip") or "",
           "jenis_pelaksana": nota.get("kpb_jenis_pelaksana") or "",
           "status_kepegawaian": nota.get("kpb_status_kepegawaian") or ""}
    isi = await bangun_nota_dinas_pdf(
        nota.get("jenis"), nota.get("items") or [], nota.get("tanggal"),
        settings, kpb, horizon_hari=int(nota.get("horizon_hari") or 30),
        seleksi=bool(nota.get("seleksi")), nomor=str(nota.get("nomor") or ""),
        yth=str(nota.get("yth") or ""))
    return isi, nota


@persediaan_router.get("/persediaan/nota-dinas/{nid}/pdf")
async def unduh_nota_dinas(nid: str, _user: dict = Depends(require_user)):
    """PDF nota dinas TERBIT — dicetak dari daftar beku di register, bukan
    dari peringatan yang dihitung ulang."""
    from io import BytesIO

    from fastapi.responses import StreamingResponse

    import persediaan_nota_utils as pnu

    isi, nota = await bangun_nota_register_pdf(nid, _user)
    fname = pnu.nama_berkas(nota.get("jenis"), nota.get("nomor"))
    return StreamingResponse(BytesIO(isi), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


class KirimTtdNotaIn(BaseModel):
    mode: str = "berurutan"
    signers: list[dict] = Field(default_factory=list, max_length=10)


@persediaan_router.post("/persediaan/nota-dinas/{nid}/kirim-ttd")
async def kirim_ttd_nota_dinas(nid: str, payload: KirimTtdNotaIn,
                               user: dict = Depends(require_writer_satker)):
    """Kirim nota dinas untuk diteken elektronik (pola Surat Persetujuan/LPB).

    Penanda tangan bawaannya adalah KPB yang SUDAH DIBEKUKAN pada nota — bukan
    yang berlaku hari ini. Meresolusi ulang di sini akan mengirim dokumen yang
    blok tanda tangannya menyebut satu nama kepada orang yang bernama lain.

    PDF-nya dibekukan ke GridFS SEKARANG: penanda tangan meneken dokumen yang
    benar-benar ia baca.
    """
    from routes.ttd import PermintaanIn, SignerIn, buat_permintaan

    import persediaan_nota_utils as pnu

    isi, nota = await bangun_nota_register_pdf(nid, user)

    daftar = list(payload.signers or [])
    if not daftar and str(nota.get("kpb_nama") or "").strip():
        from pejabat_utils import jabatan_kapasitas_kpb
        daftar = [{"nama": str(nota.get("kpb_nama") or ""),
                   "nip": str(nota.get("kpb_nip") or ""),
                   "jabatan": jabatan_kapasitas_kpb(
                       {"jenis_pelaksana": nota.get("kpb_jenis_pelaksana")}),
                   "email": ""}]
    if not daftar:
        raise HTTPException(
            status_code=400,
            detail="Nota ini terbit tanpa KPB — isi Referensi Pejabat, atau "
                   "kirim daftar penanda tangan secara manual")

    hasil = await buat_permintaan(
        payload=PermintaanIn(
            judul=f"Nota Dinas {nota.get('nomor') or nid[:8]}",
            doc_type="nota_persediaan", doc_ref=nid,
            mode=("paralel" if payload.mode == "paralel" else "berurutan"),
            signers=[SignerIn(nama=str(s.get("nama") or ""),
                              nip=str(s.get("nip") or ""),
                              jabatan=str(s.get("jabatan") or ""),
                              email=str(s.get("email") or ""))
                     for s in daftar]),
        user=user)

    nama_berkas = pnu.nama_berkas(nota.get("jenis"), nota.get("nomor"))
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        isi, nama=nama_berkas, content_type="application/pdf",
        metadata={"kind": "nota_persediaan", "nota_id": nid})
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id), "dok_nama": nama_berkas,
                  "dok_halaman": 1}})
    # Tautan MAJU ditulis `buat_permintaan` (ttd_penautan.catat_pengiriman_ttd).
    await log_audit("persediaan_nota_kirim_ttd", "", nid,
                    username=user.get("username", "system"),
                    detail=f"dikirim ke {len(daftar)} penanda tangan")
    return {**hasil, "nota_id": nid}


def _fmt_rp(val):
    try:
        return f"{int(val):,}".replace(",", ".")
    except (ValueError, TypeError, OverflowError):
        return "0"


# DITURUNKAN dari registry (persediaan_fields.py) — dulu hardcode 11 nama
# yang kebetulan sama; field baru di registry akan tertinggal diam-diam
# tanpa satu test pun yang menagih (temuan audit kesegaran template).
from persediaan_fields import FIELD_NAMES as _TEMPLATE_HEADERS  # noqa: E402


@persediaan_router.get("/persediaan/template")
async def template_persediaan(_user: dict = Depends(require_user)):
    """Template CSV impor master persediaan (kode 10 digit → nomor urut otomatis)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(_TEMPLATE_HEADERS)
    w.writerow(["1010101001", "", "Kertas HVS A4 80gr", "SiDU", "", "Rim", "Gudang ATK", "5", "", "2026", ""])
    w.writerow(["1010101001000002", "1", "Tinta Printer Hitam", "Epson", "003", "Botol", "Gudang ATK", "2", "", "2026", "contoh kode 16 digit"])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="template_persediaan.csv"'})


@persediaan_router.get("/persediaan/export")
async def export_persediaan(_user: dict = Depends(require_user)):
    """Ekspor CSV master persediaan + stok & nilai FIFO terkini."""
    import csv as csv_module
    import io

    from fastapi.responses import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(_TEMPLATE_HEADERS + ["stok", "nilai"])
    # Scope satker (REVIEW-9 R3): tanpa filter, user satker B mengunduh
    # seluruh master (stok + nilai) satker lain — data yang per item justru
    # ditolak 403 — dan roundtrip ekspor→impor menduplikasinya ke satker B.
    from shared_utils import scope_query_field_satker
    async for it in db.persediaan.find(
            scope_query_field_satker(_user), {"_id": 0}
            ).sort([("nama_barang", 1), ("kode_barang", 1)]):
        w.writerow([
            it.get("kode_barang"), it.get("nup"), it.get("nama_barang"),
            it.get("merk"), it.get("tipe"), it.get("satuan"), it.get("lokasi"),
            it.get("batas_kritis", 0), it.get("expired_default"),
            it.get("tahun_anggaran"), it.get("keterangan"),
            int(it.get("stok", 0) or 0),
            int(nilai_persediaan_dari_batches(it.get("batches"))),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="master_persediaan.csv"'})


@persediaan_router.get("/persediaan/transaksi/export")
async def export_transaksi_persediaan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh jurnal transaksi persediaan (pola #158).

    Bahan rekonsiliasi SAKTI: tiap gerakan stok (masuk/keluar/mutasi/opname)
    satu baris, terurut waktu, memuat kode transaksi SAKTI, nilai FIFO, dan
    saldo berjalan. Baca-saja — helper murni `baris_csv_transaksi` yang
    membentuk baris (teruji unit)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response

    # Batas keras: jurnal append-only tumbuh monoton — tanpa pagar ini
    # ekspor berubah jadi OOM diam-diam saat koleksi membesar.
    items = [t async for t in db.transaksi_persediaan.find(
        await _scope_jurnal(_user), {"_id": 0})
        .sort("timestamp", 1).limit(200000)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_transaksi(items):
        w.writerow(row)
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition":
                             'attachment; filename="jurnal_transaksi_persediaan.csv"'})


@persediaan_router.get("/persediaan/transaksi")
async def daftar_transaksi_persediaan(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    arah: str = Query("", pattern=r"^(masuk|keluar|mutasi|nilai|hapus)?$"),
    kode: str = Query("", max_length=3),
    dari: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
    sampai: str = Query("", pattern=r"^(\d{4}-\d{2}-\d{2})?$"),
    q: str = Query("", max_length=120),
    _user: dict = Depends(require_user),
):
    """DAFTAR TRANSAKSI persediaan lintas barang (mandat 45 kode SAKTI).

    Satu layar untuk seluruh jurnal: filter arah, kode transaksi SAKTI,
    rentang tanggal, dan teks (kode/nama barang, no bukti). Kode SAKTI
    difilter lewat kunci `jenis` (identitas stabil) — field `kode_sakti`
    tersimpan bisa berisi kode warisan pra-koreksi sehingga tak dipercaya;
    kode pada respons pun diturunkan ulang dari registry.
    """
    import re as re_module

    from persediaan_transaksi_ref import (
        JENIS_KE_KODE, info_kode, kode_sakti_dari_jenis,
    )

    query = await _scope_jurnal(_user)
    if arah:
        query["arah"] = arah
    if kode:
        kunci = [j for j, k in JENIS_KE_KODE.items()
                 if k == kode.strip().upper()]
        # Kode tak dikenal / belum pernah dipakai → hasil kosong yang jujur
        query["jenis"] = {"$in": kunci} if kunci else "__tidak_ada__"
    if dari:
        query.setdefault("timestamp", {})["$gte"] = dari
    if sampai:
        # Inklusif sampai akhir hari — '~' > semua karakter timestamp ISO
        query.setdefault("timestamp", {})["$lte"] = sampai + "~"
    # Multi-kata: tiap kata wajib ada, boleh tersebar di field berbeda
    # (mis. "atk januari" = kode/nama barang + nomor bukti).
    query.update(klausa_teks(q, ("kode_barang", "nama_barang", "no_bukti")))
    total = await db.transaksi_persediaan.count_documents(query)
    rows = [t async for t in db.transaksi_persediaan.find(query, {"_id": 0})
            .sort("timestamp", -1).skip((page - 1) * page_size).limit(page_size)]
    items = []
    for t in rows:
        kode_benar = kode_sakti_dari_jenis(t.get("jenis"), t.get("kode_sakti"))
        ref = info_kode(kode_benar)
        items.append({**t, "kode_sakti": kode_benar,
                      "uraian_kode": ref.get("uraian") or t.get("jenis_label") or "",
                      "kelompok": ref.get("kelompok", ""),
                      "label_kelompok": ref.get("label_kelompok", "")})
    return {"items": items, "total": total, "page": page,
            "page_size": page_size}


@persediaan_router.get("/persediaan/nonaktif")
async def daftar_persediaan_nonaktif(_user: dict = Depends(require_user)):
    """Daftar Persediaan USANG / RUSAK / TIDAK DIKUASAI (bahan CaLK & SK).

    DIDERIVASI dari jurnal — barang masuk daftar lewat transaksi K04 Usang /
    K05 Rusak / K09 Catat Tak Dikuasai, keluar daftar lewat penghapusan
    definitif ber-SK (H01/H02/H03) atau pembatalan M94. Tidak ada koleksi
    terpisah yang bisa melenceng dari transaksinya.
    """
    jenis_relevan = ["usang", "rusak", "catat_tak_dikuasai",
                     "hapus_usang", "hapus_rusak", "hapus_tak_dikuasai",
                     "batal_catat_tak_dikuasai"]
    rows = [t async for t in db.transaksi_persediaan.find(
        await _scope_jurnal(_user, {"jenis": {"$in": jenis_relevan}}),
        {"_id": 0}).sort("timestamp", 1)]
    rekap = rekap_nonaktif(rows)
    hasil = {k: sorted(v.values(), key=lambda e: str(e.get("kode_barang") or ""))
             for k, v in rekap.items()}
    return {**hasil,
            "ringkasan": {k: {"jumlah_barang": len(v),
                              "total_nilai": sum(e["nilai"] for e in v)}
                          for k, v in hasil.items()},
            "catatan": ("Barang usang/rusak keluar dari saldo persediaan "
                        "(neraca) saat dicatat K04/K05 dan tetap terdaftar "
                        "di sini untuk pengungkapan CaLK sampai dihapus "
                        "definitif ber-SK (H01/H02). Persediaan tidak "
                        "dikuasai (K09) menunggu pembatalan (M94) atau "
                        "penghapusan (H03).")}


class HapusDefinitifIn(BaseModel):
    jenis: str                              # hapus_usang|hapus_rusak|hapus_tak_dikuasai
    jumlah: int = Field(gt=0)
    sk_nomor: str = Field(min_length=1, max_length=200)
    sk_tanggal: str = ""                    # YYYY-MM-DD (opsional)
    keterangan: str = ""


@persediaan_router.post("/persediaan/{item_id}/hapus-definitif")
async def hapus_definitif_persediaan(item_id: str, data: HapusDefinitifIn,
                                     request: Request = None,
                                     user: dict = Depends(require_writer)):
    """Penghapusan DEFINITIF ber-SK dari daftar usang/rusak/tak dikuasai
    (H01/H02/H03) — TIDAK menggeser stok (barangnya sudah keluar saldo saat
    K04/K05/K09); hanya menutup baris daftar + jejak SK di jurnal.
    """
    await _gerbang_wajib_persetujuan(request)
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(user, item)
    kategori = {"hapus_usang": "usang", "hapus_rusak": "rusak",
                "hapus_tak_dikuasai": "tidak_dikuasai"}.get(data.jenis)
    rows = [t async for t in db.transaksi_persediaan.find(
        {"persediaan_id": item_id}, {"_id": 0}).sort("timestamp", 1)]
    sisa = rekap_nonaktif(rows).get(kategori or "", {}).get(item_id) or {
        "jumlah": 0, "nilai": 0.0}
    ok, err = validate_hapus_definitif(data.jenis, data.jumlah,
                                       sisa["jumlah"], data.sk_nomor)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    # Nilai penghapusan proporsional terhadap sisa tercatat di daftar
    nilai = (sisa["nilai"] * int(data.jumlah) / sisa["jumlah"]
             if sisa["jumlah"] else 0.0)
    from persediaan_transaksi_ref import (
        JENIS_KE_KODE, KODE_TRANSAKSI_PERSEDIAAN,
    )
    kode = JENIS_KE_KODE[data.jenis]
    now = datetime.now(timezone.utc)
    jurnal = {
        "id": str(uuid.uuid4()),
        "arah": "hapus",
        "jenis": data.jenis,
        "jenis_label": KODE_TRANSAKSI_PERSEDIAAN[kode][0],
        "kode_sakti": kode,
        "persediaan_id": item_id,
        "kode_barang": item.get("kode_barang"),
        "nup": item.get("nup"),
        "nama_barang": item.get("nama_barang"),
        "jumlah": int(data.jumlah),
        "harga_satuan": (nilai / int(data.jumlah)) if data.jumlah else 0.0,
        "total": float(nilai),
        "stok_sebelum": int(item.get("stok", 0) or 0),
        "stok_sesudah": int(item.get("stok", 0) or 0),   # stok tak berubah
        "no_bukti": data.sk_nomor.strip(),
        "jenis_dokumen": "SK Penghapusan",
        "tgl_dokumen": str(data.sk_tanggal or "").strip()[:10],
        "keterangan": data.keterangan.strip(),
        "petugas": user.get("username") or user.get("user_id") or "-",
        "timestamp": now.isoformat(),
    }
    await _insert_jurnal(jurnal)
    await log_audit("persediaan_hapus_definitif", "",
                    username=user.get("username", "system"),
                    detail=(f"{jurnal['jenis_label']} {item.get('kode_barang')} "
                            f"×{int(data.jumlah)} (Rp{int(round(nilai)):,}) — "
                            f"SK {data.sk_nomor.strip()}"))
    return {"message": f"{jurnal['jenis_label']} tercatat — SK {data.sk_nomor.strip()}",
            "transaksi": jurnal}


class KoreksiNilaiPersediaanIn(BaseModel):
    jenis: str                              # koreksi_nilai_(tambah|kurang)[_opsik]
    nilai: float = Field(gt=0)              # magnitudo selisih (Rp)
    alasan: str = Field(min_length=3, max_length=500)
    no_bukti: str = ""


@persediaan_router.post("/persediaan/{item_id}/koreksi-nilai")
async def koreksi_nilai_persediaan(item_id: str, data: KoreksiNilaiPersediaanIn,
                                   request: Request = None,
                                   user: dict = Depends(require_writer)):
    """KOREKSI NILAI persediaan (M97/M98 tambah, K97/K98 kurang) — kuantitas
    TETAP, nilai layer disebar proporsional (`koreksi_nilai_layers`). Alasan
    wajib (bahan pengungkapan). Pola OCC retry 3× seperti opname.
    """
    await _gerbang_wajib_persetujuan(request)
    from persediaan_transaksi_ref import (
        JENIS_KE_KODE, KODE_TRANSAKSI_PERSEDIAAN,
    )
    kode = JENIS_KE_KODE.get(data.jenis, "")
    info = KODE_TRANSAKSI_PERSEDIAAN.get(kode)
    if not info or info[1] != "nilai":
        raise HTTPException(status_code=400, detail=(
            "Jenis koreksi nilai tidak dikenal (pilihan: koreksi_nilai_tambah, "
            "koreksi_nilai_tambah_opsik, koreksi_nilai_kurang, "
            "koreksi_nilai_kurang_opsik)"))
    tambah = kode.startswith("M")
    now = datetime.now(timezone.utc)
    for _attempt in range(3):
        item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        from shared_utils import pastikan_akses_dok_satker
        await pastikan_akses_dok_satker(user, item)
        batches_lama = item.get("batches") or []
        selisih = float(data.nilai) if tambah else -float(data.nilai)
        try:
            batches_baru, total_lama, total_baru = koreksi_nilai_layers(
                batches_lama, selisih)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        stok = int(item.get("stok", 0) or 0)
        updated = await db.persediaan.find_one_and_update(
            {"id": item_id, "version": item.get("version")},
            {"$set": {"batches": batches_baru, "updated_at": now.isoformat()},
             "$inc": {"version": 1}},
            projection={"_id": 0}, return_document=True,
        )
        if updated is None:
            continue  # balapan — muat ulang lalu coba lagi
        jurnal = {
            "id": str(uuid.uuid4()),
            "arah": "nilai",                 # kuantitas tetap — hanya nilai
            "jenis": data.jenis,
            "jenis_label": info[0],
            "kode_sakti": kode,
            "persediaan_id": item_id,
            "kode_barang": updated.get("kode_barang"),
            "nup": updated.get("nup"),
            "nama_barang": updated.get("nama_barang"),
            "jumlah": 0,
            "harga_satuan": 0.0,
            "total": selisih,                # ber-tanda: negatif = kurang
            "stok_sebelum": stok,
            "stok_sesudah": stok,
            "no_bukti": data.no_bukti.strip(),
            "keterangan": data.alasan.strip(),
            "petugas": user.get("username") or user.get("user_id") or "-",
            "timestamp": now.isoformat(),
        }
        try:
            await _insert_jurnal(jurnal)
        except Exception:
            await db.persediaan.update_one(
                {"id": item_id},
                {"$set": {"batches": batches_lama}, "$inc": {"version": 1}})
            raise HTTPException(status_code=500,
                                detail="Gagal mencatat jurnal — koreksi dibatalkan")
        return {"message": f"{info[0]} tercatat", "nilai_lama": total_lama,
                "nilai_baru": total_baru, "transaksi": jurnal,
                "version": updated.get("version")}
    raise HTTPException(status_code=409,
                        detail="Barang sedang diubah pengguna lain — coba lagi")


@persediaan_router.post("/persediaan/import")
@limiter.limit("6/minute")
async def import_persediaan(request: Request, file: UploadFile = File(...),
                            _user: dict = Depends(require_writer)):
    """Impor massal master (CSV/XLSX): kode 16+NUP sudah ada → perbarui field
    non-identitas; selain itu buat baru (kode 10 digit → nomor urut otomatis,
    NUP kosong → otomatis). Stok/layer TIDAK tersentuh impor."""
    from routes.kodefikasi import _rows_from_upload

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File maksimal 10MB")
    # Titik panggil KEDUA parser yang sama (temuan C28). Membungkusnya di
    # kodefikasi.py TIDAK menutup yang ini: `_rows_from_upload` tetap fungsi
    # sinkron, jadi setiap pemanggil harus memasang thread-nya sendiri.
    # Inilah pemanggil "pintu belakang" yang tak terlihat oleh pencarian
    # string "openpyxl" — berkas ini tak pernah menyebutnya.
    rows = await asyncio.to_thread(_rows_from_upload, file.filename, content)
    entries, errors, dupes = parse_import_persediaan_rows(rows)

    inserted = updated = 0
    now = datetime.now(timezone.utc).isoformat()
    for e in entries:
        kode, nup = e["kode_barang"], e["nup"]
        scalar = {k: v for k, v in e.items() if k not in ("kode_barang", "nup")}
        if len(kode) == KODE_PENUH_LEN and nup:
            # Scope satker (REVIEW-9 R3): impor satker B tidak boleh menimpa
            # master milik satker A yang kebetulan ber-kode+NUP sama.
            from shared_utils import scope_query_field_satker
            res = await db.persediaan.update_one(
                scope_query_field_satker(_user, {"kode_barang": kode, "nup": nup}),
                {"$set": {**scalar, "updated_at": now}, "$inc": {"version": 1}},
            )
            if res.matched_count:
                updated += 1
                continue
        # buat baru — pakai jalur create agar aturan kode/NUP otomatis sama
        try:
            payload = PersediaanCreate(kode_barang=kode, nup=nup, **scalar)
            await create_persediaan(payload, _user=_user)
            inserted += 1
        except HTTPException as exc:
            errors.append(f"{kode}/{nup or 'auto'}: {exc.detail}")

    return {
        "message": f"Impor selesai: {inserted} baru, {updated} diperbarui",
        "inserted": inserted, "updated": updated,
        "duplikat_dalam_file": dupes,
        "errors": errors[:50], "error_count": len(errors),
    }


@persediaan_router.get("/persediaan/opname/kertas-kerja-pdf")
async def opname_kertas_kerja_pdf(gudang: str = "",
                                  _user: dict = Depends(require_user)):
    """Kertas kerja opname (pustaka §3.3): saldo buku + kolom fisik KOSONG
    untuk diisi saat penghitungan — pola "Cetak Bahan Opname Fisik" SAKTI.
    Dapat difilter satu Lokasi/Gudang (temuan #22 — opname per gudang)."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    filter_gudang = str(gudang or "").strip()
    query = ({"lokasi": {"$regex": f"^{re.escape(filter_gudang)}$", "$options": "i"}}
             if filter_gudang else {})
    from shared_utils import scope_query_field_satker
    items = [x async for x in db.persediaan.find(
        scope_query_field_satker(_user, query), {"_id": 0, "batches": 0})]
    items.sort(key=lambda x: (x.get("nama_barang") or "", x.get("kode_barang") or ""))

    today_iso = today_wib()   # tanggal lokal WIB (#25/#44)
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        "KERTAS KERJA OPNAME FISIK PERSEDIAAN",
        subjudul=f"Lokasi/Gudang: {filter_gudang}" if filter_gudang else None))
    elements.append(Paragraph(
        f"Saldo buku per {_fmt_tanggal_id(today_iso)} — kolom Stok Fisik & Keterangan diisi saat penghitungan.",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Kode Barang", "Nama Barang", "Satuan", "Stok Buku", "Stok Fisik", "Keterangan"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, it in enumerate(items, start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(it.get("kode_barang") or "-", st['Cell']),
            Paragraph(it.get("nama_barang") or "-", st['Cell']),
            Paragraph(it.get("satuan") or "-", st['CellCenter']),
            Paragraph(str(int(it.get("stok", 0) or 0)), st['CellCenter']),
            Paragraph("", st['Cell']),
            Paragraph("", st['Cell']),
        ])
    if not items:
        elements.append(Paragraph("Belum ada barang persediaan terdaftar.", st['Cell']))
    else:
        table = Table(table_data, colWidths=_fit_col_widths([28, 110, 150, 50, 55, 60, 80], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Penghitung,', 'nama': '...........................',
         'after': baris_identitas_isian(None)},
        {'pre': [''], 'header': 'Saksi,', 'nama': '...........................',
         'after': baris_identitas_isian(None)},
        {'pre': [''], 'header': 'Mengetahui,', 'nama': '...........................',
         'after': baris_identitas_isian(None)},
    ], doc.width))
    footer = _page_footer_factory("Kertas Kerja Opname Fisik Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="Kertas_Kerja_Opname.pdf"'})


@persediaan_router.get("/persediaan/opname/baof-pdf")
async def opname_baof_pdf(
    tanggal: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """BAOF — Berita Acara Opname Fisik (pustaka §3.3): penyesuaian opname
    pada tanggal tsb + 3 penandatangan (penghitung, saksi, mengetahui)."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    rows = [r async for r in db.transaksi_persediaan.find(
        await _scope_jurnal(_user, {"jenis": "opname"}), {"_id": 0})]
    rows = [r for r in rows if tanggal_wib(r.get("timestamp")) == tanggal]
    rows.sort(key=lambda r: (r.get("nama_barang") or "", r.get("timestamp") or ""))

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("BERITA ACARA OPNAME FISIK PERSEDIAAN (BAOF)"))
    elements.append(Paragraph(
        f"Pada tanggal {_fmt_tanggal_id(tanggal)} telah dilakukan opname fisik persediaan "
        f"dengan hasil penyesuaian sebagai berikut. Selisih telah dibukukan pada jurnal "
        f"transaksi; penjelasan selisih diungkapkan pada kolom alasan (bahan CaLK).",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    if not rows:
        elements.append(Paragraph(
            "Tidak ada penyesuaian opname pada tanggal tersebut (fisik = buku untuk seluruh barang yang diopname).",
            st['Cell']))
    else:
        headers = ["No", "Kode Barang", "Nama Barang", "Buku", "Fisik", "Selisih", "Alasan"]
        table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for i, r in enumerate(rows, start=1):
            selisih = int(r.get("stok_sesudah", 0)) - int(r.get("stok_sebelum", 0))
            table_data.append([
                Paragraph(str(i), st['CellCenter']),
                Paragraph(r.get("kode_barang") or "-", st['Cell']),
                Paragraph(r.get("nama_barang") or "-", st['Cell']),
                Paragraph(str(r.get("stok_sebelum", 0)), st['CellCenter']),
                Paragraph(str(r.get("stok_sesudah", 0)), st['CellCenter']),
                Paragraph(f"{'+' if selisih > 0 else ''}{selisih}", st['CellCenter']),
                Paragraph(r.get("keterangan") or "-", st['Cell']),
            ])
        table = Table(table_data, colWidths=_fit_col_widths([28, 105, 140, 42, 42, 48, 110], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    _kpb = await _kpb_signer(settings, user=_user)
    _kpb_nama = _kpb["nama"] if _kpb["nama"] != "-" else '...........................'
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Penghitung,', 'nama': '...........................',
         'after': baris_identitas_isian(None)},
        {'pre': [''], 'header': 'Saksi,', 'nama': '...........................',
         'after': baris_identitas_isian(None)},
        {'pre': [''], 'header': 'Mengetahui,', 'role': _hdr_kpb(_kpb), 'nama': _kpb_nama,
         'after': baris_identitas_ttd(_kpb["nip"], _kpb.get("status_kepegawaian"))},
    ], doc.width))
    footer = _page_footer_factory("Berita Acara Opname Fisik Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BAOF_{tanggal}.pdf"'})


@persediaan_router.get("/persediaan/opname/status")
async def opname_status(_user: dict = Depends(require_user)):
    """Status opname semester berjalan — pengingat opname semesteran."""
    from datetime import datetime, timezone

    from persediaan_utils import status_opname_semester

    today_iso = today_wib()   # tanggal lokal WIB (#25/#44)
    # Isolasi satker (REVIEW-9 R10): tanpa scope, pengingat opname semesteran
    # satker ini "padam" hanya karena satker LAIN sudah opname (kepatuhan palsu).
    terakhir = await db.transaksi_persediaan.find_one(
        await _scope_jurnal(_user, {"jenis": "opname"}),
        {"_id": 0, "timestamp": 1}, sort=[("timestamp", -1)])
    tanggal = tanggal_wib((terakhir or {}).get("timestamp"))
    return status_opname_semester(tanggal, today_iso)


@persediaan_router.get("/persediaan/laporan/posisi-pdf")
async def laporan_posisi_pdf(gudang: str = "",
                             _user: dict = Depends(require_user)):
    """Laporan Posisi Persediaan (hari ini) — per KELOMPOK kodefikasi.

    Grup per prefix 5 digit (uraian dari referensi kodefikasi); nilai per
    barang dihitung dari layer FIFO (pustaka §3.4). Dapat difilter satu
    Lokasi/Gudang. Semua data nyata.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    uraian_kelompok = {}
    async for k in db.kodefikasi.find({"level": 3}, {"_id": 0, "kode": 1, "uraian": 1}):
        uraian_kelompok[k["kode"]] = k.get("uraian") or ""

    # Peta akun neraca persediaan (sub-kelompok → 1171xx): entri satker menimpa default.
    peta_akun = {}
    async for m in db.persediaan_akun.find({}, {"_id": 0}):
        peta_akun[str(m.get("sub_kelompok") or "").strip()] = {
            "akun": m.get("akun", ""), "uraian": m.get("uraian", "")}

    filter_gudang = str(gudang or "").strip()
    query = ({"lokasi": {"$regex": f"^{re.escape(filter_gudang)}$", "$options": "i"}}
             if filter_gudang else {})
    grup = {}
    akun_total = {}
    from shared_utils import scope_query_field_satker
    async for it in db.persediaan.find(
            scope_query_field_satker(_user, query), {"_id": 0}):
        stok = int(it.get("stok", 0) or 0)
        nilai = nilai_persediaan_dari_batches(it.get("batches"))
        kel = str(it.get("kode_barang") or "")[:5]
        ak = akun_persediaan(it.get("kode_barang"), peta_akun)
        g = grup.setdefault(kel, {"kelompok": kel,
                                  "uraian": uraian_kelompok.get(kel, ""),
                                  "items": [], "stok": 0, "nilai": 0.0})
        g["items"].append({"kode": it.get("kode_barang"), "nup": it.get("nup"),
                           "nama": it.get("nama_barang"), "satuan": it.get("satuan") or "-",
                           "stok": stok, "nilai": nilai, "akun": ak["akun"]})
        g["stok"] += stok
        g["nilai"] += nilai
        at = akun_total.setdefault(ak["akun"], {"uraian": ak["uraian"], "nilai": 0.0})
        at["nilai"] += nilai

    today_iso = today_wib()   # tanggal lokal WIB (#25/#44)
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        "LAPORAN POSISI PERSEDIAAN",
        subjudul=f"Lokasi/Gudang: {filter_gudang}" if filter_gudang else None))
    elements.append(Paragraph(f"Per tanggal: {_fmt_tanggal_id(today_iso)} · nilai dihitung FIFO per layer", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Kode Barang", "NUP", "Nama Barang", "Satuan", "Akun", "Stok", "Nilai (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    grand_stok, grand_nilai = 0, 0.0
    for kel in sorted(grup):
        g = grup[kel]
        label = f"Kelompok {kel}" + (f" — {g['uraian']}" if g["uraian"] else "")
        table_data.append([Paragraph(f"<b>{label}</b>", st['Cell']), "", "", "", "", "", ""])
        for it in sorted(g["items"], key=lambda x: (x["nama"] or "", x["kode"] or "")):
            table_data.append([
                Paragraph(it["kode"] or "-", st['Cell']),
                Paragraph(it["nup"] or "-", st['CellCenter']),
                Paragraph(it["nama"] or "-", st['Cell']),
                Paragraph(it["satuan"], st['CellCenter']),
                Paragraph(it["akun"], st['CellCenter']),
                Paragraph(str(it["stok"]), st['CellCenter']),
                Paragraph(_fmt_rp(it["nilai"]), st['CellRight']),
            ])
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("", st['Cell']),
            Paragraph(f"<b>Subtotal {kel}</b>", st['Cell']), Paragraph("", st['Cell']),
            Paragraph("", st['Cell']),
            Paragraph(f"<b>{g['stok']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(g['nilai'])}</b>", st['CellRight']),
        ])
        grand_stok += g["stok"]
        grand_nilai += g["nilai"]
    table_data.append([
        Paragraph("", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("<b>TOTAL</b>", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph(f"<b>{grand_stok}</b>", st['CellCenter']),
        Paragraph(f"<b>{_fmt_rp(grand_nilai)}</b>", st['CellRight']),
    ])
    table = Table(table_data, colWidths=_fit_col_widths([104, 34, 150, 48, 54, 40, 84], doc.width), repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    # Rekap nilai persediaan per akun neraca (dasar penyajian di Neraca).
    if akun_total:
        elements.append(Spacer(1, 5 * rl_mm))
        elements.append(Paragraph("<b>Rekapitulasi per Akun Neraca</b>", st['Cell']))
        rekap_data = [[Paragraph(h, st['TableHeader']) for h in ["Akun", "Uraian", "Nilai (Rp)"]]]
        for akun in sorted(akun_total):
            a = akun_total[akun]
            rekap_data.append([
                Paragraph(akun, st['CellCenter']),
                Paragraph(a["uraian"] or "-", st['Cell']),
                Paragraph(_fmt_rp(a["nilai"]), st['CellRight']),
            ])
        rekap_data.append([
            Paragraph("", st['Cell']), Paragraph("<b>TOTAL</b>", st['Cell']),
            Paragraph(f"<b>{_fmt_rp(grand_nilai)}</b>", st['CellRight']),
        ])
        rekap = Table(rekap_data, colWidths=_fit_col_widths([60, 300, 100], doc.width), repeatRows=1)
        rekap.setStyle(_std_table_style(zebra=True, total_row=True))
        elements.append(rekap)
        elements.append(Paragraph(
            "Akun neraca 1171xx = rujukan (default 117111 Barang Konsumsi); "
            "sub-akun per jenis perlu verifikasi Lampiran BAS.", st['Meta']))

    elements.append(Spacer(1, 12 * rl_mm))
    kpb = await _kpb_signer(settings, user=_user)
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': _hdr_kpb(kpb),
         'nama': kpb["nama"],
         # Non-ASN: baris NIP/NIK tidak dicetak (privasi)
         'after': baris_identitas_ttd(kpb['nip'], kpb.get("status_kepegawaian"))},
    ], doc.width))
    footer = _page_footer_factory("Laporan Posisi Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="Laporan_Posisi_Persediaan.pdf"'})


@persediaan_router.get("/persediaan/laporan/mutasi-pdf")
async def laporan_mutasi_pdf(
    dari: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sampai: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Laporan Mutasi Persediaan per periode — dari JURNAL (pustaka §3.4).

    Kolom: saldo awal → masuk (qty & nilai) → keluar (qty & nilai) →
    saldo akhir per barang. Saldo dihitung murni dari jurnal transaksi.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    if sampai < dari:
        raise HTTPException(status_code=400, detail="Tanggal akhir sebelum tanggal awal")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    rows = [r async for r in db.transaksi_persediaan.find(
        await _scope_jurnal(_user), {"_id": 0})]
    rekap = mutasi_periode(rows, dari, sampai)

    buffer = BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN MUTASI PERSEDIAAN"))
    elements.append(Paragraph(
        f"Periode: {_fmt_tanggal_id(dari)} s.d. {_fmt_tanggal_id(sampai)} · dihitung dari jurnal transaksi",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Kode Barang", "Nama Barang", "Saldo\nAwal", "Masuk\nQty", "Masuk\nNilai (Rp)",
               "Keluar\nQty", "Keluar\nNilai (Rp)", "Saldo\nAkhir"]
    table_data = [[Paragraph(h.replace("\n", "<br/>"), st['TableHeader']) for h in headers]]
    urut = sorted(rekap.values(), key=lambda e: (e["nama_barang"] or "", e["kode_barang"] or ""))
    tot = {"masuk_qty": 0, "masuk_nilai": 0.0, "keluar_qty": 0, "keluar_nilai": 0.0}
    for e in urut:
        table_data.append([
            Paragraph(e["kode_barang"] or "-", st['Cell']),
            Paragraph(e["nama_barang"] or "-", st['Cell']),
            Paragraph(str(e["saldo_awal"]), st['CellCenter']),
            Paragraph(str(e["masuk_qty"]), st['CellCenter']),
            Paragraph(_fmt_rp(e["masuk_nilai"]), st['CellRight']),
            Paragraph(str(e["keluar_qty"]), st['CellCenter']),
            Paragraph(_fmt_rp(e["keluar_nilai"]), st['CellRight']),
            Paragraph(str(e["saldo_akhir"]), st['CellCenter']),
        ])
        for k in tot:
            tot[k] += e[k]
    if not urut:
        elements.append(Paragraph("Tidak ada transaksi pada periode ini.", st['Cell']))
    else:
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("<b>TOTAL</b>", st['Cell']),
            Paragraph("", st['CellCenter']),
            Paragraph(f"<b>{tot['masuk_qty']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(tot['masuk_nilai'])}</b>", st['CellRight']),
            Paragraph(f"<b>{tot['keluar_qty']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(tot['keluar_nilai'])}</b>", st['CellRight']),
            Paragraph("", st['CellCenter']),
        ])
        table = Table(table_data, colWidths=_fit_col_widths([115, 190, 50, 50, 90, 50, 90, 50], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True, total_row=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    kpb = await _kpb_signer(settings, user=_user)
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': _hdr_kpb(kpb),
         'nama': kpb["nama"],
         # Non-ASN: baris NIP/NIK tidak dicetak (privasi)
         'after': baris_identitas_ttd(kpb['nip'], kpb.get("status_kepegawaian"))},
    ], doc.width))
    footer = _page_footer_factory("Laporan Mutasi Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="Laporan_Mutasi_Persediaan_{dari}_{sampai}.pdf"'})


@persediaan_router.get("/persediaan/jenis-transaksi")
async def list_jenis_transaksi(_user: dict = Depends(require_user)):
    """Jenis transaksi masuk & keluar (peta 1:1 ke SAKTI) untuk dropdown.

    M11/K11 (reklasifikasi dari/ke aset) hanya mencatat SISI PERSEDIAAN —
    register aset tidak disentuh otomatis; `info` mengingatkan operator agar
    menyesuaikan sisi aset via Pembukuan → Reklasifikasi (kejujuran klaim,
    hindari dobel catat di Neraca).
    """
    from persediaan_transaksi_ref import (
        LABEL_KELOMPOK, daftar_kode_transaksi, info_kode,
    )
    info_reklas = ("Hanya mencatat sisi persediaan — sesuaikan register aset "
                   "secara terpisah (Pembukuan → Reklasifikasi, jurnal 304/107) "
                   "agar barang tidak tercatat ganda di Neraca.")
    info_per_key = {
        "reklasifikasi_dari_aset": info_reklas,
        "reklasifikasi_ke_aset": info_reklas,
        "usang": ("Barang keluar dari saldo dan masuk Daftar Persediaan "
                  "Usang (bahan CaLK) sampai dihapus definitif ber-SK (H01)."),
        "rusak": ("Barang keluar dari saldo dan masuk Daftar Persediaan "
                  "Rusak (bahan CaLK) sampai dihapus definitif ber-SK (H02)."),
        "catat_tak_dikuasai": ("Barang keluar dari saldo dan masuk Daftar "
                               "Persediaan Tidak Dikuasai sampai dibatalkan "
                               "(M94) atau dihapus ber-SK (H03)."),
        "batal_catat_tak_dikuasai": ("Hanya untuk membatalkan pencatatan "
                                     "K09 — barang kembali ke saldo dengan "
                                     "harga satuan yang diisikan."),
    }

    def _baris(peta):
        out = []
        for k, v in peta.items():
            ref = info_kode(v[1])
            out.append({"key": k, "label": v[0], "kode": v[1],
                        "kelompok": ref.get("kelompok", ""),
                        "label_kelompok": ref.get("label_kelompok", ""),
                        **({"info": info_per_key[k]} if k in info_per_key else {})})
        return out

    # Mode SEDIA-KPB ikut di sini (bukan fetch terpisah): dialog transaksi
    # perlu tahu apakah submit-nya menulis langsung atau mengajukan
    # permohonan, dan halaman sudah memuat referensi ini saat dibuka.
    s = await db.report_settings.find_one(
        {"type": "global"}, {"persediaan_wajib_persetujuan": 1}) or {}
    return {
        "masuk": _baris(JENIS_MASUK),
        "keluar": _baris(JENIS_KELUAR),
        # Registry LENGKAP 45 kode (termasuk P01/H01-H03/K09/M94 dan koreksi
        # nilai M97/M98/K97/K98 yang alur pencatatannya menyusul) — layar
        # "Referensi Kode Transaksi" membacanya dari sini.
        "referensi": daftar_kode_transaksi(),
        "label_kelompok": LABEL_KELOMPOK,
        "wajib_persetujuan": bool(s.get("persediaan_wajib_persetujuan")),
    }


class ItemMassalIn(BaseModel):
    persediaan_id: str = Field(min_length=1)
    jumlah: int = Field(gt=0)
    harga_satuan: float = Field(0, ge=0)   # dipakai arah masuk
    expired: str = ""                       # dipakai arah masuk (opsional)


class TransaksiMassalIn(BaseModel):
    arah: str                               # "masuk" | "keluar"
    jenis: str
    no_bukti: str = ""
    jenis_dokumen: str = ""                 # masuk
    tgl_dokumen: str = ""                   # masuk
    penyedia: str = ""                      # masuk
    perolehan_id: str = ""                  # masuk — tautan BAST Pengadaan (#17)
    unit_penerima: str = ""                 # keluar
    keterangan: str = ""
    # Nomor LPB otomatis dari Registrasi Persuratan bila no_bukti kosong
    # (arah masuk; tercatat di buku agenda berstatus dibooking).
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
    booking_otomatis: bool = False
    items: list[ItemMassalIn] = Field(min_length=1, max_length=100)


@persediaan_router.post("/persediaan/transaksi-massal")
async def transaksi_massal(payload: TransaksiMassalIn,
                           request: Request = None,
                           user: dict = Depends(require_writer_satker)):
    """Satu dokumen (BAST/kuitansi/nota) untuk BANYAK barang sekaligus.

    Tiap barang diproses lewat jalur transaksi tunggal yang sudah atomik +
    berjurnal + berkompensasi — massal hanyalah pengulang dengan field
    dokumen yang sama. Kegagalan per barang TIDAK membatalkan barang lain
    (Mongo standalone tanpa transaksi multi-dokumen); hasil per barang
    dilaporkan apa adanya agar operator tahu persis mana yang gagal.
    """
    await _gerbang_wajib_persetujuan(request)
    if payload.arah not in ("masuk", "keluar"):
        raise HTTPException(status_code=400, detail="Arah harus 'masuk' atau 'keluar'")
    peta_jenis = JENIS_MASUK if payload.arah == "masuk" else JENIS_KELUAR
    if payload.jenis not in peta_jenis:
        valid = ", ".join(peta_jenis)
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal (pilihan: {valid})")
    # Tautan BAST Pengadaan (#17): validasi SEKALI di muka (404 sebelum ada
    # mutasi stok barang mana pun); snapshot per baris diambil transaksi_masuk.
    snap_asal = {}
    if payload.arah == "masuk" and str(payload.perolehan_id or "").strip():
        snap_asal = await _ambil_snapshot_perolehan(payload.perolehan_id, user)

    # Nomor LPB: pakai no_bukti; atau pesan otomatis dari Persuratan.
    import uuid as _uuid
    nomor_lpb = str(payload.no_bukti or "").strip()
    surat_id = ""
    if payload.arah == "masuk" and payload.booking_otomatis and not nomor_lpb:
        # Satu-satunya tempat nomor LPB dilahirkan (lihat routes/persuratan.py):
        # jalur aset memanggil helper yang sama supaya deret nomornya tunggal.
        from routes.persuratan import booking_nomor_lpb
        nomor_lpb, surat_id = await booking_nomor_lpb(
            user, payload.tgl_dokumen,
            perihal=f"Laporan Penerimaan Barang (LPB) — {payload.jenis}",
            tujuan=str(payload.penyedia or "").strip(),
            keterangan="booking otomatis dari transaksi massal",
            kode_klasifikasi=payload.kode_klasifikasi)

    hasil = []
    for it in payload.items:
        try:
            if payload.arah == "masuk":
                r = await transaksi_masuk(it.persediaan_id, TransaksiMasukIn(
                    jenis=payload.jenis, jumlah=it.jumlah,
                    harga_satuan=it.harga_satuan, expired=it.expired,
                    no_bukti=(nomor_lpb or payload.no_bukti),
                    jenis_dokumen=payload.jenis_dokumen,
                    tgl_dokumen=payload.tgl_dokumen, penyedia=payload.penyedia,
                    perolehan_id=payload.perolehan_id,
                    keterangan=payload.keterangan,
                ), user=user)
            else:
                r = await transaksi_keluar(it.persediaan_id, TransaksiKeluarIn(
                    jenis=payload.jenis, jumlah=it.jumlah,
                    unit_penerima=payload.unit_penerima,
                    no_bukti=payload.no_bukti, keterangan=payload.keterangan,
                ), user=user)
            hasil.append({"persediaan_id": it.persediaan_id, "ok": True,
                          "stok": r.get("stok"), "message": r.get("message")})
        except HTTPException as e:
            hasil.append({"persediaan_id": it.persediaan_id, "ok": False,
                          "error": str(e.detail)})
    sukses = sum(1 for h in hasil if h["ok"])

    # Booking nomor terjadi SEBELUM loop (nomornya distempel ke tiap jurnal),
    # jadi saat SEMUA baris gagal surat 'dibooking' menggantung tanpa LPB
    # selamanya. Nomornya tetap hangus (by design — nomor terpakai tak pernah
    # dipakai ulang), tapi buku agenda harus jujur menyebutnya dibatalkan.
    if surat_id and sukses == 0:
        _now_batal = datetime.now(timezone.utc).isoformat()
        _alasan = "Semua baris transaksi massal gagal — LPB tidak terbit"
        await db.surat.update_one(
            {"id": surat_id, "status": "dibooking"},
            {"$set": {"status": "dibatalkan", "updated_at": _now_batal,
                      "alasan_batal": _alasan},
             "$push": {"riwayat": {"status": "dibatalkan",
                                   "tanggal": _now_batal,
                                   "oleh": user.get("username", "system"),
                                   "catatan": _alasan}}})

    # Register LPB (Laporan Penerimaan Barang) — hanya arah MASUK dengan
    # minimal satu barang sukses; snapshot barang dibekukan utk dokumen.
    lpb_id = ""
    if payload.arah == "masuk" and sukses:
        ok_ids = [h["persediaan_id"] for h in hasil if h["ok"]]
        master = {m["id"]: m async for m in db.persediaan.find(
            {"id": {"$in": ok_ids}},
            {"_id": 0, "id": 1, "kode_barang": 1, "nup": 1,
             "nama_barang": 1, "satuan": 1})}
        baris, total_nilai = [], 0.0
        for it in payload.items:
            if it.persediaan_id not in ok_ids:
                continue
            m = master.get(it.persediaan_id) or {}
            total = float(it.jumlah) * float(it.harga_satuan or 0)
            total_nilai += total
            baris.append({
                "persediaan_id": it.persediaan_id,
                "kode_barang": m.get("kode_barang", ""),
                "nup": m.get("nup", ""),
                "nama_barang": m.get("nama_barang", ""),
                "jumlah": it.jumlah, "satuan": m.get("satuan", ""),
                "harga_satuan": it.harga_satuan, "total": total,
                "keterangan": "Kondisi Baik & Lengkap",
            })
        lpb_id = str(_uuid.uuid4())
        from shared_utils import kode_satker_user as _ksu
        _ks_lpb = _ksu(user)
        tgl_lpb = (str(payload.tgl_dokumen or "").strip()[:10]
                   or datetime.now(timezone.utc).date().isoformat())
        # PPK pada LPB — DIBEKUKAN, dengan dua sumber berurut:
        #   1. dari BAST Pengadaan yang ditautkan (paling tepat: itulah PPK
        #      yang benar-benar menandatangani komitmen atas barang ini);
        #   2. bila tak ada tautan (penerimaan manual: hibah kecil, sisa
        #      kegiatan), resolusi peran `ppk` yang berlaku pada tanggal LPB.
        # Membekukan, bukan join saat cetak: PPK berganti, LPB tahun lalu
        # harus tetap menyebut PPK-nya sendiri.
        ppk_nama = str(snap_asal.get("perolehan_ppk_nama") or "").strip()
        ppk_nip = str(snap_asal.get("perolehan_ppk_nip") or "").strip()
        ppk_status = ""
        if not ppk_nama:
            from shared_utils import resolve_pejabat_peran as _rpp
            _pj = await _rpp("ppk", per_iso=tgl_lpb, kode_satker=_ks_lpb)
            ppk_nama = str((_pj or {}).get("nama") or "").strip()
            ppk_nip = str((_pj or {}).get("nip") or "").strip()
            ppk_status = str((_pj or {}).get("status_kepegawaian") or "").strip()
        elif ppk_nip:
            # PPK dari BAST: statusnya tak ikut di snapshot jurnal, jadi
            # dilengkapi lewat master pegawai — aturan Non-ASN tetap berlaku.
            from shared_utils import status_kepegawaian_by_nip as _skn
            ppk_status = await _skn(ppk_nip)
        await db.lpb.insert_one({
            "id": lpb_id, "nomor": nomor_lpb, "surat_id": surat_id,
            "tanggal": tgl_lpb,
            "ppk_nama": ppk_nama, "ppk_nip": ppk_nip,
            "ppk_status_kepegawaian": ppk_status,
            "jenis": payload.jenis, "jenis_dokumen": payload.jenis_dokumen,
            "penyedia": str(payload.penyedia or "").strip(),
            "perolehan_id": str(payload.perolehan_id or "").strip(),
            "keterangan": str(payload.keterangan or "").strip(),
            "items": baris, "total_nilai": total_nilai,
            "jumlah_barang": len(baris),
            # Stempel satker (REVIEW-9 R9) — tanpa ini daftar & PDF LPB tak
            # dapat diisolasi sama sekali (dokumen penerimaan barang memuat
            # penyedia, harga satuan, dan total nilai).
            "kode_satker": _ks_lpb,
            "created_by": user.get("username", "system"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"total": len(hasil), "sukses": sukses, "gagal": len(hasil) - sukses,
            "hasil": hasil, "lpb_id": lpb_id, "nomor_lpb": nomor_lpb}


@persediaan_router.get("/persediaan/lpb")
async def daftar_lpb(page: int = 1, page_size: int = 30, kategori: str = "",
                     _user: dict = Depends(require_user)):
    """Riwayat Laporan Penerimaan Barang — persediaan DAN aset.

    `kategori` kosong = keduanya. Dokumen era-lama tak punya field `kategori`
    sama sekali; ia diperlakukan sebagai "persediaan" karena memang hanya
    jalur itu yang dulu menerbitkan LPB — tanpa penyetaraan ini, memfilter
    "persediaan" akan MENYEMBUNYIKAN seluruh riwayat lama.
    """
    page, page_size = max(1, page), min(max(1, page_size), 100)
    from shared_utils import scope_query_field_satker
    q_lpb = scope_query_field_satker(_user)   # isolasi satker (REVIEW-9 R9)
    kat = str(kategori or "").strip().lower()
    if kat == "persediaan":
        q_lpb = {**q_lpb, "kategori": {"$in": ["persediaan", "", None]}}
    elif kat in ("aset", "gabungan"):
        q_lpb = {**q_lpb, "kategori": kat}
    total = await db.lpb.count_documents(q_lpb)
    items = await (db.lpb.find(q_lpb, {"_id": 0, "items": 0})
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    # Status TTD elektronik ikut — layar Riwayat LPB memakai potongan yang
    # SAMA dengan Riwayat BAST (lihat `ttd_penautan`).
    from ttd_penautan import lampirkan_status_ttd
    await lampirkan_status_ttd(db, "lpb", items)
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size))}


def _baris_nip_ppk(lpb: dict) -> str:
    """Baris "NIP PPK" untuk info LPB — TUNDUK pada aturan privasi Non-ASN.

    `baris_identitas_ttd` mengembalikan list KOSONG untuk penanda tangan
    Non-ASN atau nomor berformat NIK; itulah aturan yang berlaku di seluruh
    blok tanda tangan aplikasi ini. Mencetak `ppk_nip` mentah di info LPB
    membatalkan aturan tersebut lewat pintu belakang — dan `snapshot_ppk`
    sengaja membekukan `ppk_status_kepegawaian` justru supaya keputusan itu
    bisa diambil di sini, dari keadaan SAAT dokumen terbit.
    """
    d = lpb or {}
    if not str(d.get("ppk_nama") or "").strip():
        return "NIP PPK: <b>-</b>"
    baris = baris_identitas_ttd(d.get("ppk_nip"),
                                d.get("ppk_status_kepegawaian"))
    if not baris:
        return ""          # Non-ASN / NIK: cukup namanya saja
    return f"<b>{baris[0]}</b>"


async def bangun_lpb_pdf(lpb_id: str, _user: dict,
                         sertakan_kelengkapan: bool = False) -> bytes:
    """Susun PDF LPB → bytes. Dipisah dari route-nya karena jalur TTD
    elektronik butuh berkasnya sebagai BYTE untuk disimpan ke GridFS, bukan
    sebagai respons HTTP. Satu penyusun, dua pemakai: dokumen yang diunduh
    dan dokumen yang ditandatangani DIJAMIN identik."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import (
        KeepTogether, Paragraph, Spacer, Table, TableStyle,
    )

    from shared_utils import resolve_pejabat_peran, resolve_penandatangan_kpb
    from reportlab.lib.styles import ParagraphStyle
    from kodefikasi_utils import (
        kelompokkan_per_golongan_bidang as _kelompokkan_per_golongan_bidang,
    )
    from kodefikasi_utils import normalize_kode as _norm_kode
    from lpb_utils import bundel_sumber, label_golongan
    from routes.reports import (
        _baris_sekat_bidang, _baris_sekat_golongan, _fit_col_widths, _fmt_tanggal_id,
        _tabel_kelengkapan,
        _gaya_sekat_bidang, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _peta_subsub_kelompok, _peta_uraian_bidang,
        _std_doc, _std_table_style, _title_block,
    )

    lpb = await db.lpb.find_one({"id": lpb_id}, {"_id": 0})
    if not lpb:
        raise HTTPException(status_code=404, detail="LPB tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(_user, lpb)  # isolasi satker (REVIEW-9 R9)
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    meta, cell, cellc, cellr = st['Meta'], st['Cell'], st['CellCenter'], st['CellRight']

    # Escape teks bebas sebelum diinterpolasi ke Paragraph. Nama penyedia,
    # keterangan, dan nama barang berasal dari input pengguna; satu karakter
    # '&' atau '<' merusak parser XML ReportLab dan menggagalkan SELURUH PDF
    # (500 permanen tiap kali dokumen dibuka). `escape` menangani &, <, > —
    # markup tebal yang memang disengaja tetap ditulis di luar nilai ini.
    from xml.sax.saxutils import escape as _esc

    def fmt_rp(v):
        try:
            return f"{int(v):,}".replace(",", ".")
        except (ValueError, TypeError):
            return "0"

    # Kategori menentukan judul, label jenis, dan ADA-TIDAKNYA kolom NUP.
    # Dokumen era-lama tanpa field ini seluruhnya persediaan (hanya jalur itu
    # yang dulu menerbitkan LPB), jadi default-nya aman-mundur.
    #
    # Kolom NUP tersendiri sudah TIDAK ADA: NUP kini melebur ke kolom identitas
    # sebagai rentang, dan baris persediaan yang memang tak ber-NUP cukup tak
    # menampilkannya — lebih bersih daripada satu kolom penuh tanda hubung.
    from lpb_utils import KATEGORI_LPB
    kategori = str(lpb.get("kategori") or "persediaan").strip().lower()
    is_aset = kategori == "aset"
    is_gabungan = kategori == "gabungan"

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block(
        "LAPORAN PENERIMAAN BARANG (LPB)"
        + (" — BARANG MILIK NEGARA" if is_aset
           else " — GABUNGAN ASET & PERSEDIAAN" if is_gabungan else ""),
        nomor=lpb.get("nomor") or "......./......./........"))

    if is_gabungan:
        _n_bast = int(lpb.get("jumlah_bast") or 0)
        label_jenis = (f"Rekap {_n_bast} BAST PPK-KPB" if _n_bast
                       else "Rekap BAST PPK-KPB")
    elif is_aset:
        label_jenis = JENIS_PEROLEHAN.get(
            lpb.get("jenis"), (lpb.get("jenis") or "-",))[0]
    else:
        label_jenis = JENIS_MASUK.get(lpb.get("jenis"), lpb.get("jenis") or "-")
    label_kat = KATEGORI_LPB.get(kategori, "Persediaan")

    _items = list(lpb.get("items") or [])

    # INFORMASI BERULANG DIPANGKAS (permintaan pemilik). Bundel sumber
    # (penyedia · PPK · dokumen · BAST asal) dulu dicetak di BAWAH SETIAP
    # barang. Pada LPB yang seluruh barangnya berasal dari satu register —
    # bentuk yang paling sering — kalimat yang sama persis terulang sebanyak
    # jumlah barangnya, padahal kepala surat sudah menyebut penyedia & PPK-nya.
    # Yang terulang berhenti dibaca, dan yang berbeda jadi ikut terlewat.
    def _bundel_baris(b):
        return bundel_sumber(b.get("sumber")) or str(b.get("keterangan") or "")

    _bundel_unik = {x for x in (_bundel_baris(b) for b in _items) if x}
    # `next(iter(...))`, BUKAN `.pop()`: pop MENGOSONGKAN himpunannya, dan
    # kepala surat yang membacanya sesudah ini akan mengira tak ada sumber
    # apa pun — lalu mencetak ulang baris yang seharusnya dijatuhkan.
    _bundel_tunggal = next(iter(_bundel_unik)) if len(_bundel_unik) == 1 else ""

    # KEPALA SURAT MENJATUHKAN BARIS YANG SUDAH TERCETAK DI AREA TABEL.
    #
    # Laporan pemilik: *"hilangkan informasi yang berulang di bagian header
    # karena sudah terjabarkan di setiap pembagian row per kategori BAST."*
    #
    # Sejak bundel sumber menempel pada barisnya (atau tercetak sekali di
    # bawah tabel), penyedia/PPK/NIP dan keterangan nomor BAST muncul DUA
    # KALI dalam satu halaman. Yang selalu sama berhenti dibaca — dan ketika
    # salah satunya kelak berbeda, perbedaan itu ikut terlewat.
    #
    # DIJATUHKAN BERDASARKAN NILAI, bukan berdasarkan jenis LPB: baris hanya
    # hilang bila teksnya memang sudah ada di area tabel. LPB persediaan lama
    # yang tak punya bundel apa pun tetap menampilkan seluruh kepalanya.
    from lpb_utils import keterangan_berulang, kepala_tercakup, nilai_berulang
    _teks_tabel = " · ".join(sorted(_bundel_unik))
    # Kunci mana yang sudah tercetak pada SETIAP baris tabel. Ini penjatuh
    # yang lebih dapat diandalkan daripada mencocokkan teks: bundel sumber
    # memformat tanggal dan NIP-nya sendiri, sehingga nilai kepala surat tak
    # pernah muncul apa adanya di sana meski keterangannya sudah ada.
    _tercakup = kepala_tercakup(_items)
    _nip_ppk = _baris_nip_ppk(lpb)
    # Versi TANPA tag <b> — `_baris_nip_ppk` mengembalikan HTML, dan HTML tak
    # akan pernah cocok dengan teks bundel sumber.
    _nip_mentah = ((baris_identitas_ttd(lpb.get("ppk_nip"),
                                        lpb.get("ppk_status_kepegawaian"))
                    or [""])[0])
    _sel = [
        Paragraph(f"Instansi: <b>{_esc(str(settings.get('nama_instansi') or '-'))}</b>", meta),
        Paragraph(f"Jenis: <b>{_esc(label_kat)} — {_esc(label_jenis)}</b>", meta),
        Paragraph(f"Kantor/Satker: <b>{_esc(str(settings.get('nama_sub_unit') or settings.get('nama_unit_organisasi') or '-'))}</b>", meta),
        Paragraph("Tautan BAST Pengadaan: <b>"
                  + (f"{len(lpb.get('perolehan_ids') or [])} perolehan (gabungan)"
                     if is_gabungan
                     else (lpb.get('perolehan_id')[:8] + '…'
                           if lpb.get('perolehan_id') else '-'))
                  + "</b>", meta),
    ]
    # BARIS "No. Bukti/Faktur" DIHAPUS SELURUHNYA, bukan dijatuhkan bersyarat.
    #
    # Ia tak pernah mencetak nomor bukti: isinya `lpb["jenis_dokumen"]`, yang
    # bernilai "BAST" / "SK Penghapusan" — JENIS dokumennya, bukan nomornya.
    # Label dan isinya tak pernah cocok sejak awal. Nomor bukti yang sungguhan
    # hidup per register dan kini tercetak pada bundel sumber barisnya
    # (`bersihkan_dokumen` → "No. Bukti/Faktur: …"), jadi tak ada keterangan
    # yang hilang — yang hilang hanya label yang menyesatkan.
    #
    # Tanggal kedatangan menyusul: satu tanggal di kepala surat tak bisa
    # mewakili LPB gabungan yang merangkum banyak BAST bertanggal berbeda.
    # Ia hanya bertahan bila ada baris yang belum membawa tanggalnya sendiri.
    if "tanggal" not in _tercakup:
        _sel.append(Paragraph(
            f"Tgl Kedatangan: <b>{_fmt_tanggal_id(lpb.get('tanggal')) or '-'}</b>", meta))
    # Penyedia & PPK dijatuhkan HANYA bila NILAINYA memang sudah tercetak.
    # Sempat dicoba berbasis cakupan — dan itu keliru: LPB gabungan yang tiap
    # barisnya menyebut penyedia BERBEDA akan kehilangan nama penyedia di
    # kepala suratnya, padahal justru itu keterangan yang berbeda. Cakupan
    # hanya sah untuk keterangan yang kepala suratnya memang TAK SANGGUP
    # mewakili (tanggal kedatangan di bawah), bukan untuk yang kebetulan
    # sejenis.
    if not nilai_berulang(lpb.get("penyedia"), _teks_tabel):
        _sel.append(Paragraph(
            f"Nama Rekanan/Penyedia: <b>{_esc(str(lpb.get('penyedia') or '-'))}</b>", meta))
    if not keterangan_berulang(lpb.get("keterangan"), _teks_tabel):
        _sel.append(Paragraph(
            f"Keterangan: <b>{_esc(str(lpb.get('keterangan') or '-'))}</b>", meta))
    # PPK: pihak yang berkomitmen atas pengadaan barang ini (Perpres 16/2018
    # Pasal 11). NIP-nya melewati `baris_identitas_ttd`, ATURAN YANG SAMA
    # dengan blok tanda tangan di bawah: Non-ASN tak dicetak nomornya.
    if not nilai_berulang(lpb.get("ppk_nama"), _teks_tabel):
        _sel.append(Paragraph(f"PPK: <b>{_esc(str(lpb.get('ppk_nama') or '-'))}</b>", meta))
        if _nip_ppk:
            _sel.append(Paragraph(_nip_ppk, meta))
    elif _nip_ppk and not nilai_berulang(_nip_mentah, _teks_tabel):
        # NAMANYA sudah di area tabel, NIP-nya BELUM: bundel sumber hanya
        # membawa nama PPK. Menjatuhkan barisnya sekalian akan MEMBUANG
        # nomornya — pemangkasan pengulangan tak boleh menghilangkan
        # informasi. Dicetak ber-label sendiri karena tetangganya sudah tiada.
        _sel.append(Paragraph(f"PPK — {_nip_ppk}", meta))
    # Disusun dua kolom dari daftar sel — bukan matriks tetap: baris yang
    # dijatuhkan tak boleh meninggalkan lubang di tengah kepala surat.
    _baris_info = [_sel[i:i + 2] for i in range(0, len(_sel), 2)]
    if _baris_info and len(_baris_info[-1]) == 1:
        _baris_info[-1].append(Paragraph("", meta))
    info = Table(_baris_info,
                 colWidths=[doc.width * 0.52, doc.width * 0.48], hAlign='LEFT')
    info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    el.append(info)
    el.append(Spacer(1, 2.5 * rl_mm))

    # ── Tabel objek: BERKELOMPOK per BIDANG, dan tiap barang membawa
    #    keterangan sumbernya sendiri ──────────────────────────────────────
    #
    # Permintaan pemilik: *"keterangan rekanan/penyedia, PPK dll yang menempel
    # pada setiap barang pengadaannya masing-masing dijadikan satu bundle
    # informasi di dalam tabel, bertempat di row barang di bawahnya yang sudah
    # dikategorikan… dan pada setiap row barang tolong kategorikan dengan per
    # bidang barangnya masing-masing agar menambah kerapian."*
    #
    # Dua hal yang membuat rancangan ini bukan sekadar kerapian:
    #
    # 1. LPB GABUNGAN merangkum BANYAK BAST PPK-KPB sekaligus. Satu kepala
    #    surat hanya bisa menyebut SATU penyedia — pembaca yang ingin tahu
    #    barang ini datang dari rekanan mana harus bisa membacanya di barisnya
    #    sendiri, bukan menebak dari nomor BAST di kolom keterangan.
    # 2. Bundel itu ditaruh sebagai BARIS TERSENDIRI di bawah barangnya, bukan
    #    sebagai kolom-kolom baru. Tabel ini sudah berisi tujuh kolom; menambah
    #    enam kolom dokumen akan menyempitkan nama barang sampai tak terbaca,
    #    dan sebagian besarnya kosong karena tiap register hanya menempuh satu
    #    jalur pembayaran.
    #
    # Kolom NUP tersendiri DILEBUR ke kolom identitas sebagai RENTANG ("NUP
    # 1–3"): pemilik memintanya menyebut "dari nomor berapa sampai berapa", dan
    # nomor pertama saja membuat dokumen berkata "5 printer diterima" tanpa
    # bisa membuktikan printer YANG MANA.
    _kode_semua = [str(b.get("kode_barang") or "") for b in _items]
    _subsub = await _peta_subsub_kelompok(_kode_semua)
    _uraian_bidang = await _peta_uraian_bidang(_kode_semua)
    _kelompok = _kelompokkan_per_golongan_bidang(
        [{**b, "asset_code": b.get("kode_barang") or ""} for b in _items])

    _kepala = ["No", "Identitas Barang<br/>(Sub-sub Kelompok · Kode · NUP)",
               "Nama Barang", "Qty", "Satuan", "Harga (Rp)", "Total (Rp)"]
    lebar = [24, 150, 150, 34, 44, 78, 88]
    data = [[Paragraph(h, st['TableHeader']) for h in _kepala]]
    _kecil = ParagraphStyle('LpbKecil', parent=cell, fontSize=7.0, leading=8.6)
    _sekat_gol, _sekat_bid, _baris_bundel = [], [], []
    _bundel_terakhir = ""
    i = 0

    def _unit(daftar):
        return sum(float(x.get("jumlah") or 0) for x in daftar)

    def _rupiah(daftar):
        return sum(float(x.get("total") or 0) for x in daftar)

    for _kode_gol, _bidang_list in _kelompok:
        _isi_gol = [x for _, isi in _bidang_list for x in isi]
        _sekat_gol.append(len(data))
        data.append(_baris_sekat_golongan(
            _kode_gol, label_golongan(_kode_gol), _unit(_isi_gol),
            len(_kepala), st, keterangan=fmt_rp(_rupiah(_isi_gol))))
        for _kode_bidang, _isi in _bidang_list:
            _sekat_bid.append(len(data))
            data.append(_baris_sekat_bidang(
                _kode_bidang, _uraian_bidang.get(_kode_bidang, ""),
                _unit(_isi), len(_kepala), st,
                keterangan=fmt_rp(_rupiah(_isi))))
            for b in _isi:
                i += 1
                _kode = str(b.get("kode_barang") or "-").strip()
                _nup = str(b.get("nup") or "").strip()
                _nm_subsub = _subsub.get(_norm_kode(_kode), "")
                _identitas = "".join([
                    f"<font size=7>{_esc(_nm_subsub)}</font><br/>" if _nm_subsub else "",
                    f"<b>{_esc(_kode)}</b>",
                    f" · NUP {_esc(_nup)}" if _nup else "",
                ])
                data.append([
                    Paragraph(str(i), cellc),
                    Paragraph(_identitas, cell),
                    Paragraph(_esc(str(b.get("nama_barang") or "-")), cell),
                    Paragraph(str(b.get("jumlah")), cellc),
                    Paragraph(_esc(str(b.get("satuan") or "-")), cellc),
                    Paragraph(fmt_rp(b.get("harga_satuan")), cellr),
                    Paragraph(fmt_rp(b.get("total")), cellr),
                ])
                _bundel = _bundel_baris(b)
                # Dicetak HANYA bila sumbernya BERBEDA dari baris sebelumnya —
                # dan sama sekali tidak bila seluruh LPB satu sumber (kalimat
                # tunggalnya dicetak sekali di bawah tabel).
                if _bundel and not _bundel_tunggal and _bundel != _bundel_terakhir:
                    _bundel_terakhir = _bundel
                    _baris_bundel.append(len(data))
                    data.append([Paragraph("", _kecil),
                                 Paragraph(f"<i>{_esc(_bundel)}</i>", _kecil)]
                                + [Paragraph("", _kecil)] * (len(_kepala) - 2))
    data.append([Paragraph("", cell), Paragraph("", cell),
                 Paragraph("<b>JUMLAH</b>", cell), Paragraph("", cell),
                 Paragraph("", cell), Paragraph("", cell),
                 Paragraph(f"<b>{fmt_rp(lpb.get('total_nilai'))}</b>", cellr)])

    t = Table(data, colWidths=_fit_col_widths(lebar, doc.width), repeatRows=1)
    # Baris bundel membentang dari kolom identitas sampai ujung kanan: ia satu
    # kalimat, bukan tujuh sel kosong.
    _gaya_bundel = []
    for r in _baris_bundel:
        _gaya_bundel += [('SPAN', (1, r), (-1, r)),
                         ('TOPPADDING', (0, r), (-1, r), 0),
                         ('BOTTOMPADDING', (0, r), (-1, r), 2)]
    t.setStyle(_std_table_style(zebra=True, total_row=True, extra=[
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
    ] + _gaya_sekat_bidang(_sekat_gol, warna="#e2e8f0", padding=1.0)
        + _gaya_sekat_bidang(_sekat_bid, padding=0.5) + _gaya_bundel))
    el.append(t)
    if _bundel_tunggal:
        # Satu kalimat untuk SELURUH tabel — menggantikan pengulangan yang
        # dulu menempel di bawah setiap barang.
        el.append(Paragraph(
            f"<i>Seluruh barang di atas berasal dari — {_esc(_bundel_tunggal)}</i>",
            _kecil))
    el.append(Spacer(1, 4 * rl_mm))

    # ── Kelengkapan berkas yang menyertai barangnya ──────────────────────
    # Aturan & alasan yang sama dengan BAST PPK→KPB (lihat
    # `berkas_serah_terima`): berkas yang tidak ikut saat penerimaan hampir
    # tak pernah menyusul. LPB adalah dokumen yang DIPEGANG pengurus barang —
    # di sinilah daftar itu paling sering dibuka kembali.
    # OPSIONAL (permintaan pemilik: *"hilangkan bagian KELENGKAPAN BERKAS
    # YANG MENYERTAI BARANG, buat opsional saja, bisa ditampilkan atau
    # tidak"*). Bawaan MATI: LPB adalah bukti penerimaan yang dibaca
    # berulang-ulang, dan daftar periksa yang selalu ikut membuatnya berlipat
    # panjang tanpa diminta. Yang membutuhkannya menyalakannya sendiri.
    #
    # BAST PPK→KPB tetap memuatnya apa adanya — di sanalah serah terima
    # berkasnya benar-benar terjadi.
    from berkas_serah_terima import catatan_ambang, kelompok_berkas
    _klp_berkas = kelompok_berkas(_items) if sertakan_kelengkapan else []
    if _klp_berkas:
        el.append(Paragraph("<b>KELENGKAPAN BERKAS YANG MENYERTAI BARANG</b>",
                            st['Meta']))
        # SATU tabel berkolom — alasan & bentuk sama dengan BAST PPK→KPB.
        el.extend(_tabel_kelengkapan(_klp_berkas, doc.width, st, gaya=_kecil))
        _ctt = catatan_ambang(_items)
        if _ctt:
            el.append(Paragraph(f"<i>{_esc(_ctt)}</i>", _kecil))
        el.append(Spacer(1, 4 * rl_mm))

    # Tanda tangan 3 kolom: Dibuat (pengurus barang), Diperiksa (atasan
    # langsung — dititik bila belum diatur), Disetujui (KPB).
    #
    # Ter-scope ke satker PENERBIT dokumen, BUKAN satker pembaca (temuan audit
    # adversarial). Dulu memakai `kode_satker_user(_user)`: super-admin yang
    # mencetak LPB satker A memperoleh `""` → `_q_pejabat_satker("")` kosong →
    # pejabat SELURUH satker jadi kandidat, dan yang SK-nya paling baru menang.
    # Dokumen resmi satker A bisa tercetak dengan nama pejabat satker B.
    # `lpb["kode_satker"]` adalah stempel yang dibekukan saat LPB terbit; itulah
    # jawaban yang benar, dan ia tak berubah siapa pun yang membukanya.
    _kode = str(lpb.get("kode_satker") or "").strip()
    pengurus = await resolve_pejabat_peran("pengurus_barang",
                                           per_iso=lpb.get("tanggal"),
                                           kode_satker=_kode)
    pemeriksa = await resolve_pejabat_peran("pemeriksa_lpb",
                                            per_iso=lpb.get("tanggal"),
                                            kode_satker=_kode)
    kpb = await resolve_penandatangan_kpb(settings, per_iso=lpb.get("tanggal"),
                                          kode_satker=_kode)

    # ── Penanda tangan pilihan: dokumen → satker → peran ───────────────────
    # Permintaan pemilik: *"sudah aktif semua bisa memilih siapa saja yang
    # menandatangani sesuai referensi pejabat yang sudah ditetapkan"*.
    #
    # Slot "Diperiksa oleh" adalah yang paling sering kosong — perannya
    # (`pemeriksa_lpb`) jarang ditetapkan di Referensi Pejabat, sehingga
    # kolomnya terbit sebagai titik-titik tanpa ada yang bisa dilakukan dari
    # layar mana pun. Sekarang satker bisa menunjuk siapa pun dari Referensi
    # Pejabat, dan dokumen tertentu masih bisa menimpanya.
    #
    # Resolusi peran di atas TETAP dihitung dan tetap menjadi jaring terakhir:
    # satker yang belum pernah menyentuh setelan ini tak berubah apa pun.
    from penandatangan_dokumen import pilih_pejabat as _pilih_ttd
    from shared_utils import _q_pejabat_satker
    _daftar_pejabat = await db.pejabat.find(
        _q_pejabat_satker(_kode), {"_id": 0}).to_list(2000)
    _satker_doc = await db.satker.find_one({"kode_satker": _kode},
                                           {"_id": 0}) or {}
    _set_ttd = _satker_doc.get("penandatangan") or {}
    _dok_ttd = lpb.get("penandatangan") or {}
    pengurus = _pilih_ttd("lpb_dibuat", _dok_ttd, _set_ttd,
                          _daftar_pejabat, pengurus)
    pemeriksa = _pilih_ttd("lpb_diperiksa", _dok_ttd, _set_ttd,
                           _daftar_pejabat, pemeriksa)
    kpb = _pilih_ttd("lpb_disetujui", _dok_ttd, _set_ttd,
                     _daftar_pejabat, kpb)
    sig = st['Signature']

    def kolom_ttd(judul, nama, nip, status_kepegawaian=""):
        # Non-ASN: baris NIP/NIK tidak dicetak (privasi)
        baris = baris_identitas_ttd(nip, status_kepegawaian)
        kolom = [Paragraph(judul, sig), Spacer(1, 20 * rl_mm),
                 Paragraph(f"<b><u>{nama or '……………………………'}</u></b>", sig)]
        kolom.extend(Paragraph(b, sig) for b in baris)
        return kolom

    ttd = Table([[
        kolom_ttd("Dibuat oleh:<br/>Pengurus Barang,",
                  (pengurus or {}).get("nama"), (pengurus or {}).get("nip"),
                  (pengurus or {}).get("status_kepegawaian")),
        kolom_ttd("Diperiksa oleh:" + (f"<br/>{(pemeriksa or {}).get('jabatan')}," if (pemeriksa or {}).get('jabatan') else ""),
                  (pemeriksa or {}).get("nama"), (pemeriksa or {}).get("nip"),
                  (pemeriksa or {}).get("status_kepegawaian")),
        kolom_ttd(f"Disetujui oleh:<br/>{_hdr_kpb(kpb)}",
                  (kpb or {}).get("nama"), (kpb or {}).get("nip"),
                  (kpb or {}).get("status_kepegawaian")),
    ]], colWidths=[doc.width / 3.0] * 3)
    ttd.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    el.append(ttd)

    footer = _page_footer_factory("Laporan Penerimaan Barang (LPB)")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    return buffer.getvalue()


@persediaan_router.get("/persediaan/lpb/{lpb_id}/pdf")
async def lpb_pdf(lpb_id: str, kelengkapan: bool = False,
                  _user: dict = Depends(require_user_or_query_token)):
    """Laporan Penerimaan Barang (LPB) — format resmi satker: kop, info 2
    kolom, tabel barang ber-total (plus kolom NUP bila kategorinya aset),
    tanda tangan 3 kolom (Dibuat/Diperiksa/Disetujui).

    `kelengkapan=true` menambahkan daftar periksa berkas yang menyertai
    barang. BAWAAN MATI — lihat alasannya di `bangun_lpb_pdf`.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse

    data = await bangun_lpb_pdf(lpb_id, _user,
                                sertakan_kelengkapan=bool(kelengkapan))
    return StreamingResponse(BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="LPB_{lpb_id[:8]}.pdf"'})


class KirimTtdLpbIn(BaseModel):
    signers: list[dict] = Field(default_factory=list, max_length=10)
    mode: str = "berurutan"


@persediaan_router.post("/persediaan/lpb/{lpb_id}/kirim-ttd")
async def kirim_ttd_lpb(lpb_id: str, payload: KirimTtdLpbIn,
                        user: dict = Depends(require_writer)):
    """Kirim LPB ini untuk ditandatangani elektronik (link per penanda tangan).

    PDF disusun SEKARANG lalu DIBEKUKAN ke GridFS — bukan dibangun ulang saat
    penanda tangan membukanya. Kalau dibangun ulang, kop/pejabat/nomor bisa
    berubah di antara "dikirim" dan "diteken", dan yang bersangkutan akan
    menandatangani dokumen yang tak pernah ia baca.

    Penanda tangan bawaan diambil dari blok TTD LPB itu sendiri (Pengurus
    Barang → Pemeriksa → KPB, `mode="berurutan"`) supaya urutan tekennya sama
    dengan urutan pada kertasnya. Kirim `signers` untuk menimpanya.
    """
    from routes.ttd import PermintaanIn, SignerIn, buat_permintaan
    from shared_utils import (pastikan_akses_dok_satker, kode_satker_user,
                              resolve_pejabat_peran, resolve_penandatangan_kpb)

    lpb = await db.lpb.find_one({"id": lpb_id}, {"_id": 0, "items": 0})
    if not lpb:
        raise HTTPException(status_code=404, detail="LPB tidak ditemukan")
    await pastikan_akses_dok_satker(user, lpb)   # isolasi satker

    daftar = list(payload.signers or [])
    if not daftar:
        _kode = kode_satker_user(user)
        _tgl = lpb.get("tanggal")
        settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
        _kpb = await resolve_penandatangan_kpb(settings, per_iso=_tgl,
                                               kode_satker=_kode)
        # KPB menandatangani LPB dalam KAPASITAS "Kuasa Pengguna Barang"
        # (dokumen ber-kop KPB) — bukan jabatan strukturalnya bila rangkap.
        from pejabat_utils import jabatan_kapasitas_kpb
        if (_kpb or {}).get("nama"):
            _kpb = {**_kpb, "jabatan": jabatan_kapasitas_kpb(_kpb)}
        kandidat = [
            await resolve_pejabat_peran("pengurus_barang", per_iso=_tgl, kode_satker=_kode),
            await resolve_pejabat_peran("pemeriksa_lpb", per_iso=_tgl, kode_satker=_kode),
            _kpb,
        ]
        daftar = [{"nama": str((k or {}).get("nama") or "").strip(),
                   "nip": str((k or {}).get("nip") or "").strip(),
                   "jabatan": str((k or {}).get("jabatan") or "").strip(),
                   "email": str((k or {}).get("email") or "").strip()}
                  for k in kandidat if (k or {}).get("nama")]
    if not daftar:
        raise HTTPException(
            status_code=400,
            detail=("Belum ada pejabat penanda tangan LPB. Isi Referensi "
                    "Pejabat (Pengurus Barang / Pemeriksa LPB / KPB) lebih "
                    "dulu, atau kirim daftar penanda tangan secara manual."))

    data = await bangun_lpb_pdf(lpb_id, user)
    hasil = await buat_permintaan(
        payload=PermintaanIn(
            judul=f"LPB {lpb.get('nomor') or lpb_id[:8]}",
            doc_type="lpb", doc_ref=lpb_id,
            mode=("paralel" if payload.mode == "paralel" else "berurutan"),
            signers=[SignerIn(nama=str(s.get("nama") or ""),
                              nip=str(s.get("nip") or ""),
                              jabatan=str(s.get("jabatan") or ""),
                              email=str(s.get("email") or ""))
                     for s in daftar]),
        user=user)

    # GERBANG KOMPRESI. Dokumen ini ditulis SEBELUM QR dan spesimen tanda
    # tangan dibubuhkan (pembubuhan ada di routes/ttd.py, yang memang
    # pengecualian tetap) — jadi yang dikompres masih naskah vektor polos.
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        data, nama=f"LPB_{lpb_id[:8]}.pdf", content_type="application/pdf",
        metadata={"kind": "lpb", "lpb_id": lpb_id})
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id),
                  "dok_nama": f"LPB_{lpb_id[:8]}.pdf", "dok_halaman": 1}})
    # Tautan MAJU (LPB → permintaan) sudah ditulis `buat_permintaan` lewat
    # `ttd_penautan.catat_pengiriman_ttd` — satu pintu untuk semua modul.
    # Tautan BALIK ditulis routes/ttd.py saat semua pihak selesai meneken.
    await log_audit("lpb_kirim_ttd", "", lpb_id,
                    username=user.get("username", "system"),
                    detail=(f"LPB {lpb.get('nomor') or lpb_id[:8]} dikirim ke "
                            f"{len(daftar)} penanda tangan"))
    return {**hasil, "lpb_id": lpb_id}


@persediaan_router.get("/persediaan/gudang/daftar")
async def daftar_gudang(_user: dict = Depends(require_user)):
    """Daftar nilai Lokasi/Gudang unik yang terpakai di master (untuk filter)."""
    # Isolasi satker (REVIEW-9 R10): dropdown filter jangan memuat nama
    # gudang/ruang milik satker lain.
    from shared_utils import scope_query_field_satker
    nilai = await db.persediaan.distinct(
        "lokasi", scope_query_field_satker(_user))
    gudang = sorted({str(v).strip() for v in nilai if str(v or "").strip()},
                    key=str.casefold)
    return {"items": gudang, "total": len(gudang)}


@persediaan_router.get("/persediaan")
async def list_persediaan(
    search: str = "",
    status: str = Query("", pattern="^(|aman|kritis|habis)$"),
    gudang: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Daftar master persediaan: cari kode/nama/merk, filter status stok
    dan Lokasi/Gudang (padanan persis, abaikan kapital)."""
    from shared_utils import scope_query_field_satker
    query = scope_query_field_satker(_user)
    if gudang.strip():
        query["lokasi"] = {"$regex": f"^{re.escape(gudang.strip())}$",
                           "$options": "i"}
    # Pencarian teks bebas via Meilisearch bila aktif → id kandidat ter-scope;
    # fallback → regex Mongo lama. Scope satker tetap ditegakkan query di atas.
    meili_ids = await cari_id_persediaan(_user, search) if search.strip() else None
    # Hasil KOSONG dari Meili TIDAK dipercaya sebagai "memang tidak ada":
    # indeks bisa tertinggal (dokumen gagal sinkron saat Meili mati) dan
    # pencocokan berbasis kata di Meili tak mengenal kode yang diketik tanpa
    # pemisah. Nihil → jatuh ke regex Mongo yang otoritatif; biaya pindai
    # hanya muncul pada pencarian yang memang tak berhasil.
    if meili_ids is not None and not meili_ids:
        meili_ids = None
    if meili_ids is not None:
        query["id"] = {"$in": meili_ids}
    elif pecah_kata(search):
        # Kode barang dicocokkan dari DEPAN bila katanya angka (kode 16 digit
        # dibaca dari digit pertama); field lain substring biasa.
        query.update(klausa_teks(search, ("nama_barang", "merk"),
                                 fields_awalan=("kode_barang",)))
    # Filter status stok dihitung DI QUERY (bukan pasca-paging) agar total &
    # halaman benar: habis = stok<=0; kritis = 0<stok<=batas (batas>0).
    if status == "habis":
        query["stok"] = {"$lte": 0}
    elif status == "kritis":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$gt": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
            {"$lte": ["$stok", "$batas_kritis"]},
        ]}
    elif status == "aman":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$or": [
                {"$lte": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
                {"$gt": ["$stok", "$batas_kritis"]},
            ]},
        ]}
    total = await db.persediaan.count_documents(query)
    cursor = (db.persediaan.find(query, {"_id": 0, "batches": 0})
              .sort([("nama_barang", 1), ("kode_barang", 1)])
              .skip((page - 1) * page_size).limit(page_size))
    items = [_doc(x) async for x in cursor]
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@persediaan_router.get("/persediaan/{item_id}")
async def get_persediaan(item_id: str, _user: dict = Depends(require_user)):
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(_user, item)
    out = _doc(item)
    out["batches"] = item.get("batches") or []  # detail menampilkan layer FIFO
    return out


@persediaan_router.post("/persediaan")
async def create_persediaan(data: PersediaanCreate, _user: dict = Depends(require_writer_satker)):
    kode = str(data.kode_barang or "").strip()
    ok, err = validate_kode_persediaan(kode)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # Kode 10 digit → lengkapi 6 digit nomor urut otomatis (increment
    # dari kode terbesar se-prefix; numerik karena panjang seragam).
    if len(kode) == KODE_PREFIX_LEN:
        # Lingkup SATKER (REVIEW-9 R15): deret 6 digit ini milik satker —
        # tanpa scope, nomor melompat mengikuti volume satker lain sekaligus
        # membocorkannya (selaras deret NUP persediaan di R3).
        from shared_utils import scope_query_field_satker as _sqfs
        max_doc = await db.persediaan.find_one(
            _sqfs(_user, {"kode_barang": {"$regex": f"^{kode}"}}),
            {"_id": 0, "kode_barang": 1}, sort=[("kode_barang", -1)])
        try:
            kode = next_kode_penuh(kode, (max_doc or {}).get("kode_barang"))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    # NUP otomatis bila kosong: increment NUP terbesar pada kode sama —
    # DALAM LINGKUP SATKER pembuat (REVIEW-9 R3: deret NUP & keunikan
    # kode+NUP berlaku per satker, sejalan keunikan NIP pegawai; item era
    # lama tanpa kode_satker tetap terhitung milik satker yang melihatnya).
    from shared_utils import kode_satker_user, scope_query_field_satker
    nup = str(data.nup or "").strip()
    if not nup:
        max_nup_doc = await db.persediaan.find_one(
            scope_query_field_satker(_user, {"kode_barang": kode}),
            {"_id": 0, "nup": 1}, sort=[("nup_num", -1)])
        nup = next_nup((max_nup_doc or {}).get("nup"))
    if await db.persediaan.find_one(
            scope_query_field_satker(_user, {"kode_barang": kode, "nup": nup}),
            {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"Kode {kode} NUP {nup} sudah terdaftar")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "kode_barang": kode,
        # ISOLASI SATKER: item baru terikat satker pembuat ('' = lintas).
        "kode_satker": kode_satker_user(_user),
        "nup": nup,
        "nup_num": int(nup) if nup.isdigit() else 0,
        "nama_barang": data.nama_barang.strip(),
        "merk": data.merk.strip(),
        "tipe": data.tipe.strip(),
        "satuan": (data.satuan or "Buah").strip() or "Buah",
        "lokasi": data.lokasi.strip(),
        "batas_kritis": int(data.batas_kritis or 0),
        "expired_default": data.expired_default.strip(),
        "tahun_anggaran": data.tahun_anggaran.strip(),
        "keterangan": data.keterangan.strip(),
        "stok": 0,          # stok lahir 0 — bertambah lewat transaksi masuk
        "batches": [],      # layer FIFO {batch_id, tanggal, qty, harga, expired, ref}
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.persediaan.insert_one({**doc})
    jadwalkan_sync("persediaan", doc)  # sinkron indeks Meili (best-effort)
    return _doc(doc)


@persediaan_router.put("/persediaan/{item_id}")
async def update_persediaan(
    item_id: str,
    data: PersediaanUpdate,
    if_match: str = Header("", alias="If-Match"),
    _user: dict = Depends(require_writer),
):
    """Ubah field non-identitas master (OCC: wajib If-Match versi terkini)."""
    from shared_utils import pastikan_akses_dok_satker
    _item_scope = await db.persediaan.find_one(
        {"id": item_id}, {"_id": 0, "kode_satker": 1})
    if _item_scope:
        await pastikan_akses_dok_satker(_user, _item_scope)
    # Whitelist dari registry (persediaan_fields) — field identitas/terkelola
    # sistem tak akan pernah lolos meski model berubah; test registry menjaga.
    updates = {}
    for k, v in data.model_dump(exclude_none=True).items():
        if k not in EDITABLE_FIELD_NAMES:
            continue
        updates[k] = v.strip() if isinstance(v, str) else v
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah")
    if not if_match.strip().isdigit():
        raise HTTPException(status_code=428, detail="Header If-Match (versi) wajib disertakan")

    version = int(if_match.strip())
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.persediaan.find_one_and_update(
        {"id": item_id, "version": version},
        {"$set": updates, "$inc": {"version": 1}},
        projection={"_id": 0},
        return_document=True,
    )
    if res is None:
        exists = await db.persediaan.find_one({"id": item_id}, {"_id": 1})
        if not exists:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        raise HTTPException(status_code=409, detail="Versi berubah — muat ulang data lalu simpan lagi")
    jadwalkan_sync("persediaan", res)  # sinkron indeks Meili (best-effort)
    return _doc(res)


class TransaksiMasukIn(BaseModel):
    jenis: str = "pembelian"
    jumlah: int = Field(gt=0)
    harga_satuan: float = Field(0, ge=0)
    expired: str = ""            # YYYY-MM-DD; kosong = pakai expired_default
    no_bukti: str = ""
    jenis_dokumen: str = ""      # BAST / Kuitansi / Kontrak / SPBy / dll.
    tgl_dokumen: str = ""
    no_kontrak: str = ""
    penyedia: str = ""
    perolehan_id: str = ""       # FK perolehan Pengadaan (dokumen sumber, #259)
    keterangan: str = ""


async def _ambil_snapshot_perolehan(perolehan_id: str, user=None) -> dict:
    """Cari perolehan Pengadaan (bila id diisi) → snapshot FK dokumen sumber;
    404 bila hilang (tiru `_ambil_snapshot_penganggaran` #199/#258).

    ISOLASI SATKER (temuan audit adversarial): pencarian di-scope ke satker
    pemanggil. Tanpa itu, writer satker A yang menebak/mendapat uuid BAST
    satker B dapat MENYALIN identitas dokumen B — nomor BAST, tanggal,
    penyedia, dan sejak PR ini juga NAMA & NIP PPK-nya — ke dalam jurnal
    persediaan dan LPB satker A. Bukan sekadar terbaca: tersimpan permanen di
    dokumen resmi satker lain, lengkap dengan data pribadi pejabatnya.
    """
    pid = str(perolehan_id or "").strip()
    if not pid:
        return snapshot_perolehan(None)
    from shared_utils import scope_query_field_satker
    p = await db.pengadaan.find_one(
        scope_query_field_satker(user, {"id": pid}),
        # `ppk_*` WAJIB ikut diproyeksikan — `snapshot_perolehan` membaca
        # keduanya, dan proyeksi yang tak memuatnya membuat nama PPK selalu
        # kosong di jurnal persediaan tanpa satu pun galat yang terlihat.
        {"_id": 0, "id": 1, "nomor_bast": 1, "tanggal_bast": 1, "jenis": 1,
         "pihak": 1, "ppk_nama": 1, "ppk_nip": 1})
    if not p:
        raise HTTPException(status_code=404,
                            detail="Perolehan Pengadaan tidak ditemukan")
    return snapshot_perolehan(p)


async def _gerbang_wajib_persetujuan(request):
    """Gerbang SEDIA-KPB: bila setelan `persediaan_wajib_persetujuan` aktif,
    permintaan HTTP LANGSUNG ke endpoint transaksi ditolak — transaksi hanya
    boleh lahir dari persetujuan permohonan (routes/persediaan_permohonan.py),
    yang mengeksekusi lewat pemanggilan internal `request=None`.

    Default MATI: perilaku lama utuh sampai UI permohonan siap dan pemilik
    menyalakannya dari Pengaturan. `request is None` = pemanggil internal
    (jalur persetujuan, transaksi massal per-baris, Pengadaan) — dilewatkan,
    karena gerbangnya sudah dibayar di pintu masuknya masing-masing.
    """
    if request is None:
        return
    s = await db.report_settings.find_one(
        {"type": "global"}, {"persediaan_wajib_persetujuan": 1}) or {}
    if s.get("persediaan_wajib_persetujuan"):
        raise HTTPException(
            status_code=403,
            detail=("Transaksi persediaan wajib melalui permohonan dan "
                    "persetujuan KPB — ajukan lewat menu Permohonan"))


@persediaan_router.post("/persediaan/{item_id}/masuk")
async def transaksi_masuk(item_id: str, data: TransaksiMasukIn,
                          request: Request = None,
                          user: dict = Depends(require_writer)):
    """Transaksi MASUK: layer FIFO baru + stok naik + jurnal (pustaka §3).

    Pencatatan perpetual: master diperbarui ATOMIK ($push layer + $inc stok
    + $inc version); jurnal `transaksi_persediaan` menyusul dengan
    stok_sebelum/sesudah — bila penulisan jurnal gagal, layer dikompensasi
    (dicabut lagi) supaya master tidak pernah menyimpan stok tanpa jejak.

    Idempotency-Key (opsional): double-submit/replay jaringan tidak
    menggandakan stok — respons pertama disimpan & diputar ulang. Pemanggil
    internal (impor massal / Pengadaan) tak mengoper `request` → dilewati.
    """
    await _gerbang_wajib_persetujuan(request)
    from shared_utils import kunci_idem
    idem_key = kunci_idem(
        request.headers.get("Idempotency-Key", "") if request is not None else "",
        user)
    if idem_key:
        from shared_utils import (get_idempotent_response,
                                  reserve_idempotency_key)
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
                detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    ok, err = validate_transaksi_masuk(data.jenis, data.jumlah, data.harga_satuan)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # FK dokumen sumber (§5A gap #2): 404 dulu SEBELUM mutasi stok agar tak ada
    # layer masuk tanpa perolehan valid.
    snap_perolehan = await _ambil_snapshot_perolehan(data.perolehan_id, user)

    now = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())
    ref = (data.no_bukti or data.no_kontrak or "").strip()

    # Ambil dulu untuk stok_sebelum + expired_default (best-effort snapshot;
    # angka resmi stok sebelum/sesudah diambil dari hasil update atomik).
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(user, item)

    # M94 membatalkan pencatatan K09 — jumlahnya WAJIB <= sisa di daftar Tak
    # Dikuasai, paritas dengan H03 yang sudah lama divalidasi. Tanpa pagar
    # ini M94 bisa dicatat tanpa pernah ada K09 (stok+nilai naik sewenang
    # dengan harga bebas), dan over-pembatalan tak terlihat di mana pun
    # karena rekap_nonaktif membuang baris ber-sisa <= 0.
    if data.jenis == "batal_catat_tak_dikuasai":
        rows = [t async for t in db.transaksi_persediaan.find(
            {"persediaan_id": item_id}, {"_id": 0}).sort("timestamp", 1)]
        sisa_td = (rekap_nonaktif(rows).get("tidak_dikuasai", {})
                   .get(item_id) or {"jumlah": 0})
        if int(data.jumlah) > int(sisa_td["jumlah"]):
            raise HTTPException(
                status_code=400,
                detail=(f"Jumlah pembatalan melebihi sisa tercatat di daftar "
                        f"Tak Dikuasai ({int(sisa_td['jumlah'])})"))

    expired = (data.expired or item.get("expired_default") or "").strip()
    layer = buat_layer(batch_id, now.isoformat(), data.jumlah, data.harga_satuan, expired, ref)

    updated = await db.persediaan.find_one_and_update(
        {"id": item_id},
        {"$push": {"batches": layer},
         "$inc": {"stok": int(data.jumlah), "version": 1},
         "$set": {"updated_at": now.isoformat()}},
        projection={"_id": 0},
        return_document=True,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")

    stok_sesudah = int(updated.get("stok", 0) or 0)
    jurnal = {
        "id": str(uuid.uuid4()),
        "arah": "masuk",
        "jenis": data.jenis,
        "jenis_label": JENIS_MASUK[data.jenis][0],
        "kode_sakti": JENIS_MASUK[data.jenis][1],
        "persediaan_id": item_id,
        "kode_barang": updated.get("kode_barang"),
        "nup": updated.get("nup"),
        "nama_barang": updated.get("nama_barang"),
        "batch_id": batch_id,
        "jumlah": int(data.jumlah),
        "harga_satuan": float(data.harga_satuan),
        "total": int(data.jumlah) * float(data.harga_satuan),
        "stok_sebelum": stok_sesudah - int(data.jumlah),
        "stok_sesudah": stok_sesudah,
        "expired": expired,
        "no_bukti": data.no_bukti.strip(),
        "jenis_dokumen": data.jenis_dokumen.strip(),
        "tgl_dokumen": data.tgl_dokumen.strip(),
        "no_kontrak": data.no_kontrak.strip(),
        "penyedia": data.penyedia.strip(),
        **snap_perolehan,
        "keterangan": data.keterangan.strip(),
        "petugas": user.get("username") or user.get("user_id") or "-",
        "timestamp": now.isoformat(),
    }
    try:
        await _insert_jurnal(jurnal)
    except Exception:
        # Kompensasi: cabut layer & stok yang barusan masuk — master tidak
        # boleh menyimpan stok tanpa jejak jurnal.
        await db.persediaan.update_one(
            {"id": item_id},
            {"$pull": {"batches": {"batch_id": batch_id}},
             "$inc": {"stok": -int(data.jumlah), "version": 1}},
        )
        raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — transaksi dibatalkan")

    resp = {"message": f"{JENIS_MASUK[data.jenis][0]} tercatat", "stok": stok_sesudah,
            "transaksi": jurnal, "version": updated.get("version")}
    if idem_key:
        from shared_utils import store_idempotent_response
        await store_idempotent_response(idem_key, resp, 200)
    return resp


class TransaksiKeluarIn(BaseModel):
    jenis: str = "habis_pakai"
    jumlah: int = Field(gt=0)
    unit_penerima: str = ""
    no_bukti: str = ""
    keterangan: str = ""


@persediaan_router.post("/persediaan/{item_id}/keluar")
async def transaksi_keluar(item_id: str, data: TransaksiKeluarIn,
                           request: Request = None,
                           user: dict = Depends(require_writer)):
    """Transaksi KELUAR: konsumsi layer FIFO tertua + jurnal (pustaka §3).

    Nilai keluar = Σ (qty terpakai × harga layer) — bukan rata-rata.
    Update master BERSYARAT VERSI (retry 3x saat balapan dengan transaksi
    lain); jurnal menyertakan rincian layer terpakai. Bila tulis jurnal
    gagal → batches & stok dikembalikan ke snapshot sebelumnya.

    Idempotency-Key (opsional): OCC mencegah lost-update, tetapi replay
    kunci sama tak boleh menggandakan pengeluaran — respons pertama disimpan
    & diputar ulang. Pemanggil internal (massal) tak mengoper `request`.
    """
    await _gerbang_wajib_persetujuan(request)
    idem_key = kunci_idem(
        request.headers.get("Idempotency-Key", "") if request is not None else "",
        user)
    if idem_key:
        from shared_utils import (get_idempotent_response,
                                  reserve_idempotency_key)
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
                detail="Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar")

    now = datetime.now(timezone.utc)
    for _attempt in range(3):
        item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        from shared_utils import pastikan_akses_dok_satker
        await pastikan_akses_dok_satker(user, item)
        stok_sebelum = int(item.get("stok", 0) or 0)
        ok, err = validate_transaksi_keluar(data.jenis, data.jumlah, stok_sebelum)
        if not ok:
            raise HTTPException(status_code=400, detail=err)
        batches_lama = item.get("batches") or []
        try:
            batches_sisa, total_nilai, rincian = konsumsi_fifo(batches_lama, data.jumlah)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        stok_sesudah = stok_sebelum - int(data.jumlah)
        updated = await db.persediaan.find_one_and_update(
            {"id": item_id, "version": item.get("version")},
            {"$set": {"batches": batches_sisa, "stok": stok_sesudah,
                      "updated_at": now.isoformat()},
             "$inc": {"version": 1}},
            projection={"_id": 0},
            return_document=True,
        )
        if updated is None:
            continue  # balapan — muat ulang lalu coba lagi

        harga_rata = (total_nilai / int(data.jumlah)) if data.jumlah else 0.0
        jurnal = {
            "id": str(uuid.uuid4()),
            "arah": "keluar",
            "jenis": data.jenis,
            "jenis_label": JENIS_KELUAR[data.jenis][0],
            "kode_sakti": JENIS_KELUAR[data.jenis][1],
            "persediaan_id": item_id,
            "kode_barang": updated.get("kode_barang"),
            "nup": updated.get("nup"),
            "nama_barang": updated.get("nama_barang"),
            "jumlah": int(data.jumlah),
            "harga_satuan": harga_rata,   # rata-rata TERTIMBANG dari layer terpakai (informasi)
            "total": total_nilai,          # nilai FIFO sesungguhnya
            "rincian_layer": rincian,
            "stok_sebelum": stok_sebelum,
            "stok_sesudah": stok_sesudah,
            "unit_penerima": data.unit_penerima.strip(),
            "no_bukti": data.no_bukti.strip(),
            "keterangan": data.keterangan.strip(),
            "petugas": user.get("username") or user.get("user_id") or "-",
            "timestamp": now.isoformat(),
        }
        try:
            await _insert_jurnal(jurnal)
        except Exception:
            # Kompensasi: kembalikan snapshot batches & stok sebelum keluar
            await db.persediaan.update_one(
                {"id": item_id},
                {"$set": {"batches": batches_lama, "stok": stok_sebelum},
                 "$inc": {"version": 1}},
            )
            raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — transaksi dibatalkan")

        resp = {"message": f"{JENIS_KELUAR[data.jenis][0]} tercatat", "stok": stok_sesudah,
                "nilai_keluar": total_nilai, "transaksi": jurnal,
                "version": updated.get("version")}
        if idem_key:
            from shared_utils import store_idempotent_response
            await store_idempotent_response(idem_key, resp, 200)
        return resp

    raise HTTPException(status_code=409,
                        detail="Barang sedang diubah pengguna lain — coba lagi")


class PindahGudangIn(BaseModel):
    lokasi_baru: str = Field(min_length=1, max_length=200)
    no_bukti: str = ""
    keterangan: str = ""


@persediaan_router.post("/persediaan/{item_id}/pindah-gudang")
async def pindah_gudang_persediaan(item_id: str, data: PindahGudangIn,
                                   request: Request = None,
                                   user: dict = Depends(require_writer)):
    """Pindahkan barang ke Lokasi/Gudang lain — ber-jurnal.

    Mutasi lokasi seluruh record: stok & layer FIFO TIDAK berubah; jurnal
    arah "mutasi" jenis "pindah_gudang" mencatat lokasi_dari/lokasi_ke
    (kode SAKTI kosong — mutasi internal satker). Bila penulisan jurnal
    gagal, lokasi dikembalikan (pola kompensasi transaksi masuk).
    """
    await _gerbang_wajib_persetujuan(request)
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(user, item)
    lokasi_lama = str(item.get("lokasi") or "").strip()
    ok, err = validate_pindah_gudang(lokasi_lama, data.lokasi_baru)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    now = datetime.now(timezone.utc)
    lokasi_baru = data.lokasi_baru.strip()
    updated = await db.persediaan.find_one_and_update(
        # Anti-balapan: lokasi lama diikutkan di filter
        {"id": item_id, "lokasi": item.get("lokasi")},
        {"$set": {"lokasi": lokasi_baru, "updated_at": now.isoformat()},
         "$inc": {"version": 1}},
        projection={"_id": 0}, return_document=True)
    if updated is None:
        raise HTTPException(status_code=409,
                            detail="Lokasi barang berubah oleh pengguna lain — muat ulang")

    stok = int(updated.get("stok", 0) or 0)
    jurnal = {
        "id": str(uuid.uuid4()),
        "arah": "mutasi",
        "jenis": "pindah_gudang",
        "jenis_label": "Pindah Gudang",
        "kode_sakti": "",
        "persediaan_id": item_id,
        "kode_barang": updated.get("kode_barang"),
        "nup": updated.get("nup"),
        "nama_barang": updated.get("nama_barang"),
        "jumlah": stok,
        "harga_satuan": 0.0,
        "total": 0.0,
        "stok_sebelum": stok,
        "stok_sesudah": stok,
        "lokasi_dari": lokasi_lama,
        "lokasi_ke": lokasi_baru,
        "no_bukti": data.no_bukti.strip(),
        "keterangan": data.keterangan.strip(),
        "petugas": user.get("username") or user.get("user_id") or "-",
        "timestamp": now.isoformat(),
    }
    try:
        await _insert_jurnal(jurnal)
    except Exception:
        # Kompensasi: kembalikan lokasi — mutasi tanpa jejak jurnal dilarang.
        await db.persediaan.update_one(
            {"id": item_id, "lokasi": lokasi_baru},
            {"$set": {"lokasi": item.get("lokasi")}, "$inc": {"version": 1}})
        raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — pindah gudang dibatalkan")

    return {"message": f"Barang dipindahkan ke {lokasi_baru}",
            "lokasi": lokasi_baru, "transaksi": jurnal,
            "version": updated.get("version")}


class OpnameIn(BaseModel):
    stok_fisik: int = Field(ge=0)
    alasan: str = Field(min_length=3, max_length=500)


@persediaan_router.post("/persediaan/{item_id}/opname")
async def opname_persediaan(item_id: str, data: OpnameIn,
                            request: Request = None,
                            user: dict = Depends(require_writer)):
    """Rekam hasil opname SATU barang (pustaka §3.3 — hanya yang selisih).

    fisik < buku → kekurangan dikonsumsi FIFO; fisik > buku → layer
    penyesuaian berharga layer termuda. Saldo buku disetel = fisik +
    jurnal jenis "opname" dengan ALASAN WAJIB (bahan pengungkapan CaLK).
    Update bersyarat versi + retry 3× seperti transaksi keluar.
    """
    await _gerbang_wajib_persetujuan(request)
    now = datetime.now(timezone.utc)
    for _attempt in range(3):
        item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        from shared_utils import pastikan_akses_dok_satker
        await pastikan_akses_dok_satker(user, item)
        stok_sebelum = int(item.get("stok", 0) or 0)
        batches_lama = item.get("batches") or []
        batch_id = str(uuid.uuid4())
        try:
            batches_baru, detail = penyesuaian_opname(
                batches_lama, data.stok_fisik, batch_id, now.isoformat())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        updated = await db.persediaan.find_one_and_update(
            {"id": item_id, "version": item.get("version")},
            {"$set": {"batches": batches_baru, "stok": int(data.stok_fisik),
                      "updated_at": now.isoformat()},
             "$inc": {"version": 1}},
            projection={"_id": 0},
            return_document=True,
        )
        if updated is None:
            continue  # balapan — muat ulang lalu coba lagi

        jurnal = {
            "id": str(uuid.uuid4()),
            "arah": detail["arah"],
            "jenis": "opname",
            "jenis_label": "Hasil Opname Fisik",
            "kode_sakti": "P01",  # kode SAKTI resmi (dulu "OPN" internal)
            "persediaan_id": item_id,
            "kode_barang": updated.get("kode_barang"),
            "nup": updated.get("nup"),
            "nama_barang": updated.get("nama_barang"),
            "jumlah": int(detail["jumlah"]),
            "harga_satuan": (detail["nilai"] / detail["jumlah"]) if detail["jumlah"] else 0.0,
            "total": float(detail["nilai"]),
            "rincian_layer": detail.get("rincian", []),
            "stok_sebelum": stok_sebelum,
            "stok_sesudah": int(data.stok_fisik),
            "keterangan": data.alasan.strip(),
            "petugas": user.get("username") or user.get("user_id") or "-",
            "timestamp": now.isoformat(),
        }
        try:
            await _insert_jurnal(jurnal)
        except Exception:
            await db.persediaan.update_one(
                {"id": item_id},
                {"$set": {"batches": batches_lama, "stok": stok_sebelum},
                 "$inc": {"version": 1}},
            )
            raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — opname dibatalkan")

        selisih = int(data.stok_fisik) - stok_sebelum
        return {"message": f"Opname tercatat (selisih {'+' if selisih > 0 else ''}{selisih})",
                "stok": int(data.stok_fisik), "transaksi": jurnal,
                "version": updated.get("version")}

    raise HTTPException(status_code=409,
                        detail="Barang sedang diubah pengguna lain — coba lagi")


@persediaan_router.get("/persediaan/{item_id}/riwayat")
async def riwayat_persediaan(
    item_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_user),
):
    """Jurnal transaksi sebuah barang, terbaru dulu."""
    # Isolasi satker (REVIEW-9 R9): jurnal tak ber-kode satker, jadi guard
    # lewat master barangnya — sama seperti kartu-barang-pdf & opname.
    from shared_utils import pastikan_akses_dok_satker
    item = await db.persediaan.find_one(
        {"id": item_id}, {"_id": 0, "id": 1, "kode_satker": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Barang tidak ditemukan")
    await pastikan_akses_dok_satker(_user, item)
    query = {"persediaan_id": item_id}
    total = await db.transaksi_persediaan.count_documents(query)
    cursor = (db.transaksi_persediaan.find(query, {"_id": 0})
              .sort("timestamp", -1).skip((page - 1) * page_size).limit(page_size))
    # Kode SAKTI diturunkan ulang dari `jenis` — baris lama menyimpan kode
    # warisan bermakna lain (M06/M07/M99/K07 pra-#693, "OPN" pra-P01) yang
    # tak boleh tampil ke operator; Daftar Transaksi & ekspor CSV sudah
    # menegakkan aturan yang sama.
    from persediaan_transaksi_ref import kode_sakti_dari_jenis
    items = [{**x, "kode_sakti": kode_sakti_dari_jenis(
                  x.get("jenis"), x.get("kode_sakti"))}
             async for x in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, -(-total // page_size))}


@persediaan_router.get("/persediaan/{item_id}/kartu-barang-pdf")
async def kartu_barang_pdf(item_id: str, _user: dict = Depends(require_user)):
    """Kartu Barang Persediaan — riwayat kronologis + saldo berjalan.

    Form kendali standar penatausahaan persediaan (analog kartu barang
    manual bahan ajar DJKN): identitas barang + seluruh jurnal transaksi
    terurut waktu dengan kolom masuk/keluar/sisa dan nilai. Barang tanpa
    transaksi = 404 (tanpa data dummy).
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )

    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(_user, item)
    rows = [r async for r in db.transaksi_persediaan
            .find({"persediaan_id": item_id}, {"_id": 0}).sort("timestamp", 1)]
    if not rows:
        raise HTTPException(status_code=404,
                            detail="Belum ada transaksi untuk barang ini")

    # Label diturunkan dari registry LENGKAP 45 kode (bukan dua peta arah
    # masuk/keluar saja) — tanpa ini jenis koreksi nilai (M97/M98/K97/K98)
    # dan penghapusan definitif (H01-H03) tercetak sebagai kunci mentah
    # ("hapus_usang") di dokumen resmi Kartu Barang.
    from persediaan_transaksi_ref import (
        JENIS_KE_KODE, KODE_TRANSAKSI_PERSEDIAAN,
    )
    label_jenis = {jenis: KODE_TRANSAKSI_PERSEDIAAN[kode][0]
                   for jenis, kode in JENIS_KE_KODE.items()}
    label_jenis["pindah_gudang"] = "Pindah Gudang"

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("KARTU BARANG PERSEDIAAN"))
    elements.append(Paragraph(
        f"{item.get('nama_barang') or '-'} · Kode {item.get('kode_barang') or '-'} · "
        f"NUP {item.get('nup') or '-'} · Satuan {item.get('satuan') or '-'}"
        + (f" · Lokasi {item.get('lokasi')}" if item.get("lokasi") else "")
        + f" · Stok kini {int(item.get('stok', 0) or 0)}", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Tanggal", "Uraian", "No. Bukti", "Masuk", "Keluar", "Sisa", "Nilai (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for r in rows:
        arah = r.get("arah")
        jumlah = int(r.get("jumlah", 0) or 0)
        uraian = label_jenis.get(r.get("jenis"), r.get("jenis") or "-")
        if r.get("keterangan"):
            uraian += f" — {r['keterangan']}"
        table_data.append([
            Paragraph(_fmt_tanggal_id(tanggal_wib(r.get("timestamp"))), st['CellCenter']),
            Paragraph(uraian, st['Cell']),
            Paragraph(r.get("no_bukti") or "-", st['Cell']),
            Paragraph(str(jumlah) if arah == "masuk" else "", st['CellCenter']),
            Paragraph(str(jumlah) if arah == "keluar" else "", st['CellCenter']),
            Paragraph(str(int(r.get("stok_sesudah", 0) or 0)), st['CellCenter']),
            Paragraph(_fmt_rp(r.get("total")), st['CellRight']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([62, 160, 80, 40, 40, 40, 80], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)
    elements.append(Spacer(1, 3 * rl_mm))
    elements.append(Paragraph(
        "Catatan: kolom Sisa = stok setelah transaksi (saldo berjalan dari jurnal); "
        "nilai keluar dihitung FIFO per layer.", st['Meta']))

    elements.append(Spacer(1, 12 * rl_mm))
    # Kartu Barang ditandatangani PENGURUS BARANG (bukan Kepala Satker) —
    # temuan #27: dulu keliru diisi nama kasatker. Ambil pejabat berperan
    # pengurus_barang dari registry; belum ada → garis titik (jangan fabrikasi).
    from shared_utils import resolve_pejabat_peran, kode_satker_user
    _pengurus = await resolve_pejabat_peran(
        "pengurus_barang", kode_satker=kode_satker_user(_user)) or {}
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Pengurus Barang Persediaan,',
         'nama': str(_pengurus.get("nama") or "").strip() or '...........................',
         # Non-ASN: baris NIP/NIK tidak dicetak (privasi)
         'after': baris_identitas_ttd(
             _pengurus.get("nip"), _pengurus.get("status_kepegawaian"))},
    ], doc.width))
    footer = _page_footer_factory("Kartu Barang Persediaan")
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    nama_file = (item.get("kode_barang") or item_id)[:20]
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="Kartu_Barang_{nama_file}.pdf"'})


@persediaan_router.post("/persediaan/referensi-sakti-pdf")
async def impor_referensi_sakti_pdf(
    request: Request,
    file: UploadFile = File(...),
    terapkan: bool = Query(False),
    _user: dict = Depends(require_writer_satker),
):
    """Baca PDF SAKTI "UC_PER032 — Referensi Tabel Barang Persediaan" dan
    sinkronkan master persediaan SATKER INI.

    Dua tahap dalam satu endpoint: `terapkan=false` (bawaan) hanya PRATINJAU —
    berapa baru/berubah/tetap, plus identitas UAKPB — supaya operator melihat
    dulu apa yang akan terjadi; `terapkan=true` menuliskan.

    Aturan tulis:
      - Item BARU dibuat dengan kode 16 digit APA ADANYA dari PDF — kode urut
        SAKTI adalah identitas resmi, bukan deret internal kami.
      - Item yang SUDAH ADA hanya diperbarui `nama_barang` + `satuan` — stok,
        layer FIFO, dan field lain tak disentuh.
      - Tidak ada yang DIHAPUS: laporan bisa diunduh terfilter, dan kode
        ber-transaksi memang tak boleh hilang.
    """
    from persediaan_referensi import parse_teks_uc_per032, rencana_sinkron
    from shared_utils import kode_satker_user, scope_query_field_satker

    nama = (file.filename or "").lower()
    if not nama.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Unggah berkas PDF hasil unduhan SAKTI (UC_PER032)")
    isi = await file.read()
    if len(isi) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF terlalu besar (maks 20 MB)")

    def _ekstrak(data: bytes) -> str:
        import io as _io
        from pypdf import PdfReader
        r = PdfReader(_io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in r.pages)

    try:
        teks = await asyncio.to_thread(_ekstrak, isi)
    except Exception:
        raise HTTPException(status_code=400, detail="PDF tidak dapat dibaca — pastikan ini unduhan asli SAKTI, bukan hasil scan")

    hasil = parse_teks_uc_per032(teks)
    if not hasil["items"]:
        raise HTTPException(status_code=400, detail=(
            "Tidak ada baris referensi barang yang terbaca. Pastikan berkasnya "
            "laporan 'Referensi Tabel Barang Persediaan' (UC_PER032) dari SAKTI."))

    # PDF milik satker lain DITOLAK: referensi ini per satker, dan menimpanya
    # dengan daftar satker sebelah merusak dua-duanya sekaligus.
    satker_user = kode_satker_user(_user)
    satker_pdf = hasil["kode_satker"]
    if satker_user and satker_pdf and satker_user != satker_pdf:
        raise HTTPException(status_code=400, detail=(
            f"PDF ini milik satker {satker_pdf} ({hasil['uakpb_nama'] or 'UAKPB tak terbaca'}), "
            f"sedangkan Anda bekerja atas satker {satker_user}. Unduh UC_PER032 dari SAKTI satker Anda."))

    # Satker EFEKTIF yang disinkronkan. Operator satker-tunggal: satkernya
    # sendiri. Super-admin (lintas-satker, satker_user kosong): satker yang
    # TERTULIS di PDF — tanpa ini `scope_query_field_satker("")` melebar ke
    # SEMUA satker, sehingga terapkan me-rename master ber-kode16 sama di
    # setiap satker sekaligus DAN item baru lahir tanpa stempel satker
    # (`kode_satker=""`, bocor ke semua). Bila PDF pun tak menyebut satker,
    # tak ada tujuan yang aman → tolak.
    kode_efektif = satker_user or satker_pdf
    if not kode_efektif:
        raise HTTPException(status_code=400, detail=(
            "Kode satker tidak terbaca dari PDF dan akun Anda tidak terikat "
            "satker tertentu — buka UC_PER032 milik satu satker yang jelas."))
    q_satker = {"kode_satker": {"$in": [kode_efektif, "", None]}} if kode_efektif else {}

    # Keadaan sekarang milik satker ini, dipetakan per kode 16 digit. NUP tak
    # dilibatkan: referensi SAKTI berbicara pada tingkat kode, bukan NUP.
    existing = {}
    id_per_kode = {}
    async for d in db.persediaan.find(
            {**q_satker, "kode_barang": {"$regex": "^\\d{16}$"}},
            {"_id": 0, "id": 1, "kode_barang": 1, "nama_barang": 1, "satuan": 1}):
        k = d.get("kode_barang")
        if k and k not in existing:   # NUP>1 berbagi kode — cukup satu wakil
            existing[k] = {"deskripsi": d.get("nama_barang"), "satuan": d.get("satuan")}
        id_per_kode.setdefault(k, []).append(d.get("id"))

    rencana = rencana_sinkron(hasil["items"], existing)
    ringkas = {
        "uakpb_nama": hasil["uakpb_nama"],
        "uakpb_kode": hasil["uakpb_kode"],
        "kode_satker_pdf": satker_pdf,
        "total_di_pdf": len(hasil["items"]),
        "baru": len(rencana["baru"]),
        "berubah": len(rencana["ubah"]),
        "tetap": len(rencana["tetap"]),
        "hilang_dari_pdf": len(rencana["hilang_dari_pdf"]),
        "baris_tak_terbaca": hasil["galat"][:10],
        "contoh_baru": [
            {"kode16": i["kode16"], "deskripsi": i["deskripsi"], "satuan": i["satuan"]}
            for i in rencana["baru"][:8]
        ],
        "contoh_berubah": [
            {"kode16": i["kode16"], "deskripsi": i["deskripsi"], "satuan": i["satuan"],
             "sebelumnya": existing.get(i["kode16"]) or {}}
            for i in rencana["ubah"][:8]
        ],
    }
    if not terapkan:
        return {"pratinjau": True, **ringkas}

    now = datetime.now(timezone.utc).isoformat()
    dibuat = 0
    for it in rencana["baru"]:
        doc = {
            "id": str(uuid.uuid4()),
            "kode_barang": it["kode16"],
            "kode_satker": kode_efektif,
            "nup": "1",
            "nup_num": 1,
            "nama_barang": it["deskripsi"],
            "merk": "", "tipe": "",
            "satuan": it["satuan"] or "Buah",
            "lokasi": "", "batas_kritis": 0, "expired_default": "",
            "tahun_anggaran": "",
            "keterangan": "Impor referensi SAKTI (UC_PER032)",
            "stok": 0, "batches": [],
            "version": 1, "created_at": now, "updated_at": now,
        }
        await db.persediaan.insert_one({**doc})
        jadwalkan_sync("persediaan", doc)
        dibuat += 1

    diubah = 0
    for it in rencana["ubah"]:
        for pid in id_per_kode.get(it["kode16"], []):
            await db.persediaan.update_one(
                {"id": pid},
                {"$set": {"nama_barang": it["deskripsi"],
                          "satuan": it["satuan"] or "Buah",
                          "updated_at": now}})
            diubah += 1
    if diubah:
        # Nama berubah → indeks pencarian ikut disegarkan.
        async for d in db.persediaan.find(
                {"id": {"$in": [pid for it in rencana["ubah"] for pid in id_per_kode.get(it["kode16"], [])]}},
                {"_id": 0}):
            jadwalkan_sync("persediaan", d)

    # (Argumen sebelumnya salah posisi — `request`/`_user` dioper ke slot
    # action/activity_id, sehingga audit tak pernah tercatat dan pelakunya
    # tak terlihat. Signature: log_audit(action, activity_id, ...).)
    await log_audit("persediaan_impor_referensi_sakti", "",
                    username=_user.get("username", "system"),
                    kode_satker=kode_efektif,
                    detail=f"UAKPB {hasil['uakpb_kode']}: {dibuat} baru, {diubah} diperbarui "
                           f"dari {len(hasil['items'])} baris PDF")
    return {"pratinjau": False, **ringkas, "dibuat": dibuat, "diperbarui": diubah}


@persediaan_router.delete("/persediaan/{item_id}")
async def delete_persediaan(item_id: str, _admin: dict = Depends(require_admin)):
    """Hapus master — hanya bila stok 0 & tanpa layer (jejak transaksi aman)."""
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0, "stok": 1, "batches": 1, "kode_satker": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    from shared_utils import pastikan_akses_dok_satker
    await pastikan_akses_dok_satker(_admin, item)
    if int(item.get("stok", 0) or 0) > 0 or (item.get("batches") or []):
        raise HTTPException(status_code=409,
                            detail="Barang masih punya stok/layer — keluarkan stoknya dulu lewat transaksi")
    # Kode yang PERNAH bertransaksi tak boleh hilang walau stoknya sudah nol:
    # jurnal, LPB, dan dokumen pengadaan menunjuk kode ini — menghapusnya
    # memutus jejak audit. Keputusan pemilik: kode ber-transaksi hanya boleh
    # diubah nama & satuannya, tidak dihapus.
    ada_jurnal = await db.transaksi_persediaan.find_one(
        {"persediaan_id": item_id}, {"_id": 1})
    if ada_jurnal:
        raise HTTPException(status_code=409, detail=(
            "Kode ini punya riwayat transaksi — tidak bisa dihapus agar jejak "
            "audit utuh. Yang masih boleh: mengubah nama barang dan satuannya."))
    await db.persediaan.delete_one({"id": item_id})
    jadwalkan_hapus("persediaan", item_id)  # cabut dari indeks Meili (best-effort)
    return {"message": "Barang persediaan dihapus"}
