"""Permohonan transaksi pembukuan ASET ber-persetujuan — ASET-GERBANG-1.

Lanjutan audit permohonan aset (2026-08-09): pola SEDIA-KPB persediaan
digeneralisasi ke transaksi pembukuan aset yang selama ini dieksekusi
`require_writer` LANGSUNG padahal menulis jurnal paling berdampak:

  reklasifikasi      — pasangan 304/107, kode+NUP aset berganti in-place;
  kdp_pengembangan   — 503, nilai berjalan KDP bertambah;
  kdp_selesai        — pasangan 505/105, KDP menjadi aset definitif.

Writer mengajukan PERMOHONAN; eksekusi hanya terjadi saat admin satker yang
BUKAN pengajunya menyetujui (pemisahan peran ditegakkan kode lewat
`boleh_putuskan` yang SAMA dengan persediaan — satu aturan, dua domain).
Dokumen "Surat Persetujuan Transaksi Aset" terbit ber-nomor booking dengan
tanda tangan Kuasa Pengguna Barang.

Modul ini hanya aturan MURNI (tanpa DB/HTTP); penegakan + eksekusi ada di
routes/aset_permohonan.py.
"""
from pembukuan_utils import parse_harga

# Jalur = endpoint eksekusi yang diwakilinya (routes/mutasi_bmn.py). Payload
# permohonan adalah body ASLI endpoint itu, divalidasi ulang oleh model
# Pydantic yang sama saat dieksekusi — tidak ada skema kedua yang bisa
# melenceng dari implementasi tunggal.
JALUR_PERMOHONAN_ASET = {
    "reklasifikasi": "Reklasifikasi Kodefikasi (304/107)",
    "kdp_pengembangan": "Pengembangan KDP (503)",
    "kdp_selesai": "Penyelesaian KDP (505/105)",
}


def validate_permohonan_aset(jalur: str, payload, asset_id: str = ""):
    """(ok, err) bentuk minimum permohonan — validasi ISI transaksi tetap
    milik model Pydantic + validator endpoint eksekusi (satu sumber aturan)."""
    if jalur not in JALUR_PERMOHONAN_ASET:
        valid = ", ".join(sorted(JALUR_PERMOHONAN_ASET))
        return False, f"Jalur permohonan tidak dikenal (pilihan: {valid})"
    if not isinstance(payload, dict) or not payload:
        return False, "Payload transaksi wajib diisi"
    if not str(asset_id or "").strip():
        return False, "asset_id wajib diisi"
    return True, ""


def ringkasan_permohonan_aset(jalur: str, payload: dict, aset: dict):
    """Satu kalimat ringkas untuk daftar & surat — murni, tahan payload cacat."""
    p = payload or {}
    a = aset or {}
    label = JALUR_PERMOHONAN_ASET.get(jalur, jalur)
    inti = (f"{a.get('asset_name') or 'aset'} "
            f"({a.get('asset_code') or '-'}/{a.get('NUP') or '-'})")
    if jalur == "reklasifikasi":
        return f"{label}: {inti} → kode {p.get('kode_baru', '-')}"
    if jalur == "kdp_pengembangan":
        return (f"{label}: {inti} + "
                f"Rp{int(parse_harga(p.get('nilai'))):,}".replace(",", ".")
                + f" ({p.get('keterangan') or 'termin'})")
    if jalur == "kdp_selesai":
        return f"{label}: {inti} → aset definitif kode {p.get('kode_baru', '-')}"
    return f"{label}: {inti}"
