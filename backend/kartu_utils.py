"""Logika murni KARTU PEGAWAI (UID e-KTP / kartu NFC) — tanpa Mongo/IO.

Kartu e-KTP adalah smartcard ISO 14443 yang punya UID unik per kartu.
Aplikasi HANYA memakai UID (lapisan anti-collision) — TIDAK membaca data
kependudukan di chip (itu memerlukan perangkat SAM & kerja sama Dukcapil).
UID berperan sebagai identifikasi cepat/kenyamanan (tap → pegawai dikenal),
BUKAN bukti identitas kuat (UID dapat dikloning "magic card") — untuk aksi
berkekuatan hukum tetap pakai TTD elektronik.

Keamanan penyimpanan: UID mentah TIDAK PERNAH disimpan/di-log. Yang
disimpan hanya HMAC-SHA256(kunci_rahasia, "kartu-uid:" + UID_kanonik).
Ruang UID 4 byte cuma 2^32 sehingga hash TANPA kunci bisa di-brute-force —
karena itu wajib keyed-hash. Kunci: env `KARTU_UID_SECRET` (opsional,
tahan rotasi JWT) dengan fallback `JWT_SECRET`. CATATAN: mengganti kunci
membatalkan semua kartu terdaftar (perlu daftar ulang).

Jebakan reader (riset #489): pembaca NFC USB "keyboard-wedge" mengetik UID
dalam format BERBEDA-BEDA — 8 digit hex MSB, 8 hex LSB (byte dibalik),
10 digit desimal MSB, atau 10 desimal LSB. Supaya kartu yang sama cocok
apa pun format reader-nya, `kandidat_uid` menghasilkan SEMUA representasi
kanonik yang mungkin dan pendaftaran menyimpan hash SEMUA kandidat;
identifikasi cukup mencocokkan salah satu.
"""
import hashlib
import hmac
import os
import re

# Panjang UID sah (byte): 4 (single), 7 (double), 10 (triple) — ISO 14443-3.
_PANJANG_HEX_SAH = {8, 14, 20}


def _kunci_rahasia() -> bytes:
    """Kunci HMAC: KARTU_UID_SECRET (dibersihkan CR-LF/kutip .env Windows)
    fallback JWT_SECRET. Import saat panggil agar unit test (env dummy) aman."""
    raw = os.environ.get("KARTU_UID_SECRET", "")
    raw = raw.strip().strip('"').strip("'").strip()
    if not raw:
        from auth_utils import JWT_SECRET
        raw = JWT_SECRET
    return raw.encode()


def normalisasi_uid(v) -> str:
    """UID apa adanya dari reader/ketikan → bentuk seragam: huruf besar,
    tanpa pemisah (':' '-' '.' spasi). "" bila kosong/bukan alfanumerik."""
    s = re.sub(r"[\s:.\-]+", "", str(v or "")).upper()
    return s if re.fullmatch(r"[0-9A-F]+|[0-9]+", s or "") else ""


def _hex_dari_desimal(s: str) -> list:
    """10-an digit desimal (uint32/uint56 dari reader mode desimal) → daftar
    hex kanonik [big-endian, little-endian]. [] bila bukan desimal murni."""
    if not s.isdigit():
        return []
    try:
        n = int(s)
    except ValueError:
        return []
    if n <= 0:
        return []
    if n < 2 ** 32:
        nbytes = 4
    elif n < 2 ** 56:
        nbytes = 7
    else:
        return []
    be = n.to_bytes(nbytes, "big")
    return [be.hex().upper(), be[::-1].hex().upper()]


def kandidat_uid(v) -> list:
    """Semua representasi kanonik yang mungkin dari satu input UID.

    - Input hex sepanjang UID sah → [asli, byte-dibalik].
    - Input desimal murni → [asli, hex-BE, hex-LE] (reader mode desimal).
    - Lainnya → [asli] saja (tetap bisa dipakai asal reader konsisten).
    Terurut & unik; [] bila input kosong/tak valid.
    """
    u = normalisasi_uid(v)
    if not u:
        return []
    hasil = [u]
    if u.isdigit():
        hasil.extend(_hex_dari_desimal(u))
    elif len(u) in _PANJANG_HEX_SAH and len(u) % 2 == 0:
        try:
            hasil.append(bytes.fromhex(u)[::-1].hex().upper())
        except ValueError:
            pass
    unik = []
    for k in hasil:
        if k and k not in unik:
            unik.append(k)
    return unik


def hash_uid(v, kunci: bytes = None) -> str:
    """HMAC-SHA256 hex dari satu UID kanonik; "" bila input kosong.
    Label "kartu-uid:" memisahkan domain dari pemakaian kunci lain."""
    u = normalisasi_uid(v)
    if not u:
        return ""
    k = kunci if kunci is not None else _kunci_rahasia()
    return hmac.new(k, f"kartu-uid:{u}".encode(), hashlib.sha256).hexdigest()


def hash_kandidat(v, kunci: bytes = None) -> list:
    """Hash SEMUA kandidat representasi — disimpan saat pendaftaran dan
    dicocokkan ($in) saat identifikasi."""
    k = kunci if kunci is not None else _kunci_rahasia()
    return [hash_uid(c, k) for c in kandidat_uid(v)]


def label_kartu(v) -> str:
    """Label aman utk UI/audit: 4 karakter terakhir UID kanonik, sisanya
    disamarkan — TIDAK memuat UID penuh."""
    u = normalisasi_uid(v)
    if not u:
        return ""
    return ("•" * max(0, min(len(u), 8) - 4)) + u[-4:]


def valid_uid(v) -> str:
    """Validasi input pendaftaran/identifikasi → pesan kesalahan atau ""."""
    u = normalisasi_uid(v)
    if not u:
        return "UID kartu kosong / berisi karakter tidak sah"
    if len(u) < 6:
        return "UID kartu terlalu pendek (min. 6 karakter)"
    if len(u) > 24:
        return "UID kartu terlalu panjang (maks. 24 karakter)"
    return ""
