"""Penjaga untuk skrip diagnosa mongod.

Inventaris 29 Agustus 2026 menemukan `mongod` memakai **93,1% CPU**
terus-menerus pada mesin 2 vCPU. Skrip diagnosanya menyambung ke basis data
PRODUKSI, dan itu membuat dua hal berbahaya menjadi satu baris jauhnya:

* satu `createIndex`/`setProfilingLevel` "biar sekalian diperbaiki" — alat
  diagnosis berubah jadi alat yang bisa mengunci koleksi berisi seluruh data
  BMN di tengah jam kerja;
* satu `pprint(op)` pada hasil `currentOp` — dokumen `command` di dalamnya
  memuat NILAI filter (NIP, kode satker, nama orang), dan keluaran ini masuk
  ke log GitHub Actions yang terbaca semua kolaborator dan bertahan
  berbulan-bulan.

Keduanya tak akan membuat satu pun uji lain gagal. Uji inilah gerbangnya.

Pelajaran dari inventaris VPS ikut dipakai di sini: pencocokan teks saja tidak
cukup — putaran pertama alat itu lolos uji teks lalu salah lapor di produksi.
Karena itu skripnya juga DIJALANKAN terhadap klien Mongo tiruan yang merekam
setiap perintah, dan rekamannya yang diperiksa.
"""
import ast
import pathlib
import sys
import types

import pytest

AKAR = pathlib.Path(__file__).resolve().parents[3]
SKRIP = AKAR / "scripts" / "diagnosa_mongod.py"
ALUR = AKAR / ".github" / "workflows" / "diagnosa-mongod.yml"


@pytest.fixture(scope="module")
def isi() -> str:
    return SKRIP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def modul():
    """Muat skrip sebagai modul TANPA menjalankan main()."""
    sumber = SKRIP.read_text(encoding="utf-8")
    m = types.ModuleType("diagnosa_mongod_uji")
    m.__file__ = str(SKRIP)
    exec(compile(sumber, str(SKRIP), "exec"), m.__dict__)  # noqa: S102
    return m


def _panggilan(isi_skrip: str) -> set:
    """Nama tiap atribut/metode yang dipanggil di skrip."""
    pohon = ast.parse(isi_skrip)
    nama = set()
    for n in ast.walk(pohon):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                nama.add(f.attr)
            elif isinstance(f, ast.Name):
                nama.add(f.id)
    return nama


def _teks_kode(isi_skrip: str) -> str:
    """Teks yang BENAR-BENAR dieksekusi — docstring dan komentar dibuang.

    Versi pertama uji ini mencocokkan seluruh berkas dan gagal seketika:
    docstring skripnya SENDIRI menyebut `setProfilingLevel`, `killOp`, dan
    `shutdown` — justru untuk melarangnya. Pencocokan yang tak bisa
    membedakan larangan dari pelanggaran akan selalu menuduh yang salah.
    """
    pohon = ast.parse(isi_skrip)
    docstring = set()
    for n in ast.walk(pohon):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            d = n.body[0] if n.body else None
            if (isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant)
                    and isinstance(d.value.value, str)):
                docstring.add(id(d.value))
    potong = [
        n.value for n in ast.walk(pohon)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and id(n) not in docstring
    ]
    return "\n".join(potong) + "\n" + "\n".join(sorted(_panggilan(isi_skrip)))


