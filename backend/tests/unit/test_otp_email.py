"""send_otp_email: kembalikan (ok, alasan) — alasan actionable, bukan False bisu."""
import asyncio

import shared_utils as su


def test_tanpa_api_key_alasan_jelas(monkeypatch):
    monkeypatch.setattr(su, "RESEND_API_KEY", "")
    ok, alasan = asyncio.run(su.send_otp_email("a@b.c", "123456"))
    assert ok is False
    assert "RESEND_API_KEY" in alasan


def test_galat_domain_belum_terverifikasi(monkeypatch):
    # Pesan khas Resend saat SENDER_EMAIL masih alamat uji @resend.dev.
    monkeypatch.setattr(su, "RESEND_API_KEY", "re_uji")
    def boom(params):
        raise Exception("You can only send testing emails to your own email address")
    monkeypatch.setattr(su.resend.Emails, "send", boom)
    ok, alasan = asyncio.run(su.send_otp_email("a@b.c", "123456"))
    assert ok is False
    assert "terverifikasi" in alasan and "SENDER_EMAIL" in alasan


def test_galat_kunci_api(monkeypatch):
    monkeypatch.setattr(su, "RESEND_API_KEY", "re_uji")
    def boom(params):
        raise Exception("401 Unauthorized: invalid API key")
    monkeypatch.setattr(su.resend.Emails, "send", boom)
    ok, alasan = asyncio.run(su.send_otp_email("a@b.c", "123456"))
    assert ok is False
    assert "RESEND_API_KEY" in alasan


def test_sukses(monkeypatch):
    monkeypatch.setattr(su, "RESEND_API_KEY", "re_uji")
    monkeypatch.setattr(su.resend.Emails, "send", lambda params: {"id": "em_1"})
    ok, alasan = asyncio.run(su.send_otp_email("a@b.c", "123456", "Budi"))
    assert ok is True and alasan == ""


def test_bersihkan_env_kutip_spasi_crlf():
    # Kesalahan salin .env paling umum: kutip ikut, spasi/CR-LF di ujung.
    assert su._bersihkan_env('  "re_abc123"\r\n') == "re_abc123"
    assert su._bersihkan_env("'re_xyz' ") == "re_xyz"
    assert su._bersihkan_env(None) == ""
