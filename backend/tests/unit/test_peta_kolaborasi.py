"""Uji helper MURNI peta kolaboratif + token peta (tanpa DB/jaringan).

Fokus GERBANG AKSES: siapa boleh melihat/berkontribusi saat aktif vs setelah
masa tayang habis (tamu vs operator/admin satker terkait), dan token typ=peta.
"""
import asyncio
from datetime import datetime, timezone, timedelta


def _iso(delta_hours):
    return (datetime.now(timezone.utc) + timedelta(hours=delta_hours)).isoformat()


def _iso_wib(delta_hours):
    """Instant relatif SEKARANG, tapi dinyatakan dalam offset +07:00 (WIB)."""
    dt = datetime.now(timezone.utc) + timedelta(hours=delta_hours)
    return dt.astimezone(timezone(timedelta(hours=7))).isoformat()


def test_parse_coord():
    from routes.peta_kolaborasi import _parse_coord
    assert _parse_coord("1,5") == 1.5          # desimal koma
    assert _parse_coord("-6.2") == -6.2
    assert _parse_coord(" 106.8 ") == 106.8
    assert _parse_coord("") is None
    assert _parse_coord("abc") is None
    assert _parse_coord(None) is None


def test_kedaluwarsa():
    from routes.peta_kolaborasi import _kedaluwarsa
    assert _kedaluwarsa({"berlaku_sampai": _iso(-1)}) is True    # lampau
    assert _kedaluwarsa({"berlaku_sampai": _iso(+1)}) is False   # mendatang
    assert _kedaluwarsa({"berlaku_sampai": ""}) is False         # tak diset → tak habis


def test_kedaluwarsa_offset_non_utc():
    """Offset zona waktu (WIB +07:00) dihormati secara kronologis, bukan
    perbandingan string leksikografis (regresi temuan keamanan)."""
    from routes.peta_kolaborasi import _kedaluwarsa
    # Instant yang SAMA di WIB: 1 jam lampau → habis; 1 jam mendatang → belum.
    assert _kedaluwarsa({"berlaku_sampai": _iso_wib(-1)}) is True
    assert _kedaluwarsa({"berlaku_sampai": _iso_wib(+1)}) is False
    # Naif (tanpa tz) diperlakukan UTC.
    assert _kedaluwarsa({"berlaku_sampai": "2020-01-01T00:00:00"}) is True


def test_hitung_berlaku_plafon_base():
    """plafon_base (mis. created_at) menjepit masa tayang agar token yang sudah
    tersebar tak kedaluwarsa lebih dulu (regresi temuan keamanan)."""
    from routes.peta_kolaborasi import _hitung_berlaku
    from auth_utils import MAP_TOKEN_EXPIRATION_DAYS
    base = datetime(2026, 7, 24, 0, 0, tzinfo=timezone.utc)
    plafon = base - timedelta(days=30)   # token diterbitkan 30 hari lalu
    d = _hitung_berlaku(10_000_000, None, base, plafon)
    assert d == (plafon + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)).astimezone(timezone.utc).isoformat()


def test_hitung_berlaku_default_dan_jepit():
    from routes.peta_kolaborasi import _hitung_berlaku, _DEFAULT_JAM
    from auth_utils import MAP_TOKEN_EXPIRATION_DAYS
    base = datetime(2026, 7, 24, 0, 0, tzinfo=timezone.utc)
    # default 72 jam bila tak ada input
    d = _hitung_berlaku(None, None, base)
    assert d == (base + timedelta(hours=_DEFAULT_JAM)).isoformat()
    # durasi_jam eksplisit
    d = _hitung_berlaku(24, None, base)
    assert d == (base + timedelta(hours=24)).isoformat()
    # dijepit ke plafon token
    d = _hitung_berlaku(10_000_000, None, base)
    assert d == (base + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)).isoformat()
    # berlaku_sampai eksplisit menang atas durasi
    target = (base + timedelta(hours=5)).isoformat()
    assert _hitung_berlaku(999, target, base) == target


