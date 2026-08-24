"""Kode Klasifikasi Bawaan dan Kode Klasifikasi Arsip berdiri SENDIRI-SENDIRI.

Permintaan pemilik: *"tolong bedakan Kode Klasifikasi Bawaan (fallback)
berdiri sendiri dan Kode Klasifikasi Arsip berdiri sendiri, independent
masing masing"* — setelah melihat nomor terbit sebagai
`B-003/SATKER-D/OIKN/VIII/2026`, dengan keterangan di bawahnya berbunyi
"Klasifikasi: SATKER-D · kode bawaan pengaturan".

Kalimat itu sendiri sudah memperlihatkan cacatnya: layar menyebut SATKER-D
sebagai *klasifikasi arsip surat ini*, padahal itu Kode Klasifikasi Bawaan.
Dua hal berbeda memakai satu nilai, satu nama, dan satu slot pada nomor —
sehingga pembaca nomor tak punya cara membedakan "surat ini berklasifikasi
arsip PL.02" dari "surat ini tak berklasifikasi, jadi dipakaikan kode bawaan".

Berkas ini mengunci pemisahannya:

  - `pilih_klasifikasi` tak lagi punya jaring `default`; tak cocok = KOSONG.
  - `{kode_klasifikasi}` hanya menerima kode arsip; `{kode_bawaan}` hanya
    menerima kode bawaan. Tak ada satu pun jalan silang di antaranya.
  - Slot bawaan berada DI LUAR deret PerANRI, supaya menyisipkan seluruh chip
    berurutan tidak menyelundupkan kode bawaan ke nomor siapa pun.
"""
import ast
import asyncio
import pathlib

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    PLACEHOLDER_NOMOR, bangun_nomor, komposisi_format, peringatan_klasifikasi,
    pilih_klasifikasi, placeholder_tak_dikenal, terapkan_komposisi,
)

# Admin BER-SATKER — penerbitan nomor menolak pemanggil tanpa satker
# (satker_wajib.py): surat berstempel "" tampil di register SETIAP
# satker sekaligus menghabiskan nomor agenda mereka.
ADMIN = {"username": "admin", "role": "admin", "name": "Admin",
         "kode_satker": "527001"}
AKAR = pathlib.Path(__file__).resolve().parents[2]

PETA = [{"modul": "pengadaan", "jenis_naskah": "", "kode": "PL.02"}]


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    return fake


class TestDuaSlotTakSalingMengisi:
    def test_klasifikasi_arsip_tak_pernah_berisi_kode_bawaan(self):
        assert pilih_klasifikasi(PETA, "umum", "Nota Dinas") == ""

    def test_slot_bawaan_hanya_diisi_kode_bawaan(self):
        nomor = bangun_nomor("{urut}/{kode_klasifikasi}/{kode_bawaan}/{tahun}",
                             3, "2026-08-19",
                             kode_klasifikasi="PL.02", kode_bawaan="UM.01")
        assert nomor == "003/PL.02/UM.01/2026"

    def test_mengubah_satu_tak_menggeser_yang_lain(self):
        """Inti "independent masing masing": keduanya boleh diubah sendiri."""
        pola = "{urut}/{kode_klasifikasi}/{kode_bawaan}"
        assert bangun_nomor(pola, 1, "2026-08-19",
                            kode_klasifikasi="HK.06", kode_bawaan="UM.01") \
            == "001/HK.06/UM.01"
        assert bangun_nomor(pola, 1, "2026-08-19",
                            kode_klasifikasi="PL.02", kode_bawaan="UM.01") \
            == "001/PL.02/UM.01"
        assert bangun_nomor(pola, 1, "2026-08-19",
                            kode_klasifikasi="PL.02", kode_bawaan="AB.09") \
            == "001/PL.02/AB.09"

    def test_kode_bawaan_tak_bocor_ke_slot_klasifikasi(self):
        """Kalau slot bawaan tak diminta, kode bawaan tak muncul di mana pun."""
        nomor = bangun_nomor("{kode_keamanan}-{urut}/{kode_klasifikasi}/{tahun}",
                             3, "2026-08-19",
                             kode_klasifikasi="", kode_bawaan="SATKER-D")
        assert "SATKER-D" not in nomor
        assert nomor == "B-003/2026"


