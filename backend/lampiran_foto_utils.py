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


def susun_sel_lampiran(aset_rows, foto_st_per_aset=None, foto_st_bersama=False,
                       id_ber_sampul=None, kolom=KOLOM):
    """Kembalikan daftar SEL lampiran, terurut siap dialirkan ke grid.

    Parameter
    ---------
    aset_rows : list[dict]
        SELURUH aset objek BAST (bukan hanya yang berfoto). Tiap item minimal:
        id, asset_code, NUP, asset_name.
    foto_st_per_aset : dict[str, Any] | None
        Peta asset_id → penanda foto serah terima MILIK aset itu.
    foto_st_bersama : bool
        True bila ada SATU foto perwakilan untuk seluruh barang.
    id_ber_sampul : set[str] | None
        Id aset yang benar-benar punya foto sampul. `None` = anggap semua
        punya. Aset di luar himpunan ini TIDAK menghasilkan sel "sampul" —
        tetapi foto serah terimanya TETAP dicetak (dulu ikut hilang karena
        aset tanpa sampul disaring lebih dulu).
    kolom : int
        Lebar grid; dipakai untuk menyisipkan sel kosong agar PASANGAN
        (sampul+serah milik aset sama) tidak terbelah antar baris.

    Kembalian
    ---------
    list[dict | None] — `None` = sel kosong penyeimbang. Tiap dict berkunci:
        jenis    : "sampul" | "serah" | "serah_bersama"
        asset_id : id aset ("" untuk serah_bersama)
        judul    : label singkat untuk dicetak di atas foto
        kunci    : nilai dari `foto_st_per_aset` (untuk jenis serah)
    """
    peta = dict(foto_st_per_aset or {})
    sel = []

    def _kolom_sekarang():
        return len(sel) % kolom if kolom > 0 else 0

    for a in aset_rows or []:
        aid = str(a.get("id") or "")
        judul = _judul_aset(a)
        ada_sampul = id_ber_sampul is None or aid in id_ber_sampul
        ada_serah = bool(aid and peta.get(aid))
        if not ada_sampul and not ada_serah:
            continue                     # tak ada apa pun untuk dicetak

        # Pasangan lengkap harus MULAI di kolom pertama, kalau tidak ia
        # terbelah: "serah A" akan bersebelahan dengan "sampul B" dan
        # terbaca seperti salah pasang.
        if ada_sampul and ada_serah and _kolom_sekarang() != 0:
            sel.append(None)

        if ada_sampul:
            sel.append({"jenis": "sampul", "asset_id": aid,
                        "judul": judul, "kunci": None})
        if ada_serah:
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
    isi = [s for s in sel if s]          # buang sel kosong penyeimbang
    n_sampul = sum(1 for s in isi if s["jenis"] == "sampul")
    n_serah = sum(1 for s in isi if s["jenis"] == "serah")
    bersama = any(s["jenis"] == "serah_bersama" for s in isi)
    total = len(sel)                     # halaman dihitung dari SEL, termasuk kosong
    halaman = max(1, (total + SEL_PER_HALAMAN - 1) // SEL_PER_HALAMAN) if total else 0
    return {"aset": n_sampul, "foto_serah_terima": n_serah,
            "ada_foto_bersama": bersama, "total_foto": total,
            "perkiraan_halaman": halaman}
