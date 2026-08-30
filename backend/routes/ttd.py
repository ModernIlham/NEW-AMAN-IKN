"""Tanda Tangan Digital — spesimen TTD & pemrosesan foto (Mandat-2).

Slice 1: kelola SPESIMEN tanda tangan per pejabat/pegawai (gambar PNG
transparan dari kanvas goresan mulus ATAU foto kertas yang di-hapus
background-nya via Pillow), tersimpan di GridFS. Blok tanda tangan PDF
(reports.py `_signature_block`) otomatis menyematkan spesimen KPB. Slice 2
(menyusul): e-sign via link per dokumen (`signature_requests`).
"""
import asyncio
import base64
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import (
    create_sign_token, require_admin, require_sign_token, require_user,
    require_user_or_query_token, require_user_or_sign_token, require_writer,
    require_writer_satker,
)
from db import db, fs_bucket
from ttd_penautan import (TAUT_TTD, kedaluwarsa_terdekat,
                          ringkas_status_ttd, sisa_kedaluwarsa)
from shared_utils import (
    scope_query_field_satker,
    cek_magic_gambar, delete_document_from_gridfs, get_document_from_gridfs,
    get_idempotent_response, kunci_idem, limiter, log_audit,
    pastikan_akses_dok_satker, reserve_idempotency_key,
    store_idempotent_response,
)
from ttd_kelengkapan import (
    jumlah_pembubuhan, normalisasi_jumlah_ttd, pesan_deklarasi_tanpa_area,
)
from ttd_utils import foto_ke_png_transparan, png_transparan_valid
from ttd_validasi import (
    judul_ttd_tampil, label_jenis_ttd, status_permintaan, sudah_membubuhkan,
    sudah_terverifikasi,
)

ttd_router = APIRouter()

_ENTITAS = {"pejabat": db.pejabat, "pegawai": db.pegawai}
_PROJ = {"_id": 0}

# Basis URL publik untuk link tanda tangan (frontend). Tanpa APP_PUBLIC_URL,
# jatuh ke origin CORS pertama (deploy nyata selalu mengisinya) supaya link
# yang dibagikan & QR verifikasi TIDAK pernah berupa path relatif yang mati.
# ALLOWED_ORIGINS dibaca lebih dulu — server.py memprioritaskannya untuk CORS;
# CORS_ORIGINS dipertahankan sebagai nama legacy.
def _basis_url_publik() -> str:
    u = os.environ.get("APP_PUBLIC_URL", "").strip().rstrip("/")
    if u:
        return u
    sumber = (os.environ.get("ALLOWED_ORIGINS", "")
              or os.environ.get("CORS_ORIGINS", ""))
    for o in sumber.split(","):
        o = o.strip().rstrip("/")
        if o.startswith("http") and "localhost" not in o:
            return o
    return ""


_APP_URL = _basis_url_publik()


class SpesimenIn(BaseModel):
    png_base64: str   # data-URL atau base64 murni PNG transparan
    # Posisi pembubuhan pilihan PENANDA TANGAN pada dokumen terlampir
    # (opsional — tanpa ini stempel memakai slot otomatis halaman terakhir):
    # {halaman: 1-based, x, y: pojok kiri-atas kotak ttd sebagai FRAKSI
    #  lebar/tinggi halaman, lebar: fraksi lebar halaman}.
    posisi: dict | None = None
    # PEMBUBUHAN TAMBAHAN — satu orang kerap harus meneken LEBIH DARI SEKALI
    # pada dokumen yang sama. Contoh nyatanya BAST operasional: selain blok
    # tanda tangan Berita Acara, ada lembar Surat Pernyataan Tanggung Jawab di
    # halaman berikutnya yang juga harus ia teken. Tanpa daftar ini, orang itu
    # hanya bisa membubuhkan SATU tanda tangan dan lembar sisanya terbit
    # kosong — dokumen resmi yang tampak lengkap padahal belum diteken.
    posisi_lain: list | None = None
    # Jalan keluar bila pemilik dokumen salah mendeklarasikan jumlah tempat
    # TTD terlalu besar. Penanda tangan menyatakan sudah memeriksa seluruh PDF
    # dan tidak menemukan area miliknya lagi; kiriman TIDAK langsung final,
    # melainkan masuk ke validator operator/admin satker.
    deklarasi_tanpa_area: bool = False
    catatan_deklarasi: str = ""


# ── Jejak identitas pada TTD berposisi bebas ────────────────────────────────
# Mandat pemilik: nama & tanggal dipindah ke SISI KIRI-BAWAH tanda tangan,
# tulisannya MENYAMPING keluar, sangat kecil, dan hampir menyatu dengan
# kertas; tanggal ditaruh DI BAWAH nama (bukan berderet) untuk menghemat
# tempat.
#
# Kenapa begitu: TTD berposisi bebas dijatuhkan DI ATAS isi dokumen yang
# sudah ada. Keterangan mendatar di bawahnya ikut menimpa teks dokumen.
# Jejak ini hanya penanda asal-usul — bukan bagian naskah — jadi ia harus
# ada tapi nyaris tak terlihat.
JEJAK_TTD_FONT = 3.6      # pt (sebelumnya 6) — "sangat perkecil"
JEJAK_TTD_ABU = 0.86      # 0=hitam, 1=putih (sebelumnya 0.35) — "hampir transparan"
JEJAK_TTD_NAMA_MAKS = 28  # potong nama panjang; jejak tak boleh memanjang


def jejak_identitas_ttd(nama, signed_at, x_pt, y_pt, tinggi=0.0, ukur=None,
                        tepi_kiri=4.0, maks_nama=JEJAK_TTD_NAMA_MAKS):
    """Bahan gambar jejak identitas: titik pangkal + baris-barisnya.

    Teks digambar setelah `rotate(90)`, sehingga berjalan ke ATAS halaman
    (menyamping) dan tumbuh KE LUAR — menjauh dari tanda tangan, bukan
    menimpanya.

    TEGAK LURUS: jejak dipusatkan pada TENGAH tinggi tanda tangan (mandat
    pemilik: "tetap di samping kiri, hanya buat tepat berada di tengah").
    Karena teksnya berjalan ke atas, pemusatan butuh PANJANG teksnya —
    `ukur(teks)` disuntikkan pemanggil (mis. `canvas.stringWidth`) supaya
    fungsi ini tetap murni dan bisa diuji tanpa ReportLab. Tanpa `tinggi`
    (atau tanpa `ukur`), pangkalnya jatuh kembali ke dasar tanda tangan
    seperti perilaku lama — bukan melompat ke tempat yang salah.

    ARAH BACA — ini yang mudah keliru. Teks yang diputar 90° dibaca dari
    bawah ke atas, sehingga "atas" glyph-nya menghadap KIRI halaman. Artinya
    baris yang digambar lebih ke luar (kiri) tampak di ATAS, dan yang lebih
    dekat tanda tangan tampak di BAWAH. Mandat pemilik: tanggal DI BAWAH
    nama — jadi tanggal-lah yang mendapat geser paling kecil, dan nama yang
    terlempar ke luar. Percobaan pertama justru terbalik.

    @returns (pangkal_x, pangkal_y, [(teks, geser), ...]) — `geser` = jarak
             tegak lurus dari pangkal, ke arah LUAR (menjauh dari ttd).
    """
    urut = []            # dari yang tampak PALING BAWAH ke paling atas
    tgl = str(signed_at or "")[:10].strip()
    if tgl:
        urut.append(tgl)
    n = str(nama or "").strip()
    if n:
        urut.append(n[:maks_nama])
    langkah = JEJAK_TTD_FONT + 0.6
    baris = [(t, i * langkah) for i, t in enumerate(urut)]
    # Pangkal ditarik ke kiri tanda tangan, tapi tak pernah keluar halaman.
    pangkal_x = max(float(tepi_kiri), float(x_pt) - 2.0)
    # Pusatkan tegak lurus terhadap tinggi tanda tangan. Teks berjalan ke ATAS,
    # jadi pangkalnya turun setengah panjang teks dari titik tengah.
    pangkal_y = float(y_pt)
    if baris and float(tinggi or 0) > 0 and callable(ukur):
        panjang = max((float(ukur(t) or 0) for t, _g in baris), default=0.0)
        pangkal_y = float(y_pt) + (float(tinggi) - panjang) / 2.0
    return pangkal_x, max(2.0, pangkal_y), baris


def _nomor_urut(sg) -> float:
    """Nomor giliran seorang penanda tangan (mode berurutan).

    Data lama / hasil restore bisa saja tak punya `urutan`. Mengembalikan
    +inf untuk kasus itu membuat mereka jatuh ke BELAKANG antrean alih-alih
    menyerobot giliran orang lain — dan tetap terpilih bila memang cuma
    mereka yang tersisa.
    """
    try:
        n = sg.get("urutan")
        return float(n) if n is not None else float("inf")
    except (TypeError, ValueError):
        return float("inf")


# Batas pembubuhan tambahan per penanda tangan. Angkanya lapang — dokumen
# berlampiran banyak memang bisa menuntut belasan tanda tangan dari satu orang
# — tetapi tetap berbatas: daftar tanpa batas berarti satu permintaan bisa
# memaksa server menggambar ribuan overlay.
MAKS_PEMBUBUHAN = 20


def _posisi_bersih_banyak(daftar, maks_halaman: int = 0) -> list:
    """Bersihkan DAFTAR posisi pembubuhan tambahan; entri tak sah dibuang.

    Dibuang, bukan menggagalkan seluruh kiriman: tanda tangannya sendiri sudah
    sah dan sudah digambar orangnya. Menolak semuanya karena satu entri rusak
    berarti memaksa orang menggambar ulang tanda tangannya — dan kegagalan
    yang menyuruh pengguna mengulang pekerjaan yang benar adalah kegagalan
    yang salah tempat.
    """
    if not isinstance(daftar, list):
        return []
    keluar = []
    for p in daftar[:MAKS_PEMBUBUHAN]:
        bersih = _posisi_bersih(p, maks_halaman)
        if bersih:
            keluar.append(bersih)
    return keluar


def _posisi_bersih(p, maks_halaman: int = 0):
    """Validasi + jepit posisi pembubuhan dari klien; None bila tak dipakai.

    Tahan nilai liar apa pun dari JSON: Infinity/NaN (json.loads menerimanya)
    ditolak eksplisit — int(inf) melempar OverflowError, NaN merusak jepitan.
    x dijepit BERPASANGAN dengan lebar agar kotak tidak keluar tepi kanan.
    """
    if not isinstance(p, dict):
        return None
    import math
    try:
        halaman_f = float(p.get("halaman"))
        x = float(p.get("x")); y = float(p.get("y"))
        lebar = float(p.get("lebar"))
        if not all(math.isfinite(v) for v in (halaman_f, x, y, lebar)):
            return None
        halaman = int(halaman_f)
    except (TypeError, ValueError, OverflowError):
        return None
    if halaman < 1:
        return None
    if maks_halaman and halaman > maks_halaman:
        halaman = maks_halaman
    lebar = min(0.6, max(0.08, lebar))
    return {"halaman": halaman,
            "x": min(1.0 - lebar, max(0.0, x)),
            "y": min(0.95, max(0.0, y)),
            "lebar": lebar}


# Sisi QR verifikasi minimal (mutlak) agar tetap dapat dipindai — ditegakkan
# saat render, apa pun ukuran halaman. ±2cm cukup untuk kamera HP biasa.
QR_MIN_MM = 20.0


def _posisi_qr_bersih(p, maks_halaman: int = 0):
    """Validasi + jepit posisi & UKURAN QR verifikasi pilihan (dokumen-level).

    Seperti _posisi_bersih namun untuk QR: `lebar` (= sisi kotak QR sebagai
    fraksi lebar halaman) dijepit 0.10–0.40 agar tak terlalu kecil (gagal
    scan) atau terlalu besar. Batas MUTLAK (QR_MIN_MM) ditegakkan lagi saat
    render karena fraksi bergantung lebar halaman. None → QR pakai slot
    otomatis (pojok kanan-bawah halaman terakhir, perilaku lama)."""
    if not isinstance(p, dict):
        return None
    import math
    try:
        halaman_f = float(p.get("halaman"))
        x = float(p.get("x")); y = float(p.get("y"))
        lebar = float(p.get("lebar"))
        if not all(math.isfinite(v) for v in (halaman_f, x, y, lebar)):
            return None
        halaman = int(halaman_f)
    except (TypeError, ValueError, OverflowError):
        return None
    if halaman < 1:
        return None
    if maks_halaman and halaman > maks_halaman:
        halaman = maks_halaman
    lebar = min(0.40, max(0.10, lebar))
    return {"halaman": halaman,
            "x": min(1.0 - lebar, max(0.0, x)),
            "y": min(0.95, max(0.0, y)),
            "lebar": lebar}


def _png_dari_base64(s: str) -> bytes:
    raw = str(s or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="PNG base64 tidak valid")
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=400, detail="Berkas bukan PNG")
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Gambar TTD maksimal 4MB")
    return data


@ttd_router.post("/ttd/olah-foto")
@limiter.limit("20/minute")
async def olah_foto(request: Request, file: UploadFile = File(...),
                    _user: dict = Depends(require_user_or_sign_token)):
    """Foto TTD di kertas → PNG TRANSPARAN (hapus background otomatis). Balikan
    pratinjau data-URL base64; klien menampilkan lalu menyimpannya sebagai
    spesimen bila puas. Juga bisa dipakai penanda tangan TAMU (?token= e-sign)
    dari halaman link publik."""
    nama = str(file.filename or "").lower()
    ext = next((e for e in (".jpg", ".jpeg", ".png", ".webp") if nama.endswith(e)), "")
    if not ext:
        raise HTTPException(status_code=400, detail="Foto harus JPG/PNG/WEBP")
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto maksimal 12MB")
    if not cek_magic_gambar(data, ext):
        raise HTTPException(status_code=400, detail="Isi berkas tidak cocok ekstensi")
    try:
        # DI LUAR event loop. Pipeline ini murni Pillow/numpy dan sinkron —
        # dekode + LANCZOS + Otsu atas foto 12 MB memakan ratusan milidetik
        # sampai beberapa detik. Dijalankan langsung di event loop, SELURUH
        # permintaan lain (simpan aset lapangan, login, heartbeat lock)
        # berhenti dilayani selama itu. Pola yang sama sudah dipakai
        # `process_photos_for_storage` di routes/assets.py.
        png = await asyncio.to_thread(foto_ke_png_transparan, data)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Gagal memproses foto — coba foto lebih terang/kontras")
    if not png_transparan_valid(png):
        raise HTTPException(status_code=400,
                            detail="Tanda tangan tak terdeteksi — pastikan goresan gelap di kertas terang")
    return {"png_base64": "data:image/png;base64," + base64.b64encode(png).decode()}


