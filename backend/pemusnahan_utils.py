"""Logika murni PEMUSNAHAN (Fase 6 tahap awal: register BA Pemusnahan).

PMK 83/PMK.06/2016 (pustaka §1 & §10): pemusnahan dilakukan setelah
persetujuan Pengelola/Pengguna Barang atas BMN yang tidak dapat
digunakan/dimanfaatkan/dipindahtangankan (lazimnya rusak berat), dengan
cara dibakar/dihancurkan/ditimbun/ditenggelamkan/cara lain, dituangkan
dalam Berita Acara Pemusnahan, lalu ditindaklanjuti penghapusan.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pembukuan_utils import parse_harga

CARA_PEMUSNAHAN = {
    "dibakar": "Dibakar",
    "dihancurkan": "Dihancurkan",
    "ditimbun": "Ditimbun",
    "ditenggelamkan": "Ditenggelamkan",
    "cara_lain": "Cara lain sesuai ketentuan",
}


def _tgl(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def validate_pemusnahan(data: dict, today_iso: str) -> list:
    """Validasi payload BA pemusnahan → daftar pesan kesalahan.

    BA hanya sah setelah pelaksanaan: nomor BA + tanggal (≤ hari ini) +
    nomor persetujuan wajib; cara terdaftar; minimal satu aset.
    """
    errors = []
    if not str(data.get("nomor_ba") or "").strip():
        errors.append("Nomor Berita Acara wajib diisi")
    t = _tgl(data.get("tanggal_ba"))
    hari_ini = _tgl(today_iso)
    if not t:
        errors.append("Tanggal BA wajib (format YYYY-MM-DD)")
    elif hari_ini and t > hari_ini:
        errors.append("Tanggal BA tidak boleh di masa depan")
    if data.get("cara") not in CARA_PEMUSNAHAN:
        valid = ", ".join(CARA_PEMUSNAHAN)
        errors.append(f"Cara pemusnahan tidak dikenal (pilihan: {valid})")
    if not str(data.get("nomor_persetujuan") or "").strip():
        errors.append("Nomor persetujuan Pengelola/Pengguna Barang wajib "
                      "(pemusnahan tanpa persetujuan = temuan)")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset yang dimusnahkan")
    return errors


def kelayakan_musnah(asset: dict):
    """(layak, alasan) — objek pemusnahan lazimnya rusak berat/usang."""
    kondisi = str(asset.get("condition") or "").strip()
    if kondisi != "Rusak Berat":
        return False, (f"Kondisi '{kondisi or 'kosong'}' — pemusnahan hanya untuk "
                       "barang rusak berat/usang yang tak dapat dimanfaatkan "
                       "(PMK 83/2016)")
    return True, ""


def rekap_pemusnahan(records):
    """Ringkasan register BA: jumlah BA, aset, nilai perolehan musnah."""
    jumlah_aset = 0
    nilai = 0.0
    for r in records or []:
        for a in r.get("aset") or []:
            jumlah_aset += 1
            nilai += parse_harga(a.get("harga"))
    return {"jumlah_ba": len(records or []), "jumlah_aset": jumlah_aset,
            "nilai": nilai}
