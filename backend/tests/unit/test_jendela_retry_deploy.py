"""Jendela retry deploy tidak boleh menyusut diam-diam.

Latar: 17-18 Agustus 2026 tiga deploy gagal karena VPS tak terjangkau. Log
sshd VPS membuktikan paketnya TIDAK PERNAH SAMPAI pada jendela yang gagal —
gangguan ada di jalur jaringan penyedia, bukan di mesin atau aplikasi.

Jendela retry lama, 5x(timeout 15s + jeda 20s) ~= 2,9 menit, habis tepat di
dalam gangguan itu. Diperpanjang jadi ~6 menit sebagai BANTALAN.

Uji ini menjaga anggaran waktunya. Angka retry adalah hal yang gampang
"dirapikan" kembali ke nilai kecil oleh orang yang tidak tahu insiden ini —
dan akibatnya baru terasa berbulan-bulan kemudian saat blip berikutnya.
"""
import os
import re

import pytest

DEPLOY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".github", "workflows", "deploy.yml"))

# Serendah-rendahnya yang masih masuk akal: gangguan terakhir menutupi
# sekurangnya 2,5 menit dan jendela 2,9 menit terbukti tak cukup.
MINIMAL_DETIK = 300


def _sumber():
    with open(DEPLOY, encoding="utf-8") as f:
        return f.read()


def _anggaran_detik(src):
    """Perkiraan total jendela: jumlah percobaan x (timeout keyscan + jeda)."""
    percobaan = re.search(r"for attempt in ([\d ]+); do", src)
    timeout = re.search(r"ssh-keyscan -T (\d+)", src)
    jeda = re.search(r"gagal menjangkau VPS.*?\n\s*sleep (\d+)", src, re.S)
    assert percobaan and timeout and jeda, "pola retry tak terbaca — perbarui uji ini"
    n = len(percobaan.group(1).split())
    return n * (int(timeout.group(1)) + int(jeda.group(1))), n


class TestAnggaranRetry:
    def test_jendela_cukup_panjang(self):
        total, n = _anggaran_detik(_sumber())
        assert total >= MINIMAL_DETIK, (
            f"jendela retry hanya ~{total} detik ({n} percobaan) — gangguan "
            f"jaringan penyedia pada 18 Agu 2026 melampaui {MINIMAL_DETIK} detik")

    def test_percobaan_tidak_kembali_ke_lima(self):
        _, n = _anggaran_detik(_sumber())
        assert n >= 8, f"jumlah percobaan turun ke {n} — lihat docs/OPTIMASI-VPS.md §5"

    def test_pesan_galat_mengarahkan_ke_penyedia(self):
        """Pesan lama hanya menyuruh memeriksa secret dan 'VPS hidup' — dan
        itu justru menyesatkan pada insiden kemarin, karena VPS memang hidup."""
        src = _sumber()
        assert "penyedia" in src.lower() or "PENYEDIA" in src


class TestDokumenTidakLagiMenyesatkan:
    """Dokumen VPS pernah dijadikan dasar diagnosis yang salah karena
    menyatakan swap belum dipasang padahal sudah."""

    def _doc(self):
        p = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "docs", "OPTIMASI-VPS.md"))
        with open(p, encoding="utf-8") as f:
            return f.read()

    def test_status_swap_terverifikasi_tercatat(self):
        d = self._doc()
        assert "Status terverifikasi" in d
        assert "SUDAH DIPASANG" in d or "SUDAH DIKERJAKAN" in d

    def test_insiden_jaringan_terdokumentasi(self):
        # Spasi dinormalkan: frasa kunci bisa terpenggal baris oleh pembungkus
        # teks Markdown, dan uji yang bergantung pada posisi baris rapuh tanpa
        # alasan. Pelajaran yang sama sudah muncul pada uji panel Riwayat.
        d = re.sub(r"\s+", " ", self._doc()).lower()
        assert "insiden jaringan penyedia" in d
        assert "tidak pernah sampai" in d
