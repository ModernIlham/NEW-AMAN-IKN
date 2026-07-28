"""Uji logika MURNI penerimaan barang (lpb_utils) — tanpa DB.

Yang dijaga di sini adalah keputusan "barang ini masuk buku yang mana".
Salah memilah bukan sekadar salah tampilan: golongan 1 yang tersesat ke jalur
aset akan tercatat DUA KALI di Neraca (kartu stok + BMN ber-NUP).
"""
from lpb_utils import (
    GOLONGAN_BARANG, KATEGORI_LPB, baris_lpb_dari_aset, golongan_kode,
    is_persediaan, label_golongan, pesan_ringkas, pilah_barang_perolehan,
    ringkas_pencatatan, total_nilai_lpb,
)


def test_golongan_dari_digit_pertama():
    assert golongan_kode("1010301001") == "1"
    assert golongan_kode("3050102001") == "3"
    assert golongan_kode("") == ""
    assert golongan_kode(None) == ""
    # Kode yang tak dimulai angka bukan kode barang BMN.
    assert golongan_kode("ABC123") == ""


def test_label_golongan_menutup_seluruh_registry():
    for digit, nama in GOLONGAN_BARANG.items():
        assert label_golongan(digit + "000000000") == nama
    assert label_golongan("9999999999") == ""


def test_is_persediaan_hanya_golongan_satu():
    assert is_persediaan("1010301001") is True
    for kode in ("2010101001", "3050102001", "4010101001", "5030101001",
                 "6010101001", "7010101001", "8010101001"):
        assert is_persediaan(kode) is False, kode


def test_is_persediaan_kode_kosong_bukan_persediaan():
    """Kode kosong TIDAK BOLEH dianggap persediaan.

    `startswith('1')` atas string kosong menjawab False secara kebetulan;
    yang dijaga di sini adalah bahwa jawabannya disengaja — barang tanpa kode
    punya keranjangnya sendiri dan tak boleh diam-diam masuk stok.
    """
    assert is_persediaan("") is False
    assert is_persediaan(None) is False
    assert is_persediaan("   ") is False


def test_pilah_tiga_keranjang_dan_indeks_asli_dipertahankan():
    barang = [
        {"kode": "3050102001", "uraian": "Printer"},      # 0 → aset
        {"kode": "1010301001", "uraian": "Kertas HVS"},   # 1 → persediaan
        {"kode": "", "uraian": "Barang tanpa kode"},      # 2 → tanpa kode
        {"kode": "4010101001", "uraian": "Gedung"},       # 3 → aset
    ]
    hasil = pilah_barang_perolehan(barang)
    assert [i for i, _ in hasil["aset"]] == [0, 3]
    assert [i for i, _ in hasil["persediaan"]] == [1]
    assert [i for i, _ in hasil["tanpa_kode"]] == [2]
    # Baris dikembalikan apa adanya (bukan salinan yang kehilangan field).
    assert hasil["persediaan"][0][1]["uraian"] == "Kertas HVS"


def test_pilah_tak_pernah_menghilangkan_baris():
    """Setiap baris masuk TEPAT SATU keranjang — tak ada yang menguap."""
    barang = [{"kode": k} for k in
              ("1x", "2x", "3x", "", "  ", "8x", "ABC", "1")]
    hasil = pilah_barang_perolehan(barang)
    total = sum(len(v) for v in hasil.values())
    assert total == len(barang)
    indeks = sorted(i for v in hasil.values() for i, _ in v)
    assert indeks == list(range(len(barang)))


def test_pilah_masukan_kosong_aman():
    for kosong in (None, [], ()):
        assert pilah_barang_perolehan(kosong) == {
            "persediaan": [], "aset": [], "tanpa_kode": []}


def test_baris_lpb_satu_nup_satu_baris():
    aset = [
        {"id": "a1", "asset_code": "3050102001", "NUP": "1",
         "asset_name": "Printer", "harga_satuan": 2_500_000},
        {"id": "a2", "asset_code": "3050102001", "NUP": "2",
         "asset_name": "Printer", "harga_satuan": 2_500_000},
    ]
    baris = baris_lpb_dari_aset(aset)
    assert [b["nup"] for b in baris] == ["1", "2"]
    # Jumlah SELALU 1 per baris: itulah maksud dokumen ber-NUP.
    assert all(b["jumlah"] == 1 for b in baris)
    assert all(b["total"] == 2_500_000 for b in baris)
    assert baris[0]["golongan"] == "Peralatan dan Mesin"
    assert total_nilai_lpb(baris) == 5_000_000


