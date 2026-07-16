"""Referensi Pejabat & Unit Akuntansi Penatausahaan BMN — LOGIKA MURNI.

Dasar: PMK 181/PMK.06/2016 (Penatausahaan BMN). Struktur unit akuntansi
Pengguna Barang berjenjang (UAPB → UAPPB-E1 → UAPPB-W → UAKPB → UAPKPB);
di tingkat satker penanggung jawab UAKPB = Kepala Satker = **Kuasa Pengguna
Barang (KPB)**, penanda tangan LBKP/DBKP/laporan BMN & dokumen penghapusan/
BAST. Perekaman data BMN dijalankan **Petugas Penatausahaan / Operator
SIMAK-BMN** yang ditunjuk dengan SK. Modul ini menjadikan pejabat itu
sebagai REFERENSI (seperti "referensi penanda tangan" di SAKTI) agar dokumen
resmi memakai data pejabat yang benar & berlaku pada tanggalnya.
"""

# Peran pejabat dalam penatausahaan BMN (kode → uraian).
PERAN_PEJABAT = {
    "kuasa_pengguna_barang": "Kuasa Pengguna Barang (KPB) — Kepala Satker",
    "penatausahaan_bmn": "Petugas Penatausahaan BMN / Operator SIMAK-BMN",
    "pengurus_barang": "Pengurus Barang",
    "penanggung_jawab_ruangan": "Penanggung Jawab Ruangan (KIR/DBR)",
    "ppk": "Pejabat Pembuat Komitmen (PPK)",
    "pengguna_barang": "Pengguna Barang (Menteri/Pimpinan Lembaga)",
}

# Jenjang unit akuntansi Pengguna Barang (PMK 181/2016) — kode → detail.
UNIT_AKUNTANSI = {
    "uapb": {"uraian": "Unit Akuntansi Pengguna Barang",
             "penanggung_jawab": "Menteri/Pimpinan Lembaga"},
    "uappb_e1": {"uraian": "Unit Akuntansi Pembantu Pengguna Barang — Eselon I",
                 "penanggung_jawab": "Pejabat Eselon I"},
    "uappb_w": {"uraian": "Unit Akuntansi Pembantu Pengguna Barang — Wilayah",
                "penanggung_jawab": "Pejabat Eselon II"},
    "uakpb": {"uraian": "Unit Akuntansi Kuasa Pengguna Barang",
              "penanggung_jawab": "Kepala Kantor/Satker (Kuasa Pengguna Barang)"},
    "uapkpb": {"uraian": "Unit Akuntansi Pembantu Kuasa Pengguna Barang",
               "penanggung_jawab": "Pembantu Kuasa Pengguna Barang"},
}


def validate_pejabat(doc):
    """Kembalikan daftar pesan error (kosong bila valid). MURNI (teruji unit)."""
    errors = []
    if not str((doc or {}).get("nama") or "").strip():
        errors.append("Nama pejabat wajib diisi")
    peran = (doc or {}).get("peran") or []
    if not isinstance(peran, list) or not peran:
        errors.append("Minimal satu peran pejabat wajib dipilih")
    else:
        tak_dikenal = [p for p in peran if p not in PERAN_PEJABAT]
        if tak_dikenal:
            errors.append(f"Peran tidak dikenal: {', '.join(map(str, tak_dikenal))}")
    ua = (doc or {}).get("unit_akuntansi")
    if ua and ua not in UNIT_AKUNTANSI:
        errors.append(f"Unit akuntansi tidak dikenal: {ua}")
    mulai = str((doc or {}).get("berlaku_mulai") or "").strip()
    selesai = str((doc or {}).get("berlaku_selesai") or "").strip()
    if mulai and selesai and mulai > selesai:
        errors.append("Tanggal 'berlaku mulai' melewati 'berlaku selesai'")
    return errors


def _berlaku_pada(pj, per_iso):
    """True bila pejabat berlaku pada tanggal `per_iso` (rentang kosong = terbuka)."""
    if pj.get("aktif") is False:
        return False
    per = str(per_iso or "").strip()[:10]
    mulai = str(pj.get("berlaku_mulai") or "").strip()[:10]
    selesai = str(pj.get("berlaku_selesai") or "").strip()[:10]
    if per:
        if mulai and per < mulai:
            return False
        if selesai and per > selesai:
            return False
    return True


def pejabat_aktif_untuk_peran(pejabat_list, peran, per_iso=None):
    """Pejabat yang berlaku & memegang `peran` pada tanggal `per_iso`.

    Bila banyak yang cocok, pilih yang SK-nya paling baru (berlaku_mulai
    terbesar). Kembalikan dict pejabat atau None. MURNI (teruji unit).
    """
    kandidat = [
        pj for pj in (pejabat_list or [])
        if peran in (pj.get("peran") or []) and _berlaku_pada(pj, per_iso)
    ]
    if not kandidat:
        return None
    kandidat.sort(key=lambda pj: str(pj.get("berlaku_mulai") or ""), reverse=True)
    return kandidat[0]
