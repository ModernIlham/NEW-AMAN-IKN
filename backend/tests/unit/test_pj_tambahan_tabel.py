"""Penanggung jawab tambahan BAST: NIP/NIK, BMN yang melekat, dan TABEL.

Permintaan pemilik: *"ketika memiliki penanggung jawab tambahan per
unit/tempat/tugas, tambahkan informasi aset yang terceklist di aset yang
diserahterimakan dan juga informasi di output PDF-nya di Pasal 2 …
tambahkan informasi NIP/NIK penanggung jawabnya dan informasi barang apa saja
yang melekat ke masing-masing penanggung jawabnya, buat dalam bentuk tabel agar
lebih mudah dibaca dan dipahami, dan dibuat ser[api] dan seringkas mungkin
hingga memaksimalkan kekosongan yang ada."*

Sebelumnya keduanya dirangkai jadi SATU KALIMAT di dalam pasal:

    "Penanggung jawab pada unit/tempat tugas: Budi (Lantai 3); Sari (Gudang)."

Tanpa NIP/NIK — dokumen resmi menamai orang tanpa pengenal yang bisa
diverifikasi — dan tanpa menyebut barang siapa yang mana. Padahal justru itu
yang dicari orang saat membuka BAST setahun kemudian: siapa memegang apa.

Batas dua halaman TETAP BERLAKU dan diuji di sini juga. Ruang untuk tabel ini
tidak muncul dengan sendirinya: ia dibeli dengan merapatkan tabel aset Pasal 1
satu takik ketika (dan HANYA ketika) tabel penanggung jawab akan tercetak.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.bast as rb
from bast_pasal import (baris_pj_tambahan, bmn_tanpa_pj, label_bmn,
                        rujukan_pasal1, validate_pj_tambahan)

SATKER = "527010"
USER = {"username": "arsiparis", "role": "admin", "kode_satker": SATKER}
KODE_UJI = ["3020104001", "3100102003", "3050101001", "3060101001",
            "3080101001"]
URAIAN_UJI = {"3020104001": "Mini Bus", "3100102003": "Lap Top",
              "3050101001": "Mesin Ketik", "3060101001": "Camera Digital",
              "3080101001": "Alat Kesehatan Umum Lainnya"}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import routes.pegawai as rpg
    import routes.reports as rr
    import shared_utils as su
    for mod in (rb, su, rr, rpg):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


def _aset(n):
    return [{"id": f"a{i}", "asset_code": KODE_UJI[i % len(KODE_UJI)],
             "NUP": str(i + 1),
             "asset_name": f"Barang Contoh Nama Agak Panjang {i + 1}",
             "brand": "Merk Contoh", "model": "Tipe-XYZ-2000",
             "serial_number": f"SN-{i:05d}", "condition": "Baik",
             "purchase_date": "2025-03-01", "purchase_price": 15_000_000 + i}
            for i in range(n)]


async def _seed(dbx):
    await dbx.report_settings.insert_one({
        "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
        "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
        "alamat_instansi": "Gedung Kantor Otorita IKN, Nusantara",
        "kasatker_nama": "Kasatker Uji", "kasatker_nip": "197001011990032001"})
    await dbx.kodefikasi.insert_many(
        [{"kode": k, "uraian": u} for k, u in URAIAN_UJI.items()])


async def _pdf(dbx, pj, n_aset=12):
    aset = _aset(n_aset)
    await dbx.bast_serah_terima.insert_one({
        "id": "b-pj", "kode_satker": SATKER, "jenis": "operasional_unit",
        "nomor": "BAST-001/PPTHD/VIII/2026", "tanggal": "2026-08-04",
        "pihak_pertama": {"nama": "Karlinus Ignasius Manek",
                          "nip": "198206022001121003",
                          "jabatan": "Petugas Penatausahaan",
                          "alamat": "Gedung Kantor Otorita IKN"},
        "pihak_kedua": {"nama": "Karina Lia Meirita Ulo",
                        "nip": "199005242025062002", "jabatan": "Analis",
                        "alamat": "Gedung B Lantai 2"},
        "asset_ids": [a["id"] for a in aset], "aset": aset,
        "saksi": [], "keterangan": "", "sertakan_foto": False,
        "penyerah_atas_nama_kpb": True,
        "penanggung_jawab_tambahan": pj})
    resp = await _unwrap(rb.bast_pdf)("b-pj", _user=USER)
    buf = io.BytesIO()
    async for potong in resp.body_iterator:
        buf.write(potong if isinstance(potong, bytes) else potong.encode())
    return buf.getvalue()


def _halaman_teks(raw):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(raw)
    try:
        return [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
    finally:
        pdf.close()


# ── Logika murni ────────────────────────────────────────────────────────────

class TestBarisPjTambahan:
    ASET = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]

    def test_baris_tanpa_nama_dibuang_dan_nomornya_rapat(self):
        """Formulir menyisakan baris kosong tiap kali operator menekan
        "tambah" lalu berpindah pikiran; baris kosong yang ikut tercetak
        membuat dokumen resmi tampak salah isi."""
        r = baris_pj_tambahan(
            [{"nama": "  "}, {"nama": "Budi"}, {}, {"nama": "Sari"}], self.ASET)
        assert [x["nama"] for x in r] == ["Budi", "Sari"]
        assert [x["no"] for x in r] == [1, 2]

    def test_kolom_kosong_jadi_tanda_hubung_bukan_string_kosong(self):
        r = baris_pj_tambahan([{"nama": "Budi"}], self.ASET)
        assert r[0]["nip"] == "-" and r[0]["unit"] == "-"

    def test_aset_di_luar_daftar_serah_terima_dibuang(self):
        """Pertahanan lapis kedua: validasi menolaknya lebih dulu, tetapi BAST
        lama yang asetnya sudah dihapus tetap harus bisa dicetak."""
        r = baris_pj_tambahan(
            [{"nama": "Budi", "asset_ids": ["a1", "hantu"]}], self.ASET)
        assert r[0]["aset"] == ["a1"]

    def test_urutan_aset_dipertahankan(self):
        r = baris_pj_tambahan(
            [{"nama": "Budi", "asset_ids": ["a3", "a1"]}], self.ASET)
        assert r[0]["aset"] == ["a3", "a1"]


class TestLabelUnit:
    """Tempat tugas dan unit eselon berbagi SATU kolom.

    Kolom keenam pada tabel yang sudah berisi lima akan menyempitkan semuanya
    sampai nama orang patah jadi dua baris — dan naskah dua halaman membayar
    tiap baris yang patah dengan jatah penanggung jawab berikutnya.
    """

    def test_keduanya_terisi_digabung(self):
        from bast_pasal import label_unit
        assert label_unit({"unit": "Ruang Server", "eselon": "Direktorat BMN"}) \
            == "Ruang Server · Direktorat BMN"

    def test_salah_satu_kosong_tak_menyisakan_pemisah_menggantung(self):
        from bast_pasal import label_unit
        assert label_unit({"unit": "Ruang Server", "eselon": "-"}) == "Ruang Server"
        assert label_unit({"unit": "-", "eselon": "Direktorat BMN"}) == "Direktorat BMN"

    def test_dua_duanya_kosong_jadi_tanda_hubung(self):
        from bast_pasal import label_unit
        assert label_unit({"unit": "-", "eselon": "-"}) == "-"
        assert label_unit({}) == "-" and label_unit(None) == "-"

    def test_baris_membawa_eselon_dari_payload(self):
        r = baris_pj_tambahan(
            [{"nama": "Budi", "unit_eselon": "Direktorat BMN"}], [])
        assert r[0]["eselon"] == "Direktorat BMN"


class TestRujukanPasal1:
    def test_nomor_urut_terurut_dan_tanpa_kembar(self):
        assert rujukan_pasal1(["a3", "a1", "a3"], {"a1": 4, "a3": 1}) == "1, 4"

    def test_id_tak_dikenal_diabaikan_diam_diam(self):
        assert rujukan_pasal1(["hantu"], {"a1": 1}) == ""

    def test_kosong_menghasilkan_kosong(self):
        assert rujukan_pasal1([], {}) == "" and rujukan_pasal1(None, None) == ""


class TestBmnTanpaPj:
    ASET = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]

    def test_sisa_dihitung_benar(self):
        sisa = bmn_tanpa_pj([{"nama": "Budi", "asset_ids": ["a2"]}], self.ASET)
        assert [a["id"] for a in sisa] == ["a1", "a3"]

    def test_klaim_baris_TANPA_NAMA_tidak_dihitung(self):
        """Baris tanpa nama tak pernah tercetak, jadi asetnya tak pernah
        benar-benar melekat pada siapa pun — menghitungnya sebagai terpakai
        akan membuat jumlah sisa di bawah tabel berbohong."""
        sisa = bmn_tanpa_pj([{"nama": "", "asset_ids": ["a2"]}], self.ASET)
        assert len(sisa) == 3


class TestValidasi:
    def test_baris_terisi_tanpa_nama_ditolak(self):
        e = validate_pj_tambahan([{"nip": "123"}], [])
        assert len(e) == 1 and "belum bernama" in e[0]

    def test_baris_benar_benar_kosong_bukan_kesalahan(self):
        assert validate_pj_tambahan([{}], []) == []

    def test_aset_di_luar_daftar_ditolak(self):
        e = validate_pj_tambahan([{"nama": "Budi", "asset_ids": ["x"]}], ["a1"])
        assert len(e) == 1 and "tidak termasuk" in e[0]

    def test_satu_aset_dua_penanggung_jawab_ditolak(self):
        e = validate_pj_tambahan(
            [{"nama": "Budi", "asset_ids": ["a1"]},
             {"nama": "Sari", "asset_ids": ["a1"]}], ["a1"])
        assert len(e) == 1 and "dua penanggung jawab" in e[0]

    def test_orang_yang_sama_dua_baris_bukan_bentrok(self):
        assert validate_pj_tambahan(
            [{"nama": "Budi", "asset_ids": ["a1"]},
             {"nama": "Budi", "asset_ids": ["a1"]}], ["a1"]) == []

    def test_label_bmn_merapatkan_kode_dan_nup(self):
        """Dirapatkan dengan '·' supaya satu identitas barang tak patah jadi
        dua baris di kolom sempit."""
        assert label_bmn({"asset_code": "3.05", "NUP": "1",
                          "asset_name": "Laptop"}) == "3.05·1 — Laptop"
        assert label_bmn({}) == "-"


# ── Jalur endpoint & PDF ────────────────────────────────────────────────────

class TestGerbangEndpoint:
    def test_model_membawa_nip_dan_asset_ids(self):
        f = rb.PjTambahanIn.model_fields
        assert "nip" in f and "asset_ids" in f


class TestTabelDiPdf:
    def test_nip_dan_unit_tercetak(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [
                {"nama": "Petugas Ruang Server", "nip": "199001012021011001",
                 "unit_tempat_tugas": "Ruang Server", "asset_ids": []}])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "Petugas Ruang Server" in teks
        assert "199001012021011001" in teks
        assert "NIP/NIK" in teks

    def test_kolom_bmn_merujuk_nomor_urut_pasal_1(self, dbx):
        """Mengulang `kode·NUP — nama` akan membuat satu penanggung jawab
        bermuatan lima barang memakan lima baris. Nomor urutnya sudah tercetak
        di halaman yang sama."""
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [
                {"nama": "Petugas A", "nip": "1", "unit_tempat_tugas": "R1",
                 "asset_ids": ["a0", "a1"]}])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "No. BMN" in teks

    def test_kolom_bmn_TIDAK_dipasang_bila_tak_ada_yang_dilekatkan(self, dbx):
        """Kolom berisi tanda hubung dari atas ke bawah hanya memakan lebar
        yang bisa dipakai nama dan unit."""
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [
                {"nama": "Petugas A", "nip": "1", "unit_tempat_tugas": "R1",
                 "asset_ids": []}])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "No. BMN" not in teks

    def test_sisa_bmn_dinyatakan_bukan_didiamkan(self, dbx):
        """Pembaca yang melihat 2 dari 12 barang di tabel berhak tahu ke mana
        10 sisanya."""
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [
                {"nama": "Petugas A", "nip": "1", "unit_tempat_tugas": "R1",
                 "asset_ids": ["a0", "a1"]}])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "10 BMN Pasal 1 lainnya" in teks

    def test_baris_tanpa_nama_tak_pernah_sampai_ke_kertas(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [{"nama": "", "nip": "RAHASIA-999",
                                     "unit_tempat_tugas": "X"}])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "RAHASIA-999" not in teks


class TestBatasDuaHalamanTetapBerlaku:
    """Ruang untuk tabel ini dibeli dengan merapatkan tabel aset Pasal 1 —
    dan pembelian itu harus terus terbukti cukup. Regresinya senyap: satu
    butir panjang yang ditambahkan nanti mendorong tanda tangan ke halaman
    ketiga, dan tak ada yang mengeluh sampai dokumennya dicetak."""

    # Kapasitas TERUKUR pada muatan wajib 12 aset dengan isi terberat (unit
    # tempat tugas panjang + unit eselon panjang + NIP 18 digit): 6 penanggung
    # jawab bila tak ada BMN yang dilekatkan, 3 bila kolom BMN ikut tercetak
    # (kolom keenam menyempitkan kolom unit sampai barisnya patah dua).
    # Angkanya dikunci di sini supaya penambahan berikutnya ketahuan SEBELUM
    # dokumennya dicetak, bukan sesudah.
    @pytest.mark.parametrize("n_pj,n_bmn", [(1, 0), (3, 0), (6, 0),
                                            (1, 2), (2, 2), (3, 2),
                                            (3, 3), (3, 4)])
    def test_masih_dua_halaman(self, dbx, n_pj, n_bmn):
        async def skenario():
            await _seed(dbx)
            aset_id = [f"a{i}" for i in range(12)]
            # Kondisi TERBERAT: unit eselon panjang ikut terisi, karena
            # itulah yang benar-benar dituliskan Master Pegawai.
            pj = [{"nama": f"Petugas Contoh {i}",
                   "nip": f"19900101202101{i}001",
                   "unit_tempat_tugas": f"Ruang Contoh Agak Panjang {i}",
                   "unit_eselon": "Direktorat Barang Milik Negara",
                   "asset_ids": aset_id[i * n_bmn:(i + 1) * n_bmn]}
                  for i in range(n_pj)]
            return await _pdf(dbx, pj)
        n = len(_halaman_teks(_jalan(skenario())))
        assert n <= 2, (f"{n_pj} penanggung jawab × {n_bmn} BMN memakan "
                        f"{n} halaman — batas mandat 2 lembar")


class TestDaftarPegawaiMembawaUnitTerdalam:
    """`GET /pegawai` mengisi `unit_kerja` dengan eselon TERDALAM, sama
    seperti endpoint detail.

    Dulu hanya detail yang menerapkannya, jadi satu pegawai bisa tampil
    ber-unit di satu layar dan tanpa unit di layar lain — tanpa satu pun
    galat. Sejak pemilih penanggung jawab BAST mengambil unit eselon dari
    daftar ini, ketidaksesuaian itu berhenti jadi soal tampilan: unit yang
    hilang akan tertulis KOSONG ke dokumen resmi.
    """

    def test_unit_kerja_kosong_diisi_eselon_terdalam(self, dbx):
        import routes.pegawai as rpg

        async def skenario():
            await dbx.pegawai.insert_one({
                "id": "p1", "kode_satker": "", "nama": "Budi Santoso",
                "nip": "199001012021011001", "unit_kerja": "",
                "eselon1": "Sekretariat Jenderal",
                "eselon3": "Direktorat Barang Milik Negara"})
            return await _unwrap(rpg.list_pegawai)(_user=USER)
        hasil = _jalan(skenario())
        assert hasil["items"][0]["unit_kerja"] == "Direktorat Barang Milik Negara"

    def test_unit_kerja_yang_SUDAH_terisi_tidak_ditimpa(self, dbx):
        import routes.pegawai as rpg

        async def skenario():
            await dbx.pegawai.insert_one({
                "id": "p1", "kode_satker": "", "nama": "Budi",
                "unit_kerja": "Ditulis Manual", "eselon5": "Subbag Umum"})
            return await _unwrap(rpg.list_pegawai)(_user=USER)
        hasil = _jalan(skenario())
        assert hasil["items"][0]["unit_kerja"] == "Ditulis Manual"


# ── Lampiran Surat Pernyataan Tanggung Jawab (opsional) ─────────────────────

async def _pdf_sptj(dbx, jenis, pj, n_aset=6, p2=None, p1=None):
    aset = _aset(n_aset)
    await dbx.bast_serah_terima.insert_one({
        "id": "b-sptj", "kode_satker": SATKER, "jenis": jenis,
        "nomor": "BAST-007/PPTHD/VIII/2026", "tanggal": "2026-08-04",
        "pihak_pertama": p1 or {"nama": "Andi Penyerah",
                                "nip": "198206022001121003",
                                "jabatan": "Petugas Penatausahaan",
                                "alamat": "Gedung Kantor OIKN"},
        "pihak_kedua": p2 or {"nama": "Sari Penerima",
                              "nip": "199005242025062002",
                              "jabatan": "Analis", "alamat": "Gedung B Lt 2"},
        "asset_ids": [a["id"] for a in aset], "aset": aset,
        "saksi": [], "keterangan": "", "sertakan_foto": False,
        "penyerah_atas_nama_kpb": True, "surat_pernyataan": True,
        "penanggung_jawab_tambahan": pj})
    resp = await _unwrap(rb.bast_pdf)("b-sptj", _user=USER)
    buf = io.BytesIO()
    async for potong in resp.body_iterator:
        buf.write(potong if isinstance(potong, bytes) else potong.encode())
    return buf.getvalue()


class TestSuratPernyataanPembagian:
    """Siapa menandatangani lembar mana — logika murni."""

    ASET = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
    P2 = {"nama": "Sari", "nip": "2", "jabatan": "Analis", "alamat": "Gd B"}
    P1 = {"nama": "Andi", "nip": "1", "jabatan": "PPTHD"}

    def test_bast_biasa_satu_lembar_untuk_pihak_kedua(self):
        from bast_pasal import PERAN_PEMEGANG, daftar_penyata
        r = daftar_penyata("penggunaan_melekat", self.P2, self.P1, [], self.ASET)
        assert len(r) == 1
        assert r[0]["nama"] == "Sari" and r[0]["peran"] == PERAN_PEMEGANG
        assert len(r[0]["aset"]) == 3

    def test_pengembalian_yang_menyatakan_PIHAK_KESATU(self):
        """Membuat PIHAK KEDUA menyatakan tanggung jawab atas barang yang baru
        saja ia kembalikan adalah kebalikan dari kenyataannya."""
        from bast_pasal import PERAN_PENERIMA_KEMBALI, daftar_penyata
        r = daftar_penyata("pengembalian", self.P2, self.P1, [], self.ASET)
        assert len(r) == 1
        assert r[0]["nama"] == "Andi"
        assert r[0]["peran"] == PERAN_PENERIMA_KEMBALI

    def test_operasional_satu_lembar_per_penanggung_jawab(self):
        from bast_pasal import PERAN_PJ_UNIT, daftar_penyata
        pj = [{"nama": "Budi", "nip": "9", "unit_tempat_tugas": "Lt 3",
               "asset_ids": ["a1"]},
              {"nama": "Cici", "unit_tempat_tugas": "Gudang",
               "asset_ids": ["a2"]}]
        r = daftar_penyata("operasional_unit", self.P2, self.P1, pj, self.ASET)
        assert [x["nama"] for x in r] == ["Budi", "Cici", "Sari"]
        assert r[0]["peran"] == PERAN_PJ_UNIT
        assert [a["id"] for a in r[0]["aset"]] == ["a1"]
        # Lembar terakhir memuat SISA yang tak melekat pada siapa pun.
        assert [a["id"] for a in r[2]["aset"]] == ["a3"]

    def test_tanpa_sisa_tak_ada_lembar_tambahan(self):
        pj = [{"nama": "Budi", "asset_ids": ["a1", "a2", "a3"]}]
        from bast_pasal import daftar_penyata
        r = daftar_penyata("operasional_unit", self.P2, self.P1, pj, self.ASET)
        assert [x["nama"] for x in r] == ["Budi"]

    def test_penanggung_jawab_tanpa_BMN_tetap_dapat_lembarnya(self):
        """Ia memang ditunjuk; daftar kosong pada lembarnya menyatakan keadaan
        sebenarnya alih-alih menyembunyikannya."""
        from bast_pasal import daftar_penyata
        pj = [{"nama": "Budi", "asset_ids": []}]
        r = daftar_penyata("operasional_unit", self.P2, self.P1, pj, self.ASET)
        assert r[0]["nama"] == "Budi" and r[0]["aset"] == []
        assert r[1]["nama"] == "Sari" and len(r[1]["aset"]) == 3

    def test_operasional_tanpa_penanggung_jawab_jatuh_ke_pihak_kedua(self):
        from bast_pasal import PERAN_PEMEGANG, daftar_penyata
        r = daftar_penyata("operasional_unit", self.P2, self.P1, [], self.ASET)
        assert len(r) == 1 and r[0]["peran"] == PERAN_PEMEGANG


class TestButirPernyataan:
    def test_pemegang_menyebut_ganti_rugi_dan_larangan_pindah_tangan(self):
        from bast_pasal import PERAN_PEMEGANG, butir_pernyataan
        teks = " ".join(butir_pernyataan(PERAN_PEMEGANG))
        assert "Nomor 1 Tahun 2004" in teks and "Nomor 38 Tahun 2016" in teks
        assert "memindahtangankan" in teks

    def test_penanggung_jawab_unit_menyebut_unitnya(self):
        from bast_pasal import PERAN_PJ_UNIT, butir_pernyataan
        assert "Ruang Server" in butir_pernyataan(PERAN_PJ_UNIT, "Ruang Server")[0]

    def test_unit_kosong_tak_melahirkan_kalimat_menggantung(self):
        from bast_pasal import PERAN_PJ_UNIT, butir_pernyataan
        b0 = butir_pernyataan(PERAN_PJ_UNIT, "")[0]
        assert "unit/tempat tugas sebagaimana" in b0 and "  " not in b0

    def test_penerima_kembali_TIDAK_menyatakan_pemakaian(self):
        from bast_pasal import PERAN_PENERIMA_KEMBALI, butir_pernyataan
        teks = " ".join(butir_pernyataan(PERAN_PENERIMA_KEMBALI))
        assert "menatausahakan" in teks
        assert "kepentingan kedinasan" not in teks


class TestSuratPernyataanDiPdf:
    def test_lembar_terbit_dengan_identitas_dan_daftar_barang(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "penggunaan_melekat", [])
        hal = _halaman_teks(_jalan(skenario()))
        teks = " ".join(hal)
        assert "SURAT PERNYATAAN TANGGUNG JAWAB" in teks
        assert "Sari Penerima" in teks
        assert "TIDAK TERPISAHKAN" in teks
        assert "BAST-007/PPTHD/VIII/2026" in teks

    def test_TIDAK_terbit_bila_tak_dipilih(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf(dbx, [])
        teks = " ".join(_halaman_teks(_jalan(skenario())))
        assert "SURAT PERNYATAAN TANGGUNG JAWAB" not in teks

    def test_operasional_terbit_satu_lembar_per_orang(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "operasional_unit", [
                {"nama": "Budi Penjaga", "nip": "199001012021011001",
                 "unit_tempat_tugas": "Ruang Server",
                 "unit_eselon": "Direktorat BMN", "asset_ids": ["a0", "a1"]},
                {"nama": "Cici Penjaga", "nip": "199101012021012002",
                 "unit_tempat_tugas": "Gudang", "asset_ids": ["a2"]}])
        hal = _halaman_teks(_jalan(skenario()))
        lembar = [t for t in hal if "SURAT PERNYATAAN TANGGUNG JAWAB" in t]
        # Dua penanggung jawab + satu lembar sisa untuk PIHAK KEDUA.
        assert len(lembar) == 3
        assert any("Budi Penjaga" in t for t in lembar)
        assert any("Cici Penjaga" in t for t in lembar)
        assert any("Sari Penerima" in t for t in lembar)

    def test_daftar_barang_tiap_lembar_hanya_miliknya(self, dbx):
        """Lembar yang memuat barang orang lain membuat orang menandatangani
        tanggung jawab yang bukan miliknya."""
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "operasional_unit", [
                {"nama": "Budi Penjaga", "nip": "1",
                 "unit_tempat_tugas": "Ruang Server", "asset_ids": ["a0"]}])
        hal = _halaman_teks(_jalan(skenario()))
        lembar_budi = next(t for t in hal if "Budi Penjaga" in t
                           and "SURAT PERNYATAAN" in t)
        assert "Barang Contoh Nama Agak Panjang 1" in lembar_budi   # aset a0
        assert "Barang Contoh Nama Agak Panjang 2" not in lembar_budi

    def test_daftar_barang_tetap_berkelompok_per_bidang(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "penggunaan_melekat", [])
        hal = _halaman_teks(_jalan(skenario()))
        lembar = next(t for t in hal if "SURAT PERNYATAAN" in t)
        assert "BIDANG" in lembar

    def test_penanggung_jawab_tanpa_BMN_menyatakan_keadaannya(self, dbx):
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "operasional_unit", [
                {"nama": "Budi Penjaga", "nip": "1",
                 "unit_tempat_tugas": "Ruang Server", "asset_ids": []}])
        hal = _halaman_teks(_jalan(skenario()))
        lembar = next(t for t in hal if "Budi Penjaga" in t
                      and "SURAT PERNYATAAN" in t)
        assert "Tidak ada BMN yang dilekatkan" in lembar

    def test_berita_acara_TETAP_dua_halaman(self, dbx):
        """Lampiran pernyataan menambah lembar SESUDAH tanda tangan — ia tak
        boleh mendorong Berita Acaranya sendiri jadi tiga halaman."""
        async def skenario():
            await _seed(dbx)
            return await _pdf_sptj(dbx, "operasional_unit", [
                {"nama": "Budi Penjaga", "nip": "1",
                 "unit_tempat_tugas": "Ruang Server", "asset_ids": ["a0"]}],
                n_aset=12)
        hal = _halaman_teks(_jalan(skenario()))
        # Berita Acara = SEMUA halaman SEBELUM lembar pernyataan pertama.
        # Menyaring "halaman yang tak memuat judul pernyataan" salah: lembar
        # pernyataan yang tumpah ke halaman kedua tak membawa judulnya.
        awal = next(i for i, t in enumerate(hal) if "SURAT PERNYATAAN" in t)
        assert awal <= 2, f"Berita Acara memakan {awal} halaman"
