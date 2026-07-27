"""Uji pagar privasi pelacakan (Fase 10) — kebijakan §10 arsitektur sebagai
kode yang DITEGAKKAN, bukan dokumen yang bisa dilewati kode berikutnya."""
from datetime import datetime, timedelta, timezone

import privasi_utils as pu

WITA = timezone(timedelta(hours=8))


def _wita(y, m, d, jam, menit=0):
    """Waktu WITA → UTC (jalur masuk observasi selalu UTC)."""
    return datetime(y, m, d, jam, menit, tzinfo=WITA).astimezone(timezone.utc)


OBS = {"geo": {"type": "Point", "coordinates": [116.71, -1.40]},
       "akurasi_m": 6.5, "kecepatan_kmh": 32.4, "arah_deg": 187,
       "lokasi_spasial": {"gedung_id": "sn_g1"}}


# ── Profil: gagal-TERTUTUP ──────────────────────────────────────────────────

def test_profil_tak_dikenal_jatuh_ke_paling_ketat():
    """Salah ketik profil TIDAK boleh membuka perekaman penuh 24/7."""
    assert pu.profil_privasi("ngawur") is pu.PROFIL_PRIVASI["personal"]
    assert pu.profil_privasi(None) is pu.PROFIL_PRIVASI["personal"]
    assert pu.profil_privasi("KENDARAAN")["presisi"] == "penuh"   # case-insensitive


# ── Jam aktif ───────────────────────────────────────────────────────────────

def test_personal_hanya_jam_kerja_hari_kerja():
    p = pu.profil_privasi("personal")
    assert pu.dalam_jam_aktif(_wita(2026, 7, 27, 10), p)        # Senin 10:00
    assert not pu.dalam_jam_aktif(_wita(2026, 7, 27, 22), p)    # Senin 22:00
    assert not pu.dalam_jam_aktif(_wita(2026, 7, 26, 10), p)    # Minggu


def test_kendaraan_tanpa_batas_jam():
    """Pemakaian kendaraan dinas di luar jam kerja justru WAJIB terpantau."""
    p = pu.profil_privasi("kendaraan")
    assert pu.dalam_jam_aktif(_wita(2026, 7, 26, 2), p)         # Minggu dini hari


def test_zona_waktu_dihormati():
    """Jam kerja dihitung LOKAL: 01:00 UTC = 09:00 WITA (masuk jam kerja).
    Menghitung dengan UTC mentah akan menolak observasi pagi yang sah."""
    p = pu.profil_privasi("personal")
    utc_pagi_wita = datetime(2026, 7, 27, 1, 0, tzinfo=timezone.utc)
    assert pu.dalam_jam_aktif(utc_pagi_wita, p, offset_jam=8)


# ── Gerbang saring_observasi ────────────────────────────────────────────────

def test_personal_koordinat_dibuang_hanya_wilayah_tersisa():
    """Inti kebijakan: perangkat perorangan menyimpan 'di gedung mana', BUKAN
    jejak titik yang bisa merekonstruksi pergerakan seseorang."""
    r = pu.saring_observasi(OBS, "personal", sekarang=_wita(2026, 7, 27, 10))
    assert r["simpan"] is True
    o = r["observasi"]
    assert "geo" not in o and "kecepatan_kmh" not in o and "akurasi_m" not in o
    assert o["lokasi_spasial"]["gedung_id"] == "sn_g1"    # wilayah tetap ada
    assert o["presisi_didegradasi"] is True


def test_personal_koordinat_di_dalam_lokasi_spasial_ikut_dibuang():
    """Pintu belakang: snapshot lokasi (Fase 8) MEMBAWA koordinat mentahnya di
    `lokasi_spasial.titik`. Membuang `geo` saja akan menyisakan presisi penuh
    di field yang justru sengaja dipertahankan."""
    obs = dict(OBS, lokasi_spasial={"node_id": "sn_g1", "node_nama": "Gedung A",
                                    "jalur_nama": "Kawasan / Gedung A",
                                    "titik": [116.71, -1.40]})
    r = pu.saring_observasi(obs, "personal", sekarang=_wita(2026, 7, 27, 10))
    lok = r["observasi"]["lokasi_spasial"]
    assert "titik" not in lok
    assert lok["node_id"] == "sn_g1" and lok["jalur_nama"]   # wilayah bertahan


def test_saring_tak_memutasi_lokasi_spasial_milik_pemanggil():
    """`hasil = dict(obs)` hanya salinan DANGKAL — membuang `titik` dengan pop
    akan merusak dokumen asli dan membuat pemanggil kehilangan koordinat yang
    masih dibutuhkannya (mis. untuk profil lain di batch yang sama)."""
    lok = {"node_id": "sn_g1", "titik": [116.71, -1.40]}
    obs = dict(OBS, lokasi_spasial=lok)
    pu.saring_observasi(obs, "personal", sekarang=_wita(2026, 7, 27, 10))
    assert lok["titik"] == [116.71, -1.40]