@ttd_router.put("/ttd/spesimen/{entitas}/{eid}")
async def simpan_spesimen(entitas: str, eid: str, payload: SpesimenIn,
                          admin: dict = Depends(require_admin)):
    """Simpan spesimen TTD (PNG transparan) untuk pejabat/pegawai → GridFS +
    field `ttd_file_id`. Spesimen lama dihapus (cegah orphan)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one(
        {"id": eid}, {"_id": 0, "ttd_file_id": 1, "nama": 1, "kode_satker": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{entitas} tidak ditemukan")
    # ISOLASI SATKER (REVIEW-9 R10). Spesimen ini DISEMATKAN otomatis ke PDF
    # resmi (reports.py `_signature_block`), jadi menimpanya = memalsukan tanda
    # tangan pejabat satker lain. `require_admin` hanya memeriksa role.
    await pastikan_akses_dok_satker(admin, doc)
    data = _png_dari_base64(payload.png_base64)
    if not png_transparan_valid(data):
        raise HTTPException(status_code=400, detail="PNG TTD tidak valid / kosong")

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"ttd_{entitas}_{eid}.png",
        metadata={"content_type": "image/png", "kind": "ttd_spesimen",
                  "entitas": entitas, "eid": eid})
    await grid_in.write(data)
    await grid_in.close()

    lama = str(doc.get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": str(file_id)}})
    if lama and lama != str(file_id):
        await delete_document_from_gridfs(lama)
    await log_audit("simpan_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Spesimen TTD {entitas} {doc.get('nama') or eid}")
    return {"ok": True, "ttd_file_id": str(file_id)}


@ttd_router.get("/ttd/spesimen/{entitas}/{eid}")
async def lihat_spesimen(entitas: str, eid: str,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream gambar spesimen TTD (pratinjau)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one(
        {"id": eid}, {"_id": 0, "ttd_file_id": 1, "kode_satker": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{entitas} tidak ditemukan")
    # Gambar tanda tangan = data tanda tangan basah dalam bentuk digital;
    # jangan biarkan siapa pun yang login mengunduh milik satker lain (R10).
    await pastikan_akses_dok_satker(_user, doc)
    fid = str(doc.get("ttd_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404, detail="Spesimen TTD belum ada")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas TTD tidak ditemukan")
    return StreamingResponse(
        io.BytesIO(data), media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="ttd.png"',
                 "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "private, max-age=3600"})


@ttd_router.delete("/ttd/spesimen/{entitas}/{eid}")
async def hapus_spesimen(entitas: str, eid: str,
                         admin: dict = Depends(require_admin)):
    """Hapus spesimen TTD (dokumen kembali ke tanda tangan basah)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one(
        {"id": eid}, {"_id": 0, "ttd_file_id": 1, "kode_satker": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{entitas} tidak ditemukan")
    await pastikan_akses_dok_satker(admin, doc)  # isolasi satker (R10)
    fid = str(doc.get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": ""}})
    if fid:
        await delete_document_from_gridfs(fid)
    await log_audit("hapus_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Hapus spesimen TTD {entitas}")
    return {"ok": True}


# ============================================================================
# E-SIGN VIA LINK — permintaan tanda tangan per dokumen (Mandat-2, slice 2)
# ============================================================================

class SignerIn(BaseModel):
    nama: str
    nip: str = ""
    jabatan: str = ""
    email: str = ""     # opsional — link dikirim otomatis via email bila diisi
    # BERAPA TEMPAT yang harus diteken orang ini pada dokumen. Dideklarasikan
    # pemilik dokumen karena hanya dialah yang melihat naskahnya; sistem tak
    # bisa menebaknya dari PDF. Tanpa angka ini tak ada ukuran "lengkap", dan
    # kiriman yang kurang tak pernah bisa ditolak (lihat ttd_kelengkapan.py).
    # 1 = perilaku lama, jadi permintaan yang tak mengisinya tak berubah.
    jumlah_ttd: int = 1


class PermintaanIn(BaseModel):
    judul: str
    doc_type: str = "dokumen"          # bast|berita_acara|dokumen|…
    doc_ref: str = ""                  # id dokumen sumber (opsional)
    mode: str = "paralel"              # "berurutan" | "paralel"
    # Seberapa cepat dokumen ini harus diteken. Sumbu TERSENDIRI dari kode
    # keamanan (lihat persuratan_utils.SIFAT_URGENSI) dan bukan sekadar
    # hiasan: ia ikut ke halaman penanda tangan dan ke pesan yang dibagikan,
    # supaya "segera" tak hanya hidup di kepala orang yang mengirim.
    sifat_urgensi: str = "biasa"
    signers: List[SignerIn]


class ValidasiPembubuhanIn(BaseModel):
    """Keputusan pengelola atas SATU pembubuhan.

    ``buka_ulang`` sengaja bekerja per penanda tangan. Dokumen asli dan
    pembubuhan rekan lain tidak disentuh; bukti lama dipindahkan ke riwayat
    agar koreksi tidak menghapus jejak audit.
    """
    aksi: str = "setujui"            # setujui | buka_ulang
    alasan: str = ""


def _link_ttd(sr_id, token):
    rel = f"/ttd/{sr_id}?token={token}"
    return (_APP_URL + rel) if _APP_URL else rel


async def _link_ttd_pendek(sr_id, token, signer_id="", kode_satker="",
                           oleh="") -> str:
    """Tautan e-sign PENDEK (±46 karakter, dari ±396).

    Yang dibagikan lewat WA/email jadi satu baris, dan — ini yang penting —
    token tanda tangan TIDAK IKUT di dalam pesan yang beredar. Selama ini
    token itu ikut terbawa setiap kali pesan diteruskan atau di-screenshot.

    Masa berlaku tautan pendek disamakan dengan masa berlaku tokennya supaya
    tak ada tautan yang tampak hidup padahal tokennya sudah mati. Gagal
    memendekkan TIDAK menggagalkan penerbitan permintaan — jatuh ke tautan
    panjang seperti sebelumnya.
    """
    panjang = _link_ttd(sr_id, token)
    try:
        from datetime import timedelta

        from auth_utils import SIGN_TOKEN_EXPIRATION_DAYS
        from tautan_pendek_utils import buat_tautan_pendek, url_pendek
        kedaluwarsa = (datetime.now(timezone.utc)
                       + timedelta(days=SIGN_TOKEN_EXPIRATION_DAYS)).isoformat()
        kode = await buat_tautan_pendek(
            panjang, jenis="ttd", ref=str(sr_id), sub_ref=str(signer_id),
            kode_satker=kode_satker, dibuat_oleh=oleh,
            kedaluwarsa=kedaluwarsa)
        return url_pendek(kode) if kode else panjang
    except Exception:
        return panjang


async def _link_verifikasi_pendek(sr_id, kode_satker="", oleh="") -> str:
    """Tautan verifikasi PENDEK — dipakai untuk isi QR di dokumen ber-TTD.

    Bonus nyata di sini: isi QR jadi jauh lebih ringkas, sehingga modul QR-nya
    lebih renggang dan lebih mudah dipindai kamera HP pada ukuran cetak kecil.
    Tanpa masa berlaku: verifikasi keabsahan dokumen harus tetap bisa dibuka
    bertahun-tahun kemudian.
    """
    panjang = (_APP_URL + f"/ttd/verifikasi/{sr_id}") if _APP_URL \
        else f"/ttd/verifikasi/{sr_id}"
    try:
        from tautan_pendek_utils import buat_tautan_pendek, url_pendek
        kode = await buat_tautan_pendek(
            panjang, jenis="verifikasi", ref=str(sr_id),
            kode_satker=kode_satker, dibuat_oleh=oleh, pakai_ulang=True)
        return url_pendek(kode) if kode else panjang
    except Exception:
        return panjang


MAKS_BARANG_RINGKAS = 3      # sisanya diringkas "(+N barang lainnya)"


def _cetak_token_signer(sr_id: str, signer_id: str, jti: str):
    """Cetak token tanda tangan + kembalikan (token, kedaluwarsa ISO).

    KENAPA KEDALUWARSA DICATAT DI SINI, bukan dihitung dari `created_at`:
    `exp` token dihitung SAAT TOKEN DICETAK (auth_utils.create_sign_token).
    Ada TIGA titik pencetakan — saat permintaan dibuat, saat link seseorang
    DITERBITKAN ULANG, dan saat giliran maju pada mode berurutan — sedangkan
    `created_at` permintaan hanya ditulis sekali dan tak pernah berubah.

    Menghitung "sisa waktu" dari `created_at + 14 hari` karena itu SALAH: untuk
    link yang sudah diterbitkan ulang ia terlalu cepat (bisa mengaku
    "kedaluwarsa" padahal tautannya masih hidup 14 hari lagi), dan untuk mode
    berurutan penanda tangan ke-2 dst. menerima token yang baru dicetak saat
    gilirannya tiba. Satu-satunya angka yang benar adalah yang dicatat
    BERSAMAAN dengan pencetakan tokennya — itulah yang disimpan di
    `signers[].token_exp`.
    """
    from datetime import timedelta

    from auth_utils import SIGN_TOKEN_EXPIRATION_DAYS
    token = create_sign_token(sr_id, signer_id, jti)
    exp = (datetime.now(timezone.utc)
           + timedelta(days=SIGN_TOKEN_EXPIRATION_DAYS)).isoformat()
    return token, exp


# Perhitungan sisa waktu tautan PINDAH ke `ttd_penautan` supaya layar dokumen
# (Riwayat BAST/LPB) memakai angka yang sama persis dengan modul TTD. Alias ini
# menjaga pemanggil lama di berkas ini tetap terbaca apa adanya.
_sisa_kedaluwarsa = sisa_kedaluwarsa


def ringkas_lpb(lpb: dict) -> dict:
    """Dokumen LPB → ringkasan untuk pesan WA/email.

    Dipisah dari pembacaan basis data supaya bentuk pesannya bisa diuji apa
    adanya — termasuk dokumen era-lama yang bidangnya belum lengkap.

    Kenapa LPB perlu ini sendiri. `_ringkas_dokumen` dulu HANYA melayani
    `doc_type == "bast"` dan mengembalikan `{}` untuk yang lain, sehingga
    permintaan TTD LPB terbit dengan `ringkas` kosong. Akibatnya pesan
    WA/email-nya menyusut jadi "judul + tautan" — persis keluhan yang sudah
    diperbaiki untuk BAST. Kesalahannya tak terlihat: tak ada galat, tautannya
    tetap benar, pesannya cuma lebih pendek.

    Para pihak pada LPB adalah PENYEDIA (yang menyerahkan barang) dan PPK
    (yang berkomitmen atasnya) — bukan pihak pertama/kedua seperti BAST.
    """
    d = lpb or {}
    # Dokumen era-lama tak punya `kategori` sama sekali; ia memang hanya dipakai
    # persediaan waktu itu (lihat docstring `daftar_lpb`).
    aset = str(d.get("kategori") or "").strip().lower() == "aset"
    pihak = []
    penyedia = str(d.get("penyedia") or "").strip()
    if penyedia:
        pihak.append(f"{penyedia} (Penyedia)")
    ppk = str(d.get("ppk_nama") or "").strip()
    if ppk:
        pihak.append(f"{ppk} (PPK)")
    items = d.get("items") or []
    barang = [{"kode": str((b or {}).get("kode_barang") or "").strip(),
               "nup": str((b or {}).get("nup") or "").strip(),
               "nama": str((b or {}).get("nama_barang") or "").strip()}
              for b in items[:MAKS_BARANG_RINGKAS]]
    try:
        jumlah = int(d.get("jumlah_barang") or 0)
    except (TypeError, ValueError):
        jumlah = 0
    return {
        "nomor": str(d.get("nomor") or "").strip(),
        "perihal": ("Laporan Penerimaan Barang (BMN)" if aset
                    else "Laporan Penerimaan Barang (Persediaan)"),
        "tanggal": str(d.get("tanggal") or "")[:10],
        "pihak": pihak,
        "barang": [x for x in barang if x["kode"] or x["nama"]],
        # `jumlah_barang` tersimpan lebih dipercaya daripada panjang `items`:
        # proyeksi pembacaan boleh memotong arraynya, jumlahnya tidak boleh ikut
        # menyusut — angka di pesan itu "berapa barang yang diterima".
        "jumlah_barang": jumlah or len(items),
    }


async def _ringkas_dokumen(doc_type: str, doc_ref: str) -> dict:
    """Ringkasan singkat dokumen yang diminta ditandatangani.

    Dipakai untuk mengisi pesan WA/email agar penanda tangan tahu APA yang
    ia teken sebelum membuka tautan — dan, kemudian hari, bisa MENCARI ulang
    dokumen mana yang pernah ia tandatangani. Tanpa ini pesannya hanya berisi
    judul + tautan: penerima harus membuka tautan dulu sekadar untuk tahu
    dokumen apa itu, dan setelah berbulan-bulan tak ada jejak yang bisa
    dicari di riwayat percakapannya.

    DIBEKUKAN saat permintaan dibuat (disimpan di `signature_requests.ringkas`),
    sejalan dengan PDF-nya yang juga dibekukan — supaya isi pesan cocok dengan
    dokumen yang benar-benar diteken, walau dokumen sumber berubah kemudian.

    Selalu mengembalikan dict (kosong bila tak ada yang bisa diringkas);
    kegagalan di sini tak boleh menggagalkan penerbitan permintaan.
    """
    ref = str(doc_ref or "").strip()
    jenis = str(doc_type or "")
    if not ref:
        return {}
    if jenis == "lpb":
        try:
            # Sub-bidang `items` diproyeksikan (bukan di-`$slice`) supaya
            # panjang arraynya tetap utuh untuk dokumen lama yang belum
            # menyimpan `jumlah_barang`.
            lpb = await db.lpb.find_one(
                {"id": ref},
                {"_id": 0, "nomor": 1, "tanggal": 1, "kategori": 1,
                 "penyedia": 1, "ppk_nama": 1, "jumlah_barang": 1,
                 "items.kode_barang": 1, "items.nup": 1, "items.nama_barang": 1})
            return ringkas_lpb(lpb) if lpb else {}
        except Exception:
            return {}
    if jenis != "bast":
        return {}
    try:
        b = await db.bast_serah_terima.find_one(
            {"id": ref},
            {"_id": 0, "nomor": 1, "jenis": 1, "judul_lainnya": 1, "tanggal": 1,
             "pihak_pertama": 1, "pihak_kedua": 1, "aset": 1})
        if not b:
            return {}
        from routes.bast import JENIS_BAST
        perihal = (str(b.get("judul_lainnya") or "").strip()
                   or JENIS_BAST.get(str(b.get("jenis") or ""), "")
                   or "Berita Acara Serah Terima")
        pihak = []
        for kunci, peran in (("pihak_pertama", "Pihak Pertama"),
                             ("pihak_kedua", "Pihak Kedua")):
            nama = str(((b.get(kunci) or {}).get("nama")) or "").strip()
            if nama:
                pihak.append(f"{nama} ({peran})")
        aset = b.get("aset") or []
        barang = [{"kode": str(a.get("asset_code") or "").strip(),
                   "nup": str(a.get("NUP") or "").strip(),
                   "nama": str(a.get("asset_name") or "").strip()}
                  for a in aset[:MAKS_BARANG_RINGKAS]]
        return {"nomor": str(b.get("nomor") or "").strip(),
                "perihal": perihal,
                "tanggal": str(b.get("tanggal") or "")[:10],
                "pihak": pihak,
                "barang": [x for x in barang if x["kode"] or x["nama"]],
                "jumlah_barang": len(aset)}
    except Exception:
        return {}


def _publik_signer(sg):
    """Bidang aman signer untuk halaman publik (tanpa jti/token)."""
    return {k: sg.get(k) for k in ("signer_id", "nama", "nip", "jabatan",
                                   "urutan", "status", "signed_at",
                                   "validated_at", "deklarasi_tanpa_area",
                                   "deklarasi_jumlah_aktual",
                                   "deklarasi_jumlah_diminta")
            } | {"jumlah_ttd": normalisasi_jumlah_ttd(sg.get("jumlah_ttd"))}


@ttd_router.post("/ttd/permintaan")
async def buat_permintaan(payload: PermintaanIn,
                          user: dict = Depends(require_writer_satker)):
    """Buat permintaan tanda tangan + link per penanda tangan. Mode berurutan:
    hanya penanda tangan urutan pertama yang 'aktif'; paralel: semua aktif."""
    if not payload.signers:
        raise HTTPException(status_code=400, detail="Minimal satu penanda tangan")
    if payload.mode not in ("berurutan", "paralel"):
        raise HTTPException(status_code=400, detail="Mode harus berurutan/paralel")
    from persuratan_utils import SIFAT_URGENSI, SIFAT_URGENSI_DEFAULT
    _urgensi = str(payload.sifat_urgensi or "").strip() or SIFAT_URGENSI_DEFAULT
    if _urgensi not in SIFAT_URGENSI:
        raise HTTPException(
            status_code=400,
            detail=("Sifat urgensi tidak dikenal: "
                    f"{_urgensi} (pilih {'/'.join(SIFAT_URGENSI)})"))
    # Bila menaut dokumen TERSTRUKTUR (doc_type ber-koleksi + doc_ref = id-nya),
    # PASTIKAN dokumen itu milik satker pemohon. Ini GERBANG TUNGGAL: back-link
    # penyelesaian (menulis signature_request_id ke dokumen) dan cascade
    # pembatalan sama-sama digerakkan doc_ref — validasi kepemilikan di sini
    # mencegah SR palsu menunjuk dokumen satker lain (uuid bocor) lalu
    # men-tamper-nya.
    #
    # SETIAP doc_type baru yang punya back-link WAJIB terdaftar di sini. LPB
    # ditambahkan bersamaan dengan back-link-nya; tanpa itu `POST /ttd/permintaan`
    # yang dipanggil langsung (melewati /persediaan/lpb/{id}/kirim-ttd yang
    # memang ber-guard) bisa menulis ke LPB satker lain saat tandatangan selesai.
    #
    # doc_ref bagi doc_type lain (surat/register/dokumen unggahan) adalah teks
    # bebas tanpa back-link → tak divalidasi.
    # Diturunkan dari registry `TAUT_TTD` — dulu daftarnya ditulis ulang di
    # sini, sehingga `doc_type` yang menulis tautan maju tetapi lupa didaftar
    # di sini kehilangan gerbang kepemilikannya tanpa gejala apa pun.
    _dt = str(payload.doc_type or "")
    # `scope_query_field_satker` SENGAJA dipakai dari impor tingkat modul —
    # JANGAN meng-import-nya lagi di dalam fungsi ini. Import lokal (walau di
    # dalam `if`) membuat namanya LOKAL untuk SELURUH badan fungsi, sehingga
    # pemakaian di cabang lain (gerbang "Meninggal Dunia" di bawah) meledak
    # UnboundLocalError → 500 pada permintaan TTD tanpa doc_ref BAST/LPB.
    if _dt in TAUT_TTD and str(payload.doc_ref or "").strip():
        from ttd_penautan import koleksi_taut, label_taut
        pemilik = await koleksi_taut(db, _dt).find_one(
            scope_query_field_satker(
                user, {"id": str(payload.doc_ref).strip()}),
            {"_id": 0, "id": 1})
        if not pemilik:
            raise HTTPException(
                status_code=403,
                detail=f"{label_taut(_dt)} rujukan tidak ditemukan "
                       "pada satker Anda")
    # Penanda tangan yang sudah MENINGGAL DUNIA → tolak sejak awal. Mengirim
    # link TTD ke almarhum mustahil dipenuhi dan hanya menggantung dokumen di
    # status "menunggu". Satu query untuk semua NIP (hindari N kueri).
    _nip_signer = [str(s.nip or "").strip() for s in payload.signers
                   if str(s.nip or "").strip()]
    if _nip_signer:
        # Scope satker (REVIEW-9 R15): tanpa ini penolakan "Meninggal Dunia"
        # menjadi ORACLE — penyerang menebak NIP dan pesan galat memastikan
        # keberadaan sekaligus NAMA pegawai satker lain.
        _alm = await db.pegawai.find(
            scope_query_field_satker(
                user, {"nip": {"$in": _nip_signer}, "status": "meninggal"}),
            {"_id": 0, "nama": 1, "nip": 1}).to_list(100)
        if _alm:
            _nama = ", ".join(str(a.get("nama") or a.get("nip")) for a in _alm)
            raise HTTPException(
                status_code=400,
                detail=(f"Penanda tangan berstatus Meninggal Dunia: {_nama}. "
                        "Ganti dengan pejabat pengganti yang berwenang "
                        "(mis. atasan langsung/ahli waris) sebelum mengirim "
                        "permintaan tanda tangan."))
    now = datetime.now(timezone.utc)
    sr_id = str(uuid.uuid4())
    signers, links = [], []
    urut = 1
    # Dihitung SEBELUM perulangan: tautan pendek tiap penanda tangan ikut
    # distempel satkernya, dan nilai ini juga dipakai di record di bawah.
    from shared_utils import kode_satker_user
    kode_sat = kode_satker_user(user)
    for s in payload.signers:
        if not str(s.nama or "").strip():
            raise HTTPException(status_code=400, detail="Nama penanda tangan wajib")
        signer_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        aktif = (payload.mode == "paralel") or (urut == 1)
        signers.append({
            "signer_id": signer_id, "nama": s.nama.strip(),
            "nip": str(s.nip or "").strip(), "jabatan": str(s.jabatan or "").strip(),
            "email": str(s.email or "").strip(),
            "urutan": urut, "status": "aktif" if aktif else "menunggu",
            "jumlah_ttd": normalisasi_jumlah_ttd(s.jumlah_ttd),
            "jti": jti, "signature_file_id": "", "hash": "",
            "signed_at": "", "ip": ""})
        token, exp_tok = _cetak_token_signer(sr_id, signer_id, jti)
        signers[-1]["token_exp"] = exp_tok
        link = await _link_ttd_pendek(sr_id, token, signer_id=signer_id,
                                      kode_satker=kode_sat,
                                      oleh=user.get("username", ""))
        email_terkirim = False
        if aktif and str(s.email or "").strip():
            from shared_utils import send_esign_email
            email_terkirim = await send_esign_email(
                s.email, s.nama.strip(), payload.judul.strip() or "Dokumen", link)
        links.append({"nama": s.nama.strip(), "link": link,
                      "email": str(s.email or "").strip(),
                      "email_terkirim": email_terkirim})
        urut += 1
    record = {
        "id": sr_id, "judul": payload.judul.strip() or "Dokumen",
        "doc_type": str(payload.doc_type or "dokumen"),
        "doc_ref": str(payload.doc_ref or ""), "mode": payload.mode,
        "status": "terkirim", "signers": signers,
        "sifat_urgensi": _urgensi,
        # Isolasi multi-satker: tanpa stempel ini admin satker LAIN dapat
        # melihat & membatalkan permintaan TTD (dokumen + PII penandatangan).
        "kode_satker": kode_sat,
        # OCC untuk tindakan validator/reopen. Permintaan era-lama tanpa field
        # ini diperlakukan sebagai versi 1 dan diinisialisasi saat dimutasi.
        "version": 1,
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
        "riwayat_validasi": [],
        # Ringkasan DIBEKUKAN untuk isi pesan WA/email (lihat _ringkas_dokumen).
        "ringkas": await _ringkas_dokumen(payload.doc_type, payload.doc_ref),
    }
    await db.signature_requests.insert_one({**record})
    # TAUTAN MAJU dokumen → permintaan, ditulis DI SINI — satu pintu untuk
    # semua modul. Sebelumnya tiap modul menuliskannya sendiri, dan BAST
    # (satu-satunya yang tidak) membuat Riwayat BAST tak pernah tahu bahwa
    # permintaan sudah dikirim: tautannya hilang bersama dialog, dan yang
    # tersisa di modul TTD berminggu-minggu kemudian hanya "tautan mati".
    from ttd_penautan import catat_pengiriman_ttd
    await catat_pengiriman_ttd(db, record["doc_type"], record["doc_ref"], sr_id)
    await log_audit("buat_permintaan_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=f"Permintaan TTD '{record['judul']}' — {len(signers)} penanda tangan")
    return {"id": sr_id, "judul": record["judul"], "mode": record["mode"],
            "links": links, "ringkas": record["ringkas"]}


@ttd_router.post("/ttd/permintaan/unggah")
async def buat_permintaan_dengan_dokumen(
    file: UploadFile = File(...),
    judul: str = Form(""),
    mode: str = Form("paralel"),
    signers: str = Form("[]"),
    doc_ref: str = Form(""),      # referensi dokumen sumber (No. BAST/Surat/register)
    user: dict = Depends(require_writer),
):
    """Permintaan TTD DENGAN dokumen PDF terlampir (permintaan pemilik):
    kirim dokumen yang hendak di-ttd LANGSUNG — penanda tangan meneken via
    link seperti biasa, lalu tanda tangan DIBUBUHKAN ke halaman terakhir
    dokumen (unduh 'Dokumen ber-TTD')."""
    nama = str(file.filename or "").lower()
    if not nama.endswith(".pdf"):
        raise HTTPException(status_code=400,
                            detail="Dokumen harus berformat PDF")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 20MB")
    try:
        from pypdf import PdfReader
        n_hal = len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Berkas PDF tidak dapat dibaca/terenkripsi")
    import json as _json
    try:
        daftar = _json.loads(signers or "[]")
        assert isinstance(daftar, list)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Format daftar penanda tangan tidak valid")
    payload = PermintaanIn(
        judul=str(judul or "").strip() or str(file.filename or "Dokumen"),
        doc_type="dokumen_unggahan", doc_ref=str(doc_ref or "").strip(), mode=mode,
        signers=[SignerIn(
            nama=str((s or {}).get("nama") or ""),
            nip=str((s or {}).get("nip") or ""),
            jabatan=str((s or {}).get("jabatan") or ""),
            email=str((s or {}).get("email") or ""),
            # Jalur INILAH yang paling butuh: hanya permintaan ber-dokumen
            # terlampir yang punya halaman untuk diteken berkali-kali.
            # Menjatuhkannya di sini akan membuat deklarasi pemilik hilang
            # justru pada satu-satunya jalur yang memakainya.
            jumlah_ttd=normalisasi_jumlah_ttd((s or {}).get("jumlah_ttd")),
        ) for s in daftar])
    hasil = await buat_permintaan(payload=payload, user=user)

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=file.filename,
        metadata={"content_type": "application/pdf", "size": len(data)})
    await grid_in.write(data)
    await grid_in.close()
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id),
                  "dok_nama": str(file.filename or "dokumen.pdf"),
                  "dok_halaman": n_hal}})
    return {**hasil, "dok_nama": file.filename, "dok_halaman": n_hal}


