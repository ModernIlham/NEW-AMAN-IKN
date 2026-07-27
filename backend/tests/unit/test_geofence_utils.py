"""Uji mesin status geofence (Fase 12).

Yang diuji di sini bukan "apakah titik di dalam poligon" — itu sudah diuji di
test_spasial_utils. Yang diuji adalah SATU-SATUNYA hal yang membuat geofence
berguna atau tak berguna: apakah ia diam saat perangkat diam di garis batas.
Uji point-in-polygon polos akan LULUS sementara sistemnya membanjiri operator
dengan peringatan palsu.
"""
from datetime import datetime, timedelta, timezone

import geofence_utils as gf

T0 = datetime(2026, 7, 27, 3, 0, tzinfo=timezone.utc)

# Kotak ±0.001° ≈ 111 m sisi, di sekitar IKN.
KOTAK = {"type": "Polygon", "coordinates": [[
    [116.700, -1.401], [116.702, -1.401], [116.702, -1.399],
    [116.700, -1.399], [116.700, -1.401]]]}
TENGAH = (116.701, -1.400)


def _obs(lon, lat, detik=0, **ubah):
    o = {"geo": {"type": "Point", "coordinates": [lon, lat]},
         "ts_device": (T0 + timedelta(seconds=detik)).isoformat(),
         "akurasi_m": 8.0}
    o.update(ubah)
    return o


def _jalankan(titik_waktu, geom=KOTAK, state=None, param=None):
    """Putar deret observasi; kembalikan (state akhir, daftar event)."""
    st = state or gf.status_awal("dev1", "area1")
    events = []
    for lon, lat, dt in titik_waktu:
        r = gf.evaluasi(st, _obs(lon, lat, dt), geom,
                        T0 + timedelta(seconds=dt), param)
        st = r["state"]
        if r["event"]:
            events.append(r["event"])
    return st, events


# ── Jarak ke poligon: fondasi histeresis ────────────────────────────────────

def test_jarak_nol_di_dalam():
    assert gf.jarak_ke_poligon_m(*TENGAH, KOTAK) == 0.0


def test_jarak_di_luar_masuk_akal_dalam_meter():
    """0.0005° bujur di khatulistiwa ≈ 55 m. Angka ini yang dipakai histeresis,
    jadi salah skala = buffer 25 m jadi 25 derajat tanpa gejala apa pun."""
    d = gf.jarak_ke_poligon_m(116.7025, -1.400, KOTAK)   # 0.0005° dari tepi
    assert 45 < d < 65


def test_jarak_di_sudut_bukan_ke_garis_tak_hingga():
    """Titik diagonal dari sudut harus berjarak ke SUDUT, bukan ke perpanjangan
    sisi — inilah beda jarak-ke-ruas vs jarak-ke-garis."""
    d = gf.jarak_ke_poligon_m(116.7030, -1.4020, KOTAK)
    lurus = gf.jarak_ke_poligon_m(116.7030, -1.400, KOTAK)
    assert d > lurus


def test_jarak_geometri_bukan_poligon_tak_hingga():
    import math
    assert gf.jarak_ke_poligon_m(1, 1, {"type": "Point", "coordinates": [1, 1]}) == math.inf
    assert gf.jarak_ke_poligon_m(1, 1, None) == math.inf


def test_lubang_dianggap_di_luar():
    donat = {"type": "Polygon", "coordinates": [
        [[116.700, -1.402], [116.704, -1.402], [116.704, -1.398],
         [116.700, -1.398], [116.700, -1.402]],
        [[116.701, -1.401], [116.703, -1.401], [116.703, -1.399],
         [116.701, -1.399], [116.701, -1.401]]]}
    assert gf.jarak_ke_poligon_m(116.702, -1.400, donat) > 0     # di lubang


# ── ANTI-FLAPPING: alasan modul ini ada ─────────────────────────────────────

