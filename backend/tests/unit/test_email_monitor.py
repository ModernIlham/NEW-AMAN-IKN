"""Uji helper MURNI pemantauan kuota email Resend (tanpa DB/jaringan).

Fokus: klasifikasi galat kuota (harian/bulanan vs rate-limit throughput yang
BUKAN kuota) + bentuk ringkasan indikator (persen/sisa/status).
"""


def test_periode_email_format_utc():
    from datetime import datetime, timezone
    from shared_utils import _periode_email
    hari, bulan = _periode_email(datetime(2026, 7, 23, 5, 0, tzinfo=timezone.utc))
    assert hari == "2026-07-23"
    assert bulan == "2026-07"


def test_deteksi_kuota_harian_dan_bulanan():
    from shared_utils import _deteksi_kuota_email
    assert _deteksi_kuota_email("You have reached your daily quota") == "harian"
    assert _deteksi_kuota_email("Daily limit exceeded") == "harian"
    assert _deteksi_kuota_email("Monthly sending limit reached") == "bulanan"
    # Pesan kuota tanpa satuan → default harian (batas yg lebih dulu kena).
    assert _deteksi_kuota_email("Quota exceeded") == "harian"


def test_deteksi_bukan_kuota():
    from shared_utils import _deteksi_kuota_email
    # Rate-limit throughput (2 req/detik) BUKAN kuota kirim harian/bulanan.
    assert _deteksi_kuota_email("Too many requests, rate limit") is None
    assert _deteksi_kuota_email("rate limit exceeded per second") is None
    # Galat lain (domain/api key/jaringan) juga bukan kuota.
    assert _deteksi_kuota_email("Invalid API key") is None
    assert _deteksi_kuota_email("Domain not verified") is None
    assert _deteksi_kuota_email("") is None
    assert _deteksi_kuota_email(None) is None


def test_bagian_persen_sisa_status():
    from routes.email_monitor import _bagian
    b = _bagian({"total": 80, "per_jenis": {"otp_registrasi": 50, "esign": 30}}, 100)
    assert b["terpakai"] == 80 and b["sisa"] == 20 and b["persen"] == 80.0
    assert b["status"] == "hampir"        # >= 80% → hampir
    # Rincian terurut jumlah menurun + berlabel ramah.
    assert b["rincian"][0]["jenis"] == "otp_registrasi"
    assert b["rincian"][0]["label"] == "OTP Registrasi"

    penuh = _bagian({"total": 100}, 100)
    assert penuh["status"] == "penuh" and penuh["sisa"] == 0
    aman = _bagian({"total": 3}, 100)
    assert aman["status"] == "aman"
    # Melebihi limit → persen dijepit 100, sisa tak negatif.
    lewat = _bagian({"total": 130}, 100)
    assert lewat["persen"] == 100.0 and lewat["sisa"] == 0


def test_int_default_aman():
    from routes.email_monitor import _int
    assert _int(None, 100) == 100
    assert _int(0, 100) == 100        # <=0 → default
    assert _int("abc", 100) == 100
    assert _int(250, 100) == 250