def _mask_nip(nip) -> str:
    """Masking NIP untuk tampilan publik: hanya 3 digit terakhir terlihat."""
    s = str(nip or "").strip()
    if len(s) <= 3:
        return s
    return "•" * (len(s) - 3) + s[-3:]


def _peran_pengelola_ttd(user: dict) -> bool:
    """True bila peran user berhak MENGURUS permintaan TTD satkernya — admin
    MAUPUN operator.

    Mandat pemilik: langkah "atur letak QR" menahan unduhan SEMUA pihak
    (penanda tangan & pemindai QR), jadi ia tak boleh menunggu satu orang
    ber-role admin. Operator satker yang sama harus bisa membereskannya
    sendiri, berikut melihat penandanya di daftar.

    Viewer tetap pembaca murni: bukan pengelola. Akun lama tanpa field role
    dan role legacy 'user' diperlakukan sebagai operator (sejalan dengan
    require_writer)."""
    peran = str((user or {}).get("role") or "operator").strip().lower()
    return peran != "viewer"


def _cek_satker_sr(sr: dict, user: dict) -> None:
    """403 bila permintaan milik satker LAIN. Semantik meniru
    pastikan_akses_dok_satker: permintaan era lama tanpa kode tetap terbuka;
    user tanpa kode (super-admin) lintas-satker."""
    from shared_utils import kode_satker_user
    kode = kode_satker_user(user)
    milik = str((sr or {}).get("kode_satker") or "").strip()
    if kode and milik and milik != kode:
        raise HTTPException(
            status_code=403,
            detail=f"Permintaan milik satker {milik} — akun Anda terikat "
                   f"satker {kode}")


def _pastikan_pengelola_sr(sr: dict, user: dict) -> None:
    """403 bila user bukan pembuat permintaan DAN bukan pengelola (admin atau
    operator) SATKER YANG SAMA.

    Gerbang untuk jalur MENGURUS & MEMBACA: detail, pratinjau halaman, atur
    letak QR, dan unduh dokumen ber-TTD. Isolasi lintas-satker tetap tegak —
    yang dilonggarkan hanya sekat peran DI DALAM satker, supaya pekerjaan
    tidak menggantung menunggu admin (lihat _peran_pengelola_ttd).

    Tindakan yang tak bisa ditarik kembali (batal permintaan, terbitkan ulang
    link e-sign) TIDAK memakai gerbang ini — lihat _pastikan_pemilik_sr."""
    if (sr or {}).get("created_by") == (user or {}).get("username"):
        return
    if not _peran_pengelola_ttd(user):
        raise HTTPException(
            status_code=403,
            detail="Hanya pembuat permintaan atau pengelola satker "
                   "(admin/operator) yang berhak")
    _cek_satker_sr(sr, user)


def _pastikan_pemilik_sr(sr: dict, user: dict) -> None:
    """403 bila user bukan pembuat permintaan & bukan admin SATKER YANG SAMA.

    Lebih ketat dari _pastikan_pengelola_sr dan SENGAJA dipertahankan untuk
    tindakan yang tak bisa ditarik kembali: membatalkan permintaan (berkaskade
    menandai BAST/aset 'dicabut') dan menerbitkan ULANG link e-sign (sama
    dengan membagikan hak menandatangani dokumen resmi). Melonggarkan yang ini
    ke seluruh operator bukan bagian dari mandat "operator boleh mengatur QR".

    Semantik satker meniru pastikan_akses_dok_satker: dokumen era lama tanpa
    kode tetap terbuka; user tanpa kode (super-admin) lintas-satker."""
    if (sr or {}).get("created_by") == (user or {}).get("username"):
        return
    if (user or {}).get("role") != "admin":
        raise HTTPException(status_code=403,
                            detail="Hanya pembuat permintaan atau admin yang berhak")
    _cek_satker_sr(sr, user)


