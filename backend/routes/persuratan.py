"""PERSURATAN — buku agenda & penomoran naskah dinas lintas modul (pustaka §12).

Mengakomodir SEMUA jenis laporan/naskah yang terbit dari modul mana pun
(inventarisasi, pelaporan, penggunaan, dst.) dan kegiatan mana pun:

- **Surat keluar**: nomor DIBOOKING saat draf dibuat (atomik per PERIODE —
  dua pemanggil tak pernah dapat nomor sama), lalu **disahkan** setelah
  surat final ditandatangani atau **dibatalkan** (nomor hangus, tidak
  didaur ulang — celah nomor tetap dapat dijelaskan, kaidah kearsipan).
  Susunan nomor mengikuti PerANRI 5/2021 dan dapat diatur. Periode deret
  mengikuti setelan satker: BULANAN (bawaan — kembali ke 001 tiap awal
  bulan) atau TAHUNAN (satu tahun takwim).
- **Nomor sisipan (backdate)**: surat yang lupa dibooking diberi nomor
  menempel di belakang nomor terakhir pada tanggal backdate-nya
  (005 → 005.01) — urutan agenda tetap kronologis tanpa menomori ulang.
- **Surat masuk**: agenda kembar — nomor agenda sendiri per periode,
  status diterima → diproses → selesai.

Logika murni (format nomor, validasi, transisi, baris agenda) di
persuratan_utils.py — teruji unit.
"""
import csv as csv_module
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from pymongo import ReturnDocument

from auth_utils import require_admin, require_user, require_writer
from db import db
from shared_utils import (log_audit, kode_satker_user,
                          pastikan_akses_dok_satker, scope_query_field_satker)
from meili_utils import jadwalkan_sync, jadwalkan_hapus, cari_id_surat
from pencarian_utils import klausa_teks
from persuratan_utils import (
    FORMAT_NOMOR_DEFAULT, JENIS_NASKAH, KODE_KEAMANAN, MODUL_AMAN,
    RESET_URUT, RESET_URUT_DEFAULT,
    STATUS_KELUAR, STATUS_MASUK, TRANSISI_KELUAR, TRANSISI_MASUK,
    bangun_nomor, baris_agenda_csv, gabung_klasifikasi, periode_urut,
    pilih_klasifikasi, placeholder_tak_dikenal, sumber_pengaturan,
    urut_tampil, validate_format_reset, validate_peta_klasifikasi,
    validate_surat_keluar, validate_surat_masuk, validate_transisi,
)
from surat_relasi_utils import (
    JENIS_RELASI, STATUS_KEBERLAKUAN, baris_timeline, status_keberlakuan,
    validate_relasi,
)

persuratan_router = APIRouter()

_PROJ = {"_id": 0}


class SuratKeluarIn(BaseModel):
    perihal: str
    tujuan: Optional[str] = ""
    jenis_naskah: Optional[str] = "Laporan"
    modul: Optional[str] = "umum"
    kegiatan_id: Optional[str] = ""
    kode_klasifikasi: Optional[str] = ""
    kode_keamanan: Optional[str] = "B"
    tanggal_surat: Optional[str] = ""   # default: hari ini (UTC date)
    referensi: Optional[str] = ""       # mis. "BAHI", "LHI", "LBKP S1 2026"
    # Anchor nomor SAH dari sistem lain (Srikandi/e-office instansi dsb.)
    # bila penomoran resmi tidak dari AMAN — nomor internal tetap dibooking
    # sebagai nomor agenda, nomor eksternal jadi rujukan silang.
    nomor_eksternal: Optional[str] = ""
    keterangan: Optional[str] = ""
    # Nomor SISIPAN (backdate): surat yang lupa dibooking — nomor menempel
    # di belakang nomor terakhir pada `tanggal_surat` (005 → 005.01), bukan
    # mengambil nomor berikutnya (yang akan membuat agenda mundur tanggal).
    sisipan: Optional[bool] = False


class SuratMasukIn(BaseModel):
    nomor_surat: str
    pengirim: str
    perihal: str
    tanggal_surat: Optional[str] = ""
    modul: Optional[str] = "umum"
    kegiatan_id: Optional[str] = ""
    keterangan: Optional[str] = ""


class TransisiIn(BaseModel):
    status: str
    alasan: Optional[str] = ""


class UbahSuratIn(BaseModel):
    perihal: Optional[str] = None
    tujuan: Optional[str] = None
    pengirim: Optional[str] = None
    # Hanya untuk surat MASUK: nomor surat dari pengirim boleh dikoreksi.
    nomor_surat: Optional[str] = None
    jenis_naskah: Optional[str] = None
    modul: Optional[str] = None
    kegiatan_id: Optional[str] = None
    kode_klasifikasi: Optional[str] = None
    tanggal_surat: Optional[str] = None
    referensi: Optional[str] = None
    nomor_eksternal: Optional[str] = None
    keterangan: Optional[str] = None


class PengaturanIn(BaseModel):
    format_nomor: Optional[str] = None
    kode_unit: Optional[str] = None
    kode_klasifikasi_default: Optional[str] = None
    # "bulanan" (bawaan — kembali ke 001 tiap awal bulan) / "tahunan".
    reset_urut: Optional[str] = None
    # Aturan klasifikasi otomatis: [{modul, jenis_naskah, kode}] — field
    # kosong = wildcard; aturan paling spesifik menang (pilih_klasifikasi).
    peta_klasifikasi: Optional[list] = None


class KlasifikasiIn(BaseModel):
    kode: str
    uraian: Optional[str] = ""
    aktif: Optional[bool] = True


class RelasiIn(BaseModel):
    ke_id: str            # surat SASARAN (yang dicabut/diubah/dst.)
    jenis: str            # kunci JENIS_RELASI (arah selalu aktif→pasif)
    catatan: Optional[str] = ""


async def _pengaturan(kode_satker: str = "") -> dict:
    """Setelan penomoran EFEKTIF: dokumen global di-overlay setelan SATKER.

    ISOLASI SATKER (REVIEW-9 R9): dulu hanya ada satu dokumen `{"type":
    "global"}` yang boleh ditulis admin satker mana pun — mengubah kode_unit /
    format nomor / peta klasifikasi satu satker langsung mengubah nomor resmi
    SEMUA satker. Kini tiap satker punya dokumennya sendiri (`type="satker"`),
    dan global tinggal menjadi default bagi field yang belum diisi satker.
    `kode_unit` khususnya melekat pada unit (PerANRI 5/2021), bukan instansi.
    """
    s = await db.persuratan_settings.find_one({"type": "global"}, _PROJ) or {}
    kode = str(kode_satker or "").strip()
    if kode:
        khusus = await db.persuratan_settings.find_one(
            {"type": "satker", "kode_satker": kode}, _PROJ) or {}
        # Field non-kosong milik satker menimpa global (pola gabung_kop).
        s = {**s, **{k: v for k, v in khusus.items() if v not in ("", None, [])}}
    return {
        "format_nomor": s.get("format_nomor") or FORMAT_NOMOR_DEFAULT,
        "kode_unit": s.get("kode_unit") or "",
        "kode_klasifikasi_default": s.get("kode_klasifikasi_default") or "",
        "peta_klasifikasi": s.get("peta_klasifikasi") or [],
        # Bawaan BULANAN (permintaan lapangan): nomor kembali ke 001 tiap
        # pergantian bulan. Satker yang mengikuti PerANRI apa adanya memilih
        # "tahunan" di pengaturan.
        "reset_urut": s.get("reset_urut") or RESET_URUT_DEFAULT,
    }


def _periode(atur: dict, tanggal_iso: str) -> str:
    """Kunci periode deret nomor menurut setelan satker ('2026'/'2026-08')."""
    return periode_urut((atur or {}).get("reset_urut"), tanggal_iso)


def _cid_agenda(jenis: str, periode: str, kode: str) -> str:
    """Id dokumen counter agenda per PERIODE ('2026' tahunan / '2026-08'
    bulanan). Untuk periode tahunan id-nya identik dengan id era-lama
    (`surat_keluar_2026[...]`) sehingga deret lama menyambung tanpa lompatan;
    `kode` kosong (super-admin / era lama) memakai id tanpa akhiran satker."""
    base = f"surat_{jenis}_{periode}"
    return f"{base}:{kode}" if kode else base


