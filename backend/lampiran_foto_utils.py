"""Penyusun tata letak LAMPIRAN FOTO BUKTI SERAH TERIMA BARANG (BAST).

Satu halaman lampiran memuat GRID 2 kolom × 3 baris = 6 foto. Idealnya itu
berarti 3 aset, masing-masing sepasang: **foto sampul barang** + **foto serah
terima**-nya. Namun kenyataan di lapangan jarang serapi itu:

- sebagian barang tak difoto saat serah terima,
- kadang hanya ADA SATU foto perwakilan untuk seluruh barang dalam satu BAST,
- kadang tiap barang punya fotonya sendiri.

Modul ini memutuskan URUTAN dan PENEMPATAN sel supaya halaman tidak berlubang:
bila sebuah aset tidak punya foto serah terima, kolom yang seharusnya diisi
foto itu TIDAK dibiarkan kosong — aset berikutnya maju mengisinya, sehingga
satu halaman bisa memuat sampai 6 aset. Foto perwakilan (berlaku untuk semua
barang) dicetak SEKALI di akhir, bukan diulang di tiap aset.

Logika di sini sengaja MURNI (tanpa I/O, tanpa reportlab) agar bisa diuji
unit; pemanggil di `routes/bast.py` yang mengubah hasilnya jadi elemen PDF.
"""

KOLOM = 2
BARIS_PER_HALAMAN = 3
SEL_PER_HALAMAN = KOLOM * BARIS_PER_HALAMAN  # 6


def susun_sel_lampiran(aset_rows, foto_st_per_aset=None, foto_st_bersama=False):
    """Kembalikan daftar SEL lampiran, terurut siap dialirkan ke grid.

    Parameter
    ---------
    aset_rows : list[dict]
        Aset yang punya foto sampul. Tiap item minimal: id, asset_code, NUP,
        asset_name. Aset TANPA foto sampul jangan dikirim ke sini.
    foto_st_per_aset : dict[str, Any] | None
        Peta asset_id → penanda foto serah terima MILIK aset itu (nilainya
        bebas: file_id/URL — modul ini tak membacanya, hanya mengecek ada).
    foto_st_bersama : bool
        True bila ada SATU foto perwakilan yang berlaku untuk seluruh barang.

    Kembalian
    ---------
    list[dict] dengan kunci:
        jenis    : "sampul" | "serah" | "serah_bersama"
        asset_id : id aset ("" untuk serah_bersama)
        judul    : label singkat untuk dicetak di atas foto
        kunci    : nilai dari `foto_st_per_aset` (untuk jenis serah) — dipakai
                   pemanggil untuk mengambil gambarnya.

    Aturan penempatan:
    1. Aset yang PUNYA foto serah terima sendiri → dua sel berdampingan
       (sampul, serah) sehingga pasangannya terbaca sebagai satu kesatuan.
    2. Aset TANPA foto serah terima → satu sel saja; sel berikutnya merapat
       mengisi kolom yang tersisa (halaman tidak berlubang).
    3. Foto perwakilan bersama dicetak SEKALI di paling akhir.
    """
    peta = dict(foto_st_per_aset or {})
    sel = []
    for a in aset_rows or []:
        aid = str(a.get("id") or "")
        judul = _judul_aset(a)
        sel.append({"jenis": "sampul", "asset_id": aid,
                    "judul": judul, "kunci": None})
        if aid and peta.get(aid):
            sel.append({"jenis": "serah", "asset_id": aid,
                        "judul": f"Serah terima — {judul}",
                        "kunci": peta[aid]})
    if foto_st_bersama:
        sel.append({"jenis": "serah_bersama", "asset_id": "",
                    "judul": "Serah terima — berlaku untuk seluruh barang",
                    "kunci": "__bersama__"})
    return sel


def _judul_aset(a):
    kode = str(a.get("asset_code") or "").strip()
    nup = str(a.get("NUP") or "").strip()
    nama = str(a.get("asset_name") or "").strip()
    kepala = " · NUP ".join([x for x in (kode, nup) if x]) or "(tanpa kode)"
    return f"{kepala} — {nama}" if nama else kepala


def bagi_baris(sel, kolom=KOLOM):
    """Potong daftar sel menjadi baris-baris berisi `kolom` sel.

    Baris terakhir dipadatkan dengan `None` supaya tabel PDF tetap persegi —
    pemanggil merendernya sebagai sel kosong tanpa bingkai.
    """
    if kolom < 1:
        kolom = 1
    baris = []
    for i in range(0, len(sel), kolom):
        potong = list(sel[i:i + kolom])
        while len(potong) < kolom:
            potong.append(None)
        baris.append(potong)
    return baris


def ringkas_lampiran(sel):
    """Ringkasan untuk catatan kaki lampiran (dipakai di PDF & pengujian)."""
    n_sampul = sum(1 for s in sel if s["jenis"] == "sampul")
    n_serah = sum(1 for s in sel if s["jenis"] == "serah")
    bersama = any(s["jenis"] == "serah_bersama" for s in sel)
    total = len(sel)
    halaman = max(1, (total + SEL_PER_HALAMAN - 1) // SEL_PER_HALAMAN) if total else 0
    return {"aset": n_sampul, "foto_serah_terima": n_serah,
            "ada_foto_bersama": bersama, "total_foto": total,
            "perkiraan_halaman": halaman}
