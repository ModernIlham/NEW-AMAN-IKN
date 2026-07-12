"""Uji logika murni dasbor pemantauan Wasdal (PMK 207/2021)."""
from wasdal_utils import (
    JENIS_TEMUAN, OBJEK_PER_JENIS, OBJEK_WASDAL,
    periode_wasdal, rekap_wasdal, susun_temuan,
    temuan_pemanfaatan, temuan_pemindahtanganan, temuan_penatausahaan,
    temuan_pengamanan_pemeliharaan, temuan_penggunaan,
)

HARI_INI = "2026-07-12"

ASET_LENGKAP = {"id": "a1", "asset_code": "3100102001", "NUP": "1",
                "asset_name": "PC Unit", "user": "Budi",
                "bast_file_id": "f1", "condition": "Baik",
                "purchase_price": 5_000_000,
                "koordinat_latitude": "-1.1", "koordinat_longitude": "116.9"}


def test_registry_jenis_konsisten():
    assert set(JENIS_TEMUAN) == set(OBJEK_PER_JENIS)
    assert set(OBJEK_PER_JENIS.values()) <= set(OBJEK_WASDAL)


def test_periode():
    assert periode_wasdal("2026-07-12") == {
        "tahun": 2026, "semester": 2, "label": "Semester II 2026"}
    assert periode_wasdal("2026-03-01")["semester"] == 1


def test_penggunaan():
    tanpa_bast = dict(ASET_LENGKAP, bast_file_id="")
    tanpa_user = dict(ASET_LENGKAP, id="a2", user=" ")
    hasil = temuan_penggunaan([ASET_LENGKAP, tanpa_bast, tanpa_user])
    jenis = [t["jenis"] for t in hasil]
    assert jenis == ["pemegang_tanpa_bast", "tanpa_pengguna"]
    assert "Budi" in hasil[0]["detail"]


def test_pemanfaatan():
    lengkap = {"id": "p1", "bentuk": "sewa", "pihak": "PT X",
               "berakhir": "2027-01-01", "nomor_persetujuan": "S-1",
               "nomor_perjanjian": "PJ-1", "ntpn": "N1"}
    berakhir = dict(lengkap, id="p2", berakhir="2026-01-01")
    kurang = dict(lengkap, id="p3", nomor_persetujuan="")
    hasil = temuan_pemanfaatan([lengkap, berakhir, kurang], HARI_INI)
    jenis = {t["pemanfaatan_id"]: t["jenis"] for t in hasil}
    assert jenis == {"p2": "perjanjian_berakhir",
                     "p3": "dokumen_pemanfaatan_kurang"}
    assert "persetujuan" in hasil[1]["detail"]


def test_pemindahtanganan_dan_penghapusan():
    rb = dict(ASET_LENGKAP, id="rb1", condition="Rusak Berat")
    rb_diusulkan = dict(ASET_LENGKAP, id="rb2", condition="Rusak Berat")
    usulan = [
        {"id": "u1", "asset_id": "rb2", "asset_name": "Kursi",
         "status": "diusulkan", "created_at": "2026-01-01T00:00:00"},
        {"id": "u2", "asset_id": "x9", "asset_name": "Meja",
         "status": "diproses", "created_at": "2026-07-01T00:00:00"},
    ]
    pt = [{"id": "t1", "bentuk": "penjualan_lelang", "pihak": "KPKNL",
           "status": "disetujui", "tanggal_persetujuan": "2026-01-01"}]
    hasil = temuan_pemindahtanganan([ASET_LENGKAP, rb, rb_diusulkan],
                                    usulan, pt, HARI_INI)
    jenis = sorted(t["jenis"] for t in hasil)
    # u1 berlarut (>90 hari), u2 belum; rb1 kandidat belum diusulkan,
    # rb2 sudah punya usulan aktif; t1 lewat tenggat lelang 6 bulan
    assert jenis == ["kandidat_belum_diusulkan", "tenggat_lelang",
                     "usulan_hapus_berlarut"]
    berlarut = next(t for t in hasil if t["jenis"] == "usulan_hapus_berlarut")
    assert berlarut["usulan_id"] == "u1" and "hari" in berlarut["detail"]
    kandidat = next(t for t in hasil if t["jenis"] == "kandidat_belum_diusulkan")
    assert kandidat["asset_id"] == "rb1"


def test_penatausahaan():
    kosong = {"id": "a3", "asset_name": "Meja", "condition": "",
              "purchase_price": "", "koordinat_latitude": "",
              "koordinat_longitude": ""}
    hasil = temuan_penatausahaan([ASET_LENGKAP, kosong])
    assert sorted(t["jenis"] for t in hasil) == [
        "tanpa_kondisi", "tanpa_koordinat", "tanpa_nilai"]
    assert all(t["asset_id"] == "a3" for t in hasil)


def test_pengamanan_pemeliharaan():
    sengketa = dict(ASET_LENGKAP, id="s1", nomor_perkara="123/PDT/2026")
    rusak = dict(ASET_LENGKAP, id="r1", condition="Rusak Ringan")
    dirawat = dict(ASET_LENGKAP, id="r2", condition="Rusak Ringan")
    catatan = [{"asset_id": "r2", "tanggal": "2026-05-02"},
               {"asset_id": "r1", "tanggal": "2025-12-30"}]  # tahun lalu
    hasil = temuan_pengamanan_pemeliharaan(
        [ASET_LENGKAP, sengketa, rusak, dirawat], catatan, 2026)
    jenis = {t["asset_id"]: t["jenis"] for t in hasil}
    assert jenis == {"s1": "sengketa", "r1": "rusak_tanpa_pemeliharaan"}


def test_susun_dan_rekap():
    per_objek = susun_temuan(
        [dict(ASET_LENGKAP, bast_file_id="")], [], [], [], [], HARI_INI)
    assert set(per_objek) == set(OBJEK_WASDAL)
    assert [t["jenis"] for t in per_objek["penggunaan"]] == ["pemegang_tanpa_bast"]
    assert per_objek["penggunaan"][0]["label"] == JENIS_TEMUAN["pemegang_tanpa_bast"]
    r = rekap_wasdal(per_objek)
    assert r["total"] == 1 and r["per_objek"]["penggunaan"] == 1
    assert r["per_jenis"] == {"pemegang_tanpa_bast": 1}