class TestTidakMenulisApaPun:
    MENULIS = (
        "insert_one", "insert_many", "update_one", "update_many",
        "replace_one", "delete_one", "delete_many", "bulk_write",
        "find_one_and_update", "find_one_and_delete", "find_one_and_replace",
        "create_index", "create_indexes", "drop_index", "drop_indexes",
        "drop", "drop_collection", "rename", "create_collection",
        "set_profiling_level", "kill_op", "fsync",
    )

    @pytest.mark.parametrize("metode", MENULIS)
    def test_tidak_memanggil_metode_penulis(self, isi, metode):
        assert metode not in _panggilan(isi), (
            f"Skrip diagnosa memanggil `{metode}`. Ia menyambung ke basis data "
            "PRODUKSI dan harus aman dijalankan kapan pun."
        )

    @pytest.mark.parametrize("tahap", ["$out", "$merge"])
    def test_pipeline_tak_menulis_koleksi(self, isi, tahap):
        assert tahap not in _teks_kode(isi), (
            f"Tahap agregasi `{tahap}` MENULIS koleksi."
        )

    @pytest.mark.parametrize("perintah", [
        "setProfilingLevel", "killOp", "shutdown", "fsyncLock",
        "dropDatabase", "compact", "reIndex",
    ])
    def test_tak_menjalankan_perintah_admin_yang_mengubah(self, isi, perintah):
        assert perintah not in _teks_kode(isi), (
            f"Perintah `{perintah}` mengubah keadaan server."
        )


class TestTidakMembocorkanNilaiData:
    def test_currentop_hanya_mencetak_bentuk_query(self, modul):
        # Dokumen `command` memuat NILAI filter. Yang boleh keluar hanya
        # bentuknya: namespace, jenis operasi, lama jalan, rencana eksekusi.
        rahasia = "197001011990031001"
        keluar = "\n".join(modul.ringkas_current_op({"inprog": [{
            "ns": "aman.assets", "op": "query", "secs_running": 12,
            "planSummary": "COLLSCAN", "numYields": 3,
            "command": {"filter": {"nip": rahasia, "nama": "Budi Santoso"}},
            "client": "10.0.0.9:51234",
        }]}))
        assert rahasia not in keluar, "NIP dari filter query ikut tercetak"
        assert "Budi Santoso" not in keluar, "Nama dari filter query ikut tercetak"
        assert "10.0.0.9" not in keluar, "Alamat klien ikut tercetak"
        # …tetapi yang berguna HARUS ada, kalau tidak ujinya lulus dengan
        # skrip yang tak mencetak apa pun.
        assert "aman.assets" in keluar and "COLLSCAN" in keluar and "12" in keluar

    def test_tak_menyentuh_kredensial_selain_untuk_menyambung(self, isi):
        # MONGO_URL boleh dibaca (untuk MongoClient) tetapi tak boleh dicetak.
        pohon = ast.parse(isi)
        for n in ast.walk(pohon):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id == "print"):
                continue
            teks = ast.dump(n)
            for k in ("MONGO_URL", "DB_NAME", "url", "nama_db"):
                assert f"'{k}'" not in teks and f"id='{k}'" not in teks, (
                    f"`print` menyentuh `{k}` — kredensial/nama basis data "
                    "tak boleh masuk log Actions."
                )

    def test_galat_dilaporkan_tanpa_pesan_aslinya(self, isi):
        """Galat pymongo kerap memuat URI LENGKAP beserta sandinya.

        Versi pertama uji ini mencari teks `"{e}"` di antara konstanta string
        — dan mutasi `print(f"...: {e}._")` LOLOS. Sebabnya: bagian `{e}`
        sebuah f-string bukan konstanta melainkan `FormattedValue`, jadi ia
        tak pernah masuk himpunan yang diperiksa. Kini pemeriksaannya
        struktural: di dalam SETIAP `except … as e`, nama galat hanya boleh
        muncul sebagai `type(e).__name__`.
        """
        pohon = ast.parse(isi)
        pelanggaran = []
        for h in ast.walk(pohon):
            if not isinstance(h, ast.ExceptHandler) or not h.name:
                continue
            aman = set()
            for n in ast.walk(h):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                        and n.func.id == "type" and n.args
                        and isinstance(n.args[0], ast.Name)
                        and n.args[0].id == h.name):
                    aman.add(id(n.args[0]))
            for n in ast.walk(h):
                if (isinstance(n, ast.Name) and n.id == h.name
                        and id(n) not in aman):
                    pelanggaran.append(f"baris {n.lineno}")
        assert not pelanggaran, (
            "Nama galat dipakai mentah di " + ", ".join(pelanggaran)
            + ". Pesan galat pymongo bisa memuat URI ber-sandi — cetak "
            "`type(e).__name__` saja."
        )


