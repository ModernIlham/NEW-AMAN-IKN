"""Penyusun data LAPORAN PERSEDIAAN GAYA SAKTI — LOGIKA MURNI.

Meniru lima laporan resmi Modul Persediaan SAKTI (contoh PDF satker
691778, 2026-08) + dua daftar kondisi:
  1. Laporan Barang Persediaan        (lap_bmn_sedia_satker)
  2. Laporan Posisi Persediaan Neraca (lap_bmn_sedia_posisi_neraca_satker)
  3. Laporan Mutasi Barang Persediaan (lap_bmn_sedia_mutasi_satker)
  4. Laporan Barang Persediaan Per Layer (lap_bmn_sedia_layer_satker)
  5. Daftar Barang Persediaan Tidak Dikuasai (lap_sedia_kuasa)
  6. Daftar Persediaan Usang   7. Daftar Persediaan Rusak

Semua angka dihitung DARI JURNAL `transaksi_persediaan` (posisi as-of =
Σ nilai masuk − Σ nilai keluar s.d. tanggal; koreksi nilai arah `nilai`
ikut lewat `mutasi_periode`) — kecuali laporan Per Layer yang memotret
layer FIFO KINI di master (satu-satunya tempat komposisi layer hidup).
Fungsi murni tanpa Mongo/IO agar teruji unit; route hanya memasok data.
"""
from persediaan_utils import mutasi_periode

_AWAL_WAKTU = "0001-01-01"


def posisi_asof(jurnal_rows, sampai_iso):
    """Posisi tiap barang per tanggal → {pid: {qty, nilai, identitas…}}.

    qty = saldo kuantitas; nilai = Σ nilai masuk − Σ nilai keluar sejak
    awal waktu s.d. `sampai` (konsisten FIFO karena keluar dinilai FIFO;
    koreksi nilai ber-arah `nilai` ikut terhitung).
    """
    rekap = mutasi_periode(jurnal_rows, _AWAL_WAKTU, sampai_iso)
    out = {}
    for pid, e in rekap.items():
        out[pid] = {
            "persediaan_id": pid,
            "kode_barang": e.get("kode_barang") or "",
            "nup": e.get("nup") or "",
            "nama_barang": e.get("nama_barang") or "",
            "qty": e["saldo_akhir"],
            "nilai": e["masuk_nilai"] - e["keluar_nilai"],
        }
    return out


def susun_lap_persediaan(posisi, akun_of, uraian_akun, uraian_kode10):
    """Laporan Barang Persediaan: akun → kode barang 10 digit → nilai.

    `akun_of(kode_barang)` → kode akun 1171xx; `uraian_akun` {akun: label};
    `uraian_kode10` {kode10: uraian sub-sub kelompok} (fallback nama barang
    pertama). Kembalikan {"akun": [ {akun, uraian, baris:[{kode10, uraian,
    nilai}], nilai} ], "total": x} — barang qty 0 & nilai 0 dilewati.
    """
    per_akun = {}
    for p in posisi.values():
        if not p["qty"] and abs(p["nilai"]) < 0.005:
            continue
        akun = akun_of(p["kode_barang"])
        kode10 = str(p["kode_barang"] or "")[:10]
        a = per_akun.setdefault(akun, {"akun": akun,
                                       "uraian": uraian_akun.get(akun, ""),
                                       "per_kode": {}})
        k = a["per_kode"].setdefault(kode10, {
            "kode10": kode10,
            "uraian": uraian_kode10.get(kode10) or p["nama_barang"],
            "nilai": 0.0})
        k["nilai"] += p["nilai"]
    hasil = []
    for akun in sorted(per_akun):
        a = per_akun[akun]
        baris = [a["per_kode"][k] for k in sorted(a["per_kode"])]
        hasil.append({"akun": akun, "uraian": a["uraian"], "baris": baris,
                      "nilai": sum(b["nilai"] for b in baris)})
    return {"akun": hasil, "total": sum(a["nilai"] for a in hasil)}


def susun_lap_neraca(posisi, akun_of, uraian_akun, akun_terdaftar=None):
    """Posisi Persediaan di Neraca: satu baris per akun (nilai agregat).

    `akun_terdaftar` (opsional) = akun yang harus TETAP tampil meski nilai
    0 (contoh SAKTI menampilkan 117113 = 0). Kembalikan {"baris": [
    {akun, uraian, nilai}], "total": x}.
    """
    per_akun = {a: 0.0 for a in (akun_terdaftar or [])}
    for p in posisi.values():
        akun = akun_of(p["kode_barang"])
        per_akun[akun] = per_akun.get(akun, 0.0) + p["nilai"]
    baris = [{"akun": a, "uraian": uraian_akun.get(a, ""),
              "nilai": per_akun[a]} for a in sorted(per_akun)]
    return {"baris": baris, "total": sum(b["nilai"] for b in baris)}