def _ids_counter_tahunan(jenis: str, tahun: int, kode: str) -> list:
    """Id counter TAHUNAN yang relevan bagi sebuah satker (global + miliknya)."""
    ids = [f"surat_{jenis}_{tahun}"]
    if kode:
        ids.append(f"surat_{jenis}_{tahun}:{kode}")
    return ids


async def _seed_agenda(jenis: str, periode: str, kode: str) -> int:
    """Nilai awal counter agenda saat dokumen counternya belum ada.

    Dipakai BERSAMA oleh `_no_agenda_berikut` (yang benar-benar memesan nomor)
    dan `pratinjau_nomor` (yang hanya menghitung) — bila hanya salah satu tahu
    cara seed-nya, pratinjau menampilkan nomor 1 yang sudah terpakai. Fungsi
    ini MEMBACA saja (pratinjau tak boleh memutasi apa pun); penandaan
    migrasi counter tahunan dilakukan `_no_agenda_berikut` SETELAH counter
    barunya benar-benar tercipta.

    Dua lapis sumber, keduanya diambil MAKS-nya:

    (a) **Counter lama yang belum dimigrasi** — periode tahunan membaca
        counter global era-lama (stempel satker ditambahkan belakangan tanpa
        backfill; tanpa lantai ini nomor 1,2,3… terbit ULANG dan bentrok
        dengan surat yang sudah beredar). Periode BULANAN membaca counter
        TAHUNAN (global + milik satker) yang belum bertanda
        `dimigrasi_bulanan`: bulan transisi meneruskan posisi deret tahunan
        supaya nomor yang sudah hangus (dokumen terhapus) tidak terbit ulang.
        Setelah ditandai, bulan-bulan berikutnya TIDAK ikut dilantai — kalau
        ikut, deret tak pernah kembali ke 001.
    (b) **no_agenda tertinggi dokumen periode ini** milik satker (termasuk
        surat era-lama tanpa stempel — konvensi lama menganggapnya miliknya).
        Periode bulanan menyaring per bulan: surat KELUAR menurut tanggal
        suratnya (bulan itulah yang tercetak di nomor), surat MASUK menurut
        tanggal agendanya (created_at — tanggal surat pengirim opsional).

    Konsekuensi seed lintas-era: ada lompatan SEKALI (satker kedua / bulan
    transisi) — jauh lebih baik daripada nomor resmi ganda.
    """
    bulanan = "-" in periode
    tahun = int(periode[:4])
    maks = 0

    async def _baca_seq(cid: str, wajib_belum_migrasi: bool) -> int:
        c = await db.counters.find_one({"_id": cid})
        if not c or (wajib_belum_migrasi and c.get("dimigrasi_bulanan")):
            return 0
        try:
            return int(c.get("seq") or 0)
        except (TypeError, ValueError):
            return 0

    if bulanan:
        for cid in _ids_counter_tahunan(jenis, tahun, kode):
            maks = max(maks, await _baca_seq(cid, wajib_belum_migrasi=True))
    else:
        maks = await _baca_seq(f"surat_{jenis}_{tahun}",
                               wajib_belum_migrasi=False)

    q = {"jenis": jenis, "tahun": tahun,
         "kode_satker": {"$in": [kode, "", None]}}
    if bulanan:
        field_tgl = "tanggal_surat" if jenis == "keluar" else "created_at"
        q[field_tgl] = {"$regex": f"^{periode}"}
    async for r in db.surat.find(q, {"_id": 0, "no_agenda": 1}):
        try:
            maks = max(maks, int(r.get("no_agenda") or 0))
        except (TypeError, ValueError):
            continue
    return maks


async def _tandai_migrasi_tahunan(jenis: str, periode: str, kode: str) -> None:
    """Tandai counter tahunan sudah dipakai sebagai lantai deret bulanan.

    Dipanggil SETELAH counter bulanan pertama tercipta (bukan di dalam seed):
    bila urutannya dibalik dan proses mati di antaranya, seed berikutnya
    kehilangan lantainya → nomor hangus bisa terbit ulang DIAM-DIAM. Dengan
    urutan ini, kegagalan di jendela sempit itu paling buruk membuat SATU
    bulan berikutnya tidak mulai dari 001 (terlihat, menjengkelkan, dan
    pulih sendiri) — bukan duplikat nomor resmi yang tak terdeteksi.
    """
    tahun = int(periode[:4])
    for cid in _ids_counter_tahunan(jenis, tahun, kode):
        await db.counters.update_one(
            {"_id": cid, "dimigrasi_bulanan": {"$exists": False}},
            {"$set": {"dimigrasi_bulanan": periode}})