async def _ambil_dokumen_sr(sr_id: str):
    """(sr, bytes PDF asli) — 404 bila permintaan/dokumen tak ada."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    fid = str(sr.get("dok_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404,
                            detail="Permintaan ini tidak melampirkan dokumen")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas dokumen tidak ditemukan")
    return sr, data


def _tolak_bila_batal(sr: dict) -> None:
    """410 bila permintaan TTD sudah DIBATALKAN — berkas ber-tanda tangan /
    lembar pengesahan / gambar TTD tidak boleh lagi disajikan seolah sah
    (celah A2). Halaman verifikasi publik menandai 'dibatalkan' terpisah."""
    if (sr or {}).get("status") == "batal":
        raise HTTPException(
            status_code=410,
            detail="Permintaan TTD telah dibatalkan — tanda tangan tidak berlaku")


@ttd_router.get("/ttd/permintaan/{sr_id}/dokumen")
async def dokumen_asli(sr_id: str,
                       user: dict = Depends(require_user_or_query_token)):
    """Stream dokumen PDF asli (pratinjau dasbor pembuat)."""
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_pengelola_sr(sr, user)
    return StreamingResponse(
        io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{sr.get("dok_nama", "dokumen.pdf")}"',
                 "X-Content-Type-Options": "nosniff"})


def _pastikan_jti_signer(sr: dict, tok: dict):
    """401 bila token bukan milik signer terdaftar ATAU jti-nya sudah diganti
    (terbit ulang) — link lama yang dicabut tidak boleh lagi membaca dokumen."""
    sg = next((s for s in (sr.get("signers") or [])
               if s.get("signer_id") == tok.get("signer")), None)
    if not sg or sg.get("jti") != tok.get("jti"):
        raise HTTPException(status_code=401,
                            detail="Link ini sudah tidak berlaku (telah diterbitkan ulang)")


@ttd_router.get("/ttd/tandatangan/{sr_id}/dokumen")
async def dokumen_untuk_penanda_tangan(sr_id: str,
                                       tok: dict = Depends(require_sign_token)):
    """Stream dokumen asli untuk PENANDA TANGAN (via link e-sign) — agar yang
    meneken bisa MEMBACA dulu apa yang ditandatanganinya."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_jti_signer(sr, tok)
    return StreamingResponse(
        io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{sr.get("dok_nama", "dokumen.pdf")}"',
                 # Content-Length → viewer PDF HP bisa menampilkan progres
                 # unduhan alih-alih layar kosong tanpa kabar.
                 "Content-Length": str(len(data)),
                 "X-Content-Type-Options": "nosniff"})


# pdfium BUKAN pustaka aman-thread: dua render bersamaan meng-SIGSEGV seluruh
# proses (terukur 5/5 pada 6 thread; dengan --workers 2 itu separuh kapasitas
# hilang sampai supervisor restart). Executor 1-thread memberi tiga hal
# sekaligus — event loop bebas, render terserialisasi di SATU thread yang
# sama, dan pool bawaan asyncio.to_thread tak ikut terpakai (thumbnail
# assets.py dan to_thread lain tidak jadi lapar). `to_thread` telanjang di
# sini menukar "lambat" dengan "mati".
_PDFIUM_EXEC = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdfium")


def _render_halaman_bytes(data: bytes, no: int) -> tuple:
    """(bytes PNG, total halaman) — MURNI + SINKRON. WAJIB dipanggil lewat
    `_render_halaman_png` (executor tunggal di atas); memanggilnya dari dua
    thread bersamaan meng-crash proses."""
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(data))
    except Exception:
        raise HTTPException(status_code=422, detail="Dokumen tidak dapat dirender")
    try:
        total = len(pdf)
        idx = min(max(1, int(no)), total) - 1
        page = pdf[idx]
        # Skala menuju lebar ±1100px — cukup tajam untuk pratinjau posisi,
        # ringan diunduh di jaringan seluler. Tinggi ikut dibatasi (halaman
        # ekstrem memanjang tidak boleh menghasilkan bitmap raksasa).
        skala = 1100 / max(1.0, page.get_width())
        skala = min(skala, 2400 / max(1.0, page.get_height()))
        skala = min(2.0, max(0.3, skala))
        pil = page.render(scale=skala).to_pil()
        buf = io.BytesIO()
        # compress_level=3, DIUKUR pada halaman naskah 1100px (bawaan = 6):
        # encode 103 -> 64 ms DAN 652 -> 516 KB — lebih cepat sekaligus
        # lebih kecil. Penting karena executor di bawah TUNGGAL: waktu encode
        # langsung membatasi laju semua pratinjau. Level 0 ditolak (5 MB).
        pil.save(buf, format="PNG", compress_level=3)
    finally:
        pdf.close()
    return buf.getvalue(), total


async def _render_halaman_png(data: bytes, no: int):
    """Satu halaman PDF dirender PNG untuk PRATINJAU penempatan (tanda tangan
    MAUPUN QR). Dipakai bersama jalur penanda tangan (token e-sign) dan jalur
    pemilik dokumen (sesi login) supaya keduanya melihat gambar yang sama
    persis dengan yang jadi acuan koordinat. Render ±100–130 ms per halaman
    (pdfium 11 ms + encode PNG Pillow 87 ms) kini di executor, bukan di event
    loop — temuan S7."""
    png, total = await asyncio.get_running_loop().run_in_executor(
        _PDFIUM_EXEC, _render_halaman_bytes, data, no)
    return StreamingResponse(
        io.BytesIO(png), media_type="image/png",
        headers={"Cache-Control": "private, max-age=600",
                 "X-Jumlah-Halaman": str(total),
                 "X-Content-Type-Options": "nosniff"})


async def _dokumen_dengan_ttd_masuk(sr: dict, sr_id: str, data: bytes) -> bytes:
    """Dokumen + tanda tangan yang SUDAH masuk (tanpa QR) untuk pratinjau.

    Mode paralel: siapa pun yang meneken berikutnya melihat bubuhan rekan yang
    lebih dulu, sehingga tak menempatkan tanda tangannya bertumpuk. Bila belum
    ada yang meneken — atau perakitan gagal — dokumen asli dipakai apa adanya
    (pratinjau tak boleh gagal hanya karena hiasan)."""
    if not any(str(s.get("signature_file_id") or "").strip()
               for s in (sr.get("signers") or [])):
        return data
    try:
        return (await _bangun_pdf_ber_ttd(sr, sr_id, data,
                                          sertakan_qr=False)).getvalue()
    except Exception:
        return data


@ttd_router.get("/ttd/tandatangan/{sr_id}/dokumen/halaman/{no}")
@limiter.limit("60/minute")
async def halaman_dokumen_penanda_tangan(sr_id: str, no: int, request: Request,
                                         tok: dict = Depends(require_sign_token)):
    """Render SATU halaman dokumen sebagai PNG untuk PRATINJAU PEMBUBUHAN di
    halaman publik — penanda tangan memilih letak & ukuran tanda tangannya
    langsung di atas gambar halaman (tanpa perlu mengunduh PDF penuh)."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    _sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_jti_signer(_sr, tok)
    return await _render_halaman_png(await _dokumen_dengan_ttd_masuk(_sr, sr_id, data), no)


@ttd_router.get("/ttd/permintaan/{sr_id}/dokumen/halaman/{no}")
@limiter.limit("60/minute")
async def halaman_dokumen_pemilik(sr_id: str, no: int, request: Request,
                                  user: dict = Depends(require_user_or_query_token)):
    """Pratinjau halaman untuk PEMILIK dokumen — dipakai saat mengatur letak &
    ukuran QR verifikasi sebelum mengunduh dokumen ber-TTD (langkah terakhir,
    setelah semua pihak meneken)."""
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_pengelola_sr(sr, user)
    _tolak_bila_batal(sr)
    return await _render_halaman_png(await _dokumen_dengan_ttd_masuk(sr, sr_id, data), no)


class PosisiQrIn(BaseModel):
    # None = QR kembali OTOMATIS (pojok kanan-bawah halaman terakhir).
    posisi_qr: dict | None = None


@ttd_router.put("/ttd/permintaan/{sr_id}/posisi-qr")
async def atur_posisi_qr(sr_id: str, payload: PosisiQrIn,
                         user: dict = Depends(require_writer)):
    """Atur letak & ukuran QR verifikasi pada dokumen ber-TTD — SEKALI, oleh
    pemilik dokumen, sebagai langkah terakhir sebelum mengunduh (mandat
    pemilik: bukan lagi per penanda tangan). Idempoten; `posisi_qr: null`
    mengembalikan QR ke slot otomatis."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pengelola_sr(sr, user)
    _tolak_bila_batal(sr)
    if not str(sr.get("dok_file_id") or "").strip():
        raise HTTPException(status_code=400, detail=(
            "Permintaan ini tidak melampirkan dokumen — tak ada halaman untuk "
            "menempatkan QR"))
    if sr.get("status") != "selesai" or not _semua_terverifikasi(sr):
        raise HTTPException(status_code=409, detail=(
            "QR final baru dapat ditempatkan setelah seluruh pembubuhan "
            "divalidasi operator/admin satker"))
    posisi = _posisi_qr_bersih(payload.posisi_qr,
                               int(sr.get("dok_halaman") or 0))
    await db.signature_requests.update_one({"id": sr_id},
                                           {"$set": {"posisi_qr": posisi}})
    await log_audit("atur_posisi_qr_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=("QR verifikasi diatur manual" if posisi
                            else "QR verifikasi kembali otomatis"))
    return {"ok": True, "posisi_qr": posisi}


async def _bangun_pdf_ber_ttd(sr: dict, sr_id: str, data: bytes,
                              sertakan_qr: bool = True) -> io.BytesIO:
    """PDF dokumen + BUBUHAN tanda tangan yang SUDAH masuk → BytesIO.

    `sertakan_qr=False` menghasilkan versi TANPA QR verifikasi — dipakai untuk
    PRATINJAU: penanda tangan berikutnya (mode paralel, siapa pun yang lebih
    dulu) melihat tanda tangan rekan yang sudah masuk sehingga tak menimpanya,
    dan pemilik melihat tata letak sesungguhnya saat menempatkan QR di langkah
    terakhir. QR sengaja tidak ikut pratinjau karena letaknya baru ditentukan
    pada tahap unduh.

    Fungsi ini hanya MENGUMPULKAN data async (blob ttd GridFS, status
    kepegawaian, link verifikasi pendek); perakitan pypdf + ReportLab — bagian
    yang benar-benar makan CPU pada dokumen berhalaman banyak — ada di
    `_rakit_pdf_ber_ttd` dan dijalankan lewat thread. Dulu keduanya menyatu
    dan 4 await di tengah badan membuatnya tak bisa sekadar dibungkus
    to_thread (sisa temuan S7 yang sengaja ditunda ke PR-nya sendiri).
    Bukan `_PDFIUM_EXEC`: perakitan tidak menyentuh pypdfium2 sama sekali,
    dan menaruhnya di executor tunggal itu justru mengantre di belakang
    render pratinjau tanpa alasan."""
    from shared_utils import status_kepegawaian_by_nip

    penanda = [s for s in (sr.get("signers") or [])
               if str(s.get("signature_file_id") or "").strip()]
    gambar = {}
    for s in penanda:
        fid = s["signature_file_id"]
        if fid not in gambar:
            gambar[fid] = await get_document_from_gridfs(fid)
    # Status kepegawaian hanya dipakai baris NIP slot OTOMATIS (aturan privasi
    # Non-ASN/NIK) — penanda posisi-pilihan tak mencetak baris NIP.
    status_nip = {}
    for s in penanda:
        if (not isinstance(s.get("posisi_ttd"), dict) and s.get("nip")
                and s["nip"] not in status_nip):
            status_nip[s["nip"]] = await status_kepegawaian_by_nip(s["nip"])
    # URL verifikasi publik (dipakai QR otomatis MAUPUN posisi pilihan).
    # Bentuk PENDEK: isi QR jadi jauh lebih ringkas → modulnya lebih renggang
    # dan lebih mudah dipindai kamera HP pada ukuran cetak kecil (±2 cm).
    verif = await _link_verifikasi_pendek(
        sr_id, kode_satker=str(sr.get("kode_satker") or ""))
    return await asyncio.to_thread(_rakit_pdf_ber_ttd, sr, sr_id, data,
                                   gambar, status_nip, verif, sertakan_qr)