def test_diam_di_garis_batas_tidak_menghasilkan_event_sama_sekali():
    """Perangkat DIAM persis di tepi, GPS-nya bergoyang ±10 m masuk-keluar
    selama sejam. Sistem harus DIAM TOTAL. Uji point-in-polygon polos akan
    menerbitkan belasan peringatan di sini."""
    urut = []
    for i in range(60):
        # ganti-ganti sedikit di dalam / sedikit di luar (≈8 m), tiap menit
        lon = 116.70195 if i % 2 else 116.70205
        urut.append((lon, -1.400, i * 60))
    st, events = _jalankan(urut)
    assert events == []


def test_keluar_sungguhan_tetap_terdeteksi():
    """Histeresis tak boleh membuat sistemnya tuli: pergi 200 m dan menetap
    harus tetap menghasilkan satu event keluar."""
    urut = [(116.701, -1.400, 0), (116.701, -1.400, 120), (116.701, -1.400, 240),
            (116.701, -1.400, 360)]                         # mapan DI DALAM
    urut += [(116.7050, -1.400, 400 + i * 60) for i in range(8)]   # pergi jauh
    st, events = _jalankan(urut)
    assert [e["jenis"] for e in events] == ["masuk", "keluar"]
    assert st["status"] == gf.LUAR


def test_masuk_butuh_dwell_dan_sampel():
    """Satu sampel di dalam TIDAK cukup — kendaraan yang cuma lewat depan
    gerbang bukan kendaraan yang masuk."""
    st, events = _jalankan([(116.701, -1.400, 0)])
    assert events == [] and st["status"] == gf.KANDIDAT_MASUK
    # cukup sampel tapi belum cukup waktu
    st, events = _jalankan([(116.701, -1.400, t) for t in (0, 1, 2)])
    assert events == [] and st["status"] == gf.KANDIDAT_MASUK


def test_lewat_sekilas_lalu_pergi_tidak_memicu_masuk():
    st, events = _jalankan([(116.701, -1.400, 0), (116.7060, -1.400, 30)])
    assert events == [] and st["status"] == gf.LUAR


def test_keluar_sebentar_dalam_buffer_tidak_membatalkan_status_dalam():
    """10 m di luar garis masih DALAM — inti histeresis."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120, 180)]
    urut.append((116.70209, -1.400, 240))          # ±10 m di luar, < buffer 25
    st, events = _jalankan(urut)
    assert [e["jenis"] for e in events] == ["masuk"]
    assert st["status"] == gf.DALAM


def test_kandidat_keluar_dibatalkan_saat_kembali():
    urut = [(116.701, -1.400, t) for t in (0, 60, 120, 180)]
    urut += [(116.7025, -1.400, 240), (116.7025, -1.400, 300)]   # jauh di luar
    urut += [(116.701, -1.400, 360)]                             # kembali
    st, events = _jalankan(urut)
    assert [e["jenis"] for e in events] == ["masuk"]
    assert st["status"] == gf.DALAM and st["sampel"] == 0


# ── Gerbang kualitas ────────────────────────────────────────────────────────

def test_akurasi_buruk_tidak_menggerakkan_status():
    """Fix 500 m di dekat batas tak memberi tahu apa pun tentang sisi mana
    titik berada; peringatan dari data begitu adalah tebakan berbaju fakta."""
    st = gf.status_awal("dev1", "area1")
    r = gf.evaluasi(st, _obs(*TENGAH, akurasi_m=500), KOTAK, T0)
    assert r["event"] is None and r["state"]["status"] == gf.LUAR
    assert "akurasi" in r["abai"]


def test_outlier_teleport_diabaikan():
    st = gf.status_awal("dev1", "area1")
    r = gf.evaluasi(st, _obs(*TENGAH, outlier=True), KOTAK, T0)
    assert "outlier" in r["abai"] and r["event"] is None


def test_observasi_tanpa_koordinat_diabaikan_bukan_meledak():
    """Profil privasi 'wilayah' MEMBUANG koordinat — perangkat perorangan
    memang tak pernah dipagar-geo, dan itu disengaja."""
    st = gf.status_awal("dev1", "area1")
    r = gf.evaluasi(st, {"ts_device": T0.isoformat()}, KOTAK, T0)
    assert r["event"] is None and "koordinat" in r["abai"]


def test_akurasi_tepat_di_ambang_masih_dipakai():
    st = gf.status_awal("dev1", "area1")
    r = gf.evaluasi(st, _obs(*TENGAH, akurasi_m=100), KOTAK, T0)
    assert r["abai"] == "" and r["state"]["status"] == gf.KANDIDAT_MASUK


def test_akurasi_tak_dilaporkan_tidak_menggugurkan():
    """Perangkat murah kerap tak melaporkan akurasi. Menganggapnya buruk akan
    mematikan geofence untuk seluruh armada itu."""
    o = _obs(*TENGAH)
    o.pop("akurasi_m")
    assert gf.layak_geofence(o) == ""


# ── Cooldown ────────────────────────────────────────────────────────────────

def test_cooldown_meredam_event_sejenis_beruntun():
    """Aset yang bolak-balik gerbang: masuk t=120, keluar t=360, masuk lagi
    t=540. Jarak antar `masuk` = 420 dtk < cooldown 600 → yang kedua diredam.
    Yang TIDAK boleh ikut teredam adalah STATUS-nya."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120)]              # masuk@120
    urut += [(116.7050, -1.400, t) for t in (180, 240, 300, 360)]    # keluar@360
    urut += [(116.701, -1.400, t) for t in (420, 480, 540)]          # masuk@540
    st, events = _jalankan(urut)
    jenis = [e["jenis"] for e in events]
    assert jenis == ["masuk", "keluar"]     # masuk kedua teredam cooldown
    assert st["status"] == gf.DALAM         # status TETAP benar meski teredam


