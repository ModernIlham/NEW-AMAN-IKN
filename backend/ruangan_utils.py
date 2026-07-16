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


def ruangan_aset(asset):
    """Nama ruangan tempat aset berada (dari data yang ADA, tanpa fabrikasi).

    Prioritas: pengguna melekat ke Ruangan (`operasional_jenis == "Ruangan"` →
    nama di `user`), lalu `location` (teks bebas). Bila kosong → penanda
    "(lokasi belum dicatat)" agar aset tak hilang dari DBR. MURNI.
    """
    a = asset or {}
    if str(a.get("operasional_jenis") or "").strip().lower() == "ruangan":
        r = str(a.get("user") or "").strip()
        if r:
            return r
    loc = str(a.get("location") or "").strip()
    return loc or "(lokasi belum dicatat)"


def kelompok_dbr(assets):
    """Kelompokkan aset per ruangan untuk DBR (Daftar Barang Ruangan).

    Kembalikan list terurut nama ruangan: [{"ruangan", "jumlah", "nilai",
    "aset": [...]}]. Nilai = jumlah parse harga perolehan bila tersedia.
    "(lokasi belum dicatat)" selalu ditaruh paling akhir. MURNI (teruji unit).
    """
    from pembukuan_utils import parse_harga
    per = {}
    for a in assets or []:
        nama = ruangan_aset(a)
        g = per.setdefault(nama, {"ruangan": nama, "jumlah": 0, "nilai": 0.0, "aset": []})
        g["jumlah"] += 1
        g["nilai"] += parse_harga(a.get("purchase_price"))
        g["aset"].append(a)
    belum = "(lokasi belum dicatat)"
    rows = sorted((v for k, v in per.items() if k != belum), key=lambda x: x["ruangan"])
    if belum in per:
        rows.append(per[belum])
    return rows


def cocok_ruangan_master(label, master_list):
    """Cari ruangan master yang cocok dengan label ruangan (dari data aset).

    Cocok bila label = "KODE — Nama", KODE saja, atau Nama saja (abai kapital
    & spasi tepi). Dipakai KIR untuk menautkan Penanggung Jawab Ruangan dari
    master. Kembalikan dict master atau None. MURNI (teruji unit).
    """
    t = str(label or "").strip().lower()
    if not t:
        return None
    for m in master_list or []:
        kode = str(m.get("kode_ruangan") or "").strip()
        nama = str(m.get("nama_ruangan") or "").strip()
        kandidat = {kode.lower(), nama.lower(), f"{kode} — {nama}".strip(" —").lower()}
        kandidat.discard("")
        if t in kandidat:
            return m
    return None
