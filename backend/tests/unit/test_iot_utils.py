"""Uji helper ingest posisi IoT (Fase 11).

Fokus uji BUKAN "fungsi mengembalikan nilai", melainkan dua sifat yang membuat
ingest IoT berbeda dari CRUD biasa: pengiriman ULANG adalah normal (idempotensi
wajib), dan jam perangkat tak bisa dipercaya.
"""
from datetime import datetime, timedelta, timezone

import iot_utils as iu

KINI = datetime(2026, 7, 27, 3, 0, tzinfo=timezone.utc)   # 11:00 WITA, Senin


def _obs(**ubah):
    dasar = {"lat": -1.40, "lon": 116.71, "ts_device": KINI.isoformat(),
             "akurasi_m": 6.5, "kecepatan_kmh": 32.4, "arah_deg": 187,
             "baterai_persen": 84}
    dasar.update(ubah)
    return dasar


# ── Idempotensi: inti pertahanan at-least-once ──────────────────────────────

def test_obs_id_stabil_untuk_isi_yang_sama():
    """Pengiriman ULANG observasi yang sama HARUS menghasilkan id yang sama —
    itulah yang membuat indeks unik bisa menolaknya."""
    a = iu.obs_id("dev1", KINI.isoformat(), 116.71, -1.40)
    b = iu.obs_id("dev1", KINI.isoformat(), 116.71, -1.40)
    assert a == b and a.startswith("sha1:")


def test_obs_id_berbeda_bila_salah_satu_bahan_berbeda():
    dasar = iu.obs_id("dev1", KINI.isoformat(), 116.71, -1.40)
    assert iu.obs_id("dev2", KINI.isoformat(), 116.71, -1.40) != dasar
    assert iu.obs_id("dev1", KINI.isoformat(), 116.72, -1.40) != dasar
    lain = (KINI + timedelta(seconds=1)).isoformat()
    assert iu.obs_id("dev1", lain, 116.71, -1.40) != dasar


def test_obs_id_tak_memakai_waktu_server():
    """Kalau waktu TERIMA ikut di-hash, tiap pengiriman ulang tampak sebagai
    observasi baru dan idempotensi runtuh diam-diam. Dua normalisasi pada waktu
    server berbeda harus tetap menghasilkan obs_id identik."""
    o = _obs()
    a = iu.normalisasi_observasi(o, "dev1", KINI)
    b = iu.normalisasi_observasi(o, "dev1", KINI + timedelta(minutes=17))
    assert a["obs_id"] == b["obs_id"]
    assert a["ts_server"] != b["ts_server"]      # waktu terima memang berbeda


# ── Koordinat ───────────────────────────────────────────────────────────────

def test_koordinat_tak_sah_menggugurkan_observasi():
    for buruk in ({"lat": None}, {"lon": "abc"}, {"lat": 95.0}, {"lon": 400.0}):
        assert "tolak" in iu.normalisasi_observasi(_obs(**buruk), "dev1", KINI)


def test_null_island_ditolak():
    """(0,0) di Teluk Guinea adalah penanda de-facto parsing gagal, bukan posisi
    aset BMN di IKN."""
    r = iu.normalisasi_observasi(_obs(lat=0, lon=0), "dev1", KINI)
    assert "tolak" in r and "(0,0)" in r["tolak"]


def test_geo_disimpan_lon_dulu_sesuai_rfc7946():
    """Membalik urutan tidak memicu galat apa pun — hanya memindahkan IKN ke
    Samudra Hindia. Karena itu urutannya diuji eksplisit."""
    d = iu.normalisasi_observasi(_obs(), "dev1", KINI)
    assert d["geo"] == {"type": "Point", "coordinates": [116.71, -1.40]}


def test_koordinat_koma_desimal_diterima():
    """Perangkat/berkas berlokal Indonesia mengirim '116,71'. parse_bujur
    menanganinya; float() mentah akan meledak."""
    d = iu.normalisasi_observasi(_obs(lat="-1,40", lon="116,71"), "dev1", KINI)
    assert d["geo"]["coordinates"] == [116.71, -1.40]