def test_cooldown_lewat_maka_event_sejenis_terbit_lagi():
    """Peredam tak boleh jadi bisu permanen."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120)]
    urut += [(116.7050, -1.400, t) for t in (180, 240, 300, 360)]
    urut += [(116.701, -1.400, t) for t in (800, 860, 920)]   # 920-120 > 600
    _, events = _jalankan(urut)
    assert [e["jenis"] for e in events] == ["masuk", "keluar", "masuk"]


def test_cooldown_tidak_meredam_jenis_berbeda():
    st = gf.status_awal("d", "a")
    st.update({"redam": {"masuk": T0.isoformat()},
               "transisi": {"masuk": T0.isoformat()}, "status": gf.DALAM})
    urut = [(116.7050, -1.400, 60 + i * 60) for i in range(6)]
    st2, events = _jalankan(urut, state=st)
    assert [e["jenis"] for e in events] == ["keluar"]


# ── Backfill / retro ────────────────────────────────────────────────────────

def test_event_dari_antrean_offline_ditandai_retro():
    """Peristiwa kemarin sore tak boleh membunyikan alarm 'SEKARANG'."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120, 180)]
    st = gf.status_awal("dev1", "area1")
    ev = None
    for lon, lat, dt in urut:
        r = gf.evaluasi(st, _obs(lon, lat, dt), KOTAK,
                        T0 + timedelta(hours=6))     # tiba 6 jam kemudian
        st = r["state"]
        ev = r["event"] or ev
    assert ev and ev["retro"] is True


def test_event_segar_tidak_retro():
    _, events = _jalankan([(116.701, -1.400, t) for t in (0, 60, 120, 180)])
    assert events and events[0]["retro"] is False


# ── Kekekalan & ketahanan ───────────────────────────────────────────────────

def test_state_masukan_tidak_dimutasi():
    """Pemanggil yang gagal menyimpan tak boleh meninggalkan status setengah
    berubah di memori."""
    st = gf.status_awal("dev1", "area1")
    salinan = dict(st)
    gf.evaluasi(st, _obs(*TENGAH), KOTAK, T0)
    assert st == salinan


def test_status_rusak_jatuh_ke_luar_bukan_meledak():
    st = {"status": "ngawur-entah-apa", "sampel": 3}
    r = gf.evaluasi(st, _obs(*TENGAH), KOTAK, T0)
    assert r["state"]["status"] == gf.LUAR


def test_state_kosong_diterima():
    r = gf.evaluasi(None, _obs(*TENGAH), KOTAK, T0)
    assert r["state"]["status"] == gf.KANDIDAT_MASUK


