"""Timeline Aset HARUS menampilkan bukti lokasi lapangan, bukan membuangnya.

Dua sumber kejadian sudah lama terekam tetapi tak pernah sampai ke layar:

  * `opname_scan` — bukti bahwa petugas benar-benar MELIHAT barangnya di
    lapangan (pindai stiker QR). Satu-satunya jejaknya di timeline selama ini
    adalah baris audit "Perubahan data aset (opname_scan)": judulnya keliru
    (pemindaian tak mengubah data apa pun) dan isinya nihil — node mana,
    cocok atau tidak, sudah diterapkan atau belum, semuanya hilang.
  * `riwayat_lokasi_aset` — jejak custody antar ruangan. Koleksi ini sengaja
    menyimpan SNAPSHOT NAMA kedua sisi supaya tetap terbaca bertahun kemudian
    (node bisa diganti nama/dihapus), tetapi tak ada satu pun layar yang
    membacanya.

Berkas ini menguji bagian murninya + satu penjaga anti-ganda: setelah kedua
sumber tampil utuh, aksi audit yang sama TIDAK boleh ikut lolos ke bagian log
teknis — kalau lolos, tiap pemindaian muncul dua kali dan cacah chip filter
per modul ikut menggelembung.
"""
import os
import re

from timeline_utils import (LABEL_STATUS, LABEL_STATUS_SCAN, MODUL_LABEL,
                            event_pindah_lokasi, event_scan_opname,
                            ringkas_per_modul)

_ROUTE = os.path.join(os.path.dirname(__file__), "..", "..",
                      "routes", "timeline.py")


def _sumber_route():
    with open(os.path.abspath(_ROUTE), encoding="utf-8") as f:
        return f.read()


