"""Impor Master Pegawai harus MENGGABUNG, bukan menggandakan & menimpa.

Tiga cacat yang dilaporkan pemilik (dan satu jebakan yang nyaris ikut terbuat
saat memperbaikinya):

  1. Pegawai TANPA NIP selalu disisipkan sebagai orang baru. Mengimpor ulang
     berkas yang sama menggandakan mereka setiap kali — padahal nama, jabatan,
     unit kerja, dan status kepegawaiannya persis sama.
  2. NIP KEMBAR dalam satu berkas: baris pertama meng-upsert, baris kedua
     jatuh ke jalur sisip dan melahirkan orang baru. Ekspor→impor jadi
     memperbanyak, bukan merapikan.
  3. `$set` menulis SELURUH ~54 field, dan field yang tak ada di berkas berisi
     string kosong → NPWP, nama bank, nomor rekening, dan blok ahli waris yang
     sudah ada di master TERHAPUS hanya karena kolomnya tak ikut diimpor.
  4. JEBAKAN: `baris_impor_ke_pegawai` mengisi `status` = "aktif" sebagai
     DEFAULT, bukan sebagai data. Aturan naif "yang tidak kosong menang" akan
     MENGHIDUPKAN KEMBALI pegawai berstatus meninggal setiap kali berkas tanpa
     kolom Status diimpor.
"""
from pegawai_utils import (baris_impor_ke_pegawai, field_dipasok_baris,
                           gabung_baris_pegawai, kunci_dedup_pegawai)


class TestFieldDipasok:
    """Pembeda "tak dipasok" vs "dipasok kosong" — inti perbaikan cacat 3 & 4."""

    def test_hanya_kolom_terisi_yang_terhitung(self):
        d = field_dipasok_baris({"Nama Lengkap": "Ani", "NPWP": "  ",
                                 "No HP": "0812"})
        assert "nama" in d and "no_hp" in d
        assert "npwp" not in d, "sel kosong bukan pasokan — ia tak boleh menimpa"

    def test_header_asing_diabaikan(self):
        assert field_dipasok_baris({"Kolom Karangan": "x"}) == set()

    def test_status_tak_terhitung_bila_kolomnya_tak_ada(self):
        """Penjaga anti-kebangkitan: tanpa kolom Status, `status` TIDAK boleh
        dianggap dipasok — kalau tidak, "aktif" bawaan akan menimpa pegawai
        yang sudah berstatus meninggal."""
        raw = {"Nama Lengkap": "Ani", "Jabatan": "Analis"}
        doc, _ = baris_impor_ke_pegawai(raw)
        assert doc["status"] == "aktif"          # default, bukan data
        assert "status" not in field_dipasok_baris(raw)

    def test_status_terhitung_bila_kolomnya_ada(self):
        raw = {"Nama Lengkap": "Ani", "Status": "Meninggal Dunia",
               "Tgl Meninggal": "2026-01-02"}
        assert "status" in field_dipasok_baris(raw)

    def test_turunan_ikut_terhitung(self):
        """`sub_kategori_non_asn` diturunkan dari Status Kepegawaian, dan
        `unit_kerja` dari Eselon terdalam. Tanpa didaftarkan sebagai turunan,
        keduanya tak pernah ikut diperbarui."""
        d = field_dipasok_baris({"Status Kepegawaian": "Non-ASN - Satpam"})
        assert {"status_kepegawaian", "sub_kategori_non_asn"} <= d
        d2 = field_dipasok_baris({"Eselon 4": "Seksi Aset"})
        assert {"eselon4", "unit_kerja"} <= d2

    def test_baris_kosong_aman(self):
        assert field_dipasok_baris(None) == set()
        assert field_dipasok_baris({}) == set()


