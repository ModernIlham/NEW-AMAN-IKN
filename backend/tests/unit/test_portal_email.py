"""Email portal tetap terbaca tanpa CSS, tanpa gambar luar, dan aman dari markup nama."""
import asyncio
from html.parser import HTMLParser
from unittest.mock import AsyncMock, Mock

import pytest

from portal_email import isi_email_portal


class ElemenEmail(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elemen = []
        self.teks = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.teks.append(data)


def test_tombol_mempertahankan_link_dan_fragmen_secara_utuh():
    link = 'https://portal.example/bmn-saya#token=contoh&uji="kutip"'
    isi = isi_email_portal("Pemegang Uji", link, 15)
    dom = ElemenEmail(isi["html"])
    anchors = [attrs for tag, attrs in dom.elemen if tag == "a"]
    assert len(anchors) == 1
    assert anchors[0]["href"] == link
    assert anchors[0]["data-testid"] == "email-portal-masuk"
    assert link in isi["text"]


def test_nama_tidak_dapat_menyisipkan_markup_atau_tautan():
    nama = '<img src=x onerror="alert(1)"> & <a href="https://asing.example">Nama</a>'
    isi = isi_email_portal(nama, "https://portal.example/#token=uji", 15)
    dom = ElemenEmail(isi["html"])
    assert nama in "".join(dom.teks)
    assert len([tag for tag, _ in dom.elemen if tag == "a"]) == 1
    assert not any(tag in {"img", "script", "iframe", "link", "form"} for tag, _ in dom.elemen)
    assert not any(k.startswith("on") for _, attrs in dom.elemen for k in attrs)


@pytest.mark.parametrize("menit", [15, 10])
def test_pesan_keamanan_dan_masa_berlaku_sama_pada_kedua_format(menit):
    isi = isi_email_portal("Nama Uji", "https://portal.example/#token=uji", menit)
    for teks in ("".join(ElemenEmail(isi["html"]).teks), isi["text"]):
        for pesan in (f"{menit} menit", "dipakai sekali", "peramban tempat Anda meminta akses",
                      "Jangan teruskan tautan ini", "bila Anda tidak meminta akses",
                      "Masuk ke portal bukan tindakan penandatanganan dokumen",
                      "masukkan email Anda untuk meminta tautan baru"):
            assert pesan in teks


def test_layout_email_tidak_memerlukan_aset_eksternal():
    isi = isi_email_portal(None, "https://portal.example/#token=uji", 15)
    dom = ElemenEmail(isi["html"])
    assert "Pemegang BMN" in isi["text"]
    assert '<html lang="id">' in isi["html"]
    assert 'name="viewport"' in isi["html"]
    assert "max-width:600px" in isi["html"]
    assert "url(" not in isi["html"]
    assert not any("src" in attrs for _, attrs in dom.elemen)
    assert all(attrs.get("role") == "presentation" for tag, attrs in dom.elemen if tag == "table")


def test_transport_mengirim_kedua_format_dengan_ttl_auth(monkeypatch, caplog):
    import portal_auth as pa
    import shared_utils as su

    kirim = Mock(return_value={"id": "email-sintetis"})
    catat = AsyncMock()
    monkeypatch.setattr(su, "RESEND_API_KEY", "kunci-uji")
    monkeypatch.setattr(su, "SENDER_EMAIL", "AMAN <aman@example.test>")
    monkeypatch.setattr(su.resend.Emails, "send", kirim)
    monkeypatch.setattr(su, "catat_email_terkirim", catat)
    link = "https://portal.example/bmn-saya#token=rahasia-sintetis"
    assert asyncio.run(pa.kirim_email_portal("uji@example.test", "Nama Uji", link)) is True
    params = kirim.call_args.args[0]
    assert params == {"from": "AMAN <aman@example.test>", "to": ["uji@example.test"],
                      "subject": "Tautan masuk BMN Saya — AMAN",
                      **isi_email_portal("Nama Uji", link, int(pa.LINK_TTL.total_seconds() // 60))}
    catat.assert_awaited_once_with("portal_pemegang")
    assert "rahasia-sintetis" not in caplog.text
    assert "uji@example.test" not in caplog.text
