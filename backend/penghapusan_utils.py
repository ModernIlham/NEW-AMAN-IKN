"""Logika murni PENGHAPUSAN (Fase 6 tahap awal: kandidat usul hapus).

PMK 83/PMK.06/2016 (pustaka §1 & §7): penghapusan didahului sebab yang
sah — a.l. pemusnahan/pemindahtanganan untuk barang rusak berat, atau
penelusuran + telaah TGR untuk barang yang tidak ditemukan saat
inventarisasi. Modul ini MENJARING kandidat dari data inventarisasi
(kondisi + status inventarisasi) — pengajuan formal & SK menyusul.

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