def test_akses_aktif_tamu_dan_user():
    from routes.peta_kolaborasi import _akses_peta
    aktif = {"status": "aktif", "berlaku_sampai": _iso(+2), "kode_satker": "527010"}
    # tamu BERLINK saat aktif → lihat + kontribusi
    assert _akses_peta(aktif, {"guest": True, "role": "tamu"}, True) == (True, True, "")
    # operator satker terkait buka dari aplikasi (tanpa token) → lihat + kontribusi
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "527010"}, False) == (True, True, "")
    # tamu TANPA link valid saat aktif → ditolak (cegah IDOR via UUID)
    assert _akses_peta(aktif, {"guest": True, "role": "tamu"}, False)[:2] == (False, False)
    # user satker BEDA tanpa link saat aktif → ditolak
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "999999"}, False)[:2] == (False, False)
    # ...tetapi pemegang link publik (satker beda) → boleh (link untuk siapa saja)
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "999999"}, True)[:2] == (True, True)


def test_akses_kedaluwarsa():
    from routes.peta_kolaborasi import _akses_peta
    habis = {"status": "aktif", "berlaku_sampai": _iso(-2), "kode_satker": "527010"}
    # tamu (bahkan pemegang link) → ditolak total pasca-kedaluwarsa
    lihat, kontrib, alasan = _akses_peta(habis, {"guest": True, "role": "tamu"}, True)
    assert lihat is False and kontrib is False and "berakhir" in alasan.lower()
    # operator satker sama → boleh LIHAT (arsip), tak boleh kontribusi
    assert _akses_peta(habis, {"role": "operator", "kode_satker": "527010"}, False)[:2] == (True, False)
    # admin satker sama → boleh lihat
    assert _akses_peta(habis, {"role": "admin", "kode_satker": "527010"}, False)[:2] == (True, False)
    # super-admin (kode_satker kosong) → boleh lihat lintas-satker
    assert _akses_peta(habis, {"role": "admin", "kode_satker": ""}, False)[:2] == (True, False)
    # viewer → ditolak
    assert _akses_peta(habis, {"role": "viewer", "kode_satker": "527010"}, False)[:2] == (False, False)
    # operator satker BEDA (walau pegang link) → ditolak pasca-kedaluwarsa
    assert _akses_peta(habis, {"role": "operator", "kode_satker": "999999"}, True)[:2] == (False, False)


def test_akses_dibatalkan():
    from routes.peta_kolaborasi import _akses_peta
    batal = {"status": "batal", "berlaku_sampai": _iso(+2), "kode_satker": "527010"}
    # dibatalkan → ditolak untuk siapa pun, termasuk operator satker & pemegang link
    lihat, kontrib, alasan = _akses_peta(batal, {"role": "admin", "kode_satker": "527010"}, True)
    assert lihat is False and kontrib is False and "batal" in alasan.lower()


def test_token_peta_round_trip():
    from auth_utils import create_map_token, require_map_token
    tok = create_map_token("share-123", "jti-abc")
    out = asyncio.run(require_map_token(token=tok))
    assert out == {"share": "share-123", "jti": "jti-abc"}


def test_token_peta_tolak_typ_lain():
    import pytest
    from fastapi import HTTPException
    from auth_utils import create_sign_token, require_map_token
    # token e-sign (typ=sign) TIDAK boleh lolos sebagai token peta.
    sign_tok = create_sign_token("sr1", "signer1", "jti1")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(require_map_token(token=sign_tok))
    assert ei.value.status_code == 401


# ── Payload publik: pagar terhadap kebocoran posisi (DPIA §6, Fase 11) ──────