class TestEventScanOpname:
    def test_lokasi_dan_hasil_rekonsiliasi_tampil(self):
        e = event_scan_opname({
            "id": "opn_1", "pada": "2026-08-01T09:00:00+00:00",
            "status_rekonsiliasi": "sesuai", "oleh": "petugas1",
            "lokasi_spasial": {"node_nama": "R.101",
                               "jalur_nama": "Gedung A / Lt.1 / R.101"},
        })
        assert e["modul"] == "lokasi"
        assert e["jenis"] == "opname_scan"
        assert e["judul"] == "Dipindai di Gedung A / Lt.1 / R.101"
        assert "Oleh: petugas1" in e["detail"]
        # Hasil rekonsiliasi TIDAK di detail — ia jadi badge status di UI.
        assert "Hasil" not in e["detail"]
        assert e["tanggal"] == "2026-08-01T09:00:00+00:00"
        assert e["status"] == "sesuai"

    def test_pindah_menyebut_asal_dan_apakah_sudah_diterapkan(self):
        """Inti nilai sebuah temuan 'pindah': dari mana, dan apakah catatan
        sudah menyusul. Tanpa keduanya, operator tak tahu ada pekerjaan sisa."""
        e = event_scan_opname({
            "id": "opn_2", "pada": "2026-08-02T10:00:00+00:00",
            "status_rekonsiliasi": "pindah", "diterapkan": False,
            "lokasi_spasial": {"jalur_nama": "Gedung B / Lt.2 / R.205"},
            "lokasi_sebelum": {"node_id": "n1", "nama": "R.101",
                               "jalur": "Gedung A / Lt.1 / R.101"},
        })
        assert e["status"] == "pindah"
        assert "Tercatat sebelumnya di Gedung A / Lt.1 / R.101" in e["detail"]
        assert "BELUM diterapkan ke catatan" in e["detail"]

    def test_pindah_yang_sudah_diterapkan_dinyatakan_selesai(self):
        e = event_scan_opname({
            "status_rekonsiliasi": "pindah", "diterapkan": True,
            "lokasi_spasial": {"jalur_nama": "R.205"},
            "lokasi_sebelum": {"jalur": "R.101"}})
        assert "Sudah diterapkan" in e["detail"]
        assert "BELUM diterapkan" not in e["detail"]

    def test_scan_tanpa_node_tetap_jadi_bukti_kehadiran(self):
        """`tanpa_lokasi` = di luar kawasan terpetakan. Tetap ditampilkan:
        ia membuktikan barangnya ADA dan siapa yang melihatnya."""
        e = event_scan_opname({
            "status_rekonsiliasi": "tanpa_lokasi", "oleh": "petugas2",
            "pada": "2026-08-03T08:00:00+00:00", "lokasi_spasial": {}})
        assert e["judul"] == "Dipindai (tanpa lokasi denah)"
        assert e["status"] == "tanpa_lokasi"
        assert LABEL_STATUS["tanpa_lokasi"]        # badge-nya berlabel

    def test_hanya_status_pindah_yang_membahas_penerapan(self):
        """Scan 'sesuai'/'baru' tak pernah perlu diterapkan — menuliskan
        "BELUM diterapkan" di sana akan mengarang pekerjaan yang tak ada."""
        for st in ("sesuai", "baru", "tanpa_lokasi"):
            e = event_scan_opname({"status_rekonsiliasi": st,
                                   "lokasi_spasial": {"node_nama": "R.1"}})
            assert "diterapkan" not in e["detail"], st

    def test_status_asing_diteruskan_apa_adanya(self):
        """Status di luar daftar tetap dibawa di field `status` (UI yang
        memutuskan menampilkan atau tidak), bukan dibuang di backend."""
        e = event_scan_opname({"status_rekonsiliasi": "entah",
                               "lokasi_spasial": {"node_nama": "R.1"}})
        assert e["status"] == "entah"
        assert "entah" not in LABEL_STATUS

    def test_jatuh_ke_diterima_pada_bila_pada_kosong(self):
        """`pada` berasal dari jam PERANGKAT (antrean luring) dan bisa kosong;
        tanpa cadangan, event mendarat di tumpukan 'tanpa tanggal'."""
        e = event_scan_opname({"diterima_pada": "2026-08-04T00:00:00+00:00",
                               "lokasi_spasial": {}})
        assert e["tanggal"] == "2026-08-04T00:00:00+00:00"

    def test_scan_kosong_tak_meledak(self):
        for masukan in (None, {}, {"lokasi_spasial": None}):
            e = event_scan_opname(masukan)
            assert e["modul"] == "lokasi"
            assert e["judul"]


class TestEventPindahLokasi:
    def test_perpindahan_menyebut_kedua_sisi(self):
        e = event_pindah_lokasi({
            "asset_id": "a1", "pada": "2026-08-05T07:00:00+00:00",
            "oleh": "admin",
            "dari": {"node_id": "n1", "nama": "R.101", "jalur": "Gd.A / R.101"},
            "ke": {"node_id": "n2", "nama": "R.205", "jalur": "Gd.B / R.205"}})
        assert e["modul"] == "lokasi"
        assert e["jenis"] == "pindah"
        assert e["judul"] == "Dipindahkan: Gd.A / R.101 → Gd.B / R.205"
        assert e["detail"] == "Oleh: admin"
        assert e["ref_id"] == "a1"

    def test_penempatan_pertama_bukan_perpindahan(self):
        e = event_pindah_lokasi({"dari": {}, "ke": {"jalur": "Gd.A / R.101"}})
        assert e["jenis"] == "penempatan"
        assert e["judul"] == "Ditempatkan di Gd.A / R.101"

    def test_pencabutan_menyebut_lokasi_terakhirnya(self):
        """Tanpa menyebut asalnya, "penempatan dicabut" tak bisa ditelusuri —
        justru itu yang dicari saat barang hilang."""
        e = event_pindah_lokasi({"dari": {"jalur": "Gd.A / R.101"}, "ke": {}})
        assert e["jenis"] == "pencabutan"
        assert "Gd.A / R.101" in e["judul"]

    def test_jalur_diprioritaskan_atas_nama_node(self):
        e = event_pindah_lokasi({"ke": {"nama": "R.101",
                                        "jalur": "Gd.A / Lt.1 / R.101"}})
        assert "Gd.A / Lt.1 / R.101" in e["judul"]

    def test_nama_dipakai_bila_jalur_kosong(self):
        e = event_pindah_lokasi({"ke": {"nama": "R.101", "jalur": ""}})
        assert e["judul"] == "Ditempatkan di R.101"

    def test_baris_cacat_tetap_muncul_sebagai_jejak(self):
        """Baris tanpa kedua sisi (data lama) tak boleh dibuang senyap —
        riwayat custody yang diam-diam berlubang lebih buruk daripada baris
        yang jujur mengaku tak lengkap."""
        e = event_pindah_lokasi({"pada": "2026-01-01T00:00:00+00:00"})
        assert e["judul"] == "Perubahan penempatan denah"
        assert e["tanggal"] == "2026-01-01T00:00:00+00:00"
        assert event_pindah_lokasi(None)["modul"] == "lokasi"