def susun_lap_mutasi(jurnal_rows, dari_iso, sampai_iso, akun_of, uraian_akun):
    """Laporan Mutasi: per akun — SALDO AWAL / MUTASI TAMBAH / MUTASI
    KURANG / NILAI akhir (semua NILAI rupiah, seperti contoh SAKTI).

    Saldo awal nilai = posisi as-of sehari sebelum `dari` (dihitung dari
    jurnal, bukan master); tambah/kurang = nilai mutasi dalam periode
    (koreksi nilai ikut). Kembalikan {"baris": [...], "total": {...}}.
    """
    periode = mutasi_periode(jurnal_rows, dari_iso, sampai_iso)
    per_akun = {}
    for e in periode.values():
        akun = akun_of(e.get("kode_barang") or "")
        a = per_akun.setdefault(akun, {"akun": akun,
                                       "uraian": uraian_akun.get(akun, ""),
                                       "awal": 0.0, "tambah": 0.0,
                                       "kurang": 0.0})
        a["tambah"] += e["masuk_nilai"]
        a["kurang"] += e["keluar_nilai"]
    # Saldo awal NILAI: seluruh mutasi sebelum `dari`
    awal = mutasi_periode(jurnal_rows, _AWAL_WAKTU, _hari_sebelum(dari_iso))
    for e in awal.values():
        akun = akun_of(e.get("kode_barang") or "")
        a = per_akun.setdefault(akun, {"akun": akun,
                                       "uraian": uraian_akun.get(akun, ""),
                                       "awal": 0.0, "tambah": 0.0,
                                       "kurang": 0.0})
        a["awal"] += e["masuk_nilai"] - e["keluar_nilai"]
    baris = []
    for akun in sorted(per_akun):
        a = per_akun[akun]
        a["akhir"] = a["awal"] + a["tambah"] - a["kurang"]
        baris.append(a)
    total = {k: sum(b[k] for b in baris)
             for k in ("awal", "tambah", "kurang", "akhir")}
    return {"baris": baris, "total": total}


def _hari_sebelum(tanggal_iso):
    from datetime import date, timedelta
    try:
        t = date.fromisoformat(str(tanggal_iso or "")[:10])
    except (ValueError, TypeError):
        return _AWAL_WAKTU
    return (t - timedelta(days=1)).isoformat()


def susun_lap_layer(master_items, uraian_kode10):
    """Laporan Per Layer: kode 10 digit → baris per LAYER tiap barang 16
    digit (urut tanggal layer — FIFO). Memotret layer KINI di master.

    Kembalikan {"kelompok": [ {kode10, uraian, baris:[{kode16, uraian,
    layer, qty, nilai}], nilai} ], "total": x} — barang tanpa layer aktif
    dilewati.
    """
    per_kode10 = {}
    for it in master_items or []:
        kode16 = str(it.get("kode_barang") or "")
        layers = [b for b in (it.get("batches") or [])
                  if int(b.get("qty", 0) or 0) > 0]
        if not layers:
            continue
        layers.sort(key=lambda b: str(b.get("tanggal") or ""))
        kode10 = kode16[:10]
        k = per_kode10.setdefault(kode10, {
            "kode10": kode10,
            "uraian": uraian_kode10.get(kode10) or it.get("nama_barang") or "",
            "baris": []})
        for i, b in enumerate(layers, start=1):
            qty = int(b.get("qty", 0) or 0)
            harga = float(b.get("harga", 0) or 0)
            uraian = str(it.get("nama_barang") or "")
            satuan = str(it.get("satuan") or "").strip()
            if satuan:
                uraian += f" ({satuan})"
            k["baris"].append({"kode16": kode16, "uraian": uraian,
                               "layer": i, "qty": qty,
                               "nilai": qty * harga})
    kelompok = []
    for kode10 in sorted(per_kode10):
        k = per_kode10[kode10]
        k["nilai"] = sum(b["nilai"] for b in k["baris"])
        kelompok.append(k)
    return {"kelompok": kelompok,
            "total": sum(k["nilai"] for k in kelompok)}


def susun_daftar_nonaktif(rekap_kategori):
    """Daftar Usang/Rusak/Tidak Dikuasai (satu kategori dari
    `rekap_nonaktif`) → {"baris": [{kode, uraian, qty, nilai}], "total_qty",
    "total_nilai"} terurut kode barang."""
    baris = [{"kode": e.get("kode_barang") or "",
              "uraian": e.get("nama_barang") or "",
              "qty": e["jumlah"], "nilai": e["nilai"]}
             for e in sorted((rekap_kategori or {}).values(),
                             key=lambda x: str(x.get("kode_barang") or ""))]
    return {"baris": baris,
            "total_qty": sum(b["qty"] for b in baris),
            "total_nilai": sum(b["nilai"] for b in baris)}