def test_ts_device_rusak_jatuh_ke_waktu_server():
    st = gf.status_awal("d", "a")
    r = gf.evaluasi(st, _obs(*TENGAH, ts_device="bukan-tanggal"), KOTAK, T0)
    assert r["abai"] == "" and r["state"]["status"] == gf.KANDIDAT_MASUK


# ── Deteksi lompatan mustahil ───────────────────────────────────────────────

def test_teleport_terdeteksi():
    a = _obs(116.701, -1.400, 0)
    b = _obs(117.200, -1.400, 60)          # ±55 km dalam 1 menit
    assert gf.lompatan_mustahil(a, b) is True


def test_perjalanan_wajar_bukan_teleport():
    a = _obs(116.701, -1.400, 0)
    b = _obs(116.706, -1.400, 60)          # ±550 m/menit ≈ 33 km/jam
    assert gf.lompatan_mustahil(a, b) is False


def test_dua_observasi_detik_sama_tidak_dinilai_teleport():
    """Δt≈0 membuat kecepatan meledak jadi tak hingga; menyebutnya outlier akan
    membuang data sah dari perangkat bersampel rapat."""
    a = _obs(116.701, -1.400, 0)
    b = _obs(116.706, -1.400, 0)
    assert gf.lompatan_mustahil(a, b) is False


def test_teleport_butuh_dua_titik_sah():
    assert gf.lompatan_mustahil({}, _obs(*TENGAH)) is False
    assert gf.lompatan_mustahil(None, None) is False


# ── Parameter per aturan ────────────────────────────────────────────────────

def test_param_bawaan_dipakai_bila_aturan_kosong():
    assert gf.ringkas_aturan({}) == gf.GEO_PARAM
    assert gf.ringkas_aturan(None)["buffer_keluar_m"] == 25


def test_timpaan_sah_dipakai():
    p = gf.ringkas_aturan({"param": {"buffer_keluar_m": 50, "sampel_min": 5}})
    assert p["buffer_keluar_m"] == 50 and p["sampel_min"] == 5


def test_timpaan_ngawur_diabaikan_bukan_mematikan_aturan():
    """Geofence yang MATI karena satu salah ketik lebih berbahaya daripada
    geofence yang jalan dengan angka bawaan."""
    p = gf.ringkas_aturan({"param": {"buffer_keluar_m": -5, "sampel_min": "abc",
                                     "kunci_asing": 1}})
    assert p["buffer_keluar_m"] == 25 and p["sampel_min"] == 3
    assert "kunci_asing" not in p


