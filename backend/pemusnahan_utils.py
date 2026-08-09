"""Logika murni PEMUSNAHAN (Fase 6 tahap awal: register BA Pemusnahan).

PMK 83/PMK.06/2016 (pustaka §1 & §12): pemusnahan dilakukan setelah
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


def alasan_usulan_dari_ba(ba: dict) -> str:
    """Keterangan usulan penghapusan yang merujuk BA pemusnahan.

    Tindak lanjut PMK 83/2016: barang yang telah dimusnahkan diusulkan
    hapus dari DBKP dengan BA sebagai dokumen sumber.
    """
    return (f"Telah dimusnahkan — BA {ba.get('nomor_ba') or '-'} tanggal "
            f"{str(ba.get('tanggal_ba') or '-')[:10]} (persetujuan "
            f"{ba.get('nomor_persetujuan') or '-'})")


def usulan_penghapusan_dari_ba(ba: dict, aset: dict, now_iso: str, oleh, new_id: str) -> dict:
    """Record `usulan_penghapusan` (register Penghapusan) untuk SATU aset dari
    BA Pemusnahan — dengan TAUT STRUKTURAL ke BA sumbernya.

    Integrasi (masterplan Bab 5, prinsip 3 & 4): selain keterangan teks, usulan
    menyimpan FK `sumber_ba_id` (id BA pemusnahan) + `sumber_ba_nomor` dan
    `sumber_modul="pemusnahan"`, sehingga rantai **Pemusnahan → Penghapusan**
    bisa ditelusuri balik tanpa mencocokkan string nomor BA. Fungsi murni
    (tanpa Mongo/uuid internal) supaya teruji unit; `new_id` diberikan pemanggil.
    """
    return {
        "id": new_id,
        "asset_id": aset.get("asset_id"),
        "asset_code": aset.get("asset_code"),
        "NUP": aset.get("NUP"),
        "asset_name": aset.get("asset_name"),
        "jalur": "rusak_berat",
        "status": "diusulkan",
        "nomor_sk": "",
        "tanggal_sk": "",
        # Isolasi multi-satker: tanpa ini scope_query_field_satker menganggap
        # tiket "era lama" yang terbuka utk SEMUA satker → bocor & bisa
        # ditransisikan lintas satker.
        "kode_satker": str(ba.get("kode_satker") or "").strip(),
        "keterangan": alasan_usulan_dari_ba(ba),
        # ── Taut sumber (Pemusnahan → Penghapusan) ──
        "sumber_modul": "pemusnahan",
        "sumber_ba_id": ba.get("id"),
        "sumber_ba_nomor": ba.get("nomor_ba") or "",
        "lampiran": [],
        "riwayat": [{"status": "diusulkan", "tanggal": now_iso, "oleh": oleh,
                     "catatan": f"Otomatis dari BA {ba.get('nomor_ba')}"}],
        "created_by": oleh,
        "created_at": now_iso,
        "updated_at": now_iso,
    }


# ---------------------------------------------------------------------------
# Usulan pemusnahan berstatus (ASET-MUSNAH).
# Register BA di atas hanya merekam BA JADI (setelah persetujuan +
# pelaksanaan) — proses usulan KPB ke Pengelola/Pengguna Barang yang
# diwajibkan PMK 83/2016 tidak pernah terekam; nomor persetujuan cukup
# diketik. Tiket usulan merekam jejaknya: surat usulan → persetujuan →
# pelaksanaan (BA lahir otomatis dari usulan).
# ---------------------------------------------------------------------------
STATUS_USULAN_PEMUSNAHAN = {
    "draf": "Draf",
    "diajukan": "Diajukan ke Pengelola Barang",
    "disetujui": "Disetujui (persetujuan terbit)",
    "ditolak": "Ditolak",
    "dilaksanakan": "Dilaksanakan (BA terbit)",
    "dibatalkan": "Dibatalkan",
}

# diajukan boleh MUNDUR ke draf (koreksi salah klik — pola register TGR);
# ditolak/dilaksanakan/dibatalkan terminal.
TRANSISI_USULAN_PEMUSNAHAN = {
    "draf": {"diajukan", "dibatalkan"},
    "diajukan": {"disetujui", "ditolak", "draf"},
    "disetujui": {"dilaksanakan", "dibatalkan"},
    "ditolak": set(),
    "dilaksanakan": set(),
    "dibatalkan": set(),
}

STATUS_USULAN_MUSNAH_TERMINAL = {"ditolak", "dilaksanakan", "dibatalkan"}

# status tujuan → (field nomor, field tanggal, label dokumen wajib)
DOK_USULAN_PEMUSNAHAN = {
    "diajukan": ("nomor_usulan", "tanggal_usulan",
                 "Nomor surat usulan pemusnahan ke Pengelola Barang"),
    "disetujui": ("nomor_persetujuan", "tanggal_persetujuan",
                  "Nomor surat persetujuan Pengelola/Pengguna Barang"),
    "dilaksanakan": ("nomor_ba", "tanggal_ba",
                     "Nomor Berita Acara Pemusnahan"),
}


def validate_usulan_pemusnahan(data: dict) -> list:
    """Validasi payload usulan pemusnahan baru → daftar galat."""
    errors = []
    if data.get("cara") not in CARA_PEMUSNAHAN:
        valid = ", ".join(CARA_PEMUSNAHAN)
        errors.append(f"Cara pemusnahan tidak dikenal (pilihan: {valid})")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset yang diusulkan musnah")
    return errors


def validate_transisi_usulan_pemusnahan(dari: str, ke: str, payload: dict,
                                        today_iso: str) -> list:
    """Daftar galat transisi usulan — dokumen wajib per tahap; BA
    (dilaksanakan) tidak boleh bertanggal masa depan."""
    p = payload or {}
    if ke not in STATUS_USULAN_PEMUSNAHAN:
        return [f"Status tujuan tidak dikenal: {ke}"]
    if ke not in TRANSISI_USULAN_PEMUSNAHAN.get(dari, set()):
        return [f"Transisi {STATUS_USULAN_PEMUSNAHAN.get(dari, dari)} → "
                f"{STATUS_USULAN_PEMUSNAHAN.get(ke, ke)} tidak diizinkan"]
    errors = []
    dok = DOK_USULAN_PEMUSNAHAN.get(ke)
    if dok and not str(p.get("nomor_dokumen") or "").strip():
        errors.append(f"{dok[2]} wajib diisi")
    if ke == "dilaksanakan":
        t = _tgl(p.get("tanggal_dokumen"))
        hari_ini = _tgl(today_iso)
        if t and hari_ini and t > hari_ini:
            errors.append("Tanggal BA tidak boleh di masa depan")
    return errors


def ba_dari_usulan(usulan: dict, now_iso: str, oleh, new_id: str,
                   nomor_ba: str, tanggal_ba: str) -> dict:
    """Record BA pemusnahan (db.pemusnahan) yang LAHIR dari usulan
    dilaksanakan — nomor persetujuan & aset tersnapshot dari usulan,
    ber-taut balik `usulan_id`. Fungsi murni supaya teruji unit."""
    return {
        "id": new_id,
        "kode_satker": str(usulan.get("kode_satker") or "").strip(),
        "nomor_ba": str(nomor_ba or "").strip(),
        "tanggal_ba": str(tanggal_ba or now_iso).strip()[:10],
        "cara": usulan.get("cara"),
        "nomor_persetujuan": str(usulan.get("nomor_persetujuan") or "").strip(),
        "keterangan": str(usulan.get("keterangan") or "").strip(),
        "aset": list(usulan.get("aset") or []),
        "lampiran": [],
        "usulan_id": usulan.get("id"),
        "created_by": oleh,
        "created_at": now_iso,
        "updated_at": now_iso,
    }


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