class TestSlotBawaanDiLuarDeretPerANRI:
    def test_bukan_bagian_deret_baku(self):
        urut = [p["kunci"] for p in PLACEHOLDER_NOMOR]
        assert urut[:7] == ["kode_keamanan", "urut", "kode_klasifikasi",
                            "kode_unit", "bulan", "bulan_romawi", "tahun"]
        assert urut[7:] == ["kode_bawaan"]

    def test_menyisipkan_seluruh_chip_berurutan_tak_membawa_kode_bawaan(self):
        """Kalau slot bawaan diselipkan ke tengah deret, setiap orang yang
        memakai chip berurutan akan diam-diam mendapat kode bawaan di
        nomornya — persis penggabungan yang sedang dibereskan."""
        deret = [p["kunci"] for p in PLACEHOLDER_NOMOR
                 if p["kunci"] != "kode_bawaan"]
        template = "-".join("{" + k + "}" for k in deret)
        nomor = bangun_nomor(template, 3, "2026-08-19",
                             kode_klasifikasi="PL.02", kode_unit="OIKN",
                             kode_bawaan="SATKER-D")
        assert "SATKER-D" not in nomor


class TestKomposisiTakMenyentuhSlotBawaan:
    @pytest.mark.parametrize("pilih", ["keamanan_klasifikasi", "klasifikasi_depan",
                                       "keamanan_saja", "klasifikasi_saja", "tanpa"])
    def test_slot_bawaan_selamat_di_semua_komposisi(self, pilih):
        hasil = terapkan_komposisi("{urut}/{kode_bawaan}/{kode_unit}", pilih)
        assert "{kode_bawaan}" in hasil

    def test_komposisi_terbaca_tak_terganggu_slot_bawaan(self):
        assert komposisi_format("{urut}/{kode_bawaan}") == "tanpa"
        assert komposisi_format("{kode_keamanan}-{urut}/{kode_bawaan}") \
            == "keamanan_saja"


class TestPeringatanMemeriksaKeduanyaSendiri:
    def test_kode_bawaan_tak_meredam_peringatan_klasifikasi(self):
        pesan = peringatan_klasifikasi("{urut}/{kode_klasifikasi}", "UM.01", [])
        assert "{kode_klasifikasi}" in pesan

    def test_aturan_pemetaan_tak_meredam_peringatan_bawaan(self):
        pesan = peringatan_klasifikasi("{urut}/{kode_bawaan}", "", PETA)
        assert "{kode_bawaan}" in pesan


class TestChipDanValidatorSepakat:
    def test_setiap_chip_diterima_validator(self):
        """Chip yang disisipkan layar lalu ditolak validator sebagai
        "placeholder tak dikenal" membuat layar dan validator saling
        membantah — dan yang disalahkan penggunanya."""
        for ph in PLACEHOLDER_NOMOR:
            assert placeholder_tak_dikenal("{" + ph["kunci"] + "}") == [], ph

    def test_validator_tetap_menolak_yang_asing(self):
        assert placeholder_tak_dikenal("{kode_rahasia}") == ["kode_rahasia"]


class TestTakAdaPemanggilYangMenitipkanKodeBawaan:
    """Pemindai: tak boleh ada `pilih_klasifikasi(..., default=...)` tersisa.

    Parameter itu sudah dihapus, jadi pemanggil yang tertinggal akan meledak
    saat dijalankan — tetapi hanya pada jalur yang benar-benar dieksekusi uji.
    Jalur penerbitan nomor di BAST dan Pengadaan berjalan di balik centang
    opsional; pemindaian AST menagihnya tanpa perlu menjalankannya.
    """

    def _berkas_py(self):
        """Semua modul .py backend — routes DAN akar (persuratan_utils dsb).

        Pernah salah sekali dan mutasinya lolos: jalurnya ditulis
        "backend/routes" padahal AKAR sudah menunjuk ke backend, sehingga
        glob-nya menyapu direktori yang tak ada dan mengembalikan NOL berkas.
        Pemindai buta selalu melaporkan bersih. Karena itu jumlah temuannya
        ikut ditagih di bawah.
        """
        for sub in (AKAR / "routes", AKAR):
            for f in sorted(sub.glob("*.py")):
                yield f

    def test_pemindaiannya_benar_benar_menyapu_berkas(self):
        berkas = list(self._berkas_py())
        assert len(berkas) > 10, berkas
        assert any(f.name == "persuratan.py" for f in berkas)
        assert any(f.name == "bast.py" for f in berkas)
        assert any(f.name == "pengadaan.py" for f in berkas)

    def test_nol_pemanggil_dengan_default(self):
        pelanggar = []
        for f in self._berkas_py():
            pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for n in ast.walk(pohon):
                if not isinstance(n, ast.Call):
                    continue
                nama = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if nama != "pilih_klasifikasi":
                    continue
                for kw in n.keywords:
                    if kw.arg == "default":
                        pelanggar.append(f"{f.name}:{n.lineno}")
                if len(n.args) > 4:
                    pelanggar.append(f"{f.name}:{n.lineno} (argumen posisional ke-5)")
        assert pelanggar == []

    def test_pemindainya_benar_benar_melihat(self):
        """Pemindai yang salah nama fungsi akan selalu melaporkan nol."""
        pohon = ast.parse('pilih_klasifikasi(p, m, j, eksplisit="", default="X")')
        temuan = [kw.arg for n in ast.walk(pohon) if isinstance(n, ast.Call)
                  for kw in n.keywords]
        assert "default" in temuan

    def test_setiap_pemanggil_bangun_nomor_menyalurkan_kode_bawaan(self):
        """Slot `{kode_bawaan}` hanya berguna bila SETIAP jalur penerbitan
        mengisinya. Satu jalur yang lupa akan menerbitkan nomor dengan slot
        kosong — dan itu baru ketahuan dari nomor surat yang sudah resmi."""
        lupa, ketemu = [], 0
        for f in self._berkas_py():
            if f.name == "persuratan_utils.py":
                continue
            pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for n in ast.walk(pohon):
                if not isinstance(n, ast.Call):
                    continue
                nama = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if nama != "bangun_nomor":
                    continue
                ketemu += 1
                if not any(kw.arg == "kode_bawaan" for kw in n.keywords):
                    lupa.append(f"{f.name}:{n.lineno}")
        # Nol temuan = pemindainya tak menemukan satu pun pemanggil, dan itu
        # bukan kabar baik melainkan pemindai yang tak menyapu apa-apa.
        assert ketemu >= 5, f"hanya {ketemu} pemanggil bangun_nomor terlihat"
        assert lupa == []