def test_param_kustom_benar_benar_mengubah_perilaku():
    """Timpaan yang tak berefek = setelan bohong. Dengan buffer 200 m, pergi
    100 m tak boleh dianggap keluar."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120, 180)]
    urut += [(116.7030, -1.400, 240 + i * 60) for i in range(6)]
    _, ketat = _jalankan(urut)
    _, longgar = _jalankan(urut, param={"buffer_keluar_m": 200})
    assert "keluar" in [e["jenis"] for e in ketat]
    assert "keluar" not in [e["jenis"] for e in longgar]


# ── Dwell di luar (aset tak kunjung kembali) ────────────────────────────────

def test_dwell_terlampaui_saat_terlalu_lama_di_luar():
    """Aset yang MATI TOTAL setelah keluar area justru yang paling perlu
    diketahui — dan aset seperti itu tak akan mengirim observasi lagi, jadi
    pemicunya harus dari STATUS, bukan dari observasi baru."""
    st = {"status": gf.LUAR, "transisi": {"keluar": T0.isoformat()}}
    assert gf.jatuh_tempo_dwell(st, {"maks_di_luar_jam": 4},
                                T0 + timedelta(hours=5)) is not None
    assert gf.jatuh_tempo_dwell(st, {"maks_di_luar_jam": 4},
                                T0 + timedelta(hours=3)) is None


def test_dwell_tidak_berlaku_saat_masih_di_dalam():
    st = {"status": gf.DALAM, "transisi": {"masuk": T0.isoformat()}}
    assert gf.jatuh_tempo_dwell(st, {"maks_di_luar_jam": 1},
                                T0 + timedelta(hours=9)) is None


def test_dwell_tanpa_aturan_batas_tidak_pernah_jatuh_tempo():
    st = {"status": gf.LUAR, "transisi": {"keluar": T0.isoformat()}}
    assert gf.jatuh_tempo_dwell(st, {}, T0 + timedelta(days=30)) is None


# ═══════════════════════════════════════════════════════════════════════════
# TEMUAN TINJAUAN ADVERSARIAL — tiap uji di bawah ini mengunci satu cacat yang
# LOLOS uji gelombang pertama. Semuanya gagal pada kode sebelum perbaikan.
# ═══════════════════════════════════════════════════════════════════════════

# ── Pagar monoton: batch backfill tak boleh memundurkan mesin ───────────────

def test_observasi_lebih_tua_dari_yang_diproses_diabaikan():
    """Batch backfill bisa tiba SETELAH batch yang lebih baru. Tanpa pagar ini
    `sejak` mundur ke masa lalu, lalu observasi berikutnya menghitung selisih
    raksasa dan mematangkan dwell SEKETIKA."""
    st, _ = _jalankan([(116.701, -1.400, t) for t in (0, 60, 120)])
    assert st["status"] == gf.DALAM
    r = gf.evaluasi(st, _obs(116.7050, -1.400, -600), KOTAK,
                    T0 + timedelta(seconds=200))
    assert r["event"] is None and "lebih tua" in r["abai"]
    assert r["state"]["status"] == gf.DALAM      # tak tergoyahkan


def test_backfill_tidak_melahirkan_keluar_palsu():
    """Skenario penuh: aset mapan DI DALAM, lalu antrean offline berisi titik
    lama di luar area tiba belakangan. Sistem harus DIAM."""
    st, _ = _jalankan([(116.701, -1.400, t) for t in (0, 60, 120)])
    events = []
    for dt in (-900, -840, -780, -720):          # jauh di luar, TAPI masa lalu
        r = gf.evaluasi(st, _obs(116.7050, -1.400, dt), KOTAK,
                        T0 + timedelta(seconds=300))
        st = r["state"]
        if r["event"]:
            events.append(r["event"])
    assert events == [] and st["status"] == gf.DALAM


def test_observasi_ber_ts_sama_persis_diabaikan():
    """Duplikat ber-ts identik tak boleh menaikkan hitungan sampel dua kali."""
    st = gf.status_awal("d", "a")
    r1 = gf.evaluasi(st, _obs(*TENGAH, 0), KOTAK, T0)
    r2 = gf.evaluasi(r1["state"], _obs(*TENGAH, 0), KOTAK, T0)
    assert r2["state"]["sampel"] == 1 and "lebih tua" in r2["abai"]


# ── Cooldown: selisih bertanda ─────────────────────────────────────────────

def test_cooldown_tidak_meredam_karena_selisih_negatif():
    """Selisih BERTANDA membuat ts mundur menghasilkan angka negatif — selalu
    lebih kecil dari cooldown — sehingga peringatan NYATA teredam tanpa jejak."""
    p = dict(gf.GEO_PARAM)
    # Peringatan tercatat 5 jam DI DEPAN ts observasi (jam perangkat kacau).
    # Selisih bertanda = -18000 dtk, yang selalu < 600 → SEBELUM perbaikan ini
    # dianggap "masih cooldown" dan peringatan nyata ditelan diam-diam.
    st = {"redam": {"keluar": (T0 + timedelta(hours=5)).isoformat()}}
    assert gf._dalam_cooldown(st, "keluar", T0, p) is False
    # Jarak yang benar-benar dekat (30 dtk, arah mana pun) tetap diredam.
    dekat = {"redam": {"keluar": (T0 + timedelta(seconds=30)).isoformat()}}
    assert gf._dalam_cooldown(dekat, "keluar", T0, p) is True


# ── Invarian histeresis ────────────────────────────────────────────────────

def test_buffer_masuk_dijepit_agar_tak_melebihi_buffer_keluar():
    """Bila terbalik, ada pita jarak yang sekaligus 'di dalam' dan 'jauh di
    luar' — perangkat DIAM di pita itu berayun selamanya."""
    p = gf.ringkas_aturan({"param": {"buffer_masuk_m": 90,
                                     "buffer_keluar_m": 25}})
    assert p["buffer_masuk_m"] == 25


