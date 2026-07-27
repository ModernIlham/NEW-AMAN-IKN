"""GEOFENCE — mesin status MURNI dengan histeresis (Fase 12).

Masalah yang dipecahkan modul ini BUKAN "apakah titik ada di dalam poligon".
Itu bagian gampangnya, dan sudah ada (`spasial_utils.titik_di_dalam`). Masalah
sebenarnya adalah **flapping**: perangkat yang diam persis di garis batas akan
dilaporkan GPS-nya sedikit di dalam, lalu sedikit di luar, lalu di dalam lagi —
puluhan kali per jam. Uji point-in-polygon polos akan memuntahkan puluhan
peringatan "aset keluar area" untuk aset yang sebenarnya tak bergerak sesenti
pun, dan peringatan yang meleset seperti itu membuat SELURUH sistem peringatan
diabaikan orang.

Tiga pagar yang dipakai bersama:

1. **Histeresis** — ambang masuk dan keluar SENGAJA tidak sama. Masuk dinilai
   pada poligon apa adanya; keluar baru diakui bila titik sudah lebih dari
   `buffer_keluar_m` DI LUAR poligon. Titik yang menggantung 10 m di luar batas
   masih dianggap DI DALAM. Ini yang benar-benar mematikan flapping — dwell
   saja tidak cukup, karena perangkat diam di batas bisa bertahan "di luar"
   selama menit-menitan sebelum melompat balik.

2. **Dwell** — perubahan harus BERTAHAN sekian detik sebelum diakui.

3. **Sampel minimum** — sekaligus mencegah satu pembacaan GPS liar (yang lolos
   filter akurasi) memicu peringatan sendirian.

Buffer keluar diterapkan sebagai JARAK ke poligon, bukan dengan memperbesar
poligonnya. Memperbesar poligon (`shapely.buffer`) pada bentuk cekung — bentuk
lazim gedung berbentuk L atau U — bisa melahirkan self-intersection dan
mengubah jumlah verteks; jaraknya sendiri eksak, murah, dan tak berstatus.

Modul ini MURNI: tanpa I/O, tanpa DB, tanpa jam sistem. Waktu selalu masuk
sebagai parameter supaya seluruh mesin status bisa diuji deterministik.
"""
import math
from datetime import datetime, timedelta, timezone

RADIUS_BUMI_M = 6371008.8

# Parameter bawaan — angka dari docs/ARSITEKTUR-SPASIAL-IOT.md §8.6.
GEO_PARAM = {
    "buffer_masuk_m": 0,        # masuk dinilai pada poligon apa adanya
    "buffer_keluar_m": 25,      # keluar baru diakui > 25 m di luar → histeresis
    "sampel_min": 3,
    "dwell_masuk_dtk": 120,
    "dwell_keluar_dtk": 180,
    "cooldown_dtk": 600,        # peredam badai peringatan berulang
    "abaikan_akurasi_di_atas_m": 100,
}

# Status mesin. Dua status KANDIDAT adalah inti anti-flapping: perubahan tidak
# pernah langsung diakui, selalu lewat masa percobaan lebih dulu.
LUAR, KANDIDAT_MASUK, DALAM, KANDIDAT_KELUAR = (
    "luar", "kandidat_masuk", "dalam", "kandidat_keluar")

# Observasi yang lebih tua dari ini saat tiba = backfill antrean offline, bukan
# kejadian yang sedang berlangsung. Tetap dievaluasi (riwayatnya sah) tetapi
# ditandai `retro` agar tak memicu notifikasi "SEKARANG aset keluar area" untuk
# peristiwa kemarin sore.
AMBANG_RETRO_DTK = 3600


def _skala_meter(lat_acuan: float):
    """Meter per derajat (lintang, bujur) di sekitar lintang acuan.

    Proyeksi setara-persegi lokal. Untuk area sebesar kawasan/gedung, galatnya
    jauh di bawah ketelitian GPS itu sendiri — memakai geodesi penuh di sini
    hanya menambah biaya tanpa mengubah keputusan apa pun.
    """
    m_lat = math.pi * RADIUS_BUMI_M / 180.0
    return m_lat, m_lat * math.cos(math.radians(lat_acuan))