def _rakit_pdf_ber_ttd(sr: dict, sr_id: str, data: bytes, gambar: dict,
                       status_nip: dict, verif: str,
                       sertakan_qr: bool = True) -> io.BytesIO:
    """SINKRON murni (pypdf + ReportLab) — panggil lewat asyncio.to_thread.

    `gambar`: {signature_file_id: bytes|None}; `status_nip`: {nip: status}.
    Blob yang hilang (None) berperilaku sama dengan sebelum pemisahan:
    posisi-pilihan dilewati utuh, slot otomatis tetap mencetak nama tanpa
    gambar."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.units import mm as rl_mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    penanda = [s for s in (sr.get("signers") or [])
               if str(s.get("signature_file_id") or "").strip()]
    reader = PdfReader(io.BytesIO(data))

    # Pisahkan penanda tangan ber-POSISI PILIHAN (diatur sendiri di halaman
    # publik: halaman + x/y/lebar fraksi) dari yang memakai slot otomatis.
    otomatis = [s for s in penanda if not isinstance(s.get("posisi_ttd"), dict)]

    # SATU penanda tangan bisa punya BANYAK pembubuhan: posisi utamanya plus
    # tiap entri `posisi_ttd_lain` (lembar lanjutan / lampiran pernyataan).
    # Peta ini karena itu berisi PASANGAN (penanda tangan, posisi), bukan
    # penanda tangannya saja — dulu satu orang hanya bisa muncul sekali, dan
    # lembar keduanya terbit kosong.
    per_halaman = {}
    for s in penanda:
        semua_pos = []
        if isinstance(s.get("posisi_ttd"), dict):
            semua_pos.append(s["posisi_ttd"])
        for p in (s.get("posisi_ttd_lain") or []):
            if isinstance(p, dict):
                semua_pos.append(p)
        for p in semua_pos:
            idx = min(max(1, int(p.get("halaman") or 1)), len(reader.pages)) - 1
            per_halaman.setdefault(idx, []).append((s, p))

    # QR verifikasi: posisi/ukuran pilihan (dokumen-level) bila diatur penanda
    # tangan; jika tidak → slot otomatis pojok kanan-bawah halaman terakhir.
    qr_pos = (sr.get("posisi_qr")
              if sertakan_qr and isinstance(sr.get("posisi_qr"), dict) else None)
    qr_idx = (min(max(1, int(qr_pos.get("halaman") or 1)), len(reader.pages)) - 1
              if qr_pos else None)

    # Halaman ber-/Rotate: pratinjau posisi dirender pypdfium2 PASCA-rotasi,
    # sedangkan mediabox pypdf PRA-rotasi — normalisasi rotasi ke konten dulu
    # supaya overlay (posisi pilihan MAUPUN slot otomatis) WYSIWYG dengan
    # tampilan. Berlaku untuk semua halaman yang menerima overlay.
    for idx in (set(per_halaman) | {len(reader.pages) - 1}
                | ({qr_idx} if qr_idx is not None else set())):
        try:
            if (reader.pages[idx].rotation or 0) % 360 != 0:
                reader.pages[idx].transfer_rotation_to_content()
        except Exception:
            pass

    hal_akhir = reader.pages[-1]
    lebar = float(hal_akhir.mediabox.width)
    tinggi = float(hal_akhir.mediabox.height)

    # ── Overlay POSISI PILIHAN: gambar ttd + keterangan kecil di halaman &
    #    koordinat yang dipilih penanda tangan sendiri ──
    overlay_kustom = {}
    for idx, daftar in per_halaman.items():
        hal = reader.pages[idx]
        hw = float(hal.mediabox.width)
        hh = float(hal.mediabox.height)
        buf_k = io.BytesIO()
        ck = rl_canvas.Canvas(buf_k, pagesize=(hw, hh))
        ada_isi = False
        for s, p in daftar:
            img_data = gambar.get(s["signature_file_id"])
            if not img_data:
                continue
            try:
                img = ImageReader(io.BytesIO(img_data))
                iw, ih = img.getSize()
                # lebar/x/y sudah dijepit _posisi_bersih saat kirim (fraksi);
                # jepit ULANG terhadap tepi halaman nyata (tepi bawah/kanan
                # bergantung rasio gambar yang tidak diketahui saat kirim).
                w_pt = float(p.get("lebar") or 0.25) * hw
                h_pt = w_pt * (ih / iw)
                if h_pt > hh - 6:
                    h_pt = hh - 6
                    w_pt = h_pt * (iw / ih)
                x_pt = min(float(p.get("x") or 0) * hw, hw - w_pt)
                y_pt = max(3.0, hh - float(p.get("y") or 0) * hh - h_pt)
                ck.drawImage(img, x_pt, y_pt, width=w_pt, height=h_pt,
                             mask="auto")
                # Jejak identitas: MENYAMPING di sisi kiri-bawah tanda tangan,
                # sangat kecil & hampir menyatu dengan kertas, tanggal di baris
                # bawah nama. Digambar setelah rotate(90) sehingga berjalan ke
                # atas halaman; baris berikutnya bergeser menjauh dari tanda
                # tangan, jadi jejak ini tak pernah menimpa gambarnya maupun
                # naskah di sebelah kanannya.
                pangkal_x, pangkal_y, baris_jejak = jejak_identitas_ttd(
                    s.get("nama"), s.get("signed_at"), x_pt, y_pt,
                    tinggi=h_pt,
                    ukur=lambda t: ck.stringWidth(t, "Helvetica", JEJAK_TTD_FONT))
                if baris_jejak:
                    ck.saveState()
                    ck.setFont("Helvetica", JEJAK_TTD_FONT)
                    ck.setFillGray(JEJAK_TTD_ABU)
                    ck.translate(pangkal_x, pangkal_y)
                    ck.rotate(90)
                    for teks, geser in baris_jejak:
                        ck.drawString(0, geser, teks)
                    ck.restoreState()
                ada_isi = True
            except Exception:
                pass
        ck.save()
        buf_k.seek(0)
        # Canvas tanpa operasi menghasilkan PDF 0 halaman — jangan sampai
        # satu blob hilang membuat SELURUH unduhan dokumen-ttd gagal.
        if ada_isi:
            try:
                overlay_kustom[idx] = PdfReader(buf_k).pages[0]
            except Exception:
                pass

    # ── Overlay slot OTOMATIS halaman terakhir: berderet maks 3/baris ──
    buf_ov = io.BytesIO()
    c = rl_canvas.Canvas(buf_ov, pagesize=(lebar, tinggi))
    margin = 14 * rl_mm
    per_baris = min(3, max(1, len(otomatis)))
    slot_w = (lebar - 2 * margin) / per_baris
    slot_h = 30 * rl_mm
    for i, s in enumerate(otomatis):
        kol = i % per_baris
        brs = i // per_baris
        x = margin + kol * slot_w
        y = margin + brs * slot_h
        c.setFont("Helvetica", 6.5)
        c.setFillGray(0.35)
        c.drawCentredString(x + slot_w / 2, y + slot_h - 8,
                            "Ditandatangani secara elektronik")
        c.setFillGray(0)
        img_data = gambar.get(s["signature_file_id"])
        if img_data:
            try:
                img = ImageReader(io.BytesIO(img_data))
                iw, ih = img.getSize()
                maks_w, maks_h = slot_w - 8 * rl_mm, 13 * rl_mm
                sk = min(maks_w / iw, maks_h / ih)
                c.drawImage(img, x + (slot_w - iw * sk) / 2,
                            y + slot_h - 10 - ih * sk,
                            width=iw * sk, height=ih * sk, mask="auto")
            except Exception:
                pass
        c.setFont("Helvetica-Bold", 8)
        nama_y = y + 9 * rl_mm
        c.drawCentredString(x + slot_w / 2, nama_y, str(s.get("nama") or "")[:38])
        # Garis bawah nama dibatasi ±70mm agar tak membentang penuh saat
        # penanda tangan tunggal (slot = selebar halaman).
        garis_w = min(slot_w - 12 * rl_mm, 70 * rl_mm)
        c.setLineWidth(0.5)
        c.line(x + (slot_w - garis_w) / 2, nama_y - 1.5,
               x + (slot_w + garis_w) / 2, nama_y - 1.5)
        c.setFont("Helvetica", 6.5)
        info = []
        if s.get("jabatan"):
            info.append(str(s["jabatan"])[:40])
        if s.get("nip"):
            # Aturan privasi: penanda tangan Non-ASN (status dari registry
            # pejabat/Master Pegawai per NIP) atau nomor berformat NIK →
            # baris NIP/NIK tidak dicetak di stempel dokumen.
            from pegawai_utils import baris_identitas_laporan
            b_nip = baris_identitas_laporan(
                s["nip"], status_nip.get(s["nip"], ""))
            if b_nip:
                info.append(b_nip)
        if s.get("signed_at"):
            info.append(str(s["signed_at"])[:10])
        for j, baris in enumerate(info[:3]):
            c.drawCentredString(x + slot_w / 2, nama_y - 8 - j * 7, baris)
    # QR otomatis pojok kanan-bawah HANYA bila QR tak diatur posisinya sendiri.
    if sertakan_qr and qr_pos is None:
        try:
            from reportlab.graphics import renderPDF

            from routes.cards import build_qr_flowable
            qr = build_qr_flowable(verif, 12 * rl_mm)
            if qr is not None:
                renderPDF.draw(qr, c, lebar - margin - 12 * rl_mm, 2 * rl_mm)
            c.setFont("Helvetica", 5.5)
            c.setFillGray(0.4)
            c.drawRightString(lebar - margin - 13 * rl_mm, 5 * rl_mm,
                              f"Verifikasi: {sr_id[:8]}")
        except Exception:
            pass
    c.save()
    buf_ov.seek(0)

    # Kanvas slot otomatis bisa KOSONG — tak ada penanda tangan yang memakai
    # slot bawaan DAN QR tak digambar otomatis (QR sudah ditempatkan manual,
    # atau ini pratinjau tanpa QR). Kanvas tanpa gambar apa pun menghasilkan
    # PDF NOL halaman, dan `pages[0]` melempar IndexError → dokumen gagal
    # dirakit. Perlakukan sebagai "tidak ada overlay" alih-alih meledak.
    try:
        overlay = PdfReader(buf_ov).pages[0]
    except IndexError:
        overlay = None

    # ── Overlay QR POSISI PILIHAN (dokumen-level): pada halaman & koordinat/
    #    ukuran yang diatur, sisi minimal QR_MIN_MM agar tetap dapat dipindai ──
    overlay_qr = None
    if qr_pos is not None and qr_idx is not None:
        halq = reader.pages[qr_idx]
        qw = float(halq.mediabox.width)
        qh = float(halq.mediabox.height)
        # Sisi QR (kotak persegi): fraksi lebar halaman, tapi tak kurang dari
        # QR_MIN_MM (scannable) dan tak melebihi halaman.
        side = max(QR_MIN_MM * rl_mm, float(qr_pos.get("lebar") or 0.16) * qw)
        side = min(side, qw - 4, qh - 4)
        x_left = min(max(0.0, float(qr_pos.get("x") or 0) * qw), qw - side)
        # (x,y) posisi = pojok KIRI-ATAS kotak (fraksi) → koord bawah ReportLab.
        y_bottom = max(2.0, qh - float(qr_pos.get("y") or 0) * qh - side)
        buf_q = io.BytesIO()
        cq = rl_canvas.Canvas(buf_q, pagesize=(qw, qh))
        try:
            from reportlab.graphics import renderPDF

            from routes.cards import build_qr_flowable
            qrf = build_qr_flowable(verif, side)
            if qrf is not None:
                renderPDF.draw(qrf, cq, x_left, y_bottom)
            cq.setFont("Helvetica", 5.5)
            cq.setFillGray(0.4)
            cq.drawCentredString(x_left + side / 2, max(1.0, y_bottom - 6),
                                 f"Verifikasi: {sr_id[:8]}")
        except Exception:
            pass
        cq.save()
        buf_q.seek(0)
        try:
            overlay_qr = (qr_idx, PdfReader(buf_q).pages[0])
        except Exception:
            overlay_qr = None
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in overlay_kustom:
            page.merge_page(overlay_kustom[idx])
        if overlay_qr is not None and idx == overlay_qr[0]:
            # QR verifikasi di posisi/ukuran pilihan (bisa halaman mana pun).
            page.merge_page(overlay_qr[1])
        if overlay is not None and idx == len(reader.pages) - 1:
            # Slot ttd otomatis (+ QR otomatis bila tak diatur) di halaman akhir.
            page.merge_page(overlay)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def _semua_sudah_ttd(sr: dict) -> bool:
    daftar = sr.get("signers") or []
    return bool(daftar) and all(
        str(s.get("signature_file_id") or "").strip() for s in daftar)


def _semua_terverifikasi(sr: dict) -> bool:
    daftar = sr.get("signers") or []
    return bool(daftar) and all(sudah_terverifikasi(s) for s in daftar)


def _qr_sudah_diatur(sr: dict) -> bool:
    return isinstance(sr.get("posisi_qr"), dict)


def _siap_diunduh(sr: dict) -> bool:
    """Dokumen ber-TTD boleh dibagikan ke penanda tangan & pemindai QR HANYA
    setelah (a) semua pihak meneken dan (b) pemilik menempatkan QR verifikasi.
    Syarat (b) sengaja: tanpa itu QR jatuh di slot otomatis yang bisa menimpa
    kaki halaman — dan status "belum diatur" itulah yang dipakai layar
    pengelola (admin maupun operator) sebagai penanda agar segera diatur."""
    return (sr.get("status") == "selesai" and _semua_terverifikasi(sr)
            and _semua_sudah_ttd(sr)
            and _qr_sudah_diatur(sr)
            and bool(str(sr.get("dok_file_id") or "").strip()))


async def _catat_penyelesaian_ttd(sr: dict, sr_id: str) -> None:
    """Tulis tautan balik ke dokumen sumber SETELAH validasi final.

    Pada alur lama tautan ini ditulis segera setelah semua orang mengirim
    gambar TTD. Sekarang itu terlalu dini: hasilnya masih harus diperiksa
    operator/admin satker. Query ikut dibatasi kode satker permintaan agar
    ``doc_ref`` mentah tidak dapat menulis record satker lain.
    """
    doc_type = str((sr or {}).get("doc_type") or "").strip().lower()
    doc_ref = str((sr or {}).get("doc_ref") or "").strip()
    if not doc_ref:
        return
    q = {"id": doc_ref}
    kode = str((sr or {}).get("kode_satker") or "").strip()
    if kode:
        q["kode_satker"] = kode
    now_iso = datetime.now(timezone.utc).isoformat()
    if doc_type == "bast":
        hasil = await db.bast_serah_terima.update_one(
            q, {"$set": {"signature_request_id": sr_id,
                         "tt_esign_selesai_pada": now_iso,
                         "tt_dicabut": False}})
        if hasil.matched_count:
            await db.assets.update_many(
                {"bast_terakhir.id": doc_ref,
                 **({"kode_satker": kode} if kode else {}),
                 "bast_terakhir.tt_dicabut": True},
                {"$set": {"bast_terakhir.tt_dicabut": False}})
    elif doc_type == "lpb":
        await db.lpb.update_one(
            q, {"$set": {"signature_request_id": sr_id,
                         "tt_esign_selesai_pada": now_iso,
                         "tt_dicabut": False}})


def _respons_pdf_ttd(sr: dict, out: io.BytesIO):
    nama_dok = str(sr.get("dok_nama") or "dokumen.pdf").rsplit(".", 1)[0]
    final = sr.get("status") == "selesai" and _semua_terverifikasi(sr)
    akhiran = "ber-TTD" if final else "DRAF-pemeriksaan-TTD"
    return StreamingResponse(
        out, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{nama_dok}_{akhiran}.pdf"',
                 "X-Document-Status": "final" if final else "draft-review",
                 "X-Content-Type-Options": "nosniff"})


@ttd_router.get("/ttd/permintaan/{sr_id}/dokumen-ttd")
async def dokumen_ber_ttd(sr_id: str,
                          user: dict = Depends(require_user_or_query_token)):
    """Dokumen PDF asli DENGAN BUBUHAN tanda tangan elektronik: gambar ttd +
    nama/NIP/jabatan + waktu per penanda tangan yang sudah meneken, plus QR
    verifikasi & kode. Dibangun on-the-fly sehingga selalu memuat tanda tangan
    terbaru."""
    sr, data = await _ambil_dokumen_sr(sr_id)
    # IDOR (REVIEW-9 R11): dokumen ber-TTD memuat gambar tanda tangan +
    # NIP + jabatan penanda tangan. Guard pemilik/satker yang sama sudah
    # dipakai endpoint saudaranya — di sini terlewat.
    _pastikan_pengelola_sr(sr, user)
    _tolak_bila_batal(sr)  # dokumen ber-TTD dari permintaan batal → tak berlaku
    if not any(str(s.get("signature_file_id") or "").strip()
               for s in (sr.get("signers") or [])):
        raise HTTPException(status_code=400,
                            detail="Belum ada tanda tangan yang masuk")
    final = sr.get("status") == "selesai" and _semua_terverifikasi(sr)
    return _respons_pdf_ttd(
        sr, await _bangun_pdf_ber_ttd(sr, sr_id, data, sertakan_qr=final))


@ttd_router.get("/ttd/tandatangan/{sr_id}/dokumen-ttd")
async def dokumen_ber_ttd_penanda_tangan(sr_id: str,
                                         tok: dict = Depends(require_sign_token)):
    """Unduhan dokumen ber-TTD untuk PENANDA TANGAN lewat link e-sign-nya —
    tersedia setelah semua pihak meneken DAN pemilik menempatkan QR."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_jti_signer(sr, tok)
    _tolak_bila_batal(sr)
    if not _siap_diunduh(sr):
        raise HTTPException(status_code=409, detail=(
            "Dokumen ber-tanda tangan belum siap — menunggu seluruh pihak "
            "menandatangani dan penempatan QR verifikasi oleh penerbit"))
    return _respons_pdf_ttd(sr, await _bangun_pdf_ber_ttd(sr, sr_id, data))