# ── Jam perangkat yang tak bisa dipercaya ───────────────────────────────────

def test_jam_melenceng_jauh_ditandai_ragu_bukan_ditolak():
    """GPS murah kerap menyala dengan jam salah. Observasinya tetap berguna,
    tapi tak boleh dipakai sebagai satu-satunya sumber urutan."""
    geser = (KINI - timedelta(hours=30)).isoformat()
    d = iu.normalisasi_observasi(_obs(ts_device=geser), "dev1", KINI)
    assert d["ts_ragu"] is True and "tolak" not in d


def test_jam_wajar_tidak_ditandai_ragu():
    d = iu.normalisasi_observasi(_obs(), "dev1", KINI)
    assert d["ts_ragu"] is False


def test_ts_dari_masa_depan_dijangkar_ke_waktu_server():
    depan = (KINI + timedelta(days=3)).isoformat()
    d = iu.normalisasi_observasi(_obs(ts_device=depan), "dev1", KINI)
    assert d["ts_device"] == KINI.isoformat() and d["ts_ragu"] is True


def test_ts_rusak_jatuh_ke_waktu_server_dan_ditandai():
    d = iu.normalisasi_observasi(_obs(ts_device="bukan-tanggal"), "dev1", KINI)
    assert d["ts_device"] == KINI.isoformat() and d["ts_ragu"] is True


def test_ts_tanpa_zona_dianggap_utc_bukan_meledak():
    polos = KINI.replace(tzinfo=None).isoformat()
    d = iu.normalisasi_observasi(_obs(ts_device=polos), "dev1", KINI)
    assert d["ts_ragu"] is False


def test_observasi_terlalu_basi_ditolak():
    """Antrean offline BERTAHUN dari perangkat terlantar tak boleh membanjiri
    koleksi saat perangkat itu akhirnya menyala."""
    tua = (KINI - timedelta(days=iu.MAKS_UMUR_HARI + 1)).isoformat()
    r = iu.normalisasi_observasi(_obs(ts_device=tua), "dev1", KINI)
    assert "tolak" in r and "hari" in r["tolak"]


# ── Buang PER FIELD, bukan gugurkan seluruh observasi ───────────────────────

def test_kecepatan_mustahil_dibuang_koordinat_tetap_dipakai():
    d = iu.normalisasi_observasi(_obs(kecepatan_kmh=9000), "dev1", KINI)
    assert "kecepatan_kmh" not in d          # dibuang
    assert d["geo"]["coordinates"] == [116.71, -1.40]   # observasi tetap sah


def test_field_turunan_di_luar_rentang_dibuang():
    d = iu.normalisasi_observasi(
        _obs(akurasi_m=-5, arah_deg=999, baterai_persen=250), "dev1", KINI)
    for k in ("akurasi_m", "arah_deg", "baterai_persen"):
        assert k not in d


def test_field_turunan_wajar_dipertahankan():
    d = iu.normalisasi_observasi(_obs(), "dev1", KINI)
    assert d["akurasi_m"] == 6.5 and d["kecepatan_kmh"] == 32.4
    assert d["arah_deg"] == 187.0 and d["baterai_persen"] == 84


def test_field_turunan_tak_terkirim_tidak_mengarang_nilai():
    d = iu.normalisasi_observasi({"lat": -1.4, "lon": 116.7}, "dev1", KINI)
    for k in ("akurasi_m", "kecepatan_kmh", "arah_deg", "baterai_persen"):
        assert k not in d


# ── Batch ───────────────────────────────────────────────────────────────────

def test_batch_memisahkan_diterima_dan_ditolak_dengan_alasan():
    hasil = iu.siapkan_batch([_obs(), _obs(lat=0, lon=0), "bukan objek"],
                             "dev1", KINI)
    assert len(hasil["terima"]) == 1
    assert [t["i"] for t in hasil["tolak"]] == [1, 2]
    assert all(t["alasan"] for t in hasil["tolak"])   # tak ada tolakan senyap