class TestKunciDedup:
    def test_nip_menang_di_atas_segalanya(self):
        assert kunci_dedup_pegawai({"nip": "1985", "nama": "Ani"}) == ("nip", "1985")

    def test_wna_dipakai_bila_tanpa_nip(self):
        k = kunci_dedup_pegawai({"nama": "John", "jenis_identitas_wna": "KITAS",
                                 "nomor_identitas_wna": "0012"})
        assert k == ("wna", "kitas", "0012")

    def test_tanpa_identitas_pakai_nama_plus_tanggal_lahir(self):
        k = kunci_dedup_pegawai({"nama": " Budi  Santoso ",
                                 "tanggal_lahir": "1985-01-01"})
        assert k == ("lahir", "budi santoso", "1985-01-01")

    def test_jalan_terakhir_memakai_banyak_unsur(self):
        """Memakai NAMA SAJA akan menggabungkan dua orang berbeda yang
        kebetulan senama — lebih buruk daripada duplikat."""
        k = kunci_dedup_pegawai({"nama": "Ani", "unit_kerja": "Subbag Umum",
                                 "jabatan": "Analis", "status_kepegawaian": "pns"})
        assert k == ("jabatan", "ani", "subbag umum", "analis", "pns")
        beda = kunci_dedup_pegawai({"nama": "Ani", "unit_kerja": "Subbag Lain",
                                    "jabatan": "Analis",
                                    "status_kepegawaian": "pns"})
        assert k != beda, "unit kerja berbeda = orang berbeda"

    def test_dua_baris_ekspor_orang_sama_berkunci_sama(self):
        """Gejala yang dilaporkan: dua baris hasil ekspor untuk orang yang
        SAMA (satu membawa NPWP, satu membawa rekening) harus bertemu di kunci
        yang sama — bukan melahirkan baris ketiga."""
        a = {"nama": "Budi Santoso", "tanggal_lahir": "1985-01-01",
             "npwp": "0912"}
        b = {"nama": "BUDI SANTOSO", "tanggal_lahir": "1985-01-01",
             "nama_bank": "BRI", "no_rekening": "123"}
        assert kunci_dedup_pegawai(a) == kunci_dedup_pegawai(b)

    def test_nama_kosong_tak_berkunci(self):
        assert kunci_dedup_pegawai({"nama": "   "}) is None
        assert kunci_dedup_pegawai(None) is None


class TestGabungBaris:
    def test_dua_baris_saling_melengkapi(self):
        """Inti keluhan: satu baris punya NPWP, satunya punya bank+rekening.
        Hasilnya harus SATU orang dengan keduanya."""
        a, dip_a = {"nama": "Budi", "npwp": "0912", "nama_bank": ""}, {"nama", "npwp"}
        b, dip_b = ({"nama": "Budi", "npwp": "", "nama_bank": "BRI",
                     "no_rekening": "123"},
                    {"nama", "nama_bank", "no_rekening"})
        doc, dip = gabung_baris_pegawai(a, dip_a, b, dip_b)
        assert doc["npwp"] == "0912", "NPWP baris pertama tak boleh hilang"
        assert doc["nama_bank"] == "BRI" and doc["no_rekening"] == "123"
        assert dip == {"nama", "npwp", "nama_bank", "no_rekening"}

    def test_kosong_tak_pernah_menimpa_terisi(self):
        doc, _ = gabung_baris_pegawai(
            {"npwp": "0912"}, {"npwp"}, {"npwp": ""}, set())
        assert doc["npwp"] == "0912"

    def test_nilai_dipasok_terbaru_menang(self):
        doc, _ = gabung_baris_pegawai(
            {"jabatan": "Analis"}, {"jabatan"},
            {"jabatan": "Kepala Seksi"}, {"jabatan"})
        assert doc["jabatan"] == "Kepala Seksi"


class TestJalurImporTerpasang:
    """Penjaga sumber: helper murni di atas tak berarti apa-apa bila jalur
    impornya masih memakai pola lama (`seen_nip` + InsertOne + `$set: doc`)."""

    import os
    _ROUTE = os.path.join(os.path.dirname(__file__), "..", "..",
                          "routes", "pegawai.py")

    def _src(self):
        import os
        with open(os.path.abspath(self._ROUTE), encoding="utf-8") as f:
            return f.read()

    def test_pola_lama_benar_benar_hilang(self):
        src = self._src()
        assert "seen_nip" not in src, "penjaga NIP lama = sumber duplikat"
        assert "InsertOne" not in src, "sisip langsung melewati dedup"

    def test_impor_memakai_kunci_dan_gabungan(self):
        src = self._src()
        for nama in ("kunci_dedup_pegawai(", "field_dipasok_baris(",
                     "gabung_baris_pegawai(", "_filter_dedup("):
            assert nama in src, nama

    def test_hanya_field_dipasok_yang_ditulis(self):
        """`$set` harus disaring `dipasok`; menulis seluruh doc mengembalikan
        cacat penghapusan NPWP/rekening."""
        src = self._src()
        assert "if k in dipasok" in src
        # Cek DIBATASI pada fungsi impor: `ubah_pegawai` sah memakai
        # `{"$set": doc}` — di sana doc memang berasal dari form yang utuh.
        impor = src.split("async def impor_pegawai", 1)[1].split("\n@", 1)[0]
        assert '"$set": doc' not in impor

    def test_filter_dedup_selalu_ter_scope_satker(self):
        src = self._src()
        potong = src.split("def _filter_dedup", 1)[1].split("\ndef ", 1)[0]
        assert "kode_satker" in potong

    def test_kunci_lemah_tak_menyambar_pegawai_ber_nip(self):
        """Kunci "lahir"/"jabatan" hanya berlaku bagi pegawai TANPA NIP —
        tanpa pagar ini, baris tanpa NIP bisa menimpa orang lain yang ber-NIP
        tetapi kebetulan senama."""
        src = self._src()
        potong = src.split("def _filter_dedup", 1)[1].split("\ndef ", 1)[0]
        assert potong.count('{"nip": ""}') >= 2