class TestModulBaru:
    def test_modul_lokasi_punya_label(self):
        """Tanpa entri di MODUL_LABEL, chip filter di UI menampilkan kunci
        mentah "lokasi" alih-alih nama yang terbaca."""
        assert MODUL_LABEL["lokasi"] == "Lokasi & Opname"

    def test_semua_status_scan_punya_label(self):
        """Sinkron dengan `opname_utils.klasifikasi_scan` — status yang
        terlewat akan tampil sebagai kode mentah di layar."""
        from opname_utils import klasifikasi_scan
        keluar = {
            klasifikasi_scan("", ""),            # tanpa_lokasi
            klasifikasi_scan("", "n1"),          # baru
            klasifikasi_scan("n1", "n1"),        # sesuai
            klasifikasi_scan("n1", "n2"),        # pindah
        }
        assert keluar <= set(LABEL_STATUS_SCAN)
        assert len(keluar) == 4

    def test_event_lokasi_terhitung_di_ringkasan_modul(self):
        n = ringkas_per_modul([
            event_scan_opname({"lokasi_spasial": {"node_nama": "R.1"}}),
            event_pindah_lokasi({"ke": {"nama": "R.1"}})])
        assert n["lokasi"] == 2


class TestAntiGanda:
    """Penjaga sumber: aksi yang sudah disajikan bagian 12 tak boleh lolos ke
    bagian log audit. Repo belum punya uji endpoint timeline, jadi ini membaca
    kodenya — cukup untuk menangkap kelas kesalahan itu saja."""

    def test_daftar_aksi_mencakup_ketiga_penulisnya(self):
        from routes.timeline import AKSI_SUDAH_DI_BAGIAN_LOKASI
        assert AKSI_SUDAH_DI_BAGIAN_LOKASI == {
            "opname_scan", "aset_lokasi_tandai", "aset_lokasi_hapus"}

    def test_aksi_itu_memang_yang_ditulis_backend(self):
        """Dibaca dari pemanggilan `log_audit` di penulisnya — bila nama
        aksinya diganti kelak, daftar penyaring jadi basi tanpa tanda."""
        from routes.timeline import AKSI_SUDAH_DI_BAGIAN_LOKASI
        dasar = os.path.join(os.path.dirname(__file__), "..", "..", "routes")
        aksi = set()
        for nama in ("opname.py", "spasial.py"):
            with open(os.path.join(os.path.abspath(dasar), nama),
                      encoding="utf-8") as f:
                isi = f.read()
            aksi |= set(re.findall(r'log_audit\(\s*"(opname_scan|aset_lokasi_\w+)"',
                                   isi))
        assert aksi == AKSI_SUDAH_DI_BAGIAN_LOKASI

    def test_penyaring_benar_benar_terpasang_di_bagian_audit(self):
        src = _sumber_route()
        assert "AKSI_SUDAH_DI_BAGIAN_LOKASI" in src
        # Penyaring harus berada SESUDAH pembacaan audit_logs — bila ditaruh
        # sebelumnya ia tak menyaring apa pun.
        assert src.index("db.audit_logs.find") < src.index(
            "if aksi in AKSI_SUDAH_DI_BAGIAN_LOKASI")

    def test_kedua_koleksi_dibaca_endpoint(self):
        src = _sumber_route()
        assert "db.opname_scan.find" in src
        assert "db.riwayat_lokasi_aset.find" in src
        assert "event_scan_opname(" in src and "event_pindah_lokasi(" in src

    def test_riwayat_lokasi_tidak_disaring_kode_satker(self):
        """`riwayat_lokasi_aset` TIDAK punya field kode_satker (lihat
        spasial_utils.entri_riwayat_lokasi). Menyaringnya dengan
        `_q_satker_lunak` akan mengosongkan hasilnya diam-diam."""
        src = _sumber_route()
        potong = src.split("db.riwayat_lokasi_aset.find", 1)[1][:220]
        assert "_q_satker_lunak" not in potong
        assert "asset_id" in potong

        from spasial_utils import entri_riwayat_lokasi
        baris = entri_riwayat_lokasi("a1", {"node_id": "n1"},
                                     {"node_id": "n2"}, "u", "2026-01-01")
        assert "kode_satker" not in baris