class TestBacaannyaBenar:
    def test_indeks_tak_terpakai_ditandai(self, modul):
        keluar = "\n".join(modul.ringkas_index_stats("assets", [
            {"name": "activity_id_1", "accesses": {"ops": 91234}},
            {"name": "stiker_status_1", "accesses": {"ops": 0}},
        ]))
        assert "⚠ tak pernah" in keluar
        # Yang terpakai TIDAK ikut ditandai — kalau tidak, tandanya tak berarti.
        baris_terpakai = [b for b in keluar.splitlines() if "activity_id_1" in b]
        assert baris_terpakai and "⚠" not in baris_terpakai[0]

    def test_indeks_paling_tak_terpakai_disebut_lebih_dulu(self, modul):
        keluar = modul.ringkas_index_stats("assets", [
            {"name": "sering", "accesses": {"ops": 5000}},
            {"name": "jarang", "accesses": {"ops": 2}},
        ])
        teks = "\n".join(keluar)
        assert teks.index("jarang") < teks.index("sering")

    def test_currentop_kosong_dikatakan_apa_adanya(self, modul):
        keluar = "\n".join(modul.ringkas_current_op({"inprog": []}))
        assert "Tak ada operasi aktif" in keluar

    def test_server_status_menyebut_cache_dan_antrean(self, modul):
        keluar = "\n".join(modul.ringkas_server_status({
            "uptime": 340000,
            "connections": {"current": 12, "available": 800},
            "wiredTiger": {"cache": {
                "bytes currently in the cache": 1_500_000_000,
                "maximum bytes configured": 3_500_000_000,
                "pages read into cache": 99}},
            "globalLock": {"currentQueue": {"readers": 4, "writers": 0}},
            "opcounters": {"query": 1234567},
        }))
        assert "1430.5 MB" in keluar or "1.430,5 MB" in keluar or "MB" in keluar
        assert "| 4 / 0 |" in keluar, "antrean baca/tulis tak terbaca"
        assert "340000" in keluar, "uptime tak dicetak — angka $indexStats jadi tak terbaca"

    def test_bagian_yang_gagal_tak_menjatuhkan_sisanya(self, modul):
        # Server yang tak mengizinkan $indexStats tetap harus memberi bacaan
        # lain; diagnosis separuh lebih baik daripada tak ada sama sekali.
        assert modul.ringkas_index_stats("assets", []) == ["_`assets`: tak ada data indeks._"]


class TestAlurnyaTerkunci:
    @pytest.fixture(scope="class")
    def alur(self) -> dict:
        import yaml
        return yaml.safe_load(ALUR.read_text(encoding="utf-8"))

    def test_hanya_manual(self, alur):
        pemicu = alur.get("on", alur.get(True))
        assert set(pemicu) == {"workflow_dispatch"}, (
            f"Pemicu berubah jadi {sorted(pemicu)} — pemicu otomatis berarti "
            "sesi SSH ke basis data produksi pada tiap commit."
        )

    def test_tanpa_input(self, alur):
        pemicu = alur.get("on", alur.get(True))
        assert not (pemicu.get("workflow_dispatch") or {}).get("inputs")

    def test_berbagi_antrean_dengan_deploy(self, alur):
        assert alur["concurrency"]["group"] == "deploy-vps"

    def test_menjalankan_skrip_ini_dengan_python_venv(self, alur):
        skrip = "\n".join(s.get("run", "") for s in alur["jobs"]["diagnosa"]["steps"])
        # venv backend, BUKAN python sistem: pymongo & dotenv ada di sana, dan
        # versinya (3.11) yang memang dipakai aplikasi.
        assert "/var/www/inventarisasi/backend/venv/bin/python -" in skrip
        assert "< scripts/diagnosa_mongod.py" in skrip
        assert skrip.count("ssh -i") == 1