def test_baris_lpb_memakai_jumlah_bast_saat_baris_tak_dipecah():
    """LPB adalah dokumen resmi yang menyatakan BERAPA BANYAK barang diterima.

    Pemecahan per-NUP hanya berlaku untuk jumlah bulat 2..50. Di luar itu satu
    draft mewakili seluruh baris BAST — dan mematok `jumlah: 1` membuat
    dokumen menyebut 1 kursi padahal 100 datang, dengan total nilai yang ikut
    mengecil seratus kali lipat.
    """
    baris = baris_lpb_dari_aset([
        {"id": "a1", "asset_code": "3050201001", "NUP": "1",
         "asset_name": "Kursi rapat", "harga_satuan": 500_000,
         "jumlah_bast": 100},
    ])
    assert baris[0]["jumlah"] == 100
    assert baris[0]["total"] == 50_000_000
    assert total_nilai_lpb(baris) == 50_000_000


def test_baris_lpb_tetap_satu_saat_baris_dipecah_per_nup():
    """Sebaliknya: baris yang DIPECAH per-NUP tetap 1 unit per baris —
    kalau tidak, 5 printer akan tercetak sebagai 5 baris × 5 unit = 25."""
    baris = baris_lpb_dari_aset([
        {"id": f"a{i}", "asset_code": "3050102001", "NUP": str(i),
         "asset_name": "Printer", "harga_satuan": 2_000_000, "jumlah_bast": 1}
        for i in (1, 2, 3, 4, 5)])
    assert [b["jumlah"] for b in baris] == [1, 1, 1, 1, 1]
    assert total_nilai_lpb(baris) == 10_000_000


def test_baris_lpb_tanpa_jumlah_bast_default_satu():
    """Data lama / pemanggil yang belum menitipkan jumlah tetap aman."""
    baris = baris_lpb_dari_aset([
        {"id": "a1", "asset_code": "3x", "NUP": "1", "asset_name": "X",
         "harga_satuan": 100}])
    assert baris[0]["jumlah"] == 1 and baris[0]["total"] == 100


def test_baris_lpb_jumlah_pecahan_tak_dibulatkan_diam_diam():
    baris = baris_lpb_dari_aset([
        {"id": "a1", "asset_code": "3x", "NUP": "1", "asset_name": "Semen",
         "harga_satuan": 1_000_000, "jumlah_bast": 2.5}])
    assert baris[0]["jumlah"] == 2.5
    assert baris[0]["total"] == 2_500_000


def test_baris_lpb_harga_tak_terbaca_jadi_nol_bukan_meledak():
    baris = baris_lpb_dari_aset([
        {"id": "a1", "asset_code": "3x", "NUP": "1", "asset_name": "X",
         "harga_satuan": "bukan angka"}])
    assert baris[0]["harga_satuan"] == 0.0
    assert total_nilai_lpb(baris) == 0.0


def test_total_nilai_abai_baris_rusak():
    assert total_nilai_lpb([{"total": 100}, None, {"total": None},
                            {"total": "x"}, {}]) == 100


def test_ringkas_menggabungkan_kegagalan_dua_jalur():
    r = ringkas_pencatatan(
        {"dibuat": 3, "dilewati_tertaut": 1, "gagal": ["a: x"]},
        {"masuk": 2, "dibuat_master": 1, "dilewati_sudah_terdaftar": 4,
         "gagal": ["b: y", "c: z"]},
        tanpa_kode=2)
    assert r["aset_dibuat"] == 3
    assert r["persediaan_masuk"] == 2
    assert r["persediaan_master_baru"] == 1
    assert r["persediaan_dilewati_terdaftar"] == 4
    assert r["tanpa_kode"] == 2
    assert r["total_gagal"] == 3
    assert r["gagal"] == ["a: x", "b: y", "c: z"]


def test_ringkas_dua_jalur_kosong_tidak_meledak():
    r = ringkas_pencatatan({}, {}, tanpa_kode=0)
    assert r["aset_dibuat"] == 0 and r["persediaan_masuk"] == 0
    assert r["total_gagal"] == 0
    assert r["gagal"] == []


def test_pesan_ringkas_menyebut_keduanya():
    p = pesan_ringkas({"aset_dibuat": 3, "persediaan_masuk": 2})
    assert "3 aset" in p and "2 barang persediaan" in p


def test_pesan_ringkas_tak_menyembunyikan_kegagalan():
    """Kegagalan sebagian WAJIB muncul di kalimat ringkas.

    Jalur massal ini tak transaksional; toast yang hanya berkata "berhasil"
    saat separuh baris gagal adalah kebohongan yang paling mahal di sini.
    """
    p = pesan_ringkas({"aset_dibuat": 1, "total_gagal": 4, "tanpa_kode": 2})
    assert "4 gagal" in p
    assert "2 baris belum berkode barang" in p


def test_pesan_ringkas_saat_tak_ada_yang_tercatat():
    assert "tidak ada barang baru" in pesan_ringkas({})


def test_kategori_lpb_punya_dua_bentuk():
    assert set(KATEGORI_LPB) == {"persediaan", "aset"}