@ttd_router.get("/ttd/verifikasi/{sr_id}/dokumen-ttd")
@limiter.limit("30/minute")
async def dokumen_ber_ttd_verifikasi(sr_id: str, request: Request):
    """Unduhan dokumen ber-TTD dari halaman VERIFIKASI (dibuka lewat pemindaian
    QR pada dokumen). Terbuka bagi pemegang tautan verifikasi — id-nya UUID
    acak dan hanya tercetak pada dokumen itu sendiri — dan HANYA setelah semua
    pihak meneken serta QR ditempatkan; permintaan yang dibatalkan ditolak."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _tolak_bila_batal(sr)
    if not _siap_diunduh(sr):
        raise HTTPException(status_code=409, detail=(
            "Dokumen ber-tanda tangan belum siap diunduh"))
    data = await get_document_from_gridfs(str(sr.get("dok_file_id") or ""))
    if not data:
        raise HTTPException(status_code=404, detail="Berkas dokumen tidak ditemukan")
    return _respons_pdf_ttd(sr, await _bangun_pdf_ber_ttd(sr, sr_id, data))


@ttd_router.get("/ttd/permintaan")
async def daftar_permintaan(_user: dict = Depends(require_user)):
    """Daftar permintaan tanda tangan (terbaru dulu) + ringkas status.
    Viewer hanya melihat permintaan buatannya sendiri; IP penanda tangan
    tidak pernah ikut daftar (data forensik — cukup di audit internal)."""
    # PENGELOLA (admin MAUPUN operator) melihat permintaan SATKERNYA — bukan
    # seluruh DB. Dulu hanya role=='admin', sehingga penanda "PERLU ATUR LETAK
    # QR" tak pernah sampai ke operator: pekerjaan yang menahan unduhan semua
    # pihak jadi menggantung menunggu satu orang. Viewer (pembaca murni) tetap
    # sebatas buatannya sendiri. Super-admin (tanpa kode satker) lintas-satker.
    from shared_utils import scope_query_field_satker
    q = (scope_query_field_satker(_user, {}) if _peran_pengelola_ttd(_user)
         else {"created_by": _user.get("username", "")})
    items = await (db.signature_requests.find(
        q, {**_PROJ, "signers.jti": 0, "signers.ip": 0})
                   .sort("created_at", -1).limit(200).to_list(200))
    for it in items:
        sg = it.get("signers") or []
        it["version"] = int(it.get("version", 1) or 1)
        it["label_jenis"] = label_jenis_ttd(it.get("doc_type"))
        it["judul_tampil"] = judul_ttd_tampil(it.get("judul"), it.get("doc_type"))
        it["jumlah"] = len(sg)
        it["membubuhkan_jumlah"] = sum(1 for s in sg if sudah_membubuhkan(s))
        it["selesai_jumlah"] = sum(1 for s in sg if sudah_terverifikasi(s))
        it["menunggu_validasi_jumlah"] = sum(
            1 for s in sg if s.get("status") == "menunggu_validasi")
        it["perlu_validasi"] = (it.get("status") != "batal"
                                and it["menunggu_validasi_jumlah"] > 0)
        # Penanda kerja untuk layar admin: yang SUDAH lengkap diteken tapi QR-nya
        # belum ditempatkan menahan unduhan bagi penanda tangan & pemindai QR —
        # tampilkan mencolok supaya segera dibereskan.
        it["perlu_atur_qr"] = (it.get("status") == "selesai"
                               and bool(str(it.get("dok_file_id") or "").strip())
                               and _semua_terverifikasi(it)
                               and not _qr_sudah_diatur(it))
        it["siap_diunduh"] = _siap_diunduh(it)
        # Sisa waktu kartu = batas TERCEPAT di antara penanda tangan yang BELUM
        # meneken. Yang sudah meneken tak lagi relevan, dan menampilkan batas
        # terjauh akan menyembunyikan tautan yang justru hampir mati.
        it["kedaluwarsa_terdekat"] = kedaluwarsa_terdekat(it)
    return {"items": items}


@ttd_router.get("/ttd/permintaan/{sr_id}")
async def detail_permintaan(sr_id: str, user: dict = Depends(require_user)):
    """Detail status per penanda tangan (untuk dasbor pembuat)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, {**_PROJ, "signers.jti": 0})
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pengelola_sr(sr, user)  # isolasi: pembuat/pengelola satker
    # Sisa waktu PER penanda tangan — inilah "per masing-masing" yang dipakai
    # layar registrasi untuk memutuskan siapa yang perlu ditagih/diterbitkan
    # ulang tautannya.
    for _sg in (sr.get("signers") or []):
        _sg["kedaluwarsa_info"] = _sisa_kedaluwarsa(_sg, sr)
    return {**sr,
            "version": int(sr.get("version", 1) or 1),
            "label_jenis": label_jenis_ttd(sr.get("doc_type")),
            "judul_tampil": judul_ttd_tampil(sr.get("judul"), sr.get("doc_type")),
            "perlu_validasi": any(
                s.get("status") == "menunggu_validasi" for s in sr.get("signers") or []),
            "perlu_atur_qr": (sr.get("status") == "selesai"
                              and bool(str(sr.get("dok_file_id") or "").strip())
                              and _semua_terverifikasi(sr)
                              and not _qr_sudah_diatur(sr)),
            "siap_diunduh": _siap_diunduh(sr)}


@ttd_router.post("/ttd/permintaan/{sr_id}/validasi/{signer_id}")
async def validasi_pembubuhan(
    sr_id: str, signer_id: str, payload: ValidasiPembubuhanIn,
    request: Request, user: dict = Depends(require_writer),
):
    """Validasi atau buka ulang pembubuhan SATU penanda tangan.

    ``If-Match`` wajib agar dua validator tidak menimpa keputusan satu sama
    lain. ``Idempotency-Key`` mencegah klik/kiriman ulang membuat dua catatan
    validasi atau dua tautan baru. Dokumen yang sudah final tidak dapat dibuka
    ulang lewat jalur koreksi internal ini; setelah terbit harus memakai tata
    kelola ralat/perubahan dokumen resmi.
    """
    aksi = str(payload.aksi or "").strip().lower()
    alasan = str(payload.alasan or "").strip()
    if aksi not in {"setujui", "buka_ulang"}:
        raise HTTPException(status_code=400,
                            detail="Aksi harus 'setujui' atau 'buka_ulang'")
    if aksi == "buka_ulang" and not alasan:
        raise HTTPException(status_code=400,
                            detail="Alasan membuka ulang wajib dicatat")

    if_match = request.headers.get("If-Match", "").strip().strip('"')
    if not if_match.isdigit() or int(if_match) < 1:
        raise HTTPException(
            status_code=428,
            detail="Header If-Match (versi permintaan) wajib disertakan")
    expected_version = int(if_match)

    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pengelola_sr(sr, user)
    raw_idem = request.headers.get("Idempotency-Key", "").strip()
    idem_key = kunci_idem(
        f"ttd-validasi:{sr_id}:{signer_id}:{aksi}:{raw_idem}" if raw_idem else "",
        user)
    # Replay harus diperiksa SEBELUM If-Match/status: respons pertama memang
    # sudah menaikkan version dan mengubah status signer. Bila urutannya
    # terbalik, retry yang sah selalu ditolak 409 dan idempotensi cuma nama.
    if idem_key:
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response") is not None:
            return cached["response"]
    _tolak_bila_batal(sr)

    # Normalisasi dokumen era lama sebelum CAS. Tanpa ini `$inc` pada field
    # yang hilang menghasilkan 1 (bukan 2), sehingga versi klien tidak maju.
    if "version" not in sr:
        await db.signature_requests.update_one(
            {"id": sr_id, "version": {"$exists": False}},
            {"$set": {"version": 1}})
        sr["version"] = 1
    current_version = int(sr.get("version", 1) or 1)
    if expected_version != current_version:
        raise HTTPException(
            status_code=409,
            detail={"message": "Permintaan telah diubah. Muat ulang sebelum memvalidasi.",
                    "current_version": current_version,
                    "your_version": expected_version})

    signers = sr.get("signers") or []
    sg = next((s for s in signers if s.get("signer_id") == signer_id), None)
    if not sg:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    status_lama = str(sg.get("status") or "")
    if aksi == "setujui" and status_lama != "menunggu_validasi":
        raise HTTPException(status_code=409,
                            detail="Pembubuhan ini tidak sedang menunggu validasi")
    if aksi == "setujui" and sg.get("deklarasi_tanpa_area") and not alasan:
        raise HTTPException(
            status_code=400,
            detail="Catatan pemeriksaan wajib untuk deklarasi tidak ada area TTD")
    if aksi == "buka_ulang":
        if sr.get("status") == "selesai":
            raise HTTPException(
                status_code=409,
                detail=("Dokumen sudah final. Gunakan naskah ralat/perubahan "
                        "resmi; jangan membuka ulang pembubuhan diam-diam."))
        if status_lama not in {"menunggu_validasi", "terverifikasi"}:
            raise HTTPException(status_code=409,
                                detail="Pembubuhan ini belum dapat dibuka ulang")

    if idem_key:
        kepemilikan = await reserve_idempotency_key(idem_key)
        if kepemilikan == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response") is not None:
                return cached["response"]
        elif kepemilikan == "pending":
            raise HTTPException(
                status_code=409,
                detail="Keputusan dengan kunci ini sedang diproses; tunggu sebentar")

    now_iso = datetime.now(timezone.utc).isoformat()
    actor = user.get("username", "system")
    daftar_baru = [dict(s) for s in signers]
    target_baru = next(s for s in daftar_baru if s.get("signer_id") == signer_id)

    if aksi == "setujui":
        target_baru["status"] = "terverifikasi"
        status_baru = status_permintaan(daftar_baru)
        event = {"aksi": "setujui", "signer_id": signer_id,
                 "nama": sg.get("nama", ""), "dari_status": status_lama,
                 "ke_status": "terverifikasi", "alasan": alasan,
                 "oleh": actor, "pada": now_iso,
                 "deklarasi_tanpa_area": bool(sg.get("deklarasi_tanpa_area")),
                 "jumlah_aktual": sg.get("deklarasi_jumlah_aktual"),
                 "jumlah_diminta": sg.get("deklarasi_jumlah_diminta")}
        set_data = {
            "signers.$.status": "terverifikasi",
            "signers.$.validated_at": now_iso,
            "signers.$.validated_by": actor,
            "signers.$.validation_note": alasan,
            "status": status_baru,
            "updated_at": now_iso,
        }
        if status_baru == "selesai":
            set_data.update({"finalized_at": now_iso, "finalized_by": actor})
        res = await db.signature_requests.update_one(
            {"id": sr_id, "version": current_version,
             "status": {"$ne": "batal"},
             "signers": {"$elemMatch": {"signer_id": signer_id,
                                          "status": "menunggu_validasi"}}},
            {"$set": set_data, "$inc": {"version": 1},
             "$push": {"riwayat_validasi": event}})
        if res.modified_count == 0:
            raise HTTPException(
                status_code=409,
                detail="Permintaan berubah saat divalidasi. Muat ulang dan periksa lagi.")
        terkini = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
        if status_baru == "selesai":
            await _catat_penyelesaian_ttd(terkini or sr, sr_id)
        respons = {"ok": True, "aksi": aksi, "status": status_baru,
                   "version": current_version + 1,
                   "menunggu_validasi": status_baru != "selesai"}
        await log_audit(
            "validasi_ttd", "", sr_id, username=actor,
            detail=(f"Pembubuhan {sg.get('nama') or signer_id} disetujui"
                    + (f": {alasan}" if alasan else "")))
    else:
        jti = str(uuid.uuid4())
        token, exp_tok = _cetak_token_signer(sr_id, signer_id, jti)
        target_baru["status"] = "aktif"
        target_baru["signature_file_id"] = ""
        status_baru = status_permintaan(daftar_baru)
        event = {
            "aksi": "buka_ulang", "signer_id": signer_id,
            "nama": sg.get("nama", ""), "dari_status": status_lama,
            "ke_status": "aktif", "alasan": alasan, "oleh": actor,
            "pada": now_iso,
            # Bukti lama dipertahankan sebagai arsip, bukan dihapus dari
            # GridFS. Ini penting untuk menjelaskan apa yang diperbaiki.
            "bukti_lama": {
                "signature_file_id": sg.get("signature_file_id", ""),
                "hash": sg.get("hash", ""),
                "signed_at": sg.get("signed_at", ""),
                "posisi_ttd": sg.get("posisi_ttd"),
                "posisi_ttd_lain": sg.get("posisi_ttd_lain") or [],
                "deklarasi_tanpa_area": bool(sg.get("deklarasi_tanpa_area")),
                "deklarasi_jumlah_aktual": sg.get("deklarasi_jumlah_aktual"),
                "deklarasi_jumlah_diminta": sg.get("deklarasi_jumlah_diminta"),
            },
        }
        kosongkan = {
            "signers.$.signature_file_id": "", "signers.$.hash": "",
            "signers.$.signed_at": "", "signers.$.posisi_ttd": "",
            "signers.$.posisi_ttd_lain": "", "signers.$.ip": "",
            "signers.$.deklarasi_tanpa_area": "",
            "signers.$.deklarasi_jumlah_aktual": "",
            "signers.$.deklarasi_jumlah_diminta": "",
            "signers.$.deklarasi_catatan": "",
            "signers.$.deklarasi_pada": "",
            "signers.$.validated_at": "", "signers.$.validated_by": "",
            "signers.$.validation_note": "",
        }
        res = await db.signature_requests.update_one(
            {"id": sr_id, "version": current_version,
             "status": {"$nin": ["selesai", "batal"]},
             "signers": {"$elemMatch": {"signer_id": signer_id,
                                          "status": status_lama}}},
            {"$set": {"signers.$.status": "aktif", "signers.$.jti": jti,
                      "signers.$.token_exp": exp_tok, "status": status_baru,
                      "updated_at": now_iso},
             "$unset": kosongkan, "$inc": {"version": 1},
             "$push": {"riwayat_validasi": event}})
        if res.modified_count == 0:
            raise HTTPException(
                status_code=409,
                detail="Permintaan berubah saat dibuka ulang. Muat ulang dan periksa lagi.")

        from tautan_pendek_utils import cabut_tautan
        await cabut_tautan("ttd", sr_id, sub_ref=signer_id)
        link = await _link_ttd_pendek(
            sr_id, token, signer_id=signer_id,
            kode_satker=str(sr.get("kode_satker") or ""), oleh=actor)
        email_terkirim = False
        if str(sg.get("email") or "").strip():
            from shared_utils import send_esign_email
            email_terkirim = await send_esign_email(
                sg["email"], sg.get("nama") or "",
                sr.get("judul") or "Dokumen", link)
        respons = {"ok": True, "aksi": aksi, "status": status_baru,
                   "version": current_version + 1, "link": link,
                   "nama": sg.get("nama"), "email_terkirim": email_terkirim}
        await log_audit(
            "buka_ulang_ttd", "", sr_id, username=actor,
            detail=f"Pembubuhan {sg.get('nama') or signer_id} dibuka ulang: {alasan}")

    if idem_key:
        await store_idempotent_response(idem_key, respons)
    return respons


