"""Referensi Ruangan — LOGIKA MURNI (tanpa Mongo/IO).

Dasar lokasi TERSTRUKTUR untuk KIR (Kartu Inventaris Ruangan) & DBR (Daftar
Barang Ruangan) — penatausahaan BMN, PMK 181/2016. Selama ini lokasi aset di
AMAN berupa teks bebas; master ruangan memungkinkan penataan per ruangan +
menunjuk **Penanggung Jawab Ruangan** (dari registry pejabat, peran
`penanggung_jawab_ruangan`).
"""


def validate_ruangan(doc):
    """Kembalikan daftar pesan error (kosong bila valid). MURNI (teruji unit)."""
    errors = []
    if not str((doc or {}).get("kode_ruangan") or "").strip():
        errors.append("Kode ruangan wajib diisi")
    if not str((doc or {}).get("nama_ruangan") or "").strip():
        errors.append("Nama ruangan wajib diisi")
    return errors


def ringkas_lokasi(ruangan):
    """String lokasi ringkas untuk label/laporan: 'Gedung · Lt. N · KODE — Nama'.

    Bagian yang kosong dilewati; aman untuk masukan sebagian/None. MURNI.
    """
    r = ruangan or {}
    bagian = []
    gedung = str(r.get("gedung") or "").strip()
    if gedung:
        bagian.append(gedung)
    lantai = str(r.get("lantai") or "").strip()
    if lantai:
        bagian.append(f"Lt. {lantai}")
    kode = str(r.get("kode_ruangan") or "").strip()
    nama = str(r.get("nama_ruangan") or "").strip()
    inti = " — ".join([x for x in (kode, nama) if x])
    if inti:
        bagian.append(inti)
    return " · ".join(bagian)
