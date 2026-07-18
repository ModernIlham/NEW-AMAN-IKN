"""Uji logika murni KIB — Kartu Identitas Barang (PMK 181, pola SAKTI)."""
from pembukuan_utils import KIB_FIELDS, KIB_LABELS, bersihkan_kib, jenis_kib


def test_jenis_kib_per_kode():
    assert jenis_kib("2010104001") == "tanah"          # golongan 2
    assert jenis_kib("4010101001") == "gedung"         # golongan 4
    assert jenis_kib("3020104002") == "angkutan"       # bidang 302
    assert jenis_kib("3010203001") == "alat_besar"     # bidang 301
    assert jenis_kib("3070102001") == "senjata"        # bidang 307
    # Peralatan kantor biasa (305xxx) & golongan lain → tidak ber-KIB
    assert jenis_kib("3050104001") is None
    assert jenis_kib("5010101001") is None
    assert jenis_kib("6010101001") is None
    assert jenis_kib("") is None
    assert jenis_kib(None) is None
    assert jenis_kib("abc") is None


def test_spec_kib_konsisten():
    # Semua jenis punya label & minimal 3 field khusus
    assert set(KIB_FIELDS) == set(KIB_LABELS)
    for jenis, fields in KIB_FIELDS.items():
        assert len(fields) >= 3, jenis
        keys = [k for k, _ in fields]
        assert len(keys) == len(set(keys)), f"key ganda di {jenis}"
    # Field khas regulasi hadir
    assert "no_polisi" in dict(KIB_FIELDS["angkutan"])
    assert "no_sertifikat" in dict(KIB_FIELDS["tanah"])
    assert "no_imb" in dict(KIB_FIELDS["gedung"])


def test_bersihkan_kib():
    kotor = {"no_polisi": "  KT 1234 AB  ", "warna": "Hitam",
             "tidak_dikenal": "x", "no_rangka": "R" * 500}
    out = bersihkan_kib("angkutan", kotor)
    assert out["no_polisi"] == "KT 1234 AB"
    assert "tidak_dikenal" not in out
    assert len(out["no_rangka"]) == 200
    # Jenis tak dikenal → kosong (tidak crash)
    assert bersihkan_kib("planet", {"a": 1}) == {}
    assert bersihkan_kib("tanah", None) == {}