async def _no_agenda_berikut(jenis: str, periode: str,
                             kode_satker: str = "") -> int:
    """Nomor agenda berikutnya (atomik — $inc pada dokumen counter).

    Deret PER SATKER (REVIEW-9 R9) dan PER PERIODE: '2026' saat setelan
    tahunan, '2026-08' saat bulanan — begitu bulan berganti, dokumen counter
    baru terbentuk dan deret kembali ke 001. Pola satu-deret-bersama lama
    membuat booking satker B menghabiskan jatah nomor satker A.
    """
    kode = str(kode_satker or "").strip()
    bulanan = "-" in periode
    cid = _cid_agenda(jenis, periode, kode)
    if (kode or bulanan) and await db.counters.find_one({"_id": cid}) is None:
        maks = await _seed_agenda(jenis, periode, kode)
        # $setOnInsert idempoten: pemanggil kedua yang balapan tak menimpa seed.
        await db.counters.update_one(
            {"_id": cid}, {"$setOnInsert": {"seq": maks}}, upsert=True)
        if bulanan:
            await _tandai_migrasi_tahunan(jenis, periode, kode)
    c = await db.counters.find_one_and_update(
        {"_id": cid},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(c["seq"])


# ── Nomor sisipan (backdate) ─────────────────────────────────────────────────

def _cid_sisipan(periode: str, kode: str, jangkar: int) -> str:
    """Id counter sub-nomor sisipan per jangkar (per periode + satker)."""
    return f"{_cid_agenda('keluar', periode, kode)}:s{int(jangkar)}"


async def _jangkar_sisipan(periode: str, kode: str, tanggal: str):
    """No. agenda TERAKHIR pada/sebelum `tanggal` di periode ini — nomor
    sisipan menempel di belakangnya (005 → 005.01). None bila belum ada
    satu pun nomor pada/sebelum tanggal itu (sisipan tak bermakna; booking
    biasa memang akan menghasilkan nomor pertama periode)."""
    q = {"jenis": "keluar", "tahun": int(periode[:4]),
         "kode_satker": {"$in": [str(kode or ""), "", None]},
         # ISO YYYY-MM-DD urut leksikografis = urut kronologis; "$gt": ""
         # menyaring dokumen tanpa tanggal (tak bisa jadi jangkar).
         "tanggal_surat": {"$gt": "", "$lte": str(tanggal)[:10]}}
    if "-" in periode:
        q["tanggal_surat"]["$gte"] = periode  # batas awal bulan periode
    maks = None
    async for r in db.surat.find(q, {"_id": 0, "no_agenda": 1}):
        try:
            v = int(r.get("no_agenda") or 0)
        except (TypeError, ValueError):
            continue
        maks = v if maks is None else max(maks, v)
    return maks


async def _sisipan_berikut(periode: str, kode: str, jangkar: int) -> int:
    """Sub-nomor sisipan berikutnya untuk satu jangkar (atomik).

    005.01 sudah terpakai → 005.02, dst. Counter di-seed dari dokumen yang
    ada (pemulihan backup tanpa koleksi counters tak melahirkan duplikat).
    """
    kode = str(kode or "").strip()
    cid = _cid_sisipan(periode, kode, jangkar)
    if await db.counters.find_one({"_id": cid}) is None:
        maks = 0
        q = {"jenis": "keluar", "tahun": int(periode[:4]),
             "no_agenda": int(jangkar), "sisipan": {"$gte": 1},
             "kode_satker": {"$in": [kode, "", None]}}
        if "-" in periode:
            q["tanggal_surat"] = {"$regex": f"^{periode}"}
        async for r in db.surat.find(q, {"_id": 0, "sisipan": 1}):
            try:
                maks = max(maks, int(r.get("sisipan") or 0))
            except (TypeError, ValueError):
                continue
        await db.counters.update_one(
            {"_id": cid}, {"$setOnInsert": {"seq": maks}}, upsert=True)
    c = await db.counters.find_one_and_update(
        {"_id": cid}, {"$inc": {"seq": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER)
    return int(c["seq"])


async def booking_nomor_lpb(user, tgl_iso: str, perihal: str,
                            tujuan: str = "", keterangan: str = "",
                            kode_satker: str = "") -> tuple:
    """Pesan satu nomor surat keluar untuk Laporan Penerimaan Barang.

    → `(nomor, surat_id)`; keduanya "" bila gagal dipesan.

    DIEKSTRAK dari `transaksi_massal` persediaan supaya jalur ASET memakai
    deret nomor yang SAMA PERSIS. Dua salinan logika penomoran adalah cara
    paling pasti melahirkan dua deret yang diam-diam berbeda — dan nomor surat
    yang bercabang tak bisa diperbaiki belakangan tanpa menomori ulang arsip.

    Surat tercatat berstatus `dibooking` di buku agenda satker penerbit
    dokumen, sehingga nomor yang sudah terpakai tak pernah dipakai ulang meski
    dokumen LPB-nya nanti batal.

    `kode_satker` (opsional): satker DOKUMEN — dipakai saat pemanggil bisa
    lintas-satker (super-admin) agar nomor terbit di buku agenda satker yang
    benar, bukan deret global. Kosong → jatuh ke satker pemanggil (perilaku
    lama untuk operator satker-tunggal).
    """
    from persuratan_utils import bangun_nomor, pilih_klasifikasi
    now0 = datetime.now(timezone.utc)
    tgl_surat = str(tgl_iso or "").strip()[:10] or now0.date().isoformat()
    kode_satker = str(kode_satker or "").strip() or kode_satker_user(user)
    atur = await _pengaturan(kode_satker)
    kode_klas = pilih_klasifikasi(atur["peta_klasifikasi"], "persediaan",
                                  "Laporan",
                                  default=atur["kode_klasifikasi_default"])
    tahun = int(tgl_surat[:4]) if tgl_surat[:4].isdigit() else now0.year
    periode = (_periode(atur, tgl_surat)
               or _periode(atur, now0.date().isoformat()))
    no_agenda = await _no_agenda_berikut("keluar", periode, kode_satker)
    nomor = bangun_nomor(atur["format_nomor"], no_agenda, tgl_surat,
                         kode_klasifikasi=kode_klas,
                         kode_unit=atur["kode_unit"])
    surat_id = str(uuid.uuid4())
    await db.surat.insert_one({
        "id": surat_id, "jenis": "keluar", "no_agenda": no_agenda,
        "sisipan": 0,
        "tahun": tahun, "nomor": nomor, "status": "dibooking",
        # Stempel satker (REVIEW-9 R10): tanpa ini surat booking otomatis
        # muncul di buku agenda & arsip SEMUA satker.
        "kode_satker": kode_satker,
        "perihal": str(perihal or "Laporan Penerimaan Barang (LPB)")[:300],
        "tujuan": str(tujuan or "").strip(),
        "jenis_naskah": "Laporan", "modul": "persediaan",
        "kegiatan_id": "", "nama_kegiatan": "",
        "kode_klasifikasi": kode_klas, "kode_keamanan": "B",
        "tanggal_surat": tgl_surat, "referensi": "LPB",
        "nomor_eksternal": "",
        "keterangan": str(keterangan or "booking otomatis dari LPB")[:300],
        "dibuat_oleh": user.get("username", "system"),
        "riwayat": [{"status": "dibooking", "tanggal": now0.isoformat(),
                     "oleh": user.get("username", "system"),
                     "catatan": "booking otomatis dari LPB"}],
        "created_at": now0.isoformat(), "updated_at": now0.isoformat(),
    })
    return nomor, surat_id


async def _nama_kegiatan(kegiatan_id: str) -> str:
    if not str(kegiatan_id or "").strip():
        return ""
    act = await db.inventory_activities.find_one(
        {"id": kegiatan_id}, {"_id": 0, "nama_kegiatan": 1})
    if not act:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    return act.get("nama_kegiatan") or ""


@persuratan_router.get("/persuratan/referensi")
async def referensi_persuratan(_user: dict = Depends(require_user)):
    """Pilihan dropdown + pengaturan aktif (untuk form UI)."""
    return {
        "jenis_naskah": list(JENIS_NASKAH),
        "modul": list(MODUL_AMAN),
        "kode_keamanan": [{"kode": k, "uraian": v} for k, v in KODE_KEAMANAN.items()],
        "status_keluar": [{"kode": k, "uraian": v} for k, v in STATUS_KELUAR.items()],
        "status_masuk": [{"kode": k, "uraian": v} for k, v in STATUS_MASUK.items()],
        "reset_urut": [{"kode": k, "uraian": v} for k, v in RESET_URUT.items()],
        "transisi_keluar": {k: sorted(v) for k, v in TRANSISI_KELUAR.items()},
        "transisi_masuk": {k: sorted(v) for k, v in TRANSISI_MASUK.items()},
        "jenis_relasi": [{"kode": k, **v} for k, v in JENIS_RELASI.items()],
        "status_keberlakuan": dict(STATUS_KEBERLAKUAN),
        "pengaturan": await _pengaturan(kode_satker_user(_user)),
        # Daftar klasifikasi EFEKTIF pemanggil: Bersama di-overlay entri
        # satkernya (kode senama → entri satker menang), hanya yang aktif.
        "klasifikasi": [k for k in gabung_klasifikasi(
            *_pisah_klas(await _klas_terlihat(kode_satker_user(_user)),
                         kode_satker_user(_user)))
            if k.get("aktif") is not False],
    }


# ── Master kode klasifikasi arsip (dinamis, admin mengelola) ──
#
# PER-SATKER (mandat SURAT-3A): tiap satker punya pedoman klasifikasi
# arsipnya sendiri. Entri ber-kode_satker "" = BERSAMA (warisan/dikelola
# super-admin, tampil untuk semua); entri ber-kode_satker = milik satker itu
# dan MENIMPA entri Bersama berkode sama pada daftar efektif (pola overlay
# yang sama dengan `_pengaturan`). Data lama tanpa kode_satker otomatis
# terbaca sebagai Bersama — tidak butuh migrasi.


def _scope_klas(doc) -> str:
    return str((doc or {}).get("kode_satker") or "").strip()


async def _klas_terlihat(kode_satker: str) -> list:
    """Entri yang TERLIHAT satu pemanggil: Bersama + milik satkernya.
    Pemanggil lintas-satker (kode kosong) melihat semuanya (pengelolaan)."""
    q = ({} if not kode_satker
         else {"$or": [{"kode_satker": {"$in": ["", None]}},
                       {"kode_satker": kode_satker}]})
    return await db.klasifikasi_arsip.find(q, _PROJ).sort("kode", 1).to_list(2000)


def _pisah_klas(items: list, kode_satker: str) -> tuple:
    """(milik_bersama, milik_satker) dari daftar entri terlihat."""
    bersama = [k for k in items if not _scope_klas(k)]
    satker = [k for k in items if kode_satker and _scope_klas(k) == kode_satker]
    return bersama, satker


async def _klas_dipakai(kode: str, scope: str) -> int:
    """Berapa aturan pemetaan yang RESOLUSINYA jatuh ke entri (kode, scope).

    Presisi per-scope supaya satker A tetap boleh menghapus kodenya sendiri
    meski satker B memakai kode senama (referensi B jatuh ke entri B/Bersama):
    - entri SATKER hanya dirujuk oleh peta pengaturan satker itu sendiri;
    - entri BERSAMA dirujuk oleh peta global DAN peta satker mana pun yang
      TIDAK punya entri sendiri berkode sama (overlay belum menimpanya).
    """
    async def _n_rujukan(st_doc) -> int:
        return sum(1 for a in (st_doc.get("peta_klasifikasi") or [])
                   if str((a or {}).get("kode") or "").strip() == kode)

    n = 0
    if scope:
        st = await db.persuratan_settings.find_one(
            {"type": "satker", "kode_satker": scope},
            {"_id": 0, "peta_klasifikasi": 1}) or {}
        return await _n_rujukan(st)
    g = await db.persuratan_settings.find_one(
        {"type": "global"}, {"_id": 0, "peta_klasifikasi": 1}) or {}
    n += await _n_rujukan(g)
    async for st in db.persuratan_settings.find(
            {"type": "satker"},
            {"_id": 0, "kode_satker": 1, "peta_klasifikasi": 1}):
        ks = str(st.get("kode_satker") or "").strip()
        punya_sendiri = ks and await db.klasifikasi_arsip.find_one(
            {"kode": kode, "kode_satker": ks}, {"_id": 1})
        if not punya_sendiri:
            n += await _n_rujukan(st)
    return n


@persuratan_router.get("/persuratan/klasifikasi")
async def daftar_klasifikasi(_user: dict = Depends(require_user)):
    """Master kode klasifikasi arsip yang terlihat pemanggil (termasuk
    nonaktif): entri Bersama + entri satkernya; lintas-satker melihat semua.
    Tiap entri membawa `kode_satker` ('' = Bersama) untuk badge scope UI."""
    items = await _klas_terlihat(kode_satker_user(_user))
    return {"items": items, "jumlah": len(items)}


@persuratan_router.post("/persuratan/klasifikasi")
async def tambah_klasifikasi(payload: KlasifikasiIn,
                             user: dict = Depends(require_admin)):
    """Tambah kode klasifikasi arsip — tersimpan pada scope penulis:
    admin satker → milik satkernya; super-admin (lintas) → Bersama."""
    kode = payload.kode.strip()
    if not kode:
        raise HTTPException(status_code=400, detail="Kode klasifikasi wajib diisi")
    _ks = kode_satker_user(user)
    # Keunikan per SCOPE penulis: Bersama unik antar sesama Bersama, entri
    # satker unik antar entri satker itu. Kode satker yang senama dengan
    # entri Bersama justru SAH — itulah override pedoman: daftar efektif
    # (gabung_klasifikasi) menampilkan versi satker menggantikan Bersama.
    q_bentrok = {"kode": kode,
                 "kode_satker": ({"$in": ["", None]} if not _ks else _ks)}
    if await db.klasifikasi_arsip.find_one(q_bentrok, _PROJ):
        raise HTTPException(status_code=409, detail=f"Kode {kode} sudah terdaftar")
    doc = {"id": str(uuid.uuid4()), "kode": kode,
           "uraian": str(payload.uraian or "").strip(),
           "aktif": payload.aktif is not False,
           "kode_satker": _ks,
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.klasifikasi_arsip.insert_one({**doc})
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Tambah kode klasifikasi {kode} ({_ks or 'Bersama'})")
    return doc


def _pastikan_milik_scope(user, doc) -> None:
    """Admin satker hanya mengelola entri satkernya; entri Bersama milik
    super-admin. (Super-admin lintas boleh menyentuh semuanya.)"""
    _ks = kode_satker_user(user)
    if _ks and _scope_klas(doc) != _ks:
        raise HTTPException(status_code=403, detail=(
            "Entri ini milik "
            + (f"satker {_scope_klas(doc)}" if _scope_klas(doc) else "Bersama")
            + " — hanya dapat dikelola pemiliknya/super-admin"))


@persuratan_router.put("/persuratan/klasifikasi/{klas_id}")
async def ubah_klasifikasi(klas_id: str, payload: KlasifikasiIn,
                           user: dict = Depends(require_admin)):
    """Ubah kode klasifikasi arsip (admin — sebatas scope miliknya)."""
    kode = payload.kode.strip()
    if not kode:
        raise HTTPException(status_code=400, detail="Kode klasifikasi wajib diisi")
    lama = await db.klasifikasi_arsip.find_one({"id": klas_id}, _PROJ)
    if not lama:
        raise HTTPException(status_code=404, detail="Kode klasifikasi tidak ditemukan")
    _pastikan_milik_scope(user, lama)
    scope = _scope_klas(lama)
    # Keunikan dinilai pada scope ENTRI (bukan scope penulis — super-admin
    # yang mengubah entri satker tetap diuji terhadap himpunan satker itu).
    q_bentrok = {"kode": kode, "id": {"$ne": klas_id},
                 "kode_satker": ({"$in": ["", None]} if not scope else scope)}
    if await db.klasifikasi_arsip.find_one(q_bentrok, _PROJ):
        raise HTTPException(status_code=409, detail=f"Kode {kode} sudah terdaftar")
    # Guard "masih dipakai" saat GANTI kode (audit P4 #14) — presisi per scope
    # (lihat _klas_dipakai): aturan pemetaan yang resolusinya jatuh ke entri
    # ini akan kehilangan klasifikasinya bila kodenya berganti.
    if lama.get("kode") != kode:
        _dipakai_n = await _klas_dipakai(lama.get("kode"), scope)
        if _dipakai_n:
            raise HTTPException(status_code=409, detail=(
                f"Kode {lama.get('kode')} masih dipakai {_dipakai_n} aturan "
                "pemetaan — ubah aturannya dulu sebelum mengganti kodenya"))
    res = await db.klasifikasi_arsip.find_one_and_update(
        {"id": klas_id},
        {"$set": {"kode": kode, "uraian": str(payload.uraian or "").strip(),
                  "aktif": payload.aktif is not False}},
        return_document=ReturnDocument.AFTER)
    # (tanpa kwarg projection — mongomock_motor mengembalikan None bila diberi
    # projection padahal update-nya terterap; _id dibuang manual)
    if res is not None:
        res.pop("_id", None)
    if res is None:
        raise HTTPException(status_code=404, detail="Kode klasifikasi tidak ditemukan")
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Ubah kode klasifikasi {kode} ({scope or 'Bersama'})")
    return res


@persuratan_router.delete("/persuratan/klasifikasi/{klas_id}")
async def hapus_klasifikasi(klas_id: str, user: dict = Depends(require_admin)):
    """Hapus kode klasifikasi (sebatas scope miliknya). Ditolak bila masih
    dipakai aturan pemetaan yang resolusinya jatuh ke entri ini (#34) —
    presisi per scope: kode senama milik satker LAIN tidak menghalangi."""
    k = await db.klasifikasi_arsip.find_one({"id": klas_id}, _PROJ)
    if not k:
        raise HTTPException(status_code=404, detail="Kode klasifikasi tidak ditemukan")
    _pastikan_milik_scope(user, k)
    _dipakai_n = await _klas_dipakai(k["kode"], _scope_klas(k))
    if _dipakai_n:
        raise HTTPException(status_code=409, detail=(
            f"Kode {k['kode']} masih dipakai {_dipakai_n} aturan pemetaan — "
            "hapus/ubah aturannya dulu"))
    await db.klasifikasi_arsip.delete_one({"id": klas_id})
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Hapus kode klasifikasi {k['kode']} "
                           f"({_scope_klas(k) or 'Bersama'})")
    return {"ok": True, "id": klas_id}


@persuratan_router.get("/persuratan/pratinjau-nomor")
async def pratinjau_nomor(jenis_naskah: str = "", modul: str = "",
                          kode_klasifikasi: str = "", kode_keamanan: str = "B",
                          tanggal_surat: str = "", sisipan: bool = False,
                          _user: dict = Depends(require_user)):
    """Pratinjau nomor yang AKAN terbit (tanpa memesan — counter tidak naik).

    Perkiraan: bila ada booking lain sebelum Anda menekan simpan, nomor
    final bisa bergeser maju — keunikan tetap dijamin counter atomik.
    `sisipan=true` memperkirakan nomor sisipan backdate (005.01) untuk
    `tanggal_surat`; bila belum ada jangkarnya, `sisipan_galat` menjelaskan.
    """
    _ks = kode_satker_user(_user)
    atur = await _pengaturan(_ks)
    now = datetime.now(timezone.utc)
    tanggal = str(tanggal_surat or "").strip()[:10] or now.date().isoformat()
    periode = _periode(atur, tanggal) or _periode(atur, now.date().isoformat())
    kode = pilih_klasifikasi(atur["peta_klasifikasi"], modul, jenis_naskah,
                             eksplisit=kode_klasifikasi,
                             default=atur["kode_klasifikasi_default"])
    sumber = ("eksplisit" if str(kode_klasifikasi or "").strip()
              else ("pemetaan" if kode and kode != atur["kode_klasifikasi_default"]
                    else ("bawaan" if kode else "kosong")))

    if sisipan:
        # Perkiraan nomor sisipan: jangkar + sub berikutnya, TANPA memutasi.
        galat = ""
        if not str(tanggal_surat or "").strip():
            galat = "Pilih Tanggal Surat (tanggal backdate) dulu"
        elif tanggal > now.date().isoformat():
            galat = "Tanggal nomor sisipan tidak boleh di masa depan"
        jangkar = (None if galat
                   else await _jangkar_sisipan(periode, _ks, tanggal))
        if not galat and jangkar is None:
            galat = ("Belum ada nomor pada/sebelum tanggal itu di periode "
                     "ini — gunakan booking biasa")
        if galat:
            return {"nomor": "", "urut_berikut": "", "kode_klasifikasi": kode,
                    "sumber_klasifikasi": sumber, "sisipan_galat": galat}
        c = await db.counters.find_one(
            {"_id": _cid_sisipan(periode, _ks, jangkar)})
        try:
            sub = int((c or {}).get("seq") or 0) + 1
        except (TypeError, ValueError):
            sub = 1
        urut = urut_tampil(jangkar, sub)
        nomor = bangun_nomor(atur["format_nomor"], urut, tanggal,
                             kode_klasifikasi=kode, kode_unit=atur["kode_unit"],
                             kode_keamanan=kode_keamanan)
        return {"nomor": nomor, "urut_berikut": urut, "kode_klasifikasi": kode,
                "sumber_klasifikasi": sumber}

    # Pakai jalur seed yang SAMA dengan _no_agenda_berikut (REVIEW-9 R11):
    # sebelum counter per-satker/periode terbentuk, membaca counter kosong
    # menghasilkan "1" — nomor yang justru sudah terpakai. Pratinjau harus
    # memperkirakan nomor yang benar-benar akan terbit.
    _cid = _cid_agenda("keluar", periode, _ks)
    c = await db.counters.find_one({"_id": _cid})
    if c is None and (_ks or "-" in periode):
        posisi = await _seed_agenda("keluar", periode, _ks)
    else:
        try:
            posisi = int((c or {}).get("seq") or 0)
        except (TypeError, ValueError):
            posisi = 0
    urut_berikut = posisi + 1
    nomor = bangun_nomor(atur["format_nomor"], urut_berikut, tanggal,
                         kode_klasifikasi=kode, kode_unit=atur["kode_unit"],
                         kode_keamanan=kode_keamanan)
    return {"nomor": nomor, "urut_berikut": urut_berikut,
            "kode_klasifikasi": kode, "sumber_klasifikasi": sumber}


@persuratan_router.get("/persuratan/pengaturan")
async def get_pengaturan_persuratan(_user: dict = Depends(require_user)):
    """Setelan penomoran EFEKTIF pemanggil + metadata scope untuk UI:
    `scope` = kode satker yang sedang diatur ('' = Universal), `sumber` =
    per field dari mana nilai efektifnya berasal (satker/global/bawaan) —
    admin satker jadi tahu field mana warisan Universal dan mana khusus
    satkernya."""
    _ks = kode_satker_user(_user)
    efektif = await _pengaturan(_ks)
    g = await db.persuratan_settings.find_one({"type": "global"}, _PROJ) or {}
    s = ({} if not _ks else await db.persuratan_settings.find_one(
        {"type": "satker", "kode_satker": _ks}, _PROJ) or {})
    return {**efektif, "scope": _ks, "sumber": sumber_pengaturan(g, s)}


@persuratan_router.post("/persuratan/pengaturan")
async def set_pengaturan_persuratan(payload: PengaturanIn,
                                    user: dict = Depends(require_admin)):
    """Atur format nomor & kode unit (admin). Placeholder divalidasi.

    Pada scope SATKER, nilai kosong ('') berarti "kembali ikut Universal" —
    overlay `_pengaturan` melewatkan field kosong sehingga default Universal
    kembali berlaku. Pada scope Universal, format kosong dikembalikan ke
    format bawaan (tak ada lapisan lain untuk diikuti)."""
    _ks = kode_satker_user(user)
    mentah = {k: v for k, v in payload.model_dump().items() if v is not None}
    update = {k: v.strip() for k, v in mentah.items() if isinstance(v, str)}
    if ("reset_urut" in update and update["reset_urut"] not in RESET_URUT
            and not (_ks and update["reset_urut"] == "")):
        raise HTTPException(status_code=400, detail=(
            f"Reset nomor tidak dikenal: {update['reset_urut']} "
            f"(pilihan: {', '.join(RESET_URUT)}"
            + ("; kosong = ikut Universal)" if _ks else ")")))
    if "peta_klasifikasi" in mentah:
        peta = [{"modul": str((a or {}).get("modul") or "").strip(),
                 "jenis_naskah": str((a or {}).get("jenis_naskah") or "").strip(),
                 "kode": str((a or {}).get("kode") or "").strip()}
                for a in mentah["peta_klasifikasi"]]
        errors = validate_peta_klasifikasi(peta)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        update["peta_klasifikasi"] = peta
    if "format_nomor" in update:
        if not update["format_nomor"] and not _ks:
            update["format_nomor"] = FORMAT_NOMOR_DEFAULT
        if update["format_nomor"]:
            asing = placeholder_tak_dikenal(update["format_nomor"])
            if asing:
                raise HTTPException(status_code=400, detail=(
                    f"Placeholder tidak dikenal: {', '.join(asing)} — yang sah: "
                    "{kode_keamanan} {urut} {kode_klasifikasi} {kode_unit} "
                    "{bulan} {bulan_romawi} {tahun}"))
            if "{urut}" not in update["format_nomor"]:
                raise HTTPException(status_code=400,
                                    detail="Format nomor wajib memuat {urut}")
    if not update:
        raise HTTPException(status_code=400, detail="Tidak ada yang diubah")
    # Keserasian reset × format dinilai atas nilai EFEKTIF setelah perubahan —
    # disimulasikan lewat jalur overlay yang sama dengan `_pengaturan`
    # (field kosong TIDAK menimpa), supaya "kembalikan ke Universal" divalidasi
    # terhadap nilai Universal yang akan benar-benar berlaku, bukan terhadap
    # string kosongnya.
    g = await db.persuratan_settings.find_one({"type": "global"}, _PROJ) or {}
    s = ({} if not _ks else await db.persuratan_settings.find_one(
        {"type": "satker", "kode_satker": _ks}, _PROJ) or {})
    if _ks:
        s = {**s, **update}
    else:
        g = {**g, **update}
    _gabung = {**g, **{k: v for k, v in s.items() if v not in ("", None, [])}}
    _pesan = validate_format_reset(
        _gabung.get("reset_urut") or RESET_URUT_DEFAULT,
        _gabung.get("format_nomor") or FORMAT_NOMOR_DEFAULT)
    if _pesan:
        raise HTTPException(status_code=400, detail=_pesan)
    # ISOLASI SATKER (REVIEW-9 R9): admin SATKER menulis dokumen satkernya
    # sendiri; hanya super-admin yang menyentuh dokumen global (default
    # bersama). Dulu semua admin menulis satu dokumen global, sehingga
    # kode_unit/format nomor satu satker mengubah nomor resmi satker lain.
    if _ks:
        kunci = {"type": "satker", "kode_satker": _ks}
        update.update(kunci)
    else:
        kunci = {"type": "global"}
        update["type"] = "global"
    await db.persuratan_settings.update_one(kunci, {"$set": update}, upsert=True)
    await log_audit("pengaturan_persuratan", "",
                    username=user.get("username", "system"),
                    detail=(f"Ubah pengaturan persuratan "
                            f"({_ks or 'global'}): "
                            f"{sorted(set(update) - {'type', 'kode_satker'})}"))
    return await _pengaturan(_ks)


@persuratan_router.get("/persuratan")
async def daftar_surat(jenis: str = "", status: str = "", modul: str = "",
                       tahun: str = "", q: str = "", page: int = 1,
                       page_size: int = 50,
                       _user: dict = Depends(require_user)):
    """Buku agenda gabungan (filter jenis/status/modul/tahun + cari)."""
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    query = {}
    if jenis in ("keluar", "masuk"):
        query["jenis"] = jenis
    if status:
        query["status"] = status
    if modul:
        query["modul"] = modul
    if tahun.strip().isdigit():
        query["tahun"] = int(tahun)
    # Pencarian teks bebas via Meilisearch bila aktif → id kandidat ter-scope;
    # fallback → regex Mongo lama. Isolasi satker tetap ditegakkan Mongo di bawah.
    meili_ids = await cari_id_surat(_user, q) if q.strip() else None
    # Hasil KOSONG dari Meili TIDAK dipercaya sebagai "memang tidak ada":
    # indeks bisa tertinggal (dokumen gagal sinkron saat Meili mati) dan
    # pencocokan berbasis kata di Meili tak mengenal kode yang diketik tanpa
    # pemisah. Nihil → jatuh ke regex Mongo yang otoritatif; biaya pindai
    # hanya muncul pada pencarian yang memang tak berhasil.
    if meili_ids is not None and not meili_ids:
        meili_ids = None
    if meili_ids is not None:
        query["id"] = {"$in": meili_ids}
    else:
        # Multi-kata: tiap kata wajib ada, boleh di field berbeda (mis.
        # "undangan rapat" di perihal, "biro umum" di tujuan).
        query.update(klausa_teks(q, ("nomor", "perihal", "tujuan", "pengirim",
                                     "referensi", "nama_kegiatan",
                                     "nomor_eksternal")))
    # ISOLASI SATKER: user terikat hanya melihat surat satkernya (+ era-lama).
    query = scope_query_field_satker(_user, query)
    total = await db.surat.count_documents(query)
    # `sisipan` ikut kunci sort: dalam no_agenda yang sama, 005.02 → 005.01 →
    # 005 (dokumen tanpa/0 sisipan) — nomor sisipan menempel pada induknya.
    items = await (db.surat.find(query, _PROJ)
                   .sort([("tahun", -1), ("no_agenda", -1), ("sisipan", -1)])
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    # Status KEBERLAKUAN terhitung per baris (satu kueri massal halaman ini):
    # badge "Tidak Berlaku" surat yang dicabut tampil tanpa diketik siapa pun.
    items = await _stempel_keberlakuan(items)
    ringkas = {
        "keluar_dibooking": await db.surat.count_documents(
            scope_query_field_satker(_user, {"jenis": "keluar", "status": "dibooking"})),
        "keluar_disahkan": await db.surat.count_documents(
            scope_query_field_satker(_user, {"jenis": "keluar", "status": "disahkan"})),
        "keluar_dibatalkan": await db.surat.count_documents(
            scope_query_field_satker(_user, {"jenis": "keluar", "status": "dibatalkan"})),
        "masuk_terbuka": await db.surat.count_documents(
            scope_query_field_satker(_user, {"jenis": "masuk", "status": {"$in": ["diterima", "diproses"]}})),
    }
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "ringkasan": ringkas}


@persuratan_router.post("/persuratan/keluar")
async def booking_surat_keluar(payload: SuratKeluarIn,
                               user: dict = Depends(require_writer)):
    """BOOKING nomor surat keluar — nomor terbit atomik, status 'dibooking'.

    Nomor tetap milik surat ini sampai disahkan/dibatalkan; pembatalan
    TIDAK mengembalikan nomor ke antrean. `sisipan=true` menerbitkan nomor
    sisipan backdate: menempel di belakang nomor terakhir pada
    `tanggal_surat` (005 → 005.01) alih-alih mengambil nomor berikutnya.
    """
    data = payload.model_dump()
    now = datetime.now(timezone.utc)
    errors = validate_surat_keluar(data, today_iso=now.date().isoformat())
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    nama_kegiatan = await _nama_kegiatan(data.get("kegiatan_id"))
    tanggal_surat = (str(data.get("tanggal_surat") or "").strip()[:10]
                     or now.date().isoformat())
    tahun = int(tanggal_surat[:4])
    _ks = kode_satker_user(user)
    atur = await _pengaturan(_ks)
    periode = (_periode(atur, tanggal_surat)
               or _periode(atur, now.date().isoformat()))
    # Klasifikasi otomatis: eksplisit → aturan pemetaan (modul/jenis naskah,
    # paling spesifik menang) → kode bawaan pengaturan.
    kode_klas = pilih_klasifikasi(
        atur["peta_klasifikasi"], data.get("modul"), data.get("jenis_naskah"),
        eksplisit=data.get("kode_klasifikasi"),
        default=atur["kode_klasifikasi_default"])
    sisip = 0
    if data.get("sisipan"):
        jangkar = await _jangkar_sisipan(periode, _ks, tanggal_surat)
        if jangkar is None:
            raise HTTPException(status_code=400, detail=(
                "Belum ada nomor surat pada/sebelum tanggal itu di periode "
                "ini — nomor sisipan tidak diperlukan; gunakan booking biasa "
                "(nomor berikutnya terbit otomatis)"))
        no_agenda = jangkar
        sisip = await _sisipan_berikut(periode, _ks, jangkar)
    else:
        no_agenda = await _no_agenda_berikut("keluar", periode, _ks)
    nomor = bangun_nomor(
        atur["format_nomor"], urut_tampil(no_agenda, sisip), tanggal_surat,
        kode_klasifikasi=kode_klas,
        kode_unit=atur["kode_unit"],
        kode_keamanan=data.get("kode_keamanan") or "B")
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": kode_satker_user(user),
        "jenis": "keluar",
        "no_agenda": no_agenda,
        "sisipan": sisip,
        "tahun": tahun,
        "nomor": nomor,
        "status": "dibooking",
        "perihal": data["perihal"].strip(),
        "tujuan": str(data.get("tujuan") or "").strip(),
        "jenis_naskah": str(data.get("jenis_naskah") or "Laporan").strip(),
        "modul": str(data.get("modul") or "umum").strip(),
        "kegiatan_id": str(data.get("kegiatan_id") or "").strip(),
        "nama_kegiatan": nama_kegiatan,
        "kode_klasifikasi": kode_klas,
        "kode_keamanan": str(data.get("kode_keamanan") or "B").strip().upper(),
        "tanggal_surat": tanggal_surat,
        "referensi": str(data.get("referensi") or "").strip(),
        "nomor_eksternal": str(data.get("nomor_eksternal") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "dibuat_oleh": user.get("username", "system"),
        "riwayat": [{"status": "dibooking", "tanggal": now.isoformat(),
                     "oleh": user.get("username", "system"),
                     "catatan": (f"nomor sisipan (backdate {tanggal_surat})"
                                 if sisip else "")}],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.surat.insert_one({**record})
    jadwalkan_sync("surat", record)  # sinkron indeks Meili (best-effort)
    await log_audit("booking_surat", record["kegiatan_id"],
                    username=user.get("username", "system"),
                    detail=(f"Booking nomor surat keluar {nomor} — {record['perihal']}"
                            + (f" (sisipan backdate {tanggal_surat})" if sisip else "")))
    return record


@persuratan_router.post("/persuratan/masuk")
async def agenda_surat_masuk(payload: SuratMasukIn,
                             user: dict = Depends(require_writer)):
    """Catat surat masuk pada buku agenda (nomor agenda otomatis per periode).

    Periode mengikuti TANGGAL AGENDA (hari ini) — tanggal surat pengirim
    opsional dan bukan tanggal pencatatan kita.
    """
    data = payload.model_dump()
    errors = validate_surat_masuk(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    nama_kegiatan = await _nama_kegiatan(data.get("kegiatan_id"))
    now = datetime.now(timezone.utc)
    tahun = now.year
    _ks = kode_satker_user(user)
    atur = await _pengaturan(_ks)
    periode = _periode(atur, now.date().isoformat())
    no_agenda = await _no_agenda_berikut("masuk", periode, _ks)
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": _ks,
        "jenis": "masuk",
        "no_agenda": no_agenda,
        "sisipan": 0,
        "tahun": tahun,
        "nomor": data["nomor_surat"].strip(),
        "status": "diterima",
        "perihal": data["perihal"].strip(),
        "pengirim": data["pengirim"].strip(),
        "tanggal_surat": str(data.get("tanggal_surat") or "").strip()[:10],
        "modul": str(data.get("modul") or "umum").strip(),
        "kegiatan_id": str(data.get("kegiatan_id") or "").strip(),
        "nama_kegiatan": nama_kegiatan,
        "keterangan": str(data.get("keterangan") or "").strip(),
        "dibuat_oleh": user.get("username", "system"),
        "riwayat": [{"status": "diterima", "tanggal": now.isoformat(),
                     "oleh": user.get("username", "system"), "catatan": ""}],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.surat.insert_one({**record})
    jadwalkan_sync("surat", record)  # sinkron indeks Meili (best-effort)
    await log_audit("agenda_surat_masuk", record["kegiatan_id"],
                    username=user.get("username", "system"),
                    detail=f"Agenda surat masuk #{no_agenda}/{tahun}: {record['nomor']}")
    return record


@persuratan_router.post("/persuratan/{surat_id}/status")
async def transisi_surat(surat_id: str, payload: TransisiIn,
                         user: dict = Depends(require_writer)):
    """Pindahkan status surat (sahkan/batalkan/proses/selesai) — anti-race.

    Pembatalan surat keluar WAJIB beralasan (tercatat; nomor hangus).
    """
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    await pastikan_akses_dok_satker(user, s)
    ke = str(payload.status or "").strip()
    err = validate_transisi(s.get("status"), ke, s.get("jenis"))
    if err:
        raise HTTPException(status_code=409, detail=err)
    alasan = str(payload.alasan or "").strip()
    if ke == "dibatalkan" and not alasan:
        raise HTTPException(status_code=400,
                            detail="Pembatalan wajib disertai alasan")
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": ke, "updated_at": now}
    if ke == "disahkan":
        set_fields["disahkan_pada"] = now
        set_fields["disahkan_oleh"] = user.get("username", "system")
    if ke == "dibatalkan":
        set_fields["alasan_batal"] = alasan
    res = await db.surat.find_one_and_update(
        {"id": surat_id, "status": s.get("status")},  # anti-race
        {"$set": set_fields,
         "$push": {"riwayat": {"status": ke, "tanggal": now,
                               "oleh": user.get("username", "system"),
                               "catatan": alasan}}},
        return_document=ReturnDocument.AFTER)
    # (tanpa kwarg projection — mongomock_motor mengembalikan None bila diberi
    # projection padahal update-nya terterap; _id dibuang manual)
    if res is not None:
        res.pop("_id", None)
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Status surat berubah — muat ulang dulu")
    jadwalkan_sync("surat", res)  # sinkron indeks Meili (best-effort)
    await log_audit("status_surat", s.get("kegiatan_id", ""),
                    username=user.get("username", "system"),
                    detail=f"Surat {s.get('nomor')} → {ke}"
                           + (f" (alasan: {alasan})" if alasan else ""))
    return res


@persuratan_router.put("/persuratan/{surat_id}")
async def ubah_surat(surat_id: str, payload: UbahSuratIn,
                     user: dict = Depends(require_writer)):
    """Ubah metadata surat. Surat keluar DISAHKAN terkunci (hanya keterangan);
    nomor & no. agenda tidak pernah bisa diubah."""
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    await pastikan_akses_dok_satker(user, s)
    update = {k: str(v).strip() for k, v in payload.model_dump().items()
              if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Tidak ada yang diubah")
    if "nomor_surat" in update:
        # Nomor surat keluar milik counter agenda — tak pernah bisa diubah;
        # nomor surat MASUK berasal dari pengirim, boleh dikoreksi.
        if s.get("jenis") != "masuk":
            raise HTTPException(status_code=409,
                                detail="Nomor surat keluar tidak dapat diubah")
        if not update["nomor_surat"]:
            raise HTTPException(status_code=400, detail="Nomor surat wajib diisi")
        update["nomor"] = update.pop("nomor_surat")
    if s.get("jenis") == "keluar" and s.get("status") != "dibooking":
        terlarang = set(update) - {"keterangan", "nomor_eksternal"}
        if terlarang:
            raise HTTPException(status_code=409, detail=(
                "Surat sudah final — hanya 'keterangan' dan 'nomor eksternal' yang boleh diubah "
                f"(ditolak: {', '.join(sorted(terlarang))})"))
    if "modul" in update and update["modul"] and update["modul"] not in MODUL_AMAN:
        raise HTTPException(status_code=400,
                            detail=f"Modul tidak dikenal: {update['modul']}")
    if "kegiatan_id" in update:
        update["nama_kegiatan"] = await _nama_kegiatan(update["kegiatan_id"])
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.surat.find_one_and_update(
        {"id": surat_id}, {"$set": update},
        return_document=ReturnDocument.AFTER)
    # (tanpa kwarg projection — mongomock_motor mengembalikan None bila diberi
    # projection padahal update-nya terterap; _id dibuang manual)
    if res is not None:
        res.pop("_id", None)
    jadwalkan_sync("surat", res)  # sinkron indeks Meili (best-effort)
    await log_audit("ubah_surat", s.get("kegiatan_id", ""),
                    username=user.get("username", "system"),
                    detail=f"Ubah surat {s.get('nomor')}: "
                           f"{sorted(set(update) - {'updated_at', 'nama_kegiatan'})}")
    return res


@persuratan_router.delete("/persuratan/{surat_id}")
async def hapus_surat(surat_id: str, user: dict = Depends(require_admin)):
    """Hapus surat salah catat / batal dibuat (khusus admin).

    Surat keluar yang sudah DISAHKAN tidak dapat dihapus — batalkan dulu
    (beralasan) agar jejak nomor resmi tetap tercatat. Nomor agenda yang
    telanjur terpakai HANGUS (tidak dipakai ulang) demi keunikan penomoran.
    """
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    await pastikan_akses_dok_satker(user, s)
    if s.get("jenis") == "keluar" and s.get("status") == "disahkan":
        raise HTTPException(status_code=409, detail=(
            "Surat keluar yang sudah DISAHKAN tidak dapat dihapus — batalkan "
            "dulu (dengan alasan) agar jejak nomor resmi tetap tercatat"))
    await db.surat.delete_one({"id": surat_id})
    # Relasi yang menyentuh surat terhapus ikut dibersihkan — panah gantung
    # membuat surat lain tampak "dicabut oleh" dokumen yang tak ada.
    await db.surat_relasi.delete_many(
        {"$or": [{"dari_id": surat_id}, {"ke_id": surat_id}]})
    jadwalkan_hapus("surat", surat_id)  # cabut dari indeks Meili (best-effort)
    await log_audit("hapus_surat", s.get("kegiatan_id", ""),
                    username=user.get("username", "system"),
                    detail=(f"Hapus surat {s.get('jenis')} {s.get('nomor')} "
                            f"(status {s.get('status')}; nomor agenda hangus)"))
    return {"ok": True}


# ── Relasi ANTAR SURAT + status keberlakuan (mandat SURAT-3B) ───────────────
#
# Satu dokumen db.surat_relasi per panah aktif→pasif (dari MENCABUT ke).
# Status keberlakuan tidak pernah disimpan — selalu dihitung dari status
# surat + panah masuk (surat_relasi_utils.status_keberlakuan), sehingga buku
# agenda tak bisa "lupa diperbarui". Asas yang dipakai: pencabutan TIDAK
# pulih dengan dicabutnya surat pencabut (non-herleving); panah hanya mati
# bila surat pencabutnya DIBATALKAN nomornya (dokumen itu tak pernah sah).


async def _panah_masuk_hidup(ids: list) -> dict:
    """{surat_id: [relasi masuk yang panahnya hidup]} untuk sekumpulan surat.
    Panah mati = surat sumbernya berstatus 'dibatalkan' (nomor hangus)."""
    if not ids:
        return {}
    masuk = await db.surat_relasi.find(
        {"ke_id": {"$in": list(ids)}}, _PROJ).to_list(4000)
    dari_ids = sorted({r.get("dari_id") for r in masuk if r.get("dari_id")})
    status_dari = {}
    if dari_ids:
        async for s in db.surat.find({"id": {"$in": dari_ids}},
                                     {"_id": 0, "id": 1, "status": 1}):
            status_dari[s["id"]] = s.get("status")
    out = {}
    for r in masuk:
        if status_dari.get(r.get("dari_id")) == "dibatalkan":
            continue
        out.setdefault(r.get("ke_id"), []).append(r)
    return out


async def _stempel_keberlakuan(items: list) -> list:
    """Tambahkan `keberlakuan` + `keberlakuan_label` pada tiap dokumen surat
    (satu kueri massal — bukan per baris)."""
    hidup = await _panah_masuk_hidup([s.get("id") for s in items])
    for s in items:
        kode = status_keberlakuan(s, hidup.get(s.get("id"), []))
        s["keberlakuan"] = kode
        s["keberlakuan_label"] = STATUS_KEBERLAKUAN.get(kode, kode)
    return items


@persuratan_router.post("/persuratan/{surat_id}/relasi")
async def tambah_relasi_surat(surat_id: str, payload: RelasiIn,
                              user: dict = Depends(require_writer)):
    """Catat panah relasi: surat INI (sumber/aktif) → surat sasaran.

    Contoh: SK baru MENCABUT SK lama → panggil di SK baru dengan ke_id SK
    lama. Buku agenda lalu menampilkan SK lama "Tidak Berlaku (dicabut
    oleh …)" tanpa ada yang mengetik status itu.
    """
    dari = await db.surat.find_one({"id": surat_id}, _PROJ)
    ke = await db.surat.find_one({"id": str(payload.ke_id or "").strip()},
                                 _PROJ)
    if not dari or not ke:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    await pastikan_akses_dok_satker(user, dari)
    await pastikan_akses_dok_satker(user, ke)
    sudah = await db.surat_relasi.find(
        {"$or": [{"dari_id": dari["id"], "ke_id": ke["id"]},
                 {"dari_id": ke["id"], "ke_id": dari["id"]}]},
        _PROJ).to_list(200)
    galat = validate_relasi(dari, ke, payload.jenis, sudah_ada=sudah)
    if galat:
        raise HTTPException(status_code=400, detail=galat)
    r = await catat_relasi_surat(dari, ke, payload.jenis,
                                 str(payload.catatan or "").strip(),
                                 user.get("username", "system"))
    ke_baru = (await _stempel_keberlakuan([dict(ke)]))[0]
    return {"relasi": r, "sasaran": {
        "id": ke["id"], "keberlakuan": ke_baru["keberlakuan"],
        "keberlakuan_label": ke_baru["keberlakuan_label"]}}


async def catat_relasi_surat(dari: dict, ke: dict, jenis: str,
                             catatan: str, oleh: str) -> dict:
    """Tanam SATU panah relasi + jejak riwayat kedua surat + log audit —
    dipakai endpoint relasi DAN modul lain (mis. revisi BAST menautkan nomor
    baru → nomor lama). Validasi/guard akses adalah tanggung jawab pemanggil.
    """
    now = datetime.now(timezone.utc).isoformat()
    info = JENIS_RELASI[jenis]
    r = {"id": str(uuid.uuid4()),
         # Stempel satker dari DOKUMEN (bukan user) — super-admin lintas
         # satker tak boleh melahirkan relasi berstempel '' yang bocor.
         "kode_satker": dari.get("kode_satker") or ke.get("kode_satker") or "",
         "dari_id": dari["id"], "ke_id": ke["id"], "jenis": jenis,
         "catatan": str(catatan or "").strip(),
         "dari_nomor": dari.get("nomor") or "", "dari_perihal": dari.get("perihal") or "",
         "ke_nomor": ke.get("nomor") or "", "ke_perihal": ke.get("perihal") or "",
         "oleh": oleh, "created_at": now}
    await db.surat_relasi.insert_one({**r})
    # Jejak pada riwayat KEDUA surat — timeline masing-masing bercerita utuh.
    await db.surat.update_one({"id": dari["id"]}, {"$push": {"riwayat": {
        "status": dari.get("status"), "tanggal": now, "oleh": oleh,
        "catatan": f"{info['aktif']} {ke.get('nomor') or ke['id']}"}}})
    await db.surat.update_one({"id": ke["id"]}, {"$push": {"riwayat": {
        "status": ke.get("status"), "tanggal": now, "oleh": oleh,
        "catatan": f"{info['pasif']} {dari.get('nomor') or dari['id']}"}}})
    await log_audit("relasi_surat", dari.get("kegiatan_id", ""),
                    username=oleh,
                    detail=(f"Surat {dari.get('nomor')} {info['aktif']} "
                            f"{ke.get('nomor')}"
                            + (f" — {r['catatan']}" if r["catatan"] else "")))
    return r


@persuratan_router.delete("/persuratan/relasi/{relasi_id}")
async def hapus_relasi_surat(relasi_id: str,
                             user: dict = Depends(require_admin)):
    """Hapus relasi salah catat (khusus admin — relasi mengubah status
    keberlakuan dokumen resmi, jejaknya tetap di riwayat surat & log audit)."""
    r = await db.surat_relasi.find_one({"id": relasi_id}, _PROJ)
    if not r:
        raise HTTPException(status_code=404, detail="Relasi tidak ditemukan")
    await pastikan_akses_dok_satker(user, r)
    await db.surat_relasi.delete_one({"id": relasi_id})
    await log_audit("relasi_surat", "", username=user.get("username", "system"),
                    detail=(f"Hapus relasi: {r.get('dari_nomor')} "
                            f"{r.get('jenis')} {r.get('ke_nomor')}"))
    return {"ok": True, "id": relasi_id}


@persuratan_router.get("/persuratan/{surat_id}/timeline")
async def timeline_surat(surat_id: str, _user: dict = Depends(require_user)):
    """Timeline lengkap satu surat: riwayat status + panah relasi dua arah +
    status keberlakuan terhitung — bahan dialog Relasi/Timeline di UI."""
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    await pastikan_akses_dok_satker(_user, s)
    keluar = await db.surat_relasi.find({"dari_id": surat_id},
                                        _PROJ).to_list(500)
    masuk = await db.surat_relasi.find({"ke_id": surat_id},
                                       _PROJ).to_list(500)
    s = (await _stempel_keberlakuan([s]))[0]
    # Keberlakuan tiap UJUNG LAIN panah ikut disajikan supaya dialog bisa
    # menandai "pencabutnya sendiri sudah tidak berlaku" tanpa fetch ulang.
    ujung_ids = ({r.get("ke_id") for r in keluar}
                 | {r.get("dari_id") for r in masuk}) - {None, ""}
    ujung = await db.surat.find({"id": {"$in": sorted(ujung_ids)}},
                                _PROJ).to_list(1000) if ujung_ids else []
    ujung = await _stempel_keberlakuan(ujung)
    peta_ujung = {u["id"]: {"id": u["id"], "nomor": u.get("nomor"),
                            "perihal": u.get("perihal"),
                            "status": u.get("status"),
                            "keberlakuan": u.get("keberlakuan"),
                            "keberlakuan_label": u.get("keberlakuan_label")}
                  for u in ujung}
    return {"surat": s,
            "relasi_keluar": keluar, "relasi_masuk": masuk,
            "ujung": peta_ujung,
            "timeline": baris_timeline(s, keluar, masuk)}


@persuratan_router.get("/persuratan/export")
async def export_agenda(jenis: str = "", tahun: str = "",
                        _user: dict = Depends(require_user)):
    """Ekspor buku agenda ke CSV (pola ekspor #158)."""
    query = {}
    if jenis in ("keluar", "masuk"):
        query["jenis"] = jenis
    if tahun.strip().isdigit():
        query["tahun"] = int(tahun)
    query = scope_query_field_satker(_user, query)
    items = await (db.surat.find(query, _PROJ)
                   .sort([("tahun", 1), ("no_agenda", 1), ("sisipan", 1)])
                   .to_list(100000))
    items = await _stempel_keberlakuan(items)
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_agenda_csv(items):
        w.writerow(row)
    nama = f"Buku_Agenda_Surat{('_' + jenis) if jenis else ''}{('_' + tahun) if tahun else ''}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'})
