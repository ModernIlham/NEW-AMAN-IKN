"""Uji redaksi data sensitif pada log (ATURAN MAIN LOGGING #3)."""
import logging

from log_setup import RedaksiLogFilter, redaksi_log


class TestRedaksiLog:
    def test_kunci_rahasia_disensor(self):
        assert redaksi_log("login gagal password=Rahasia123!") == \
            "login gagal password=***"
        assert redaksi_log("kirim api_key: sk-abcdef123456") == \
            "kirim api_key: ***"
        assert redaksi_log("OTP=482913 terkirim") == "OTP=*** terkirim"
        assert redaksi_log("header Authorization: Basic dXNlcjpwYXNz") == \
            "header Authorization: ***"

    def test_bearer_dan_jwt(self):
        assert redaksi_log("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def") \
            == "Authorization: ***"
        assert redaksi_log(
            "token bocor eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpM") == \
            "token bocor ***jwt***"

    def test_nik_16_digit_disamarkan_sisakan_4(self):
        assert redaksi_log("NIK 6472011203990001 terdaftar") == \
            "NIK ************0001 terdaftar"

    def test_nip_18_digit_dan_kode_satker_tak_tersentuh(self):
        # NIP (18 digit) & kode satker (20 digit) BUKAN NIK — jangan disensor.
        assert redaksi_log("NIP 199003052015041001 aktif") == \
            "NIP 199003052015041001 aktif"
        assert redaksi_log("satker 12601160069177800000") == \
            "satker 12601160069177800000"

    def test_teks_biasa_utuh(self):
        pesan = "aset A-123 diperbarui oleh admin (3 field)"
        assert redaksi_log(pesan) == pesan

    def test_filter_menyensor_argumen_persen(self):
        # Argumen %s ikut tersensor karena pesan dirender dini di filter.
        record = logging.LogRecord(
            "app", logging.INFO, __file__, 1,
            "reset user %s token=%s", ("budi", "abc123xyz"), None)
        assert RedaksiLogFilter().filter(record) is True
        assert record.getMessage() == "reset user budi token=***"
