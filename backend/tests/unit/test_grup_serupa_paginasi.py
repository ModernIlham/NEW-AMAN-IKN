"""Barang Serupa tidak lagi berhenti diam-diam di 100 kelompok.

Dua cacat sekaligus pada endpoint lama:

  1. `{"$limit": 100}` memotong hasil, DAN `total_groups` melaporkan jumlah
     yang DIKEMBALIKAN — bukan jumlah sebenarnya. Kegiatan dengan 400 kelompok
     tampak persis seperti kegiatan dengan 100, tanpa satu pun tanda bahwa
     sisanya ada. Itu bentuk pemotongan paling berbahaya: yang tak terlihat.

  2. Rincian anggota (12 field per aset) di-`$push` untuk SETIAP kelompok pada
     SETIAP permintaan, padahal panel hanya memakainya saat satu kelompok
     dibuka. Biaya seluruh kegiatan dibayar demi kelompok yang mungkin tak
     pernah diklik — dan itulah yang membuat menaikkan batas 100 jadi mahal.

Perbaikannya menyelesaikan keduanya: `$facet` memberi total sebenarnya +
satu halaman dalam satu perjalanan, dan rincian anggota pindah ke endpoint
terpisah yang dipanggil saat dibuka.
"""
import ast
import os

import pytest

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _fungsi(berkas, nama):
    with open(os.path.join(BACKEND, berkas), encoding="utf-8") as f:
        src = f.read()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nama:
            return ast.get_source_segment(src, n) or ""
    raise AssertionError(f"{nama} tidak ditemukan di {berkas}")


class TestBatasKerasSudahHilang:
    def test_tidak_ada_limit_100_yang_dipatok(self):
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '{"$limit": 100}' not in fn, "batas keras 100 hidup lagi"

    def test_memakai_skip_dan_limit_dari_parameter(self):
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '{"$skip": lewati}' in fn and '{"$limit": ukuran}' in fn

    def test_ukuran_halaman_dibatasi_atas(self):
        """Klien tak boleh meminta satu halaman raksasa dan meniadakan gunanya
        paginasi — yang butuh lebih memanggil halaman berikutnya."""
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert "min(500," in fn


class TestTotalDilaporkanJujur:
    def test_facet_menghitung_total_terpisah(self):
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '"$facet"' in fn
        assert '"total": [{"$count": "n"}]' in fn

    def test_total_bukan_panjang_halaman(self):
        """Inti cacat lama: `len(groups)` dilaporkan sebagai total."""
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '"total_groups": len(groups)' not in fn
        assert '"total_groups": total' in fn

    def test_ada_penanda_masih_ada_sisa(self):
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '"has_more"' in fn


class TestAnggotaTidakLagiDiborong:
    def test_daftar_tak_mem_push_rincian_anggota(self):
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '"members": {"$push"' not in fn, (
            "rincian anggota diborong lagi di daftar — biaya seluruh kegiatan "
            "dibayar demi kelompok yang mungkin tak pernah dibuka")

    def test_daftar_tetap_membawa_yang_dibutuhkan_baris_ringkas(self):
        """Baris ringkas butuh id (untuk ubah massal) dan NUP (untuk rentang).
        Memangkas terlalu jauh akan mematikan fiturnya."""
        fn = _fungsi("routes/batch.py", "get_asset_groups")
        assert '"asset_ids": {"$push": "$id"}' in fn
        assert '"NUPs": {"$push": "$NUP"}' in fn

    def test_endpoint_anggota_ada_dan_ter_scope_satker(self):
        # Menuntut PEMANGGILAN, bukan sekadar nama. Baris `import` di dalam
        # fungsi memuat nama yang sama, sehingga pencarian substring polos
        # tetap ketemu meski panggilannya dicabut — uji-mutasi membuktikannya
        # lolos hijau. Ini kedua kalinya jebakan yang sama muncul di repo ini.
        fn = _fungsi("routes/batch.py", "get_group_members")
        assert "await scope_query_aset(" in fn, (
            "id dari klien dipakai apa adanya — satker lain bisa membaca "
            "rincian aset dengan menyelipkan id")

    def test_endpoint_anggota_dibatasi(self):
        fn = _fungsi("routes/batch.py", "get_group_members")
        assert "MAKS_ANGGOTA_KELOMPOK" in fn

    def test_urutan_anggota_mengikuti_permintaan(self):
        """Mongo mengembalikan dokumen tanpa urutan yang dijamin; tanpa
        pengurutan ulang, daftar NUP di layar teracak setiap kali dibuka."""
        fn = _fungsi("routes/batch.py", "get_group_members")
        assert "members.sort(" in fn


class TestPanelLayarIkut:
    def _panel(self):
        p = os.path.join(BACKEND, "..", "frontend", "src", "components",
                         "assets", "AssetGroupsPanel.jsx")
        with open(os.path.abspath(p), encoding="utf-8") as f:
            return f.read()

    def test_menampilkan_jumlah_sebenarnya(self):
        src = self._panel()
        assert "total_groups" in src and "dari {total} kelompok" in src

    def test_ada_tombol_muat_lebih_banyak(self):
        src = self._panel()
        assert "grup-muat-lagi" in src and "hasMore" in src

    def test_anggota_diambil_saat_dibuka(self):
        src = self._panel()
        assert "assets/group-members" in src
        assert "group.members" not in src, (
            "panel masih membaca members dari daftar — jalur lama hidup lagi")
