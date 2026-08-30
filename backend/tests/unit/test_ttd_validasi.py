from ttd_validasi import (
    judul_ttd_tampil, label_jenis_ttd, status_permintaan,
    sudah_membubuhkan, sudah_terverifikasi,
)


def _sg(status, fid=""):
    return {"status": status, "signature_file_id": fid}


class TestStatusValidasi:
    def test_belum_ada_yang_membubuhkan(self):
        assert status_permintaan([_sg("aktif"), _sg("menunggu")]) == "terkirim"

    def test_sebagian_sudah_masuk(self):
        assert status_permintaan([
            _sg("menunggu_validasi", "f1"), _sg("aktif")]) == "sebagian"

    def test_semua_masuk_belum_divalidasi(self):
        assert status_permintaan([
            _sg("menunggu_validasi", "f1"),
            _sg("menunggu_validasi", "f2"),
        ]) == "menunggu_validasi"

    def test_sebagian_terverifikasi_tetap_menunggu_validasi(self):
        assert status_permintaan([
            _sg("terverifikasi", "f1"),
            _sg("menunggu_validasi", "f2"),
        ]) == "menunggu_validasi"

    def test_semua_terverifikasi_baru_selesai(self):
        assert status_permintaan([
            _sg("terverifikasi", "f1"), _sg("terverifikasi", "f2")]) == "selesai"

    def test_status_lama_tetap_dianggap_final(self):
        lama = _sg("ditandatangani", "f1")
        assert sudah_membubuhkan(lama)
        assert sudah_terverifikasi(lama)
        assert status_permintaan([lama]) == "selesai"


class TestJudulTtd:
    def test_jenis_dan_judul_bast_dipisah(self):
        assert label_jenis_ttd("bast") == "BAST"
        assert judul_ttd_tampil(
            "BAST BAST-035/SATKER-D/OIKN/VIII/2026", "bast"
        ) == "BAST-035/SATKER-D/OIKN/VIII/2026"

    def test_judul_tanpa_duplikasi_tidak_dirusak(self):
        assert judul_ttd_tampil("BAST-035/OIKN/2026", "bast") == "BAST-035/OIKN/2026"

    def test_jenis_bebas_tetap_punya_label(self):
        assert label_jenis_ttd("nota_dinas") == "Nota Dinas"