def test_titik_publik_hanya_kunci_yang_diizinkan():
    """Sejak Fase 11 aplikasi menyimpan posisi perangkat yang dipegang
    PERORANGAN. Payload peta publik dapat dibuka siapa pun yang memegang tautan,
    jadi kunci yang keluar diuji EKSPLISIT — bukan diserahkan pada ingatan orang
    yang menambah field berikutnya."""
    from routes.peta_kolaborasi import KUNCI_PUBLIK_TITIK, baris_titik_publik
    aset = {"id": "a1", "asset_code": "3.05.01", "NUP": "7",
            "asset_name": "Laptop", "category": "Peralatan", "brand": "X",
            # Field yang TIDAK boleh menembus keluar:
            "lokasi_spasial": {"node_id": "sn_g1", "titik": [116.71, -1.40]},
            "pengguna": "Budi", "nip_pengguna": "1990...", "harga": 15000000,
            "photos": ["base64..."], "device_id": "dev_1",
            "koordinat_latitude": "-1.40", "koordinat_longitude": "116.71"}
    baris = baris_titik_publik(aset, -1.40, 116.71)
    assert set(baris) == set(KUNCI_PUBLIK_TITIK)
    bocor = {"lokasi_spasial", "pengguna", "nip_pengguna", "harga", "photos",
             "device_id", "koordinat_latitude", "koordinat_longitude"}
    assert not (set(baris) & bocor)


def test_titik_publik_tetap_membawa_data_verifikasi_lapangan():
    """Pagar privasi tak boleh mengosongkan peta — kode/NUP/kondisi memang
    tujuan berbagi tautan ini."""
    from routes.peta_kolaborasi import baris_titik_publik
    b = baris_titik_publik({"id": "a1", "asset_code": "3.05", "NUP": 7,
                            "asset_name": "Laptop", "condition": "Baik"},
                           -1.40, 116.71)
    assert b["kode"] == "3.05" and b["nama"] == "Laptop"
    assert b["kondisi"] == "Baik" and (b["lat"], b["lng"]) == (-1.40, 116.71)


def test_titik_publik_aset_minim_tak_meledak():
    from routes.peta_kolaborasi import baris_titik_publik
    b = baris_titik_publik({"id": "a1"}, 0.5, 100.0)
    assert b["nama"] == "" and b["jumlah_foto"] == 0