class TestBadgeStatus:
    """Status tiap kejadian dulu dikirim backend lalu DIBUANG UI: dari 7 field
    event, dialog hanya membaca 5 (modul, jenis, judul, detail, tanggal).
    Operator tak pernah tahu sebuah usulan itu masih diusulkan, sudah
    disetujui, atau sudah selesai."""

    _DIALOG = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "frontend", "src", "components", "assets",
                           "AssetTimelineDialog.jsx")

    def _dialog(self):
        with open(os.path.abspath(self._DIALOG), encoding="utf-8") as f:
            return f.read()

    def test_ui_membaca_status_dan_petanya(self):
        src = self._dialog()
        assert "label_status" in src
        assert "labelStatus[e.status]" in src

    def test_endpoint_mengirim_peta_labelnya(self):
        src = _sumber_route()
        assert '"label_status": LABEL_STATUS' in src

    def test_semua_status_scan_punya_label_badge(self):
        """Sinkron dengan `opname_utils.klasifikasi_scan` — status yang tak
        berlabel TIDAK akan tampil sama sekali (peta ini kuratif), sehingga
        hasil pemindaian hilang dari layar tanpa jejak."""
        from opname_utils import klasifikasi_scan
        keluar = {klasifikasi_scan("", ""), klasifikasi_scan("", "n1"),
                  klasifikasi_scan("n1", "n1"), klasifikasi_scan("n1", "n2")}
        assert keluar <= set(LABEL_STATUS)

    def test_kode_transaksi_buku_TIDAK_dilabeli(self):
        """`status` event pembukuan diisi `kode_transaksi` ("100", "101", …).
        Mendaftarkannya di sini membuat badge mengulang judul barisnya persis
        (judul sudah memakai `label_transaksi_buku`)."""
        from timeline_utils import KODE_TRANSAKSI_LABEL
        bentrok = [k for k in KODE_TRANSAKSI_LABEL if k in LABEL_STATUS]
        assert bentrok == []
        assert not any(k.isdigit() for k in LABEL_STATUS)

    def test_status_register_umum_terlabeli(self):
        """Nilai status yang benar-benar dipakai register siklus di repo ini."""
        for st in ("draft", "diusulkan", "diproses", "disetujui", "ditolak",
                   "selesai", "dibatalkan", "aktif", "berakhir"):
            assert LABEL_STATUS.get(st), st

    def test_label_scan_lama_tetap_selaras(self):
        """`LABEL_STATUS_SCAN` masih dipakai sebagai daftar acuan; kedua peta
        tak boleh menyimpang soal status MANA yang dikenal."""
        assert set(LABEL_STATUS_SCAN) <= set(LABEL_STATUS)
