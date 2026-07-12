"""Logika murni PENGGUNAAN (Fase 3 — modul Penggunaan tahap awal).

Rekap aset per PEMEGANG (pengguna barang) lintas kegiatan, dibangun dari
field yang sudah dicatat modul inventarisasi: `user` (nama pemegang/
jabatan/operasional), `pengguna_nip`, `pengguna_melekat_ke`,
`pengguna_jabatan`, dan `bast_file_id` (BAST terunggah) — plus daftar
pantau BMN IDLE (PMK 120/2024: BMN yang tidak digunakan untuk tusi wajib
diklarifikasi lalu diserahkan ke Pengelola Barang bila benar idle).

Dasar: PMK 40/2024 (Penggunaan BMN) + PMK 120/2024 (BMN idle) — pustaka
§1 & §8. Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

# Status tiket penanganan BMN idle → label Indonesia
STATUS_IDLE = {
    "klarifikasi": "Klarifikasi (diteliti penggunaannya)",
    "digunakan_kembali": "Digunakan Kembali (bukan idle)",
    "usul_serah": "Diusulkan Serah ke Pengelola",
    "diserahkan": "Diserahkan ke Pengelola Barang",
}

TRANSISI_IDLE = {
    "klarifikasi": {"digunakan_kembali", "usul_serah"},
    "usul_serah": {"diserahkan"},
    "digunakan_kembali": set(),
    "diserahkan": set(),
}


def indikasi_idle(asset: dict):
    """(kandidat, alasan) — indikasi BMN idle dari data inventarisasi.

    Kandidat: aset berstatus Nonaktif ATAU tanpa pengguna tercatat.
    Aset Tidak Ditemukan bukan kandidat idle (jalurnya penelusuran/TGR
    di modul Penghapusan). Hanya penanda klarifikasi — keputusan idle
    final lewat penelitian (PMK 120/2024).
    """
    if str(asset.get("inventory_status") or "").strip() == "Tidak Ditemukan":
        return False, ""
    if str(asset.get("status") or "").strip() == "Nonaktif":
        return True, "Status aset Nonaktif"
    if not str(asset.get("user") or "").strip():
        return True, "Tanpa pengguna tercatat (indikasi tidak digunakan untuk tusi)"
    return False, ""


def validate_transisi_idle(dari: str, ke: str, data: dict) -> list:
    """Validasi pindah status tiket idle + dokumen wajib per tahap."""
    errors = []
    if ke not in STATUS_IDLE:
        errors.append("Status tujuan tidak dikenal")
        return errors
    if ke not in TRANSISI_IDLE.get(dari, set()):
        errors.append(f"Transisi {dari} → {ke} tidak sah")
        return errors
    if ke == "usul_serah" and not str(data.get("nomor_usulan") or "").strip():
        errors.append("Nomor surat usulan penyerahan wajib diisi")
    if ke == "diserahkan" and not str(data.get("nomor_bast_serah") or "").strip():
        errors.append("Nomor BAST penyerahan ke Pengelola wajib diisi")
    return errors


def rekap_idle(kandidat, tiket) -> dict:
    """Ringkasan dasbor idle: jumlah kandidat + tiket per status."""
    per_status = {k: 0 for k in STATUS_IDLE}
    for t in tiket or []:
        s = t.get("status")
        if s in per_status:
            per_status[s] += 1
    return {"kandidat": len(kandidat or []), "per_status": per_status,
            "tiket": len(tiket or [])}


def kunci_pemegang(asset: dict):
    """Kunci identitas pemegang: (nama_norm, nip). None bila tanpa pengguna.

    Nama dinormalkan (trim + satu spasi + lower) supaya "Budi  Santoso" dan
    "budi santoso" tergabung; NIP kosong tetap membentuk kunci tersendiri
    per nama (dua orang beda NIP tidak boleh tercampur).
    """
    nama = " ".join(str(asset.get("user") or "").split())
    if not nama:
        return None
    nip = str(asset.get("pengguna_nip") or "").strip()
    return (nama.lower(), nip)


def rekap_pemegang(assets):
    """Rekap per pemegang → list terurut (jumlah aset terbanyak dulu).

    Tiap entri: nama (tampilan pertama yang dijumpai), nip, melekat_ke
    (moda terbanyak), jabatan (bila ada), jumlah_aset, jumlah_bast
    (aset ber-BAST terunggah), kegiatan (set id kegiatan → jumlah),
    lengkap (True bila SEMUA asetnya ber-BAST dan NIP terisi).
    """
    agg = {}
    for a in assets or []:
        key = kunci_pemegang(a)
        if key is None:
            continue
        e = agg.setdefault(key, {
            "nama": " ".join(str(a.get("user") or "").split()),
            "nip": key[1],
            "jabatan": "",
            "_melekat": {},
            "jumlah_aset": 0,
            "jumlah_bast": 0,
            "_kegiatan": set(),
        })
        e["jumlah_aset"] += 1
        if str(a.get("bast_file_id") or "").strip():
            e["jumlah_bast"] += 1
        jab = str(a.get("pengguna_jabatan") or "").strip()
        if jab and not e["jabatan"]:
            e["jabatan"] = jab
        melekat = str(a.get("pengguna_melekat_ke") or "").strip()
        if melekat:
            e["_melekat"][melekat] = e["_melekat"].get(melekat, 0) + 1
        act = str(a.get("activity_id") or "").strip()
        if act:
            e["_kegiatan"].add(act)

    hasil = []
    for e in agg.values():
        melekat = max(e["_melekat"], key=e["_melekat"].get) if e["_melekat"] else ""
        hasil.append({
            "nama": e["nama"],
            "nip": e["nip"],
            "jabatan": e["jabatan"],
            "melekat_ke": melekat,
            "jumlah_aset": e["jumlah_aset"],
            "jumlah_bast": e["jumlah_bast"],
            "jumlah_kegiatan": len(e["_kegiatan"]),
            "lengkap": bool(e["nip"]) and e["jumlah_bast"] == e["jumlah_aset"],
        })
    hasil.sort(key=lambda x: (-x["jumlah_aset"], x["nama"].lower()))
    return hasil