@ttd_router.delete("/ttd/permintaan/{sr_id}")
async def batal_permintaan(sr_id: str, user: dict = Depends(require_writer)):
    """Batalkan permintaan (hanya pembuat atau admin)."""
    sr = await db.signature_requests.find_one(
        {"id": sr_id}, {"_id": 0, "created_by": 1, "judul": 1, "status": 1,
                        "doc_type": 1, "doc_ref": 1, "kode_satker": 1})
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pemilik_sr(sr, user)  # pembuat / admin SATKER YANG SAMA
    await db.signature_requests.update_one({"id": sr_id}, {"$set": {"status": "batal"}})
    # Tautan pendek SELURUH permintaan ikut mati — termasuk tautan verifikasi
    # yang tercetak sebagai QR di dokumen. Rute panjangnya sudah menolak
    # permintaan batal (410); tautan pendek tak boleh jadi pintu belakang yang
    # tampak masih hidup.
    from tautan_pendek_utils import cabut_tautan
    await cabut_tautan("ttd", sr_id)
    await cabut_tautan("verifikasi", sr_id)
    # Rekam jejak pembatalan — setara buat/tandatangani/terbit-ulang link yang
    # sudah ber-audit; agar dapat ditelusuri SIAPA & KAPAN membatalkan, dan
    # menjadi fondasi propagasi lintas modul (langkah observability murni —
    # tidak menyentuh record konsumen).
    # ── CASCADE SINYAL-LUNAK (propagasi otomatis lintas modul) ──────────────
    # Bila permintaan ini menaut BAST terstruktur (doc_type='bast' + doc_ref =
    # id BAST) DAN memang e-sign yang tertaut ke BAST (back-link
    # signature_request_id == sr_id), TANDAI BAST & aset terkait "TT dicabut".
    # Penjaga penting:
    #  - scope_query_field_satker → cegah tulis LINTAS-SATKER (doc_ref mentah tak
    #    dipercaya; batal hanya oleh pembuat/admin tetapi doc_ref bisa apa saja);
    #  - signature_request_id == sr_id → hanya permintaan yang BENAR menandatangani
    #    BAST yang boleh mencabut (bukan permintaan lain yang kebetulan menunjuk);
    #  - update TANPA gerbang modified_count → aman DI-RETRY (idempoten $set);
    #  - dibungkus try/except → kegagalan cascade tak menggugurkan pembatalan &
    #    pencatatan audit (best-effort). TIDAK menghapus data (reversibel).
    # Aset yang ditandai hanya yang bast_terakhir-nya MEMANG BAST ini (presisi).
    bast_dicabut = 0
    if sr.get("doc_type") == "bast" and str(sr.get("doc_ref") or "").strip():
        doc_ref = str(sr["doc_ref"]).strip()
        try:
            b = await db.bast_serah_terima.find_one(
                scope_query_field_satker(
                    user, {"id": doc_ref, "signature_request_id": sr_id}),
                {"_id": 0, "id": 1})
            if b:
                now_iso = datetime.now(timezone.utc).isoformat()
                await db.bast_serah_terima.update_one(
                    {"id": doc_ref},
                    {"$set": {"tt_dicabut": True, "tt_dicabut_pada": now_iso}})
                await db.assets.update_many(
                    {"bast_terakhir.id": doc_ref, "dihapus": {"$ne": True}},
                    {"$set": {"bast_terakhir.tt_dicabut": True}})
                bast_dicabut = 1
        except Exception:
            bast_dicabut = 0  # cascade best-effort — batal & audit tetap jalan
    # Cascade setara untuk LPB, dengan penjaga yang sama persis: scope satker
    # (doc_ref mentah tak dipercaya) + `signature_request_id == sr_id` (hanya
    # permintaan yang BENAR menandatangani LPB ini yang boleh mencabutnya).
    if sr.get("doc_type") == "lpb" and str(sr.get("doc_ref") or "").strip():
        try:
            milik = await db.lpb.find_one(
                scope_query_field_satker(
                    user, {"id": str(sr["doc_ref"]).strip(),
                           "signature_request_id": sr_id}),
                {"_id": 0, "id": 1})
            if milik:
                await db.lpb.update_one(
                    {"id": milik["id"]},
                    # `signature_request_id` DIKOSONGKAN: layar memakainya
                    # sebagai penanda "sudah dikirim", jadi membiarkannya
                    # terisi setelah dibatalkan membuat tombol "Kirim TTD"
                    # hilang SELAMANYA — LPB yang tandatangannya dicabut tak
                    # akan pernah bisa dikirim ulang.
                    {"$set": {"tt_dicabut": True,
                              "signature_request_id": "",
                              "tt_dicabut_pada": datetime.now(timezone.utc).isoformat()}})
        except Exception:
            pass  # best-effort, seperti cascade BAST di atas
    await log_audit("batal_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=(f"Permintaan TTD '{sr.get('judul') or sr_id}' dibatalkan"
                            f" (status sebelumnya: {sr.get('status') or '-'}"
                            + (f"; BAST {sr.get('doc_ref')} ditandai dicabut"
                               if bast_dicabut else "") + ")"))
    return {"ok": True, "bast_dicabut": bool(bast_dicabut)}


@ttd_router.post("/ttd/permintaan/{sr_id}/link/{signer_id}")
async def buat_ulang_link(sr_id: str, signer_id: str,
                          user: dict = Depends(require_writer)):
    """Terbitkan ULANG link e-sign seorang penanda tangan (pembuat/admin) —
    dipakai bila link hilang setelah dialog pembuatan ditutup, atau link lama
    kedaluwarsa/tersebar keliru. jti BARU dibuat sehingga link lama langsung
    MATI (sekali-pakai tetap terjaga). Ditolak bila sudah ditandatangani."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    # Guard ber-SATKER (REVIEW-9 R11): cek lama hanya role=='admin',
    # sehingga admin satker LAIN bisa menerbitkan ulang link e-sign —
    # link itu memberi hak menandatangani dokumen resmi satker ini.
    _pastikan_pemilik_sr(sr, user)
    signers = sr.get("signers") or []
    idx = next((i for i, s in enumerate(signers)
                if s.get("signer_id") == signer_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    if sudah_membubuhkan(signers[idx]):
        raise HTTPException(
            status_code=409,
            detail="Pembubuhan sudah masuk — gunakan Buka Ulang bila perlu koreksi")
    jti = str(uuid.uuid4())
    token, exp_tok = _cetak_token_signer(sr_id, signer_id, jti)
    # token_exp ikut diperbarui: link BARU berlaku 14 hari sejak SEKARANG,
    # bukan sejak permintaan dibuat.
    await db.signature_requests.update_one(
        {"id": sr_id, "signers.signer_id": signer_id},
        {"$set": {"signers.$.jti": jti, "signers.$.token_exp": exp_tok}})
    # jti BARU sudah mematikan token lama; tautan pendek lama yang menunjuk
    # token itu harus ikut mati, bukan menyisakan alamat yang membuka halaman
    # "link tidak valid" tanpa penjelasan. HANYA milik penanda tangan ini —
    # tautan rekan-rekannya masih sah dan mereka belum tentu sudah meneken.
    from tautan_pendek_utils import cabut_tautan
    await cabut_tautan("ttd", sr_id, sub_ref=signer_id)
    link = await _link_ttd_pendek(sr_id, token, signer_id=signer_id,
                                  kode_satker=str(sr.get("kode_satker") or ""),
                                  oleh=user.get("username", ""))
    email_terkirim = False
    if str(signers[idx].get("email") or "").strip():
        from shared_utils import send_esign_email
        email_terkirim = await send_esign_email(
            signers[idx]["email"], signers[idx].get("nama"),
            sr.get("judul") or "Dokumen", link)
    await log_audit("terbit_ulang_link_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=f"Link e-sign diterbitkan ulang untuk {signers[idx].get('nama')}")
    return {"nama": signers[idx].get("nama"), "status": signers[idx].get("status"),
            "link": link, "email_terkirim": email_terkirim}


@ttd_router.get("/ttd/tandatangan/{sr_id}")
async def info_tandatangan(sr_id: str, tok: dict = Depends(require_sign_token)):
    """Info dokumen + penanda tangan untuk HALAMAN PUBLIK (link e-sign)."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    sg = next((s for s in sr.get("signers") or [] if s.get("signer_id") == tok["signer"]), None)
    if not sg:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    # Link LAMA yang jti-nya sudah diganti (terbit ulang) harus mati juga di
    # halaman info — bukan hanya saat kirim.
    if sg.get("jti") != tok["jti"]:
        raise HTTPException(status_code=401,
                            detail="Link ini sudah tidak berlaku (telah diterbitkan ulang)")
    bisa = sg.get("status") == "aktif"
    alasan = ""
    if sg.get("status") == "menunggu_validasi":
        alasan = ("Pembubuhan Anda sudah masuk dan sedang diperiksa "
                  "operator/admin satker.")
    elif sg.get("status") in ("terverifikasi", "ditandatangani"):
        alasan = "Pembubuhan Anda sudah diverifikasi dan dinyatakan sesuai."
    elif sg.get("status") == "menunggu":
        alasan = "Menunggu giliran penanda tangan sebelumnya (mode berurutan)."
    return {"id": sr_id, "judul": sr.get("judul"), "doc_type": sr.get("doc_type"),
            "label_jenis": label_jenis_ttd(sr.get("doc_type")),
            "judul_tampil": judul_ttd_tampil(sr.get("judul"), sr.get("doc_type")),
            "mode": sr.get("mode"), "status_dokumen": sr.get("status"),
            # Penanda tangan berhak tahu seberapa cepat ini dituntut — kalau
            # hanya hidup di kepala pengirim, "segera" tak mengubah apa pun.
            "sifat_urgensi": str(sr.get("sifat_urgensi") or "biasa"),
            "penanda_tangan": _publik_signer(sg), "boleh_ttd": bisa,
            "alasan": alasan,
            # Sisa waktu tautan — dihitung DI SERVER (jam perangkat tamu bisa
            # meleset; "kedaluwarsa" palsu membuat orang berhenti meneken
            # dokumen yang masih sah).
            **_sisa_kedaluwarsa(sg, sr),
            # dokumen terlampir → halaman publik menampilkan tombol baca
            # + pratinjau pembubuhan (jumlah halaman utk navigasi posisi)
            "ada_dokumen": bool(str(sr.get("dok_file_id") or "").strip()),
            "dok_nama": sr.get("dok_nama", ""),
            "jumlah_halaman": int(sr.get("dok_halaman") or 0),
            # Hasil akhir bisa diunduh penanda tangan setelah SEMUA meneken dan
            # penerbit menempatkan QR; `menunggu_qr` menerangkan penantiannya.
            "siap_diunduh": _siap_diunduh(sr),
            "menunggu_validasi": sr.get("status") == "menunggu_validasi",
            "menunggu_qr": (sr.get("status") == "selesai" and _semua_terverifikasi(sr)
                            and not _qr_sudah_diatur(sr)
                            and bool(str(sr.get("dok_file_id") or "").strip()))}