def test_duplikat_dalam_satu_batch_disaring_lebih_murah():
    """Perangkat yang mengirim ulang antreannya tanpa membersihkan sering
    memuat kembar DI DALAM satu batch — dicegat sebelum menabrak indeks."""
    hasil = iu.siapkan_batch([_obs(), _obs(), _obs()], "dev1", KINI)
    assert len(hasil["terima"]) == 1
    assert all("duplikat" in t["alasan"] for t in hasil["tolak"])


def test_titik_berbeda_bukan_duplikat():
    hasil = iu.siapkan_batch([_obs(), _obs(lon=116.72)], "dev1", KINI)
    assert len(hasil["terima"]) == 2


def test_plafon_batch_dipotong_dan_DILAPORKAN():
    """Pemotongan senyap akan membuat perangkat mengira semua terkirim."""
    hasil = iu.siapkan_batch(
        [_obs(lon=116.0 + i / 10000.0)
         for i in range(iu.MAKS_OBSERVASI_PER_BATCH + 25)], "dev1", KINI)
    assert hasil["plafon"] is True
    assert len(hasil["terima"]) == iu.MAKS_OBSERVASI_PER_BATCH


def test_batch_bukan_daftar_tidak_meledak():
    hasil = iu.siapkan_batch({"lat": 1}, "dev1", KINI)
    assert hasil["terima"] == [] and hasil["tolak"]


def test_batch_kosong_bukan_galat():
    assert iu.siapkan_batch([], "dev1", KINI) == {
        "terima": [], "tolak": [], "plafon": False}


# ── Ringkasan kesehatan ─────────────────────────────────────────────────────

def test_kesehatan_menghitung_lama_diam():
    doc = {"ts_server": (KINI - timedelta(minutes=45)).isoformat(),
           "baterai_persen": 71, "ts_ragu": False}
    r = iu.ringkas_kesehatan(doc, KINI)
    assert r["diam_menit"] == 45 and r["baterai_persen"] == 71


def test_kesehatan_perangkat_belum_pernah_mengirim():
    """Perangkat baru terdaftar TIDAK boleh membuat daftar perangkat meledak."""
    r = iu.ringkas_kesehatan(None, KINI)
    assert r["diam_menit"] is None and r["terakhir_terdengar"] == ""
    # Satuan DETIK ikut kosong — layar memakainya sebagai jam hidup, dan 0
    # detik berarti "baru saja terdengar", kebalikan dari kenyataannya.
    assert r["diam_detik"] is None


def test_kesehatan_dalam_DETIK_bukan_menit():
    """Jam hidup di layar Pelacakan berdenyut per detik.

    Uji ini sengaja memakai jarak yang HABIS DIBAGI menit (45 menit) supaya
    satu-satunya pembeda antara satuan yang benar dan yang salah adalah
    ANGKANYA: 2700 versus 45. Mutasi apa pun yang mengembalikan menit dari
    field berlabel detik akan gagal di sini, bukan lolos karena kebetulan.
    """
    doc = {"ts_server": (KINI - timedelta(minutes=45)).isoformat()}
    r = iu.ringkas_kesehatan(doc, KINI)
    assert r["diam_detik"] == 2700
    assert r["diam_menit"] == 45


def test_kesehatan_dibawah_semenit_masih_terbaca():
    """Justru inilah kasus yang membuat field ini ada: di bawah satu menit,
    `diam_menit` mendatar di 0 dan operator tak bisa membedakan perangkat yang
    hidup dari perangkat yang layarnya membeku."""
    doc = {"ts_server": (KINI - timedelta(seconds=12)).isoformat()}
    r = iu.ringkas_kesehatan(doc, KINI)
    assert r["diam_detik"] == 12 and r["diam_menit"] == 0


def test_kesehatan_tak_pernah_negatif():
    """Cap waktu yang MENDAHULUI `sekarang` (mis. terbaca dari replika yang
    tertinggal) harus mendarat di 0, bukan menjadi "-30 dtk lalu"."""
    doc = {"ts_server": (KINI + timedelta(seconds=30)).isoformat()}
    r = iu.ringkas_kesehatan(doc, KINI)
    assert r["diam_detik"] == 0 and r["diam_menit"] == 0