def test_izin_kontribusi_berlaku_per_link():
    """Setelan per-link mengikat SETIAP kunjungan lewat link — termasuk
    pengunjung yang kebetulan sedang login. Regresi: dulu setiap user login
    lolos begitu saja, sehingga link 'tanpa komentar/titik' tetap bisa dipakai
    berkontribusi dan setelan tiap link jadi tak berarti."""
    from routes.peta_kolaborasi import _izin_kontribusi
    mati = {"status": "aktif", "kode_satker": "527010",
            "izinkan_titik_publik": False, "izinkan_komentar_publik": False}
    tamu = {"guest": True, "role": "tamu"}
    op = {"role": "operator", "kode_satker": "527010"}
    luar = {"role": "operator", "kode_satker": "999999"}

    # Lewat link → setelan berlaku untuk SIAPA PUN.
    assert _izin_kontribusi(mati, tamu, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(mati, op, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(mati, luar, True, "izinkan_komentar_publik") is False
    # Operator/admin satker share membuka DARI APLIKASI (tanpa token link) →
    # mengelola petanya sendiri, tak dibatasi setelan publik.
    assert _izin_kontribusi(mati, op, False, "izinkan_titik_publik") is True
    # Satker lain tanpa link tetap tak boleh.
    assert _izin_kontribusi(mati, luar, False, "izinkan_titik_publik") is False

    # Setelan menyala → semua pengunjung berlink boleh.
    hidup = dict(mati, izinkan_titik_publik=True, izinkan_komentar_publik=True)
    assert _izin_kontribusi(hidup, tamu, True, "izinkan_titik_publik") is True
    assert _izin_kontribusi(hidup, tamu, True, "izinkan_komentar_publik") is True


def test_izin_kontribusi_dua_setelan_terpisah():
    """Titik & komentar berdiri sendiri — mematikan satu tak ikut mematikan
    yang lain (tiap link punya kombinasinya sendiri)."""
    from routes.peta_kolaborasi import _izin_kontribusi
    sh = {"status": "aktif", "kode_satker": "527010",
          "izinkan_titik_publik": False, "izinkan_komentar_publik": True}
    tamu = {"guest": True, "role": "tamu"}
    assert _izin_kontribusi(sh, tamu, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(sh, tamu, True, "izinkan_komentar_publik") is True


def test_izin_kontribusi_share_lama_tanpa_field():
    """Share yang dibuat sebelum fitur toggle (field tak ada) tetap terbuka —
    tak boleh mendadak mengunci peta yang sedang berjalan."""
    from routes.peta_kolaborasi import _izin_kontribusi
    lama = {"status": "aktif", "kode_satker": "527010"}
    assert _izin_kontribusi(lama, {"guest": True}, True, "izinkan_titik_publik") is True


# ── Arsip otomatis: link mati > sebulan tak lagi didaftar ───────────────────

def _hari(n):
    return (datetime.now(timezone.utc) + timedelta(days=n)).isoformat()


def test_share_usang_hanya_untuk_yang_sudah_mati():
    """Link yang MASIH HIDUP tak pernah usang — setua apa pun umurnya. Link
    berdurasi 1 tahun yang dibuat 6 bulan lalu masih dipakai orang di
    lapangan."""
    from routes.peta_kolaborasi import _share_usang
    hidup_tua = {"status": "aktif", "created_at": _hari(-180),
                 "updated_at": _hari(-180), "berlaku_sampai": _hari(+180)}
    assert _share_usang(hidup_tua) is False


def test_share_usang_dibatalkan_dihitung_dari_saat_pembatalan():
    from routes.peta_kolaborasi import _share_usang
    baru_batal = {"status": "batal", "created_at": _hari(-400),
                  "updated_at": _hari(-3), "berlaku_sampai": _hari(-390)}
    lama_batal = dict(baru_batal, updated_at=_hari(-31))
    # Dibatalkan 3 hari lalu → masih tampil (bisa diterbitkan ulang).
    assert _share_usang(baru_batal) is False
    # Dibatalkan 31 hari lalu → disingkirkan dari daftar.
    assert _share_usang(lama_batal) is True


def test_share_usang_kedaluwarsa_dihitung_dari_berlaku_sampai():
    """Regresi rancangan: memakai `updated_at` untuk link kedaluwarsa membuat
    link 30-hari yang dibuat sekali sentuh langsung dianggap usang PERSIS saat
    berakhir — operator kehilangan kesempatan memperpanjangnya."""
    from routes.peta_kolaborasi import _share_usang
    sebulan = {"status": "aktif", "created_at": _hari(-30),
               "updated_at": _hari(-30), "berlaku_sampai": _hari(-1)}
    assert _share_usang(sebulan) is False       # baru berakhir kemarin
    lama = dict(sebulan, berlaku_sampai=_hari(-31))
    assert _share_usang(lama) is True


def test_share_usang_tanpa_cap_waktu_tak_disingkirkan():
    """Data lama/rusak tanpa cap waktu yang bisa dibaca lebih baik tetap
    tampil daripada hilang tanpa alasan yang bisa dijelaskan."""
    from routes.peta_kolaborasi import _share_usang
    assert _share_usang({"status": "batal"}) is False
    assert _share_usang({"status": "batal", "updated_at": "bukan-tanggal"}) is False
    assert _share_usang({"status": "aktif", "berlaku_sampai": ""}) is False


def test_share_usang_tepat_di_batas_sebulan():
    from routes.peta_kolaborasi import _share_usang, UMUR_ARSIP_HARI
    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    persis = (now - timedelta(days=UMUR_ARSIP_HARI)).isoformat()
    lewat = (now - timedelta(days=UMUR_ARSIP_HARI, seconds=1)).isoformat()
    assert _share_usang({"status": "batal", "updated_at": persis}, now) is False
    assert _share_usang({"status": "batal", "updated_at": lewat}, now) is True


# ── Lingkup berbagi: filter/seleksi aktif → HANYA titik itu ──────────────
#
# Permintaan pemilik: *"ketika filter dan seleksi aktif, pada saat dibuat
# Bagikan Peta Kolaboratif, berarti hanya titik-titik itu saja yang dibagikan
# dan tidak semua titik. tolong berikan informasi jumlahnya juga."*
#
# Sebelum ini, `_titik_aset` mencocokkan `activity_id` saja: peta yang disaring
# hingga tersisa lima titik tetap membagikan SELURUH aset kegiatan. Operator
# tak punya cara mengetahuinya — tautannya terlihat sama persis.

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbp(monkeypatch):
    import routes.peta_kolaborasi as pk
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(pk, "db", fake, raising=False)
    monkeypatch.setattr(pk, "log_audit", _diam, raising=False)
    return fake


async def _isi_aset(fake, activity_id, n, mulai=0):
    for i in range(mulai, mulai + n):
        await fake.assets.insert_one({
            "id": f"a{i}", "activity_id": activity_id, "asset_name": f"Aset {i}",
            "koordinat_latitude": -6.2 + i / 1000, "koordinat_longitude": 106.8,
        })


def test_lingkup_kosong_berarti_seluruh_kegiatan(dbp):
    """Perilaku sejak awal harus utuh: tanpa penyempit, tautan tetap HIDUP —
    aset yang ditambahkan sesudahnya ikut tampil."""
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 3)
        titik = await pk._titik_aset({"activity_id": "keg-1", "asset_ids": []})
        assert len(titik) == 3
        # Aset baru sesudah tautan terbit tetap ikut.
        await _isi_aset(dbp, "keg-1", 1, mulai=99)
        assert len(await pk._titik_aset({"activity_id": "keg-1"})) == 4
    _jalan(jalan())


def test_lingkup_terbatas_hanya_mengirim_titik_itu(dbp):
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 5)
        titik = await pk._titik_aset(
            {"activity_id": "keg-1", "asset_ids": ["a1", "a3"]})
        assert {t["id"] for t in titik} == {"a1", "a3"}
    _jalan(jalan())


def test_lingkup_terbatas_TIDAK_ikut_bertambah(dbp):
    """Sifat yang membedakan menyimpan DAFTAR ID dari menyimpan filternya.

    Filter adalah pertanyaan yang jawabannya berubah seiring data. Tautan yang
    sudah tersebar ke pihak luar tak boleh diam-diam memuat aset yang belum
    ada saat ia dibagikan — apalagi karena penerimanya tak punya cara tahu.
    """
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 2)
        share = {"activity_id": "keg-1", "asset_ids": ["a0", "a1"]}
        assert len(await pk._titik_aset(share)) == 2
        await _isi_aset(dbp, "keg-1", 3, mulai=50)
        assert len(await pk._titik_aset(share)) == 2, "aset baru ikut bocor"
    _jalan(jalan())