@ttd_router.post("/ttd/tandatangan/{sr_id}/kirim")
@limiter.limit("15/minute")
async def kirim_tandatangan(sr_id: str, payload: SpesimenIn, request: Request,
                            tok: dict = Depends(require_sign_token)):
    """Kirim gambar tanda tangan (PNG transparan) via link publik."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    signers = sr.get("signers") or []
    idx = next((i for i, s in enumerate(signers) if s.get("signer_id") == tok["signer"]), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    sg = signers[idx]
    if sg.get("jti") != tok["jti"] or sudah_membubuhkan(sg):
        raise HTTPException(status_code=409, detail="Link sudah dipakai / tidak berlaku")
    if sg.get("status") != "aktif":
        raise HTTPException(status_code=409, detail="Belum giliran Anda menandatangani")

    data = _png_dari_base64(payload.png_base64)
    if not png_transparan_valid(data):
        raise HTTPException(status_code=400, detail="Tanda tangan tidak valid / kosong")
    # Posisi divalidasi SEBELUM blob diunggah — nilai liar (Infinity dkk.)
    # tidak boleh meninggalkan blob yatim di GridFS lewat jalur exception.
    _maks_hal = int(sr.get("dok_halaman") or 0)
    posisi_ttd = _posisi_bersih(payload.posisi, _maks_hal)
    posisi_lain = _posisi_bersih_banyak(payload.posisi_lain, _maks_hal)
    # KELENGKAPAN DITEGAKKAN DI SERVER, bukan hanya di layar. Link e-sign
    # dibuka di peramban tamu yang tak terkendali, dan kiriman yang kurang
    # TIDAK BISA diperbaiki sesudahnya: link sekali-pakai langsung tertutup
    # dan satu-satunya pemulihan adalah membatalkan permintaan lalu meminta
    # SEMUA orang meneken ulang. Diperiksa SEBELUM blob diunggah supaya
    # penolakan tak meninggalkan berkas yatim di GridFS — dan dihitung dari
    # posisi yang SUDAH dibersihkan, bukan dari kiriman mentah, agar entri
    # rusak yang dibuang tak ikut terhitung sebagai pembubuhan yang sah.
    _ada_dokumen = bool(str(sr.get("dok_file_id") or "").strip())
    # Tanpa PDF, gambar TTD itu sendiri adalah satu pembubuhan pada Lembar
    # Pengesahan (perilaku lama). Deklarasi kekurangan hanya masuk akal pada
    # PDF yang bisa diperiksa halaman demi halaman.
    _kurang = ("" if not _ada_dokumen
               and normalisasi_jumlah_ttd(sg.get("jumlah_ttd")) == 1 else
               pesan_deklarasi_tanpa_area(
                   sg.get("jumlah_ttd"), posisi_ttd, posisi_lain,
                   deklarasi=bool(payload.deklarasi_tanpa_area),
                   ada_dokumen=_ada_dokumen))
    if _kurang:
        raise HTTPException(status_code=400, detail=_kurang)
    # QR verifikasi TIDAK diatur di sini (mandat pemilik): dulu tiap penanda
    # tangan bisa menggeser/memperbesar QR dan pengatur terakhir menang —
    # membingungkan dan sering terlewat sehingga QR jatuh menimpa footer.
    # Sekarang QR diatur SEKALI oleh pemilik dokumen di akhir, saat semua
    # sudah meneken (PUT /ttd/permintaan/{id}/posisi-qr).
    now = datetime.now(timezone.utc)
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"ttd_sign_{sr_id}_{sg['signer_id']}.png",
        metadata={"content_type": "image/png", "kind": "ttd_sign", "sr": sr_id})
    await grid_in.write(data)
    await grid_in.close()
    h = hashlib.sha256(data + sg["signer_id"].encode() + now.isoformat().encode()).hexdigest()

    # TULIS ATOMIK per-signer ($elemMatch + operator posisional) — BUKAN
    # menulis balik seluruh array. Dua penanda tangan PARALEL yang submit
    # bersamaan tidak lagi saling menimpa (lost-update), dan filter jti/
    # status/batal di sini menutup jendela race pembatalan/link-lama yang
    # terbuka selama upload GridFS multi-await di atas.
    _jumlah_aktual = (jumlah_pembubuhan(posisi_ttd, posisi_lain)
                      if _ada_dokumen else 1)
    _jumlah_diminta = normalisasi_jumlah_ttd(sg.get("jumlah_ttd"))
    _pakai_deklarasi = bool(payload.deklarasi_tanpa_area
                            and _jumlah_aktual < _jumlah_diminta)
    set_fields = {"signers.$.status": "menunggu_validasi",
                  "signers.$.signature_file_id": str(file_id),
                  "signers.$.hash": h,
                  "signers.$.signed_at": now.isoformat(),
                  # Posisi pembubuhan pilihan penanda tangan (None = slot
                  # otomatis di halaman terakhir seperti sebelumnya).
                  "signers.$.posisi_ttd": posisi_ttd,
                  # Pembubuhan tambahan (lembar lanjutan, lampiran pernyataan).
                  "signers.$.posisi_ttd_lain": posisi_lain,
                  "signers.$.deklarasi_tanpa_area": _pakai_deklarasi,
                  "signers.$.deklarasi_jumlah_aktual": _jumlah_aktual,
                  "signers.$.deklarasi_jumlah_diminta": _jumlah_diminta,
                  "signers.$.deklarasi_catatan": (
                      str(payload.catatan_deklarasi or "").strip()
                      if _pakai_deklarasi else ""),
                  "signers.$.deklarasi_pada": (now.isoformat()
                                                if _pakai_deklarasi else ""),
                  "signers.$.ip": (request.client.host if request.client else "")}
    res = await db.signature_requests.update_one(
        {"id": sr_id, "status": {"$ne": "batal"},
         "signers": {"$elemMatch": {"signer_id": tok["signer"],
                                    "jti": tok["jti"], "status": "aktif"}}},
        {"$set": set_fields, "$inc": {"version": 1}})
    if res.modified_count == 0:
        # Kalah race (sudah ttd / dibatalkan / link diganti) — bersihkan blob.
        try:
            await fs_bucket.delete(file_id)
        except Exception:
            pass
        raise HTTPException(status_code=409,
                            detail="Link sudah dipakai / permintaan berubah — muat ulang halaman")

    # Langkah 2 (idempoten, baca kondisi TERKINI): aktifkan giliran berikutnya
    # (mode berurutan) & hitung status dokumen dari keadaan nyata.
    segar = await db.signature_requests.find_one(
        {"id": sr_id}, {"_id": 0, "mode": 1, "status": 1, "judul": 1,
                        "signers.status": 1, "signers.signer_id": 1,
                        "signers.jti": 1, "signers.email": 1, "signers.nama": 1,
                        # `urutan` WAJIB ikut diproyeksikan — ia yang menentukan
                        # giliran berikutnya. Tanpa field ini semua signer
                        # bernilai sama dan pengurutannya jadi hampa.
                        "signers.urutan": 1})
    signers_segar = (segar or {}).get("signers") or []
    if (segar or {}).get("mode") == "berurutan":
        # Giliran berikutnya dipilih dari `urutan` — BUKAN dari posisi elemen
        # di array. Keduanya kebetulan sama saat permintaan dibuat, tapi
        # `urutan` adalah kontrak yang kita simpan DAN kirim ke layar; kalau
        # array-nya pernah tersusun ulang (restore, perbaikan manual, fitur
        # ubah-urutan kelak), memilih berdasarkan posisi akan mengaktifkan
        # ORANG YANG SALAH tanpa satu pun galat. Bertumpu pada satu sumber
        # kebenaran menutup kemungkinan itu sekarang, bukan nanti.
        nxt_sg = min(
            (s for s in signers_segar if s.get("status") == "menunggu"),
            key=lambda s: _nomor_urut(s), default=None)
        if nxt_sg:
            res_nxt = await db.signature_requests.update_one(
                {"id": sr_id, "status": {"$ne": "batal"},
                 "signers": {"$elemMatch": {"signer_id": nxt_sg["signer_id"],
                                            "status": "menunggu"}}},
                {"$set": {"signers.$.status": "aktif"}})
            # Giliran maju → beri tahu penanda tangan berikutnya via email
            # (best-effort; link memakai jti tersimpan — token identik dgn
            # yang dibagikan pembuat, jadi tidak mematikan link lama).
            #
            # `token_exp` SENGAJA TIDAK diperbarui di sini. jti tak berubah,
            # sehingga tautan yang SUDAH dibagikan pembuat tetap sah sampai
            # exp lamanya, sedangkan token yang baru dicetak untuk email ini
            # punya exp yang lebih panjang. Penanda tangan bisa memegang salah
            # satu dari keduanya, jadi yang ditampilkan adalah batas TERCEPAT
            # (dari pembuatan): mengaku waktunya lebih panjang daripada
            # kenyataan akan membuat orang melewatkan tenggat, sedangkan
            # mengaku lebih pendek paling banter membuatnya meneken lebih awal.
            if res_nxt.modified_count and str(nxt_sg.get("email") or "").strip():
                from shared_utils import send_esign_email
                tok_nxt = create_sign_token(sr_id, nxt_sg["signer_id"],
                                            nxt_sg.get("jti") or "")
                await send_esign_email(
                    nxt_sg["email"], nxt_sg.get("nama") or "",
                    (segar or {}).get("judul") or "Dokumen",
                    _link_ttd(sr_id, tok_nxt))
    status_dok = status_permintaan(signers_segar)
    # Pembubuhan TIDAK pernah membuat permintaan final. Status final hanya
    # bisa lahir dari endpoint validasi pengelola. Filter berbeda mencegah
    # submit paralel yang membaca keadaan basi menurunkan "menunggu_validasi"
    # kembali menjadi "sebagian".
    if status_dok == "menunggu_validasi":
        filter_status = {"$nin": ["batal", "selesai"]}
    else:
        filter_status = {"$in": ["terkirim", "sebagian"]}
    await db.signature_requests.update_one(
        {"id": sr_id, "status": filter_status},
        {"$set": {"status": status_dok,
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_audit(
        "kirim_ttd", "", sr_id, username=sg.get("nama") or "tamu",
        detail=(f"Pembubuhan e-sign '{sr.get('judul')}' oleh {sg.get('nama')} "
                "dikirim untuk validasi operator/admin satker"))
    return {"ok": True, "status_dokumen": status_dok,
            "menunggu_validasi": True,
            "verifikasi": f"/ttd/verifikasi/{sr_id}"}


@ttd_router.get("/ttd/tandatangan/{sr_id}/gambar/{signer_id}")
async def gambar_ttd_signer(sr_id: str, signer_id: str,
                            user: dict = Depends(require_user_or_query_token)):
    """Stream gambar tanda tangan seorang penanda tangan (pratinjau dasbor)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pengelola_sr(sr, user)
    _tolak_bila_batal(sr)  # gambar TTD dari permintaan batal → tak berlaku
    sg = next((s for s in (sr or {}).get("signers") or []
               if s.get("signer_id") == signer_id), None)
    fid = str((sg or {}).get("signature_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ditandatangani")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return StreamingResponse(io.BytesIO(data), media_type="image/png",
                             headers={"X-Content-Type-Options": "nosniff",
                                      "Content-Disposition": 'inline; filename="ttd.png"'})


@ttd_router.get("/ttd/verifikasi/{sr_id}")
async def verifikasi_publik(sr_id: str):
    """Verifikasi PUBLIK keabsahan e-sign (dibuka dari QR). Tanpa token —
    hanya menampilkan siapa menandatangani & kapan (bukan gambar/hash mentah)."""
    sr = await db.signature_requests.find_one(
        {"id": sr_id}, {"_id": 0, "judul": 1, "doc_type": 1, "status": 1,
                        "created_at": 1, "dok_file_id": 1, "posisi_qr": 1,
                        "signers.nama": 1, "signers.jabatan": 1,
                        "signers.nip": 1, "signers.status": 1,
                        "signers.signed_at": 1, "signers.validated_at": 1,
                        "signers.signature_file_id": 1})
    if not sr:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    dibatalkan = sr.get("status") == "batal"
    return {
        "judul": sr.get("judul"), "doc_type": sr.get("doc_type"),
        "label_jenis": label_jenis_ttd(sr.get("doc_type")),
        "judul_tampil": judul_ttd_tampil(sr.get("judul"), sr.get("doc_type")),
        "status": sr.get("status"), "dibuat": sr.get("created_at"),
        # Unduhan dokumen ber-TTD dari halaman verifikasi: hanya setelah semua
        # meneken DAN QR ditempatkan. `menunggu_qr` dipakai layar untuk
        # menerangkan mengapa tombolnya belum ada (bukan diam-diam hilang).
        "dapat_unduh": _siap_diunduh(sr),
        "menunggu_validasi": (not dibatalkan
                               and sr.get("status") == "menunggu_validasi"),
        "menunggu_qr": (not dibatalkan and sr.get("status") == "selesai"
                        and _semua_terverifikasi(sr)
                        and not _qr_sudah_diatur(sr)
                        and bool(str(sr.get("dok_file_id") or "").strip())),
        # Tanda pembatalan eksplisit agar halaman publik menegaskan dokumen
        # TIDAK berlaku, alih-alih tampak sah (celah A2).
        "dibatalkan": dibatalkan,
        "penanda_tangan": [
            {"nama": s.get("nama"), "jabatan": s.get("jabatan"),
             # NIP di-masking di halaman verifikasi PUBLIK (data pribadi):
             # cukup 3 digit akhir untuk memastikan kecocokan, sisanya bintang.
             "nip": _mask_nip(s.get("nip")), "status": s.get("status"),
             "signed_at": s.get("signed_at"),
             "validated_at": s.get("validated_at")}
            for s in sr.get("signers") or []],
        "catatan": ("PERMINTAAN TANDA TANGAN INI TELAH DIBATALKAN — tanda tangan "
                    "elektronik yang tercantum TIDAK berlaku."
                    if dibatalkan else (
                    "Pembubuhan masih menunggu validasi operator/admin satker "
                    "dan belum merupakan dokumen final."
                    if sr.get("status") != "selesai" else
                    "Tanda tangan elektronik internal satker (integritas + "
                    "jejak audit). Sah tanpa tanda tangan basah untuk keperluan "
                    "administrasi internal.")),
    }


@ttd_router.get("/ttd/permintaan/{sr_id}/lembar-pdf")
async def lembar_pdf(sr_id: str, user: dict = Depends(require_user_or_query_token)):
    """Lembar Pengesahan Tanda Tangan Elektronik: judul dokumen + daftar
    penanda tangan dengan GAMBAR tanda tangan, waktu, NIP, dan QR verifikasi."""
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table

    from routes.reports import (
        _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _std_doc, _std_table_style, _title_block,
    )

    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    # IDOR (REVIEW-9 R11): lembar pengesahan memuat GAMBAR tanda tangan
    # seluruh penanda tangan + NIP.
    _pastikan_pengelola_sr(sr, user)
    _tolak_bila_batal(sr)  # lembar pengesahan dari permintaan batal → tak berlaku
    settings = await db.report_settings.find_one({"type": "global"}, _PROJ) or {}
    st = _get_report_styles()
    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("LEMBAR PENGESAHAN\nTANDA TANGAN ELEKTRONIK",
                           subjudul=sr.get("judul")))
    if sr.get("status") != "selesai" or not _semua_terverifikasi(sr):
        el.append(Paragraph(
            "<b>DRAF PEMERIKSAAN — BELUM DIVALIDASI / BELUM FINAL</b>",
            st['Meta']))
    el.append(Paragraph(
        f"Dokumen: <b>{sr.get('judul')}</b> · Mode: {sr.get('mode')} · "
        f"Status: {sr.get('status')}", st['Meta']))
    el.append(Spacer(1, 3 * rl_mm))

    from xml.sax.saxutils import escape as _esc
    baris = [[Paragraph(h, st['TableHeader']) for h in
              ("No", "Nama & Jabatan", "Tanda Tangan", "Waktu")]]
    for i, s in enumerate(sr.get("signers") or [], 1):
        idn = f"<b>{_esc(s.get('nama') or '-')}</b>"
        if s.get("jabatan"):
            idn += f"<br/><font size=8>{_esc(s['jabatan'])}</font>"
        if s.get("nip"):
            # Non-ASN/NIK: baris NIP tidak dicetak di Lembar Pengesahan
            from pegawai_utils import baris_identitas_laporan
            from shared_utils import status_kepegawaian_by_nip
            b_nip = baris_identitas_laporan(
                s["nip"], await status_kepegawaian_by_nip(s["nip"]))
            if b_nip:
                idn += f"<br/><font size=8>{_esc(b_nip)}</font>"
        ttd_cell = Paragraph("<font size=8 color='#94a3b8'>belum ditandatangani</font>", st['Cell'])
        fid = str(s.get("signature_file_id") or "").strip()
        if fid:
            data = await get_document_from_gridfs(fid)
            if data:
                try:
                    img = RLImage(io.BytesIO(data), mask='auto')
                    sk = min((doc.width * 0.22) / img.imageWidth, (16 * rl_mm) / img.imageHeight)
                    img.drawWidth, img.drawHeight = img.imageWidth * sk, img.imageHeight * sk
                    ttd_cell = img
                except Exception:
                    pass
        waktu = _fmt_tanggal_id(s.get("signed_at", "")[:10]) if s.get("signed_at") else "-"
        baris.append([Paragraph(str(i), st['CellCenter']),
                      Paragraph(idn, st['Cell']), ttd_cell,
                      Paragraph(waktu, st['CellCenter'])])
    t = Table(baris, colWidths=[doc.width * 0.08, doc.width * 0.40,
                                doc.width * 0.32, doc.width * 0.20], repeatRows=1)
    t.setStyle(_std_table_style(zebra=True))
    el.append(t)
    el.append(Spacer(1, 5 * rl_mm))

    # QR verifikasi.
    try:
        from routes.cards import build_qr_flowable
        verif = await _link_verifikasi_pendek(
            sr_id, kode_satker=str(sr.get("kode_satker") or ""))
        el.append(build_qr_flowable(verif, 28 * rl_mm))
    except Exception:
        pass
    if sr.get("status") == "selesai" and _semua_terverifikasi(sr):
        catatan_lembar = (
            "Ditandatangani secara elektronik — sah tanpa tanda tangan basah "
            "untuk keperluan administrasi internal satker. ")
    else:
        catatan_lembar = (
            "Lembar ini hanya bahan pemeriksaan internal dan belum boleh "
            "diperlakukan sebagai dokumen final. ")
    el.append(Paragraph(
        f"{catatan_lembar}Verifikasi kode: {sr_id[:8]}.", st['Small']))

    footer = _page_footer_factory("Lembar Pengesahan TTD Elektronik")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="Lembar_TTD_{sr_id[:8]}.pdf"'})
