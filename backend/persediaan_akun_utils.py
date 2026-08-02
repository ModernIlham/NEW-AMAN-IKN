"""Akun neraca Persediaan (sub-kelompok 1171xx) — LOGIKA MURNI.

Persediaan (golongan kodefikasi 1) tersaji di neraca pada akun **117xxx**.
Akun golongan-level (117111) sudah dipetakan di `akun_bas_utils` (#300); modul
ini menyediakan **rincian sub-akun 1171xx** untuk pelaporan posisi persediaan
per akun. Kode 6-digit sub-akun bervariasi per jenis persediaan.

VERIFIKASI (evaluasi #3c, Jul 2026): kode **117111 Barang Konsumsi, 117113 Bahan
untuk Pemeliharaan, 117114 Suku Cadang, 117131 Bahan Baku, 117199 Persediaan
Lainnya** dikonfirmasi konsisten di **laporan neraca/BMN audited berbagai K/L**
(sumber sekunder resmi). KOREKSI dari rujukan awal: **117131 = Bahan Baku**
(sebelumnya keliru "untuk Diserahkan"); kode `117191` (tebakan awal Bahan Baku)
DIHAPUS. Akun **117112 Amunisi** & **117128 (untuk Diserahkan kpd Masyarakat —
seri 11712x per jenis)** masih **[PERLU VERIFIKASI Lampiran BAS / KEP-211/PB/2018]**
(sumber primer .go.id terblokir proxy). Semua dapat ditimpa per sub-kelompok
(5 digit) oleh satker. Default aman = **117111 (Barang Konsumsi)**.

Evaluasi #2 (satu sumber akun golongan-1): `AKUN_PERSEDIAAN_UTAMA` DITURUNKAN dari
`akun_bas_utils.AKUN_NERACA_DEFAULT["1"]` agar tidak ada dua kebenaran akun
golongan Persediaan yang bisa saling drift.
"""
from akun_bas_utils import AKUN_NERACA_DEFAULT

# Akun utama persediaan — satu sumber dari akun_bas golongan "1" (terkonfirmasi).
AKUN_PERSEDIAAN_UTAMA = AKUN_NERACA_DEFAULT["1"]["akun"]

# Sub-akun neraca persediaan (kode 6-digit → uraian) — DITURUNKAN dari seed
# BAS resmi `data/referensi_akun_bas.json` (21 akun 1171xx, sumber KEP-211/
# PB/2018), menutup drift lama saat katalog hardcode hanya memuat 7 akun
# sementara seed BAS memuat 21 (117121 Pita Cukai, 117122-117128 untuk
# diserahkan, 117141 Bansos, 117191 Tujuan Strategis, dst. tak pernah bisa
# dipilih). Fallback minimal dipertahankan bila file seed tak terbaca —
# jangan sampai laporan posisi mati hanya karena katalog kosong.
_FALLBACK_AKUN = {
    "117111": "Persediaan — Barang Konsumsi",
    "117113": "Persediaan — Bahan untuk Pemeliharaan",
    "117114": "Persediaan — Suku Cadang",
    "117131": "Persediaan — Bahan Baku",
    "117199": "Persediaan — Lainnya",
}


def _muat_akun_persediaan_dari_seed():
    import json
    import os
    jalur = os.path.join(os.path.dirname(__file__), "data",
                         "referensi_akun_bas.json")
    try:
        with open(jalur, encoding="utf-8") as f:
            data = json.load(f)
        hasil = {}
        for a in data.get("akun") or []:
            kode = str(a.get("kode") or "")
            if kode.startswith("1171") and len(kode) == 6:
                hasil[kode] = f"Persediaan — {a.get('nama') or kode}"
        return hasil or dict(_FALLBACK_AKUN)
    except (OSError, ValueError):
        return dict(_FALLBACK_AKUN)


AKUN_PERSEDIAAN_DEFAULT = _muat_akun_persediaan_dari_seed()


def validate_akun_persediaan(akun):
    """Kembalikan daftar error (kosong bila valid). MURNI (teruji unit)."""
    errors = []
    a = str(akun or "").strip()
    if not a.isdigit() or len(a) != 6 or not a.startswith("1171"):
        errors.append("Akun persediaan harus 6 digit diawali 1171 (mis. 117111)")
    return errors


def akun_persediaan(kode_barang, peta=None):
    """Akun neraca untuk sebuah kode barang persediaan (via sub-kelompok 5 digit).

    `peta` = {sub_kelompok_5digit: {akun, uraian}} override satker (menang).
    Tanpa override → default **117111 (Barang Konsumsi)**. Kembalikan
    {akun, uraian, sumber}. MURNI (teruji unit).
    """
    peta = peta or {}
    sub = str(kode_barang or "").strip()[:5]
    if sub in peta:
        rec = peta[sub]
        akun = str(rec.get("akun") or "").strip() or AKUN_PERSEDIAAN_UTAMA
        uraian = str(rec.get("uraian") or "").strip() or AKUN_PERSEDIAAN_DEFAULT.get(akun, "")
        return {"akun": akun, "uraian": uraian, "sumber": "override satker"}
    return {"akun": AKUN_PERSEDIAAN_UTAMA,
            "uraian": AKUN_PERSEDIAAN_DEFAULT[AKUN_PERSEDIAAN_UTAMA],
            "sumber": "default (verifikasi Lampiran BAS)"}