def test_buffer_terbalik_tidak_melahirkan_badai_peringatan():
    """Bukti perilaku, bukan sekadar angka: perangkat DIAM 50 m di luar batas
    dengan param terbalik harus tetap menghasilkan nol peringatan."""
    urut = [(116.7025, -1.400, i * 60) for i in range(40)]
    _, events = _jalankan(urut, param={"buffer_masuk_m": 90,
                                       "buffer_keluar_m": 25})
    assert events == []


# ── inf tak boleh masuk state (JSON tak mengenal Infinity) ─────────────────

def test_jarak_tak_terukur_tidak_menaruh_inf_di_state():
    """`inf` di state akan meledakkan SELURUH daftar aturan saat diserialisasi,
    jauh dari tempat kejadiannya."""
    garis = {"type": "LineString", "coordinates": [[116.70, -1.40], [116.71, -1.40]]}
    r = gf.evaluasi(gf.status_awal("d", "a"), _obs(*TENGAH), garis, T0)
    import json
    assert r["state"]["jarak_m"] is None
    json.dumps(r["state"])           # tak boleh melempar


# ── Pengurutan lintas zona waktu ───────────────────────────────────────────

def test_kunci_urut_memakai_instan_bukan_teks():
    """'10:00+07:00' dan '03:00Z' adalah instan yang SAMA tetapi berjauhan
    sebagai string; perangkat beda merek memang menulis offset berbeda."""
    a = "2026-07-27T10:00:00+07:00"
    b = "2026-07-27T03:00:00+00:00"
    assert gf.kunci_urut(a) == gf.kunci_urut(b)
    assert a > b                      # sebagai TEKS urutannya justru terbalik


def test_kunci_urut_menaruh_ts_rusak_di_awal_secara_deterministik():
    urut = sorted(["bukan-tanggal", "2026-07-27T03:00:00Z",
                   "2026-07-27T01:00:00Z"], key=gf.kunci_urut)
    assert urut[0] == "bukan-tanggal"


# ── Celah uji yang ditemukan tinjauan (perilaku sudah benar, kuncinya hilang)

def test_dwell_keluar_benar_benar_ditegakkan():
    """dwell_keluar_dtk sebelumnya tak teruji: nilainya boleh 0 dan 36 uji tetap
    hijau. Di sini 4 sampel jauh di luar dalam 90 dtk (< 180) TIDAK boleh
    menghasilkan keluar; menambah waktu barulah menghasilkannya."""
    mapan = [(116.701, -1.400, t) for t in (0, 60, 120)]
    cepat = mapan + [(116.7050, -1.400, t) for t in (150, 180, 210)]
    _, e1 = _jalankan(cepat)
    assert [x["jenis"] for x in e1] == ["masuk"]          # 60 dtk < 180
    lambat = mapan + [(116.7050, -1.400, t) for t in (150, 240, 330)]
    _, e2 = _jalankan(lambat)
    assert [x["jenis"] for x in e2] == ["masuk", "keluar"]  # 180 dtk ≥ 180


def test_sampel_min_benar_benar_ditegakkan():
    """Waktu SUDAH cukup tetapi sampel kurang → belum boleh matang."""
    _, events = _jalankan([(116.701, -1.400, 0), (116.701, -1.400, 300)])
    assert events == []                     # 2 sampel < 3, walau 300 dtk


def test_jam_di_luar_tetap_berjalan_meski_peringatan_teredam():
    """Regresi yang diperbaiki: keluar yang peringatannya teredam TETAP keluar,
    dan `dwell_terlampaui` harus tetap bisa jatuh tempo."""
    st = gf.status_awal("d", "a")
    st.update({"status": gf.DALAM,
               "redam": {"keluar": (T0 - timedelta(seconds=60)).isoformat()},
               "transisi": {"keluar": (T0 - timedelta(seconds=60)).isoformat()}})
    events = []
    for dt in (60, 240, 420, 600):
        r = gf.evaluasi(st, _obs(116.7050, -1.400, dt), KOTAK,
                        T0 + timedelta(seconds=dt))
        st = r["state"]
        if r["event"]:
            events.append(r["event"])
    assert events == []                                  # peringatan teredam
    assert st["status"] == gf.LUAR                       # TAPI status berpindah
    assert st["transisi"]["keluar"] != ""                # dan jamnya dicatat
    assert gf.jatuh_tempo_dwell(st, {"maks_di_luar_jam": 1},
                                T0 + timedelta(hours=3)) is not None


