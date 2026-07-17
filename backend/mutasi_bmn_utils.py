"""Jurnal Mutasi BMN (Buku Barang) — LOGIKA MURNI. Gelombang 7 (riset
terverifikasi, pustaka §2.6): dalam praktik SIMAK-BMN/SAKTI yang otoritatif
adalah REKAMAN TRANSAKSI BER-KODE PER NUP; Buku Barang/DBKP/KIB hanyalah
proyeksi. AMAN meniru pola itu: koleksi `mutasi_bmn` append-only menampung
jurnal barang lintas modul; laporan menghitung saldo awal → mutasi → saldo
akhir dari jurnal (fallback: derivasi assets ala `pembukuan_utils`).

Reklasifikasi (SAKTI 304/107): pasangan tak terpisahkan pada periode sama,
nilai bruto keluar = masuk; aset TIDAK dibuat ulang — kode+NUP dimutakhirkan
in-place dengan riwayat, sehingga id internal & kode register SIMAN tetap.
"""

# Kode transaksi barang selaras SIMAK/SAKTI (pustaka §2.3a) — subset yang
# dipakai AMAN; uraian resmi utuh.
KODE_TRANSAKSI_BMN = {
    "100": ("Saldo Awal", "tambah"),
    "101": ("Pembelian", "tambah"),
    "102": ("Transfer Masuk", "tambah"),
    "103": ("Hibah Masuk", "tambah"),
    "105": ("Penyelesaian Pembangunan Dengan KDP", "tambah"),
    "107": ("Reklasifikasi Masuk", "tambah"),
    "112": ("Perolehan Lainnya", "tambah"),
    "202": ("Pengembangan Nilai Aset", "tambah"),
    "203": ("Perubahan Kondisi", "netral"),
    "204": ("Koreksi Nilai Bertambah", "tambah"),
    "205": ("Koreksi Nilai Berkurang", "kurang"),
    "301": ("Penghapusan", "kurang"),
    "302": ("Transfer Keluar", "kurang"),
    "303": ("Hibah Keluar", "kurang"),
    "304": ("Reklasifikasi Keluar", "kurang"),
    "305": ("Koreksi Pencatatan", "kurang"),
    "401": ("Penghentian BMN dari Penggunaan", "netral"),
}


def arah_transaksi(kode) -> str:
    """'tambah' / 'kurang' / 'netral' — '' bila kode tak dikenal."""
    info = KODE_TRANSAKSI_BMN.get(str(kode or "").strip())
    return info[1] if info else ""


def validate_entri_mutasi(e) -> list:
    """Daftar pesan error entri jurnal (kosong = valid). MURNI."""
    errors = []
    e = e or {}
    kode = str(e.get("kode_transaksi") or "").strip()
    if kode not in KODE_TRANSAKSI_BMN:
        errors.append(f"Kode transaksi tidak dikenal: {kode or '(kosong)'}")
    if not str(e.get("asset_id") or "").strip():
        errors.append("asset_id wajib diisi")
    tgl = str(e.get("tanggal_buku") or "").strip()
    if len(tgl) != 10 or tgl[4] != "-" or tgl[7] != "-":
        errors.append("tanggal_buku wajib berformat YYYY-MM-DD")
    try:
        float(e.get("nilai") or 0)
    except (TypeError, ValueError):
        errors.append("nilai harus angka")
    return errors


def buat_pasangan_reklasifikasi(asset, kode_baru, nup_baru, tanggal_buku,
                                alasan, oleh):
    """Pasangan entri 304 (keluar dari kode lama) + 107 (masuk ke kode baru)
    — nilai bruto sama (nilai perolehan aset), periode sama. MURNI: pemanggil
    menyediakan nup_baru & menyimpan; id/created_at diisi pemanggil."""
    from pembukuan_utils import parse_harga
    nilai = parse_harga(asset.get("purchase_price"))
    dasar = {
        "asset_id": asset.get("id"),
        "tanggal_buku": str(tanggal_buku or "")[:10],
        "jumlah": 1,
        "nilai": nilai,
        "sumber_modul": "pembukuan",
        "keterangan": (f"Reklasifikasi {asset.get('asset_code')}/{asset.get('NUP')} "
                       f"→ {kode_baru}/{nup_baru}"
                       + (f" — {alasan}" if str(alasan or "").strip() else "")),
        "oleh": oleh,
    }
    keluar = {**dasar, "kode_transaksi": "304",
              "kode_barang": str(asset.get("asset_code") or ""),
              "nup": str(asset.get("NUP") or "")}
    masuk = {**dasar, "kode_transaksi": "107",
             "kode_barang": str(kode_baru or ""), "nup": str(nup_baru or "")}
    return keluar, masuk


def rekap_mutasi_periode(entries, dari, sampai):
    """Rekap jurnal per kode barang (sub-sub kelompok) untuk periode
    [dari, sampai] (ISO date inklusif): {kode: {tambah_n, tambah_rp,
    kurang_n, kurang_rp, per_kode_transaksi:{kode:{n,rp}}}}. Entri 'netral'
    tidak menggeser kuantitas/nilai tetapi tetap dihitung per jenis. MURNI."""
    out = {}
    d0, d1 = str(dari or "")[:10], str(sampai or "9999-12-31")[:10]
    for e in entries or []:
        tgl = str(e.get("tanggal_buku") or "")[:10]
        if not tgl or tgl < d0 or tgl > d1:
            continue
        kode = str(e.get("kode_barang") or "")
        kt = str(e.get("kode_transaksi") or "")
        arah = arah_transaksi(kt)
        b = out.setdefault(kode, {"tambah_n": 0, "tambah_rp": 0.0,
                                  "kurang_n": 0, "kurang_rp": 0.0,
                                  "per_kode_transaksi": {}})
        n = int(e.get("jumlah") or 1)
        rp = float(e.get("nilai") or 0)
        pk = b["per_kode_transaksi"].setdefault(kt, {"n": 0, "rp": 0.0})
        pk["n"] += n
        pk["rp"] += rp
        if arah == "tambah":
            b["tambah_n"] += n
            b["tambah_rp"] += rp
        elif arah == "kurang":
            b["kurang_n"] += n
            b["kurang_rp"] += rp
    return out


def deteksi_reklasifikasi_siman(aset, siman) -> dict:
    """Sinyal reklasifikasi saat sinkron SIMAN (riset §5): kode_register
    COCOK tetapi kodefikasi/NUP BERBEDA → bukan sekadar selisih field,
    melainkan aset yang direklasifikasi di SIMAN. Kembalikan {} bila bukan.
    MURNI."""
    from siman_utils import norm_kode, norm_teks
    reg_a = norm_teks((aset or {}).get("kode_register"))
    reg_s = norm_teks((siman or {}).get("kode_register"))
    if not reg_a or not reg_s or reg_a != reg_s:
        return {}
    kode_a = norm_kode((aset or {}).get("asset_code"))
    kode_s = norm_kode((siman or {}).get("kode_barang"))
    nup_a = norm_kode((aset or {}).get("NUP"))
    nup_s = norm_kode((siman or {}).get("nup"))
    if (kode_s and kode_s != kode_a) or (nup_s and nup_s != nup_a):
        return {"kode_lama": kode_a, "nup_lama": nup_a,
                "kode_baru": kode_s or kode_a, "nup_baru": nup_s or nup_a}
    return {}