class TestPengukuranYangMenutupKasus:
    """Bacaan 29 Agustus 2026 menemukan bebannya tetapi TIDAK menyebut namanya.

    6.943.415 query dalam 17 jam — 112 per detik, terus-menerus, pada 06:49
    pagi waktu setempat saat tak seorang pun memakai aplikasi — sementara
    seluruh akses indeks pada `assets` hanya 236 kali. Query sebanyak itu
    jelas tak memakai indeks.

    Tetapi `currentOp` hanya menangkap operasi yang SEDANG berjalan. Query
    yang selesai dalam 8 milidetik tak akan pernah tertangkap betapa pun
    seringnya diulang — dan memang hanya `admin.$cmd` yang muncul. Alat itu
    menemukan gejalanya lalu berhenti.

    Dua bacaan kumulatif menutup celahnya: rasio dipindai/dikembalikan
    (tanda pindai-koleksi), dan `top` yang menyebut namespace pemakan waktu
    secara langsung.
    """

    def test_rasio_pindai_menandai_pindai_koleksi(self, modul):
        keluar = "\n".join(modul.ringkas_beban({
            "uptime": 61716,
            "opcounters": {"query": 6_943_415, "insert": 115, "update": 1053, "delete": 52},
            "metrics": {
                "queryExecutor": {"scanned": 236, "scannedObjects": 44_000_000,
                                  "collectionScans": {"total": 6_900_000}},
                "document": {"returned": 120_000},
            },
        }))
        assert "⚠ pindai-koleksi" in keluar
        assert "112,5" in keluar, "query per detik tak dihitung"

    def test_rasio_sehat_TIDAK_ditandai(self, modul):
        # Kalau tandanya selalu muncul, ia tak berarti apa-apa.
        keluar = "\n".join(modul.ringkas_beban({
            "uptime": 1000, "opcounters": {"query": 100},
            "metrics": {"queryExecutor": {"scanned": 100, "scannedObjects": 120},
                        "document": {"returned": 100}},
        }))
        assert "⚠" not in keluar

    def test_top_menyebut_namespace_pemakan_waktu_terbesar_lebih_dulu(self, modul):
        # Yang KECIL sengaja ditaruh lebih dulu: dict Python mempertahankan
        # urutan sisip, jadi kalau datanya sudah urut, uji ini lulus bahkan
        # ketika pengurutannya dicabut — dan itu memang sempat terjadi.
        keluar = modul.ringkas_top({"totals": {
            "note": "all times in microseconds",
            "aman.assets": {"total": {"time": 5_000_000, "count": 240},
                            "queries": {"count": 240}, "commands": {"count": 0}},
            "aman.report_settings": {"total": {"time": 900_000_000, "count": 6_900_000},
                                     "queries": {"count": 6_900_000},
                                     "commands": {"count": 0}},
        }})
        teks = "\n".join(keluar)
        assert teks.index("report_settings") < teks.index("assets"), (
            "namespace pemakan waktu terbesar harus disebut lebih dulu"
        )
        assert "note" not in teks, "kunci `note` dari `top` ikut jadi baris"
        # Yang menguasai waktu ditebalkan supaya mata menemukannya.
        baris = [b for b in keluar if "report_settings" in b][0]
        assert "**" in baris

    def test_top_kosong_dikatakan_apa_adanya(self, modul):
        assert "tak memberi data" in "\n".join(modul.ringkas_top({"totals": {}}))

    def test_angka_indonesia_tak_bercampur_titik_dan_titik(self, modul):
        # Versi pertama menghasilkan `3.458.0 MB` — dua titik dengan arti
        # berbeda dalam satu angka.
        assert modul._angka(3458.0, 1) == "3.458,0"
        assert modul._angka(6_943_415) == "6.943.415"
        assert modul._mb(3458.0 * 1024 * 1024) == "3.458,0 MB"
