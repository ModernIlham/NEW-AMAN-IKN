"""Test helper murni konverter WebP (tanpa DB/jaringan/Tinify).

Fokus pada GERBANG KEAMANAN: verifikasi_webp harus MENOLAK apa pun yang bukan
WebP utuh berdimensi sama — inilah yang mencegah penghapusan foto lama sebelum
hasil konversi benar-benar valid.
"""
import io

from PIL import Image as PILImage


def _img_bytes(fmt, size=(20, 30), color=(10, 20, 30)):
    buf = io.BytesIO()
    PILImage.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def test_verifikasi_webp_terima_webp_dimensi_sama():
    import webp_converter as wc
    webp = _img_bytes("WEBP", (20, 30))
    assert wc.verifikasi_webp(webp, 20, 30) is True


def test_verifikasi_webp_tolak_non_webp():
    import webp_converter as wc
    jpg = _img_bytes("JPEG", (20, 30))
    png = _img_bytes("PNG", (20, 30))
    # Format bukan WEBP → HARUS ditolak (jangan sampai hapus lama).
    assert wc.verifikasi_webp(jpg, 20, 30) is False
    assert wc.verifikasi_webp(png, 20, 30) is False


def test_verifikasi_webp_tolak_dimensi_beda():
    import webp_converter as wc
    webp = _img_bytes("WEBP", (20, 30))
    assert wc.verifikasi_webp(webp, 21, 30) is False   # lebar beda
    assert wc.verifikasi_webp(webp, 20, 31) is False   # tinggi beda


def test_verifikasi_webp_tolak_kosong_dan_sampah():
    import webp_converter as wc
    assert wc.verifikasi_webp(b"", 20, 30) is False
    assert wc.verifikasi_webp(None, 20, 30) is False
    assert wc.verifikasi_webp(b"bukan gambar sama sekali", 20, 30) is False


def test_dimensi():
    import webp_converter as wc
    assert wc._dimensi(_img_bytes("JPEG", (64, 48))) == (64, 48)
    assert wc._dimensi(_img_bytes("WEBP", (100, 10))) == (100, 10)
    assert wc._dimensi(b"") is None
    assert wc._dimensi(b"rusak") is None


def test_tebak_media_type():
    from routes.assets import _tebak_media_type
    assert _tebak_media_type(_img_bytes("JPEG")) == "image/jpeg"
    assert _tebak_media_type(_img_bytes("PNG")) == "image/png"
    assert _tebak_media_type(_img_bytes("WEBP")) == "image/webp"
    assert _tebak_media_type(_img_bytes("GIF")) == "image/gif"
    assert _tebak_media_type(b"") == "image/jpeg"   # default aman


def test_activity_tracker_relevan():
    import activity_tracker as at
    # Health/probe/ws TIDAK dihitung aktivitas; endpoint biasa dihitung.
    assert at._relevan("/api/assets") is True
    assert at._relevan("/api/health/deep") is False
    assert at._relevan("/api/ws/updates") is False
    assert at._relevan("") is False


def test_konstanta_default_aman():
    import webp_converter as wc
    # Ambang stop kuota = 50 (sesuai permintaan); worker id unik.
    assert wc.KUOTA_SISA_MIN == 50
    assert wc._worker_id and "-" in wc._worker_id


def test_registry_sumber_prioritas_dan_query():
    import webp_converter as wc
    nama = [s["nama"] for s in wc.SUMBER]
    # Prioritas: foto ASLI aset dulu, lalu foto pegawai (tampil), lalu asli krop.
    assert nama == ["aset", "pegawai", "pegawai_asli"]
    q_aset = wc.SUMBER[0]["query"]
    # Query aset tak boleh menyeret blob ber-`jenis` (mis. foto pegawai).
    assert q_aset["metadata.jenis"] == {"$exists": False}
    assert q_aset["metadata.content_type"] == "image/jpeg"
    # Query pegawai spesifik ke jenis-nya & tak menyeret yg sudah webp.
    assert wc.SUMBER[1]["query"]["metadata.jenis"] == "foto_pegawai"
    assert "image/webp" not in wc.SUMBER[1]["query"]["metadata.content_type"]["$in"]


def test_registry_meta_baru_pertahankan_pemilik():
    import webp_converter as wc
    m = {"pegawai_id": "peg-1", "jenis": "foto_pegawai", "content_type": "image/png"}
    # Blob WebP baru harus MEMBAWA jenis + pegawai_id agar serve & query kandidat
    # tetap benar.
    assert wc.SUMBER[1]["meta"](m) == {"jenis": "foto_pegawai", "pegawai_id": "peg-1"}
    assert wc.SUMBER[2]["meta"]({"pegawai_id": "peg-2"}) == {
        "jenis": "foto_pegawai_asli", "pegawai_id": "peg-2"}
    assert wc.SUMBER[0]["meta"]({}) == {}   # aset: tak perlu metadata tambahan
