"""Logika murni PERENCANAAN (Fase 4 — tahap awal: kandidat RKBMN pemeliharaan).

PMK 153/PMK.06/2021 (riset di pustaka §4): usulan RKBMN pemeliharaan hanya
untuk BMN kondisi Baik/Rusak Ringan; TIDAK boleh untuk rusak berat
(jalurnya usul penghapusan/pemindahtanganan), BMN idle (PMK 120/2024),
atau barang yang tidak dioperasikan. Bahan penyusunan: Daftar Barang Kuasa
Pengguna + Daftar Hasil Pemeliharaan — di AMAN: master aset + riwayat
biaya modul Pemeliharaan.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

KONDISI_LAYAK = ("Baik", "Rusak Ringan")


def kelayakan_rkbmn(asset: dict):
    """(layak, alasan) usulan pemeliharaan satu aset — urutan telaah:
    kondisi RB dulu (jalur lain), lalu status operasional, lalu kondisi."""
    kondisi = str(asset.get("condition") or "").strip()
    status = str(asset.get("status") or "").strip()
    if kondisi == "Rusak Berat":
        return False, "Rusak Berat — jalurnya usul penghapusan/pemindahtanganan, bukan pemeliharaan"
    if status == "Nonaktif":
        return False, "Status Nonaktif — barang tidak dioperasikan"
    if status == "Idle":
        return False, "BMN idle — usulkan penetapan status/penyerahan (PMK 120/2024)"
    if kondisi in KONDISI_LAYAK:
        return True, ""
    return False, f"Kondisi belum tercatat ({kondisi or 'kosong'}) — lengkapi data aset dulu"


def rekap_rkbmn(assets, biaya_per_aset=None):
    """Pisahkan aset layak/tidak layak usul pemeliharaan + biaya riwayat.

    biaya_per_aset: {asset_id: {"jumlah": n, "total_biaya": x}} dari rekap
    modul Pemeliharaan (tahun anggaran berjalan) — aset dengan riwayat
    biaya terbesar tampil dulu (bahan pertimbangan usulan).
    """
    biaya_per_aset = biaya_per_aset or {}
    layak, tidak = [], []
    for a in assets or []:
        ok, alasan = kelayakan_rkbmn(a)
        b = biaya_per_aset.get(a.get("id")) or {}
        row = {
            "id": a.get("id"),
            "asset_code": a.get("asset_code"),
            "NUP": a.get("NUP"),
            "asset_name": a.get("asset_name"),
            "condition": a.get("condition"),
            "status": a.get("status"),
            "location": a.get("location"),
            "riwayat_jumlah": int(b.get("jumlah", 0) or 0),
            "riwayat_biaya": float(b.get("total_biaya", 0) or 0.0),
        }
        if ok:
            layak.append(row)
        else:
            row["alasan"] = alasan
            tidak.append(row)
    layak.sort(key=lambda r: (-r["riwayat_biaya"], r["asset_name"] or ""))
    tidak.sort(key=lambda r: (r["alasan"], r["asset_name"] or ""))
    return {
        "layak": layak,
        "tidak": tidak,
        "ringkasan": {
            "total": len(layak) + len(tidak),
            "layak": len(layak),
            "tidak": len(tidak),
            "total_biaya_riwayat": sum(r["riwayat_biaya"] for r in layak),
        },
    }