def _jarak_ke_ruas(px, py, x1, y1, x2, y2) -> float:
    """Jarak titik ke RUAS garis (bukan ke garis tak hingga) di bidang datar."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    # t = proyeksi skalar, dijepit ke [0,1] supaya jatuh di dalam ruas.
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def jarak_ke_poligon_m(lon: float, lat: float, geom) -> float:
    """Jarak titik ke poligon dalam METER; **0.0 bila titik di dalam**.

    Inilah pengganti "poligon diperbesar": alih-alih menggeser batas, kita ukur
    seberapa jauh titik terlempar keluar. `dist > buffer_keluar_m` setara persis
    dengan "di luar poligon yang diperbesar sebesar buffer", tanpa perlu
    membangun geometri baru yang bisa rusak pada bentuk cekung.
    """
    from spasial_utils import titik_di_dalam
    if not isinstance(geom, dict):
        return math.inf
    if titik_di_dalam(lon, lat, geom):
        return 0.0
    koor = geom.get("coordinates") or []
    if geom.get("type") == "Polygon":
        poligon = [koor]
    elif geom.get("type") == "MultiPolygon":
        poligon = koor
    else:
        return math.inf

    m_lat, m_lon = _skala_meter(lat)
    px, py = lon * m_lon, lat * m_lat
    terdekat = math.inf
    for pol in poligon:
        for cincin in pol:            # cincin luar DAN lubang: tepi lubang juga
            for i in range(len(cincin) - 1):   # batas yang sah untuk diukur
                try:
                    x1, y1 = cincin[i][0] * m_lon, cincin[i][1] * m_lat
                    x2, y2 = cincin[i + 1][0] * m_lon, cincin[i + 1][1] * m_lat
                except (TypeError, IndexError):
                    continue
                d = _jarak_ke_ruas(px, py, x1, y1, x2, y2)
                if d < terdekat:
                    terdekat = d
    return terdekat


def _waktu(nilai):
    if isinstance(nilai, datetime):
        return nilai if nilai.tzinfo else nilai.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(nilai).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def kunci_urut(ts_device):
    """Kunci pengurutan observasi menurut WAKTU SESUNGGUHNYA.

    Mengurutkan `ts_device` sebagai teks itu menggoda dan salah: "10:00+07:00"
    dan "03:00Z" menunjuk instan yang sama tetapi berjauhan sebagai string, dan
    perangkat berbeda merek memang menulis offset berbeda. Observasi yang tak
    terbaca waktunya diletakkan di AWAL (bukan diabaikan) agar urutannya
    deterministik.
    """
    t = _waktu(ts_device)
    return (1, t) if t is not None else (0, datetime.min.replace(tzinfo=timezone.utc))


def layak_geofence(obs: dict, param: dict = None) -> str:
    """'' bila observasi boleh menggerakkan mesin status, atau ALASAN penolakan.

    Observasi berakurasi buruk TETAP DISIMPAN (berguna untuk "ada di gedung
    mana") tetapi TIDAK BOLEH memicu peringatan: fix GPS dengan akurasi 500 m
    di dekat batas area sama sekali tak memberi tahu kita di sisi mana titik itu
    berada, dan peringatan yang lahir dari data seperti itu adalah tebakan yang
    berpakaian sebagai fakta.
    """
    p = ringkas_aturan({"param": dict(param or {})})
    if not isinstance(obs, dict):
        return "observasi tidak sah"
    geo = obs.get("geo") or {}
    if geo.get("type") != "Point" or len(geo.get("coordinates") or []) != 2:
        # Profil privasi 'wilayah' memang MEMBUANG koordinat (Fase 10). Perangkat
        # perorangan karena itu tak pernah dipagar-geo, dan itu disengaja:
        # memagari orang bukan tujuan sistem ini.
        return "tanpa koordinat (profil privasi wilayah atau data tak lengkap)"
    if obs.get("outlier"):
        return "lompatan mustahil (outlier)"
    akurasi = obs.get("akurasi_m")
    if akurasi is not None and akurasi > p["abaikan_akurasi_di_atas_m"]:
        return f"akurasi {akurasi} m di atas ambang {p['abaikan_akurasi_di_atas_m']} m"
    return ""


def status_awal(device_id: str, area_id: str) -> dict:
    """Dokumen status kosong untuk pasangan (perangkat, area) yang belum pernah
    dievaluasi. Sengaja mulai dari LUAR, bukan 'tak diketahui': perangkat yang
    baru terpasang dan memang berada di dalam area akan menghasilkan satu event
    `masuk` yang benar dan informatif, bukan diam-diam dianggap sudah di dalam.

    `transisi` dan `redam` DIPISAH dengan sengaja — lihat `evaluasi`.
    """
    return {"device_id": device_id, "area_id": area_id, "status": LUAR,
            "sejak": "", "sampel": 0,
            # KAPAN perpindahan benar-benar terjadi (selalu dicatat).
            "transisi": {},
            # KAPAN peringatan terakhir benar-benar TERBIT, per jenis.
            "redam": {}}


def evaluasi(state: dict, obs: dict, geom, sekarang: datetime,
             param: dict = None) -> dict:
    """Satu observasi → {"state": dict, "event": dict|None, "abai": str}.

    Pemanggil menyimpan `state` yang dikembalikan APA ADANYA dan menerbitkan
    `event` bila tidak None. Fungsi tidak memutasi `state` masukan — pemanggil
    yang gagal menyimpan tak boleh meninggalkan status setengah berubah.
    """
    # Dinormalkan lewat jalur yang SAMA dengan konfigurasi. Menjepit invarian
    # hanya di lapis rute berarti mesinnya tetap bisa dijalankan dengan
    # parameter terbalik oleh pemanggil mana pun — pagar yang hanya berdiri di
    # pintu depan bukan pagar.
    p = ringkas_aturan({"param": {**{k: v for k, v in (param or {}).items()}}})
    st = dict(state or {})
    st.setdefault("status", LUAR)
    st.setdefault("sampel", 0)

    alasan = layak_geofence(obs, p)
    if alasan:
        # Observasi diabaikan TANPA menyentuh status. Menganggapnya "di luar"
        # akan membuat kabut GPS (akurasi buruk) tampak seperti aset yang pergi.
        return {"state": st, "event": None, "abai": alasan}

    lon, lat = obs["geo"]["coordinates"]
    jarak = jarak_ke_poligon_m(lon, lat, geom)
    di_dalam = jarak <= p["buffer_masuk_m"]
    # HISTERESIS: "di luar" untuk keperluan KELUAR menuntut jarak melampaui
    # buffer — bukan sekadar keluar garis. Titik 10 m di luar batas masih
    # dihitung sebagai di dalam.
    jauh_di_luar = jarak > p["buffer_keluar_m"]

    ts = _waktu(obs.get("ts_device")) or sekarang

    # PAGAR MONOTON — observasi yang lebih tua dari yang terakhir diproses
    # DIABAIKAN. Batch backfill dari antrean offline bisa tiba SETELAH batch
    # yang lebih baru; tanpa pagar ini `sejak` mundur ke masa lalu, lalu
    # observasi berikutnya menghitung selisih raksasa dan mematangkan dwell
    # SEKETIKA — melahirkan `keluar` palsu untuk aset yang justru sedang di
    # dalam. Mengurutkan di dalam satu batch (routes/geofence) tidak cukup:
    # urutan ANTAR batch tak bisa dijamin siapa pun.
    ts_terakhir = _waktu(st.get("ts_terakhir"))
    if ts_terakhir is not None and ts <= ts_terakhir:
        return {"state": st, "event": None,
                "abai": "observasi lebih tua dari yang sudah diproses"}

    retro = (sekarang - ts).total_seconds() > AMBANG_RETRO_DTK
    status = st["status"]
    event = None

    def _mulai(status_baru):
        st["status"] = status_baru
        st["sejak"] = ts.isoformat()
        st["sampel"] = 1

    def _matang(dwell_dtk):
        """True bila masa percobaan sudah cukup lama DAN cukup banyak sampel."""
        mulai = _waktu(st.get("sejak"))
        if mulai is None:
            return False
        return (st.get("sampel", 0) >= p["sampel_min"]
                and (ts - mulai).total_seconds() >= dwell_dtk)

    if status == LUAR:
        if di_dalam:
            _mulai(KANDIDAT_MASUK)
    elif status == KANDIDAT_MASUK:
        if di_dalam:
            st["sampel"] = st.get("sampel", 0) + 1
            if _matang(p["dwell_masuk_dtk"]):
                st["status"] = DALAM
                event = "masuk"
        else:
            st["status"], st["sampel"], st["sejak"] = LUAR, 0, ""
    elif status == DALAM:
        if jauh_di_luar:
            _mulai(KANDIDAT_KELUAR)
    elif status == KANDIDAT_KELUAR:
        if jauh_di_luar:
            st["sampel"] = st.get("sampel", 0) + 1
            if _matang(p["dwell_keluar_dtk"]):
                st["status"] = LUAR
                event = "keluar"
        else:
            # Kembali ke dalam zona toleransi — batalkan percobaan keluar TANPA
            # menerbitkan apa pun. Inilah yang menelan flapping di garis batas.
            st["status"], st["sampel"], st["sejak"] = DALAM, 0, ""
    else:
        st["status"] = LUAR                     # status rusak → jatuh ke aman

    # `inf` (geometri tak bisa diukur) TIDAK boleh masuk state: JSON tak
    # mengenal Infinity, dan nilai itu akan meledakkan SELURUH daftar aturan
    # saat diserialisasi — jauh dari tempat kejadiannya.
    st["jarak_m"] = round(jarak, 1) if math.isfinite(jarak) else None
    st["ts_terakhir"] = ts.isoformat()
    st["diperiksa_pada"] = sekarang.isoformat()

    if not event:
        return {"state": st, "event": None, "abai": ""}

    # PERPINDAHAN dicatat SELALU, bahkan saat peringatannya diredam. Dua hal ini
    # berbeda dan pernah tercampur di versi pertama: kalau jam "sejak kapan di
    # luar" ikut diredam, aset yang keluar lalu MATI TOTAL tak akan pernah
    # memicu `dwell_terlampaui` — persis kasus yang paling perlu diketahui.
    transisi = dict(st.get("transisi") or {})
    transisi[event] = ts.isoformat()
    st["transisi"] = transisi
    if event == "keluar":
        # Diwariskan ke `dwell_terlampaui` yang lahir dari kepergian ini —
        # peringatan turunan tak boleh tampak segar bila asalnya backfill.
        st["keluar_retro"] = retro

    if _dalam_cooldown(st, event, ts, p):
        # Peristiwa nyata, tetapi peringatan sejenis baru saja terbit. Status
        # dan waktu transisi TETAP diperbarui; yang diredam HANYA notifikasinya,
        # supaya satu aset yang mondar-mandir di gerbang tak membanjiri operator.
        return {"state": st, "event": None, "abai": "cooldown"}

    redam = dict(st.get("redam") or {})
    redam[event] = ts.isoformat()
    st["redam"] = redam
    return {"state": st,
            "event": {"jenis": event, "pada": ts.isoformat(),
                      "jarak_m": round(jarak, 1), "retro": retro,
                      "titik": [lon, lat]},
            "abai": ""}


def _dalam_cooldown(st: dict, jenis: str, ts: datetime, p: dict) -> bool:
    """Cooldown dihitung PER JENIS event.

    Versi pertama membandingkan dengan event terakhir apa pun jenisnya, sehingga
    deret masuk→keluar→masuk tak pernah teredam sama sekali: tiap event selalu
    berbeda jenis dari pendahulunya. Yang ingin dibatasi adalah frekuensi tiap
    JENIS peringatan, bukan jarak antar peringatan yang berlainan.
    """
    lalu = _waktu((st.get("redam") or {}).get(jenis))
    if lalu is None:
        return False
    # abs(): selisih BERTANDA membuat observasi ber-ts mundur menghasilkan angka
    # negatif — yang selalu lebih kecil dari cooldown — sehingga peringatan
    # NYATA teredam tanpa jejak apa pun. Pagar monoton di `evaluasi` sudah
    # menangkal sebagian besar kasus; ini lapis keduanya.
    return abs((ts - lalu).total_seconds()) < p["cooldown_dtk"]


def lompatan_mustahil(sebelum: dict, sesudah: dict,
                      maks_kmh: float = 250.0) -> bool:
    """True bila perpindahan antar dua observasi melebihi kecepatan darat wajar.

    Dipakai menandai `outlier` sebelum geofence dievaluasi: satu koordinat kacau
    yang melompat 40 km lalu kembali akan menghasilkan sepasang peringatan
    keluar-masuk yang sepenuhnya palsu.
    """
    for d in (sebelum, sesudah):
        if not isinstance(d, dict) or (d.get("geo") or {}).get("type") != "Point":
            return False
    t1, t2 = _waktu(sebelum.get("ts_device")), _waktu(sesudah.get("ts_device"))
    if t1 is None or t2 is None:
        return False
    dt = abs((t2 - t1).total_seconds())
    if dt < 1.0:
        # Δt ~0 membuat kecepatan meledak jadi tak hingga. Dua observasi pada
        # detik yang sama TIDAK bisa dinilai — menyebutnya outlier akan
        # membuang data sah dari perangkat yang mengirim sampel rapat.
        return False
    (x1, y1) = sebelum["geo"]["coordinates"]
    (x2, y2) = sesudah["geo"]["coordinates"]
    m_lat, m_lon = _skala_meter((y1 + y2) / 2.0)
    jarak = math.hypot((x2 - x1) * m_lon, (y2 - y1) * m_lat)
    return (jarak / dt) * 3.6 > maks_kmh


def ringkas_aturan(aturan: dict) -> dict:
    """Parameter efektif satu aturan = bawaan + timpaan yang sah saja.

    Nilai timpaan yang ngawur (negatif, bukan angka) DIABAIKAN, bukan
    menggagalkan aturan: geofence yang mati karena satu salah ketik lebih
    berbahaya daripada geofence yang berjalan dengan angka bawaan.
    """
    p = dict(GEO_PARAM)
    for k, v in (aturan or {}).get("param", {}).items():
        if k not in GEO_PARAM:
            continue
        try:
            nilai = float(v)
        except (TypeError, ValueError):
            continue
        if nilai < 0 or not math.isfinite(nilai):
            continue
        p[k] = int(nilai) if isinstance(GEO_PARAM[k], int) else nilai
    # INVARIAN histeresis: ambang masuk tak boleh MELEBIHI ambang keluar.
    # Bila terbalik, ada pita jarak yang sekaligus dianggap "di dalam" (untuk
    # masuk) dan "jauh di luar" (untuk keluar) — perangkat yang DIAM di pita
    # itu akan berayun masuk-keluar selamanya. Dijepit, bukan ditolak: aturan
    # yang mati karena satu salah ketik lebih berbahaya daripada aturan yang
    # berjalan dengan angka yang dirapikan.
    if p["buffer_masuk_m"] > p["buffer_keluar_m"]:
        p["buffer_masuk_m"] = p["buffer_keluar_m"]
    return p


def jatuh_tempo_dwell(state: dict, aturan: dict, sekarang: datetime):
    """Detik yang sudah dilewati sejak aset DI LUAR area sahnya — bahan event
    `dwell_terlampaui` (aset tak kunjung kembali). None bila tak berlaku.

    Dievaluasi dari status, bukan dari observasi: aset yang MATI TOTAL setelah
    keluar area justru kasus yang paling perlu diketahui, dan aset seperti itu
    tak akan pernah mengirim observasi baru untuk memicu apa pun.
    """
    if (state or {}).get("status") != LUAR:
        return None
    batas = (aturan or {}).get("maks_di_luar_jam")
    if not batas:
        return None
    # Dibaca dari `transisi`, BUKAN dari catatan peringatan: keluar yang
    # peringatannya teredam cooldown tetap keluar, dan jamnya tetap berjalan.
    sejak = _waktu((state.get("transisi") or {}).get("keluar"))
    if sejak is None:
        return None
    lewat = (sekarang - sejak).total_seconds()
    return lewat if lewat >= float(batas) * 3600 else None


def batas_waktu_iso(sekarang: datetime, jam: float) -> str:
    return (sekarang - timedelta(hours=float(jam))).isoformat()