def test_kendaraan_mempertahankan_titik_di_lokasi_spasial():
    obs = dict(OBS, lokasi_spasial={"node_id": "sn_g1",
                                    "titik": [116.71, -1.40]})
    r = pu.saring_observasi(obs, "kendaraan", sekarang=_wita(2026, 7, 27, 10))
    assert r["observasi"]["lokasi_spasial"]["titik"] == [116.71, -1.40]


def test_personal_di_luar_jam_tidak_disimpan_sama_sekali():
    """Bukan 'disimpan lalu disembunyikan': data yang tak pernah ada tak bisa
    bocor, disalahgunakan, atau diminta lewat jalur hukum."""
    r = pu.saring_observasi(OBS, "personal", sekarang=_wita(2026, 7, 27, 23))
    assert r["simpan"] is False and r["observasi"] is None
    assert "jam aktif" in r["alasan"]


def test_kendaraan_presisi_penuh_dipertahankan():
    r = pu.saring_observasi(OBS, "kendaraan", sekarang=_wita(2026, 7, 27, 23))
    assert r["simpan"] is True
    assert r["observasi"]["geo"] == OBS["geo"]
    assert "presisi_didegradasi" not in r["observasi"]


def test_ts_device_string_iso_dipakai_bukan_waktu_server():
    """Perangkat yang mengirim batch tertunda harus dinilai pada waktu
    OBSERVASI-nya, bukan waktu tiba di server."""
    obs = dict(OBS, ts_device=_wita(2026, 7, 27, 23).isoformat())
    r = pu.saring_observasi(obs, "personal", sekarang=_wita(2026, 7, 28, 10))
    assert r["simpan"] is False          # 23:00 → tetap ditolak


def test_ts_rusak_jatuh_ke_sekarang_bukan_meledak():
    obs = dict(OBS, ts_device="bukan-tanggal")
    r = pu.saring_observasi(obs, "personal", sekarang=_wita(2026, 7, 27, 10))
    assert r["simpan"] is True


def test_darurat_membuka_presisi_dan_jam():
    r = pu.saring_observasi(OBS, "personal", sekarang=_wita(2026, 7, 27, 23),
                            darurat=True)
    assert r["simpan"] is True
    assert r["observasi"]["geo"] == OBS["geo"]
    assert r["observasi"]["akses_darurat"] is True


def test_observasi_asli_tak_dimutasi():
    """Pemanggil menyimpan HASIL fungsi; dokumen asli harus utuh agar tak ada
    jalur yang tanpa sengaja menyimpan versi belum tersaring."""
    salinan = dict(OBS)
    pu.saring_observasi(OBS, "personal", sekarang=_wita(2026, 7, 27, 10))
    assert OBS == salinan


# ── Izin darurat ────────────────────────────────────────────────────────────

def _izin(**ubah):
    dasar = {"alasan": "Laptop dilaporkan hilang di Blok A3",
             "diminta_oleh": "operator1", "disetujui_oleh": "kpb",
             "berlaku_sampai": (datetime.now(timezone.utc)
                                + timedelta(hours=24)).isoformat()}
    dasar.update(ubah)
    return dasar


def test_izin_darurat_lengkap_sah():
    assert pu.izin_darurat_sah(_izin()) is None


def test_izin_wajib_beralasan_bermakna():
    assert "Alasan" in pu.izin_darurat_sah(_izin(alasan="x"))
    assert "Alasan" in pu.izin_darurat_sah(_izin(alasan=""))


def test_izin_wajib_pejabat_dan_bukan_diri_sendiri():
    assert "Pejabat" in pu.izin_darurat_sah(_izin(disetujui_oleh=""))
    galat = pu.izin_darurat_sah(_izin(disetujui_oleh="operator1"))
    assert "orang yang sama" in galat


def test_izin_permanen_ditolak():
    """Izin tanpa batas = kebijakan yang dibatalkan diam-diam."""
    jauh = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    assert "maksimal" in pu.izin_darurat_sah(_izin(berlaku_sampai=jauh))
    assert "wajib" in pu.izin_darurat_sah(_izin(berlaku_sampai="")).lower()


def test_izin_kedaluwarsa_ditolak():
    lalu = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert "kedaluwarsa" in pu.izin_darurat_sah(_izin(berlaku_sampai=lalu))


# ── Retensi ─────────────────────────────────────────────────────────────────

def test_batas_retensi_per_profil():
    kini = datetime(2026, 7, 27, tzinfo=timezone.utc)
    assert pu.batas_retensi("personal", kini) == kini - timedelta(days=30)
    assert pu.batas_retensi("kendaraan", kini) == kini - timedelta(days=90)
    # profil ngawur → retensi TERPENDEK (gagal-tertutup)
    assert pu.batas_retensi("ngawur", kini) == kini - timedelta(days=30)


def test_ringkas_kebijakan_bisa_ditampilkan():
    r = pu.ringkas_kebijakan()
    assert {x["profil"] for x in r} == set(pu.PROFIL_PRIVASI)
    personal = next(x for x in r if x["profil"] == "personal")
    assert personal["jam_aktif"] == "07:00–18:00"
    assert personal["presisi"] == "wilayah"
