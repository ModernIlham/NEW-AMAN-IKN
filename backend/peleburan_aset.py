"""Peleburan baris pengadaan ke aset yang SUDAH tercatat — LOGIKA MURNI.

Permintaan pemilik: *"pastikan sistem pengadaan sekarang juga sudah dapat
melebur pengadaan jika kode asetnya sama dengan memilih kode barang yang sudah
tercatat ingin dileburkan ke mana melalui fitur pengembangan aset sehingga
tidak merubah kuantitas barang tersebut karena tetap 1 kesatuan akan tetapi
dengan pengembangan nilai sesuai NUP yang ditunjuk (berikan peringatan agar
jika yang dikembangkan lebih dari 1 dan sasarannya hanya NUP hanya 1 maka
berikan proses harus 1 NUP 1 barang, sehingga penginput harus mengulang proses
yang sama agar barang tersebut semua dikembangkan ke 1 NUP saja). Dan juga
pastikan fitur KDP juga dapat dikerjakan dan dipisahkan fitur pengembangannya
dengan kode barang definitif karena masih berupa termin dan terus berkembang
ke depannya."*

── Bedanya dengan "Tautkan" yang sudah ada ─────────────────────────────────
`POST /pengadaan/{id}/tautkan` hanya MENAUTKAN baris ke aset: ia menyalin
kode/NUP/nama ke barisnya dan menulis back-link. Nilai asetnya TIDAK berubah
sama sekali. Untuk belanja yang menambah nilai barang yang sudah ada, itu
berarti uangnya tercatat di register pengadaan tetapi tak pernah sampai ke
nilai perolehan asetnya.

Peleburan menambah NILAI-nya (jurnal 202 "Pengembangan Nilai Aset Langsung")
sementara KUANTITASnya tetap — satu aset tetap satu kesatuan.

── Kenapa KDP DITOLAK di sini ──────────────────────────────────────────────
Registry kode transaksi memisahkan keduanya sejak awal: KDP punya kategori
sendiri (501 saldo awal, 502 penambahan, 503 pengembangan, 505 penghapusan),
sementara aset definitif memakai 202. KDP masih berupa TERMIN dan terus
berkembang sampai diselesaikan menjadi aset definitif — pengembangannya sudah
punya jalur sendiri di modul Pembukuan.

Menerima KDP di sini akan mencatat termin konstruksi dengan kode transaksi
aset definitif. Jurnalnya tetap tertulis, nilainya tetap bertambah, dan tak
ada galat apa pun — yang keliru baru terlihat saat rekonsiliasi KDP tak
menemukan terminnya. Karena itu penolakannya ditegakkan di kode, bukan
diserahkan pada kedisiplinan operator.

MURNI: tanpa Mongo/IO, seluruhnya teruji unit.
"""

# Jurnal untuk peleburan ke aset DEFINITIF. Bukan 503 (itu milik KDP) dan
# bukan 208 (itu penyelesaian pengembangan LEWAT KDP).
KODE_TRANSAKSI_LEBUR = "202"

GOLONGAN_KDP = "7"
GOLONGAN_PERSEDIAAN = "1"


def _golongan(kode) -> str:
    k = str(kode or "").strip()
    return k[0] if k and k[0].isdigit() else ""


def _angka(v, bawaan=0.0) -> float:
    import math
    try:
        f = float(v if v is not None else bawaan)
    except (TypeError, ValueError):
        return bawaan
    return f if math.isfinite(f) else bawaan


def validate_leburan(row, aset) -> list:
    """Pesan penolakan peleburan satu baris ke satu aset. [] = boleh. MURNI.

    Seluruh syaratnya dikumpulkan di sini supaya layar dapat menerangkan
    penolakan yang sama dengan yang ditegakkan server — bukan menebaknya.
    """
    r = row or {}
    a = aset or {}
    galat = []

    kode = str(r.get("kode") or "").strip()
    kode_aset = str(a.get("asset_code") or "").strip()

    if not kode:
        galat.append("Baris ini belum berkode barang — isi kodenya dulu.")
    elif _golongan(kode) == GOLONGAN_PERSEDIAAN:
        galat.append(
            f"Kode {kode} bergolongan 1 = barang persediaan, bukan aset tetap. "
            "Persediaan bertambah lewat kartu stok, bukan pengembangan nilai.")

    if str(r.get("asset_id") or "").strip():
        galat.append("Baris ini sudah tertaut ke aset — lepaskan tautannya dulu.")
    if str(r.get("psd_item_id") or "").strip():
        galat.append("Baris ini sudah tercatat sebagai persediaan.")

    # SATU NUP SATU BARANG — permintaan pemilik, verbatim maksudnya: bila yang
    # dikembangkan lebih dari satu sedangkan sasarannya satu NUP, prosesnya
    # harus diulang per barang. Menerima jumlah > 1 di sini akan menambahkan
    # nilai N barang ke SATU aset sekaligus, dan tak ada yang bisa memisahkan
    # kembali mana nilai milik unit yang mana.
    jumlah = _angka(r.get("jumlah"), 1.0)
    if jumlah != 1:
        galat.append(
            f"Baris ini berjumlah {jumlah:g} unit sedangkan sasarannya satu NUP. "
            "Peleburan berlaku 1 NUP untuk 1 barang — pecah barisnya menjadi "
            "beberapa baris ber-jumlah 1, lalu ulangi peleburan untuk "
            "masing-masing agar semuanya dikembangkan ke NUP yang dituju.")

    if not kode_aset:
        galat.append("Aset tujuan tidak punya kode barang.")
    elif kode and kode_aset != kode:
        galat.append(
            f"Kode barang berbeda: baris {kode} versus aset tujuan {kode_aset}. "
            "Peleburan hanya untuk barang berkode SAMA.")

    if _golongan(kode_aset) == GOLONGAN_KDP:
        galat.append(
            "Aset tujuan adalah KDP (golongan 7). Pengembangan KDP masih "
            "berupa termin dan punya jalurnya sendiri di Pembukuan → KDP "
            "(jurnal 503); jalur ini khusus aset definitif (jurnal 202).")

    if a.get("dihapus"):
        galat.append("Aset tujuan sudah dihapus.")

    return galat


def nilai_leburan(row) -> float:
    """Nilai yang ditambahkan ke aset tujuan. MURNI.

    Harga SATUAN, bukan harga × jumlah: peleburan hanya sah untuk baris
    ber-jumlah 1 (lihat `validate_leburan`), jadi keduanya bernilai sama —
    tetapi menuliskannya sebagai harga satuan membuat maksudnya tak bisa
    disalahbaca bila syarat jumlahnya kelak dilonggarkan.
    """
    return _angka((row or {}).get("harga_satuan"), 0.0)


def ringkas_leburan(row, aset, nilai_lama) -> dict:
    """Ringkasan untuk konfirmasi layar & catatan audit. MURNI."""
    tambah = nilai_leburan(row)
    lama = _angka(nilai_lama, 0.0)
    return {
        "kode": str((aset or {}).get("asset_code") or ""),
        "nup": str((aset or {}).get("NUP") or ""),
        "nama_aset": str((aset or {}).get("asset_name") or ""),
        "uraian_baris": str((row or {}).get("uraian") or ""),
        "nilai_lama": lama,
        "nilai_ditambahkan": tambah,
        "nilai_baru": lama + tambah,
        "kode_transaksi": KODE_TRANSAKSI_LEBUR,
    }
