"""Koordinat disimpan dengan pemisah desimal TITIK, di SELURUH jalur tulis.

Permintaan pemilik: *"ketika lat lng ditulis menggunakan koma ketika disimpan,
tolong sesuaikan langsung menggunakan titik saja."*

Cacat ini tak pernah berbunyi. Pembaca koordinat di aplikasi ini toleran
terhadap koma desimal, jadi pin tetap muncul di tempat yang benar dan tak satu
pun galat muncul. Yang bocor di tepi: Excel hasil ekspor menerima "-1,4001"
sebagai TEKS, baris koordinat di laporan tercetak "-1,4001, 116,7001" yang
mustahil dibaca sebagai sepasang angka, dan pembanding "berubah atau tidak"
menganggap "-1,4" dan "-1.4" dua nilai berlainan.

Yang diuji di sini: setiap jalur yang MENULIS koordinat merapikannya. Satu
jalur yang terlewat sudah cukup — dan yang terlewat justru akan jadi jalur
yang paling sering dipakai, sebab jalur cepat (lembar edit, impor Excel)
adalah yang paling jarang diingat.
"""
import inspect

import pytest

import routes.assets as ra
import routes.batch as rb
import routes.imports as ri
from models import AssetCreate
from spasial_utils import normalisasi_koordinat_doc


def _aset(**kw):
    dasar = {"asset_code": "3050104001", "asset_name": "Meja",
             "category": "Meja", "activity_id": "k1"}
    dasar.update(kw)
    return AssetCreate(**dasar)


class TestModelAset:
    """Create, update, dan pembuatan draft semuanya melewati model ini."""

    def test_koma_pada_kedua_sumbu_menjadi_titik(self):
        a = _aset(koordinat_latitude="-1,4001", koordinat_longitude="116,7001")
        assert a.koordinat_latitude == "-1.4001"
        assert a.koordinat_longitude == "116.7001"

    def test_yang_sudah_bertitik_tak_berubah(self):
        a = _aset(koordinat_latitude="-1.4001", koordinat_longitude="116.7001")
        assert (a.koordinat_latitude, a.koordinat_longitude) == ("-1.4001", "116.7001")

    def test_kosong_tetap_kosong(self):
        a = _aset()
        assert (a.koordinat_latitude, a.koordinat_longitude) == ("", "")

    def test_ketelitian_TIDAK_dipangkas(self):
        # Digit terakhir koordinat ~1 cm; merender ulang lewat float
        # membuangnya tanpa satu pun tanda.
        a = _aset(koordinat_latitude="-1,4001000")
        assert a.koordinat_latitude == "-1.4001000"

    def test_lintang_memakai_batas_LINTANG_bukan_bujur(self):
        """116 sah sebagai bujur, mustahil sebagai lintang.

        Merapikan komanya membuat nilai yang salah kolom tampak makin sah —
        padahal justru di situ petugas perlu melihat ada yang keliru.
        """
        a = _aset(koordinat_latitude="116,7", koordinat_longitude="116,7")
        assert a.koordinat_latitude == "116,7"
        assert a.koordinat_longitude == "116.7"


class TestJalurTulisLain:
    """Jalur yang TIDAK melewati model harus merapikannya sendiri."""

    @pytest.mark.parametrize("sumber, nama", [
        (ra.patch_asset, "PATCH aset"),
        (rb.batch_update_assets, "ubah massal"),
        (ri.import_assets, "impor berkas"),
    ])
    def test_memanggil_pembersih_koordinat(self, sumber, nama):
        kode = inspect.getsource(sumber)
        assert "normalisasi_koordinat_doc" in kode, (
            f"{nama} menyimpan koordinat tanpa merapikannya")


class TestPembersihDokumen:
    """Sifat yang diandalkan ketiga jalur di atas."""

    def test_patch_sebagian_tak_kehilangan_koordinat(self):
        # Menyisipkan kunci yang tak dikirim berarti menimpa koordinat
        # tersimpan dengan kosong — aset kehilangan titiknya hanya karena
        # namanya diperbaiki.
        body = {"asset_name": "Meja Baru"}
        normalisasi_koordinat_doc(body)
        assert "koordinat_latitude" not in body
        assert "koordinat_longitude" not in body

    def test_ubah_massal_mengosongkan_tetap_kosong(self):
        # Sentinel "__clear__" sudah diterjemahkan jadi "" sebelum pembersih
        # dipanggil; pembersih tak boleh menghidupkannya kembali.
        upd = {"koordinat_latitude": "", "koordinat_longitude": ""}
        normalisasi_koordinat_doc(upd)
        assert upd == {"koordinat_latitude": "", "koordinat_longitude": ""}

    def test_impor_excel_koma_dirapikan(self):
        baris = {"asset_code": "3050104001", "koordinat_latitude": "-1,4001",
                 "koordinat_longitude": "116,7001"}
        normalisasi_koordinat_doc(baris)
        assert baris["koordinat_latitude"] == "-1.4001"
        assert baris["koordinat_longitude"] == "116.7001"
        assert baris["asset_code"] == "3050104001"   # field lain tak disentuh
