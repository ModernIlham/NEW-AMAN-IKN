"""Aturan murni portal pemegang: identitas, bukti asli, dan batas status.

Laporan portal adalah pernyataan pemegang, bukan perubahan master BMN.
Identitas teks lama hanya dibekukan untuk mendeteksi perubahan penugasan;
otorisasi memakai FK pegawai_id + penugasan_id dan satker eksplisit.
"""
import base64
import binascii
import hashlib
import io
import json
import re
import warnings
from datetime import datetime, timezone

from PIL import Image, UnidentifiedImageError

from foto_kompresi import sumber_foto_valid

STATUS_PENUGASAN = ("menunggu_konfirmasi", "diterima", "disanggah", "dicabut")
STATUS_LAPORAN = ("diajukan", "terverifikasi", "perlu_perbaikan", "ditolak")
JENIS_LAPORAN = ("berkala", "kerusakan", "kehilangan", "perbaikan", "pengembalian")
KONDISI_LAPORAN = ("Baik", "Rusak Ringan", "Rusak Berat", "Tidak diketahui")
STATUS_OPERASIONAL = ("digunakan", "tidak_digunakan", "diperbaiki", "tidak_diketahui")
MAX_BUKTI = 3
MAX_BUKTI_BYTES = 3 * 1024 * 1024
MAX_BUKTI_BASE64 = 4 * 1024 * 1024
MAX_PIXELS = 20_000_000
MIME_GAMBAR = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def teks(value):
    return str(value or "").strip()


def sidik_data(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        default=str).encode("utf-8")).hexdigest()


def alias_identitas_aset(aset, kode_satker):
    """Kunci multikey unik mengunci register DAN kode/NUP lintas kegiatan.

Baris saudara tanpa register tetap berbagi alias kode/NUP dengan baris yang
memiliki register. Identitas parsial tidak boleh memperoleh akses portal.
"""
    kode = teks(aset.get("asset_code"))
    nup = teks(aset.get("NUP"))
    satker = teks(kode_satker)
    if not satker or not re.fullmatch(r"\d{10}", kode) or not nup:
        raise ValueError("Satker, kode barang 10 digit, dan NUP wajib lengkap")
    if nup.isdecimal():
        nup = str(int(nup))
    aliases = [sidik_data([satker, "kode_nup", kode, nup])]
    register = teks(aset.get("kode_register")).lower()
    if register:
        aliases.append(sidik_data([satker, "register", register]))
    return aliases


def ikatan_sumber(aset, kode_satker):
    """Perubahan pemegang, identitas, atau kegiatan membatalkan akses lama."""
    return {
        "asset_id": teks(aset.get("id")),
        "activity_id": teks(aset.get("activity_id")),
        "kode_satker": teks(kode_satker),
        "asset_code": teks(aset.get("asset_code")),
        "NUP": teks(aset.get("NUP")),
        "kode_register": teks(aset.get("kode_register")),
        "user": " ".join(teks(aset.get("user")).split()).casefold(),
        "pengguna_nip": teks(aset.get("pengguna_nip")),
        "bast_id": teks((aset.get("bast_terakhir") or {}).get("id")),
    }


def tindak_lanjut_laporan(jenis, kondisi):
    flags = []
    if jenis == "kehilangan":
        flags.append("Verifikasi kehilangan dan telaah Wasdal/Pengamanan oleh petugas")
    if jenis in ("kerusakan", "perbaikan") or kondisi in ("Rusak Ringan", "Rusak Berat"):
        flags.append("Telaah kebutuhan atau hasil pemeliharaan oleh petugas")
    if jenis == "pengembalian":
        flags.append("Proses pengembalian dan BAST melalui modul Penggunaan")
    return flags


def waktu_pengambilan(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(teks(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError("Waktu pengambilan harus berupa tanggal ISO dengan zona waktu")
    if dt.tzinfo is None:
        raise ValueError("Waktu pengambilan wajib menyertakan zona waktu")
    return dt.astimezone(timezone.utc).isoformat()


def validasi_bukti(items):
    """Validasi byte asli, tanpa menulis GridFS atau mengubah bukti pemegang."""
    if len(items or []) > MAX_BUKTI:
        raise ValueError("Maksimal tiga foto per laporan")
    total = 0
    out = []
    for i, item in enumerate(items or []):
        raw64 = teks(item.get("data_base64"))
        if not raw64 or len(raw64) > MAX_BUKTI_BASE64:
            raise ValueError("Foto kosong atau terlalu besar")
        try:
            raw = base64.b64decode(raw64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Data foto bukan base64 yang valid")
        total += len(raw)
        if not raw or total > MAX_BUKTI_BYTES:
            raise ValueError("Jumlah ukuran foto maksimal 3 MiB per laporan")
        if not sumber_foto_valid(raw):
            raise ValueError("Foto harus utuh; unggah ulang berkas aslinya")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as im:
                    fmt = im.format
                    width, height = im.size
                    if (fmt not in MIME_GAMBAR or min(width, height) < 1
                            or max(width, height) > 6000 or width * height > MAX_PIXELS
                            or getattr(im, "n_frames", 1) != 1):
                        raise ValueError("Foto harus JPEG/PNG/WebP statis maksimal 6000 piksel dan 20 megapiksel")
                    im.verify()
                with Image.open(io.BytesIO(raw)) as im:
                    im.load()
        except (UnidentifiedImageError, OSError, SyntaxError,
                Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValueError("Isi foto rusak atau bukan gambar yang didukung")
        mime = MIME_GAMBAR[fmt]
        if teks(item.get("mime")).lower() != mime:
            raise ValueError("Jenis berkas foto tidak sesuai dengan isinya")
        nama = re.sub(r"[^\w. -]", "_", teks(item.get("nama")))[:120]
        out.append({
            "nama": nama or f"bukti-{i + 1}", "mime": mime,
            "ukuran": len(raw), "width": width, "height": height,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "data_base64": base64.b64encode(raw).decode("ascii"),
        })
    return out


def bukti_metadata(items):
    return [{k: v for k, v in b.items() if k != "data_base64"}
            for b in items or []]