def test_id_kegiatan_lain_disaring_di_server(dbp):
    """Id datang dari layar, jadi tak boleh dipercaya. Tanpa pemeriksaan ini,
    permintaan yang disusun tangan dapat membagikan aset kegiatan LAIN lewat
    tautan publik."""
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 2)
        await _isi_aset(dbp, "keg-2", 2, mulai=90)
        sah = await pk._lingkup_aset("keg-1", ["a0", "a90", "a91"])
        assert sah == ["a0"], sah
    _jalan(jalan())


def test_aset_dihapus_tak_ikut_lingkup(dbp):
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 2)
        await dbp.assets.update_one({"id": "a1"}, {"$set": {"dihapus": True}})
        assert await pk._lingkup_aset("keg-1", ["a0", "a1"]) == ["a0"]
    _jalan(jalan())


def test_id_kembar_dan_kosong_dibersihkan(dbp):
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 2)
        assert await pk._lingkup_aset(
            "keg-1", ["a0", " a0 ", "", None, "a1"]) == ["a0", "a1"]
    _jalan(jalan())


def test_melebihi_plafon_DITOLAK_bukan_dipotong_diam_diam(dbp):
    """Peta publik memang hanya mengirim `MAKS_TITIK_ASET_PUBLIK` titik.
    Memotong diam-diam akan membuat tautan menjanjikan sesuatu yang tak pernah
    ia tampilkan, dan operator baru tahu dari penerima."""
    import routes.peta_kolaborasi as pk

    async def jalan():
        banyak = [f"x{i}" for i in range(pk.MAKS_TITIK_ASET_PUBLIK + 1)]
        with pytest.raises(HTTPException) as e:
            await pk._lingkup_aset("keg-1", banyak)
        assert e.value.status_code == 400
        assert str(pk.MAKS_TITIK_ASET_PUBLIK) in e.value.detail
    _jalan(jalan())