class TestJalurBookingSungguhan:
    def test_surat_tanpa_aturan_terbit_TANPA_kode_bawaan(self, dbx):
        """Skenario persis dari tangkapan layar pemilik: kode bawaan terisi,
        tak ada aturan pemetaan, tak ada isian manual."""
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(rp.PengaturanIn(
                kode_klasifikasi_default="SATKER-D",
                format_nomor="{kode_keamanan}-{urut}/{kode_klasifikasi}/"
                             "{kode_unit}/{bulan_romawi}/{tahun}",
                kode_unit="OIKN"), user=ADMIN)
            hasil = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Uji pemisahan",
                                 tanggal_surat="2026-08-19"), user=ADMIN)
            assert "SATKER-D" not in hasil["nomor"]
            assert hasil["kode_klasifikasi"] == ""
        _jalan(skenario())

    def test_kode_bawaan_muncul_HANYA_bila_formatnya_meminta(self, dbx):
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(rp.PengaturanIn(
                kode_klasifikasi_default="SATKER-D",
                format_nomor="{kode_keamanan}-{urut}/{kode_bawaan}/"
                             "{kode_unit}/{bulan_romawi}/{tahun}",
                kode_unit="OIKN"), user=ADMIN)
            hasil = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Uji slot bawaan",
                                 tanggal_surat="2026-08-19"), user=ADMIN)
            assert "SATKER-D" in hasil["nomor"]
            # …dan klasifikasi arsip suratnya TETAP kosong. Kode bawaan ikut ke
            # nomor tanpa berpura-pura jadi klasifikasi arsip surat ini.
            assert hasil["kode_klasifikasi"] == ""
        _jalan(skenario())

    def test_klasifikasi_manual_tetap_menang_dan_tak_menyentuh_slot_bawaan(self, dbx):
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(rp.PengaturanIn(
                kode_klasifikasi_default="SATKER-D",
                format_nomor="{urut}/{kode_klasifikasi}/{kode_bawaan}/"
                             "{bulan_romawi}",
                kode_unit="OIKN"), user=ADMIN)
            hasil = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Uji manual", kode_klasifikasi="PL.02",
                                 tanggal_surat="2026-08-19"), user=ADMIN)
            assert hasil["kode_klasifikasi"] == "PL.02"
            assert "/PL.02/SATKER-D/" in hasil["nomor"]
        _jalan(skenario())

    def test_pratinjau_tak_pernah_menyebut_sumber_bawaan(self, dbx):
        """Kalimat "Klasifikasi: SATKER-D · kode bawaan pengaturan" itulah yang
        dikeluhkan — ia menamai kode bawaan sebagai klasifikasi arsip."""
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(rp.PengaturanIn(
                kode_klasifikasi_default="SATKER-D"), user=ADMIN)
            pra = await _unwrap(rp.pratinjau_nomor)(
                jenis_naskah="Laporan", modul="umum",
                tanggal_surat="2026-08-19", _user=ADMIN)
            assert pra["sumber_klasifikasi"] == "kosong"
            assert pra["kode_klasifikasi"] == ""
        _jalan(skenario())