def test_muatan_event_lengkap_dan_masuk_akal():
    """Muatan event sebelumnya tak pernah diperiksa: `pada`, `titik`, `jarak_m`
    bebas berubah tanpa satu uji pun gagal."""
    _, events = _jalankan([(116.701, -1.400, t) for t in (0, 60, 120)])
    ev = events[0]
    assert ev["jenis"] == "masuk"
    assert ev["titik"] == [116.701, -1.400]
    assert ev["jarak_m"] == 0.0
    assert ev["pada"] == (T0 + timedelta(seconds=120)).isoformat()


def test_state_masukan_tak_dimutasi_pada_jalur_BER_EVENT():
    """Uji lama hanya melewati jalur TANPA event, jadi mutasi `transisi`/`redam`
    (dict bersarang) tak akan ketahuan."""
    st = gf.status_awal("d", "a")
    st.update({"status": gf.KANDIDAT_MASUK, "sampel": 2,
               "sejak": T0.isoformat()})
    import copy
    salinan = copy.deepcopy(st)
    r = gf.evaluasi(st, _obs(*TENGAH, 300), KOTAK, T0 + timedelta(seconds=300))
    assert r["event"] is not None            # jalur ber-event sungguhan
    assert st == salinan                     # asli utuh, termasuk dict bersarang


def test_dwell_tanpa_catatan_keluar_tidak_jatuh_tempo():
    """Perangkat yang baru terdaftar berstatus LUAR tanpa pernah 'keluar' —
    tanpa penjaga ini setiap perangkat baru jadi alarm palsu."""
    assert gf.jatuh_tempo_dwell({"status": gf.LUAR, "transisi": {}},
                                {"maks_di_luar_jam": 1},
                                T0 + timedelta(days=9)) is None
    assert gf.jatuh_tempo_dwell(gf.status_awal("d", "a"),
                                {"maks_di_luar_jam": 1},
                                T0 + timedelta(days=9)) is None


def test_param_nan_dan_infinity_ditolak():
    p = gf.ringkas_aturan({"param": {"buffer_keluar_m": float("nan"),
                                     "dwell_masuk_dtk": float("inf")}})
    assert p["buffer_keluar_m"] == 25 and p["dwell_masuk_dtk"] == 120


def test_ambang_retro_benar_benar_dipakai():
    """AMBANG_RETRO_DTK sebelumnya tak tersentuh: 200 dtk maupun 20000 dtk
    sama-sama hijau."""
    urut = [(116.701, -1.400, t) for t in (0, 60, 120)]
    st = gf.status_awal("d", "a")
    ev = None
    for lon, lat, dt in urut:                 # tiba TEPAT di bawah ambang
        r = gf.evaluasi(st, _obs(lon, lat, dt), KOTAK,
                        T0 + timedelta(seconds=gf.AMBANG_RETRO_DTK - 100))
        st = r["state"]; ev = r["event"] or ev
    assert ev and ev["retro"] is False


def test_teleport_tepat_di_bawah_dan_di_atas_ambang():
    """Pita 250–3300 km/jam sebelumnya tak teruji sama sekali."""
    a = _obs(116.700, -1.400, 0)
    # 0.010° bujur ≈ 1113 m dalam 60 dtk ≈ 67 km/jam → wajar
    assert gf.lompatan_mustahil(a, _obs(116.710, -1.400, 60)) is False
    # 0.060° ≈ 6678 m dalam 60 dtk ≈ 400 km/jam → mustahil untuk darat
    assert gf.lompatan_mustahil(a, _obs(116.760, -1.400, 60)) is True