def test_semua_id_asing_ditolak_dengan_terang(dbp):
    """Membiarkannya lolos sebagai daftar kosong akan diam-diam berubah makna
    menjadi "bagikan SELURUH kegiatan" — kebalikan dari yang diminta."""
    import routes.peta_kolaborasi as pk

    async def jalan():
        await _isi_aset(dbp, "keg-1", 1)
        with pytest.raises(HTTPException) as e:
            await pk._lingkup_aset("keg-1", ["tak-ada", "juga-tidak"])
        assert e.value.status_code == 400
    _jalan(jalan())


# ── Jumlahnya harus terbaca, di kedua sisi ──────────────────────────────

def test_daftar_pengelola_membawa_jumlah_bukan_daftar_id():
    """Operator bertanya "berapa titik yang saya bagikan lewat tautan ini?".
    Daftar id-nya sendiri tak dibutuhkan layar mana pun, dan membawa ribuan
    id di tiap entri membengkakkan jawaban tanpa alasan."""
    from routes.peta_kolaborasi import _share_keluar
    d = _share_keluar({"id": "s1", "jti": "rahasia",
                       "asset_ids": ["a1", "a2", "a3"],
                       "berlaku_sampai": _iso(+5)})
    assert d["lingkup"] == "terpilih"
    assert d["jumlah_titik_dibagikan"] == 3
    assert "asset_ids" not in d, "daftar id bocor ke daftar pengelola"
    assert "jti" not in d


def test_lingkup_semua_tak_mengaku_punya_jumlah_tetap():
    """0 akan terbaca "tak ada titik"; None menyatakan yang sebenarnya —
    jumlahnya mengikuti isi kegiatan, jadi tak ada angka tetap untuk disebut."""
    from routes.peta_kolaborasi import _share_keluar
    d = _share_keluar({"id": "s1", "jti": "x", "berlaku_sampai": _iso(+5)})
    assert d["lingkup"] == "semua"
    assert d["jumlah_titik_dibagikan"] is None


def test_terbitkan_ulang_TIDAK_melebarkan_lingkup(dbp, monkeypatch):
    """Menerbitkan ulang mengganti tautannya, bukan isinya.

    Kalau `asset_ids` ikut hilang, tautan pengganti diam-diam membagikan
    SELURUH kegiatan — pelebaran akses yang tak diminta siapa pun, pada
    tautan yang justru diterbitkan ulang karena yang lama bocor.
    """
    import routes.peta_kolaborasi as pk

    async def jalan():
        await dbp.peta_shares.insert_one({
            "id": "s1", "activity_id": "keg-1", "kode_satker": "111111",
            "jti": "lama", "status": "aktif", "asset_ids": ["a0", "a1"],
            "berlaku_sampai": _iso(+5), "created_at": _iso(-1),
        })
        monkeypatch.setattr(pk, "pastikan_akses_dok_satker", _diam, raising=False)
        monkeypatch.setattr(pk, "create_map_token", lambda *a, **k: "tok",
                            raising=False)

        async def _link(*a, **k):
            return "https://contoh/peta"
        monkeypatch.setattr(pk, "_link_peta_pendek", _link, raising=False)
        import tautan_pendek_utils as tp
        monkeypatch.setattr(tp, "cabut_tautan", _diam, raising=False)

        await pk.terbitkan_ulang_share(
            "s1", pk.PerpanjangIn(durasi_jam=24),
            user={"username": "op", "kode_satker": "111111"})
        sh = await dbp.peta_shares.find_one({"id": "s1"})
        assert sh["asset_ids"] == ["a0", "a1"], "lingkup hilang saat terbit ulang"
        assert sh["jti"] != "lama", "jti tak dirotasi"
    _jalan(jalan())
