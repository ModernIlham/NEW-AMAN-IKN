"""Logika murni PENGHAPUSAN (Fase 6 tahap awal: kandidat usul hapus).

PMK 83/PMK.06/2016 (pustaka §1 & §7): penghapusan didahului sebab yang
sah — a.l. pemusnahan/pemindahtanganan untuk barang rusak berat, atau
penelusuran + telaah TGR untuk barang yang tidak ditemukan saat
inventarisasi. Modul ini MENJARING kandidat dari data inventarisasi
(kondisi + status inventarisasi); register usulan formal + SK penghapusan
dikelola di routes/penghapusan.py dan memproyeksikan status ke master aset.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from pembukuan_utils import parse_harga

JALUR_KANDIDAT = {
    "tidak_ditemukan": (
        "Tidak Ditemukan — penelusuran + telaah TGR",
        "Tidak ditemukan saat inventarisasi: lakukan penelusuran; bila tetap "
        "tidak ditemukan, usulkan penghapusan disertai telaah Tuntutan Ganti "
        "Rugi (PMK 83/2016)"),
    "rusak_berat": (
        "Rusak Berat — pemusnahan/pemindahtanganan",
        "Rusak berat: usulkan pemusnahan atau pemindahtanganan, lalu "
        "penghapusan setelah persetujuan (PMK 83/2016)"),
}


def jalur_kandidat(asset):
    """Kunci jalur kandidat penghapusan sebuah aset, atau None.

    Tidak Ditemukan diprioritaskan di atas Rusak Berat: barang yang tak
    ditemukan tidak bisa dimusnahkan — jalurnya penelusuran/TGR.
    """
    if str(asset.get("inventory_status") or "").strip() == "Tidak Ditemukan":
        return "tidak_ditemukan"
    if str(asset.get("condition") or "").strip() == "Rusak Berat":
        return "rusak_berat"
    return None


STATUS_USULAN = {
    "diusulkan": "Diusulkan",
    "diproses": "Diproses (Pengguna/Pengelola Barang)",
    "sk_terbit": "SK Penghapusan Terbit",
    "ditolak": "Ditolak/Dibatalkan",
}

# Alur PMK 83/2016: usulan → persetujuan → SK; tolak bisa di dua tahap.
# "diproses" boleh KEMBALI ke "diusulkan" (koreksi salah klik — audit G5 #10);
# status terminal (sk_terbit/ditolak) tetap tak bisa mundur.
TRANSISI_USULAN = {
    "diusulkan": {"diproses", "ditolak"},
    "diproses": {"sk_terbit", "ditolak", "diusulkan"},
    "sk_terbit": set(),
    "ditolak": set(),
}


def boleh_transisi(dari: str, ke: str) -> bool:
    """Apakah perpindahan status usulan sah menurut alur PMK 83/2016."""
    return ke in TRANSISI_USULAN.get(dari, set())


def validate_transisi(dari: str, ke: str, nomor_sk: str = "") -> list:
    """Daftar pesan kesalahan transisi status usulan."""
    errors = []
    if ke not in STATUS_USULAN:
        valid = ", ".join(STATUS_USULAN)
        errors.append(f"Status tidak dikenal (pilihan: {valid})")
        return errors
    if not boleh_transisi(dari, ke):
        errors.append(
            f"Transisi {STATUS_USULAN.get(dari, dari)} → {STATUS_USULAN[ke]} tidak sah")
    if ke == "sk_terbit" and not str(nomor_sk or "").strip():
        errors.append("Nomor SK penghapusan wajib diisi saat SK terbit")
    return errors


def build_asset_penghapusan_projection(usulan: dict, now_iso: str) -> dict:
    """Proyeksi master aset saat SK penghapusan terbit (Prinsip 3 Bab 5:
    transaksi = jurnal, master = proyeksi).

    Mengembalikan dict `$set` untuk `db.assets` — HANYA field marker khusus
    penghapusan. SENGAJA tidak menyentuh `inventory_status`/`condition`/
    `purchase_price`: itu dibaca laporan resmi (DBKP/neraca/penyusutan), jadi
    mengubahnya di sini berisiko regresi laporan. Penyaringan aset ber-SK dari
    laporan adalah langkah lanjutan terpisah — di sini master cukup MEMBAWA
    kebenaran transaksi hilir (jejak SK) + `dihapus=True`. Pemanggil menambah
    `$inc: {version: 1}` (bust cache media/ETag + picu OCC 409 pada form usang).
    """
    return {
        "dihapus": True,
        "penghapusan": {
            "status": "sk_terbit",
            "usulan_id": str(usulan.get("id") or ""),
            "jalur": str(usulan.get("jalur") or ""),
            "nomor_sk": str(usulan.get("nomor_sk") or "").strip(),
            "tanggal_sk": str(usulan.get("tanggal_sk") or "").strip()[:10],
            "diproyeksikan_pada": now_iso,
        },
    }


def rekap_kandidat(assets):
    """Jaring kandidat per jalur → {"jalur": {key: {label, alasan, rows,
    jumlah, nilai}}, "ringkasan": {...}} — semua dari data nyata."""
    jalur = {
        k: {"label": v[0], "alasan": v[1], "rows": [], "jumlah": 0, "nilai": 0.0}
        for k, v in JALUR_KANDIDAT.items()
    }
    for a in assets or []:
        k = jalur_kandidat(a)
        if not k:
            continue
        harga = parse_harga(a.get("purchase_price"))
        b = jalur[k]
        b["rows"].append({
            "id": a.get("id"),
            "asset_code": a.get("asset_code"),
            "NUP": a.get("NUP"),
            "asset_name": a.get("asset_name"),
            "location": a.get("location"),
            "harga": harga,
            "keterangan": str(a.get("uraian_tidak_ditemukan") or "").strip(),
        })
        b["jumlah"] += 1
        b["nilai"] += harga
    for b in jalur.values():
        b["rows"].sort(key=lambda r: (-r["harga"], r["asset_name"] or ""))
    return {
        "jalur": jalur,
        "ringkasan": {
            "jumlah": sum(b["jumlah"] for b in jalur.values()),
            "nilai": sum(b["nilai"] for b in jalur.values()),
        },
    }


# ---------------------------------------------------------------------------
# Jejak Aset Terhapus (arsip read-only). Aset yang dihapus permanen tetap
# tertelusur lewat audit_logs — endpoint hanya MEMBACA jejak itu, tidak
# mengubah mekanisme hapus. Nilai perolehan direkam di changes saat hapus
# (field purchase_price, sisi "from").
# ---------------------------------------------------------------------------

def _nilai_dari_changes(changes) -> float:
    """Ambil nilai perolehan aset dari entri audit penghapusan."""
    for c in changes or []:
        if c.get("field") == "purchase_price":
            return parse_harga(c.get("from"))
    return 0.0


def normalisasi_jejak_terhapus(logs):
    """Ubah entri audit_logs penghapusan → baris jejak siap tampil."""
    rows = []
    for lg in logs or []:
        rows.append({
            "id": lg.get("id"),
            "asset_code": lg.get("asset_code") or "",
            "NUP": lg.get("nup") or "",
            "asset_name": lg.get("asset_name") or "",
            "nilai": _nilai_dari_changes(lg.get("changes")),
            "oleh": lg.get("username") or "",
            "waktu": lg.get("timestamp") or "",
            "activity_id": lg.get("activity_id") or "",
            "massal": lg.get("action") == "bulk_delete",
        })
    return rows


def rekap_jejak_terhapus(rows):
    """Ringkasan jejak terhapus: jumlah baris + total nilai perolehan."""
    return {
        "jumlah": len(rows or []),
        "total_nilai": sum(float(r.get("nilai") or 0) for r in (rows or [])),
    }
