"""Pengunduh teks peraturan — manifes dan pengerok tautan PDF.

Permintaan pemilik: *"download semua referensi untuk memperkaya pustaka,
temukan hingga ke sumber lainnya jika terblokir untuk mengunduh sampai
pustaka kita lengkap."*

Lingkungan pengembangan tidak bisa menjangkau satu pun sumber peraturan —
gerbang egress menjawab 403 pada CONNECT untuk setiap host yang dicoba.
Pengunduhannya karena itu berjalan di runner GitHub Actions. Uji ini menjaga
bagian yang MURNI (manifes, pengerokan tautan, pemilihan berkas) supaya
kesalahan di sana ketahuan di sini, bukan setelah workflow berjalan delapan
menit dan pulang dengan tangan kosong.
"""
import importlib.util
import pathlib
import sys

import pytest

_JALUR = (pathlib.Path(__file__).resolve().parents[3]
          / "scripts" / "regulasi_sumber.py")
_spec = importlib.util.spec_from_file_location("regulasi_sumber", _JALUR)
rs = importlib.util.module_from_spec(_spec)
sys.modules["regulasi_sumber"] = rs
_spec.loader.exec_module(rs)


# ── Integritas manifes ─────────────────────────────────────────────────────

def test_setiap_entri_lengkap():
    for e in rs.MANIFES:
        for kunci in ("kode", "judul", "guna", "prioritas", "sumber"):
            assert e.get(kunci), f"{e.get('kode')}: {kunci} kosong"


def test_kode_unik_dan_aman_jadi_nama_berkas():
    """Kode dipakai langsung sebagai nama berkas — satu garis miring saja
    akan menulis ke luar direktori tujuan."""
    kode = [e["kode"] for e in rs.MANIFES]
    assert len(kode) == len(set(kode))
    for k in kode:
        assert k == k.lower()
        assert all(c.isalnum() or c == "-" for c in k), k


def test_prioritas_unik_dan_berurutan():
    p = sorted(e["prioritas"] for e in rs.MANIFES)
    assert p == list(range(1, len(rs.MANIFES) + 1))


def test_tak_ada_peraturan_yang_bersumber_tunggal():
    """URL JDIH berubah saat situsnya diperbarui; satu URL mati akan
    mematikan seluruh unduhan untuk peraturan itu.

    Ambangnya sengaja NOL, bukan "sedikit". Versi pertama manifes ini
    membiarkan enam peraturan bersumber tunggal — semuanya menunjuk ke
    jdih.kemenkeu.go.id atau peraturan.bpk.go.id, dua host yang pola
    URL-nya paling tidak pasti. Enam kegagalan yang bisa dicegah dengan
    satu pencarian tiap peraturan.
    """
    tunggal = [e["kode"] for e in rs.MANIFES if len(e["sumber"]) < 2]
    assert tunggal == [], f"bersumber tunggal: {tunggal}"


def test_ada_cermin_di_luar_dua_host_utama():
    """Kalau seluruh sumber sebuah peraturan ada di jdih.kemenkeu.go.id dan
    peraturan.bpk.go.id saja, satu gangguan di sisi Kemenkeu/BPK
    menjatuhkan semuanya sekaligus. Minimal satu cermin di luar keduanya."""
    utama = ("jdih.kemenkeu.go.id", "peraturan.bpk.go.id")
    kurus = [e["kode"] for e in rs.MANIFES
             if not any(all(h not in url for h in utama) for _, url in e["sumber"])]
    assert kurus == [], f"hanya bersandar pada Kemenkeu/BPK: {kurus}"


def test_semua_sumber_https_dan_jenisnya_dikenal():
    for e in rs.MANIFES:
        for jenis, url in e["sumber"]:
            assert jenis in ("pdf", "html"), f"{e['kode']}: jenis {jenis}"
            assert url.startswith("https://"), f"{e['kode']}: {url}"


def test_celah_terbesar_didahulukan():
    """Pemindahtanganan, penghapusan, dan pemanfaatan adalah rezim yang di
    registry syarat dokumen belum punya dasar pasal sama sekali. Kalau
    unduhan terputus di tengah, merekalah yang harus sudah masuk."""
    tiga_teratas = {e["kode"] for e in rs.MANIFES if e["prioritas"] <= 4}
    assert "pmk-111-2016-pemindahtanganan" in tiga_teratas
    assert "pmk-83-2016-pemusnahan-penghapusan" in tiga_teratas
    assert "pmk-115-2020-pemanfaatan" in tiga_teratas


# ── Pengerok tautan PDF ────────────────────────────────────────────────────

def test_tautan_relatif_dijadikan_absolut():
    html = '<a href="/download/abc.pdf">Unduh</a>'
    hasil = rs.tautan_pdf(html, "https://jdih.contoh.go.id/dok/x")
    assert hasil == ["https://jdih.contoh.go.id/download/abc.pdf"]


def test_lampiran_dikalahkan_batang_tubuh():
    """Halaman JDIH kerap memuat PDF lampiran; yang dicari batang tubuhnya.

    Kedua tautan sengaja dibuat SAMA PERSIS kecuali kata "lampiran" — dan
    yang berlampiran ditaruh LEBIH DULU. Versi awal uji ini membandingkan
    `/f/lampiran-i.pdf` dengan `/download/pmk-111.pdf`, sehingga yang kedua
    menang karena "download" dan "pmk", bukan karena penalti lampirannya.
    Mutasi yang mencabut penalti itu lolos tanpa terdeteksi.
    """
    html = ('<a href="/download/pmk-111-lampiran.pdf">L</a>'
            '<a href="/download/pmk-111.pdf">Batang tubuh</a>')
    hasil = rs.tautan_pdf(html, "https://jdih.contoh.go.id/dok/x")
    assert hasil[0].endswith("/download/pmk-111.pdf")


def test_iframe_dan_data_src_ikut_terbaca():
    """Sebagian JDIH menyematkan PDF lewat iframe, bukan tautan biasa."""
    html = '<iframe data-src="https://a.contoh.go.id/dok/pmk.pdf"></iframe>'
    assert rs.tautan_pdf(html, "https://jdih.contoh.go.id/x") == [
        "https://a.contoh.go.id/dok/pmk.pdf"]


def test_tautan_kembar_dibuang():
    html = '<a href="/a.pdf">1</a><a href="/a.pdf">2</a>'
    assert len(rs.tautan_pdf(html, "https://x.go.id/")) == 1


def test_halaman_tanpa_pdf_menghasilkan_daftar_kosong():
    assert rs.tautan_pdf("<p>tak ada apa-apa</p>", "https://x.go.id/") == []


def test_pdf_dengan_query_string_tetap_tertangkap():
    html = '<a href="/unduh?berkas=pmk.pdf&v=2">x</a>'
    hasil = rs.tautan_pdf(html, "https://x.go.id/")
    assert hasil and "pmk.pdf" in hasil[0]


# ── Alur unduh, dengan jaringan disulih ────────────────────────────────────

_PDF_KOSONG = b"%PDF-1.4 palsu"

#: Teks tiruan yang berbentuk NASKAH peraturan. Fixture alur unduh memakainya
#: alih-alih "A"*600: sejak ada `bukan_batang_tubuh`, teks asal-asalan ditolak
#: — dan memang seharusnya begitu.
_TEKS_NASKAH = (
    "Menimbang: a. bahwa ...\nMEMUTUSKAN:\nPasal 1\nDalam Peraturan ini "
    + "yang dimaksud dengan Barang Milik Negara adalah ... " * 20
)


@pytest.fixture()
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(rs.time, "sleep", lambda *_: None)


def test_sumber_kedua_dipakai_saat_yang_pertama_mati(monkeypatch, tanpa_jeda):
    panggil = []

    def _ambil(url):
        panggil.append(url)
        if url.endswith("satu.pdf"):
            raise OSError("host tak terjangkau")
        return _PDF_KOSONG, "application/pdf"

    monkeypatch.setattr(rs, "_ambil", _ambil)
    monkeypatch.setattr(rs, "ekstrak_teks", lambda b: (_TEKS_NASKAH, 12))
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/satu.pdf"),
                                  ("pdf", "https://x/dua.pdf")]})
    assert r["ok"] is True and r["url"].endswith("dua.pdf")
    assert len(panggil) == 2
    # Kegagalan yang pertama TETAP dicatat, bukan hilang karena akhirnya
    # berhasil — itulah yang memberi tahu URL mana yang perlu diganti.
    assert any("satu.pdf" in g for g in r["galat"])


def test_halaman_html_dikerok_dulu_baru_pdfnya_diambil(monkeypatch, tanpa_jeda):
    def _ambil(url):
        if url.endswith(".pdf"):
            return _PDF_KOSONG, "application/pdf"
        return b'<a href="/dok/pmk.pdf">unduh</a>', "text/html"

    monkeypatch.setattr(rs, "_ambil", _ambil)
    monkeypatch.setattr(rs, "ekstrak_teks", lambda b: (_TEKS_NASKAH, 3))
    r = rs.unduh_satu({"sumber": [("html", "https://jdih.x.go.id/dok/a")]})
    assert r["ok"] is True and r["url"] == "https://jdih.x.go.id/dok/pmk.pdf"


def test_pdf_hasil_pindai_tanpa_teks_DITOLAK(monkeypatch, tanpa_jeda):
    """Berkas .txt kosong yang tersimpan akan terlihat seperti bukti padahal
    tak memuat apa pun — kegagalan paling berbahaya di seluruh alur ini."""
    monkeypatch.setattr(rs, "_ambil", lambda u: (_PDF_KOSONG, "application/pdf"))
    monkeypatch.setattr(rs, "ekstrak_teks", lambda b: ("   \n  ", 80))
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/a.pdf")]})
    assert r["ok"] is False
    assert any("tanpa lapisan teks" in g for g in r["galat"])
    assert any("OCR" in g for g in r["galat"])


def test_balasan_html_pada_sumber_pdf_ditolak(monkeypatch, tanpa_jeda):
    """Situs yang mati kerap membalas halaman error 200, bukan 404."""
    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (b"<html>404</html>", "text/html"))
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/a.pdf")]})
    assert r["ok"] is False and any("bukan PDF" in g for g in r["galat"])


def test_semua_sumber_gagal_dilaporkan_satu_per_satu(monkeypatch, tanpa_jeda):
    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (_ for _ in ()).throw(OSError("mati")))
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/a.pdf"),
                                  ("html", "https://x/b")]})
    assert r["ok"] is False and len(r["galat"]) == 2


def test_galat_pypdf_tak_menghentikan_sumber_berikutnya(monkeypatch, tanpa_jeda):
    """pypdf melempar bermacam pengecualian; satu PDF rusak tak boleh
    membatalkan percobaan ke cermin berikutnya."""
    monkeypatch.setattr(rs, "_ambil", lambda u: (_PDF_KOSONG, "application/pdf"))
    urut = iter([RuntimeError("PDF rusak"), None])

    def _ekstrak(b):
        e = next(urut)
        if e:
            raise e
        return _TEKS_NASKAH, 5

    monkeypatch.setattr(rs, "ekstrak_teks", _ekstrak)
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/a.pdf"),
                                  ("pdf", "https://x/b.pdf")]})
    assert r["ok"] is True and r["url"].endswith("b.pdf")


# ── Manifes tak boleh kehilangan bukti yang sudah terkumpul ────────────────

def test_diagnosis_run_ini_tak_ditimpa_catatan_lama(tmp_path, monkeypatch,
                                                   tanpa_jeda):
    """KOREKSI (2026-09-01). Penjaga "pertahankan manifes lama" dulu
    mempertahankan entri APA PUN keadaannya — termasuk yang `berkas`-nya
    None. Akibatnya `percobaan_gagal` LAMA menimpa hasil percobaan kali ini,
    persis keterangan yang dibutuhkan untuk memperbaiki sumbernya.

    Pada unduhan ketiga hal itu benar-benar terjadi: PMK 111/2016 melaporkan
    kegagalan sumber yang sudah DICABUT dari manifes, sementara apa yang
    terjadi pada URL penggantinya hilang tanpa jejak. Satu putaran penuh
    terbuang.
    """
    import json

    tujuan = tmp_path / "regulasi"
    tujuan.mkdir()
    kode = rs.MANIFES[0]["kode"]
    (tujuan / "MANIFEST.json").write_text(json.dumps({"berkas": [{
        "kode": kode, "judul": "lama", "guna": "lama", "berkas": None,
        "percobaan_gagal": ["sumber-yang-sudah-dicabut: catatan lama"],
    }]}), encoding="utf-8")

    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (_ for _ in ()).throw(OSError("galat baru")))
    rs.main(["x", str(tujuan)])

    m = json.loads((tujuan / "MANIFEST.json").read_text(encoding="utf-8"))
    entri = next(b for b in m["berkas"] if b["kode"] == kode)
    gabung = " ".join(entri["percobaan_gagal"])
    assert "galat baru" in gabung, "diagnosis run ini harus tercatat"
    assert "sudah-dicabut" not in gabung, "catatan lama tak boleh menimpa"
    # Entri tanpa berkas ditulis ULANG dari manifes yang berlaku, bukan
    # disalin dari yang lama: judul/guna yang berubah harus ikut berubah,
    # dan `dipertahankan_dari` tak boleh muncul karena tak ada yang
    # dipertahankan.
    assert entri["judul"] == rs.MANIFES[0]["judul"], "judul lama tak boleh melekat"
    assert "dipertahankan_dari" not in entri


def test_berkas_dipertahankan_tetapi_diagnosisnya_diperbarui(tmp_path,
                                                            monkeypatch,
                                                            tanpa_jeda):
    """Saat berkasnya memang ada, provenansnya tetap utuh — tetapi
    `percobaan_gagal` diisi hasil KALI INI, bukan yang lama."""
    import json

    tujuan = tmp_path / "regulasi"
    tujuan.mkdir()
    kode = rs.MANIFES[0]["kode"]
    (tujuan / "MANIFEST.json").write_text(json.dumps({"berkas": [{
        "kode": kode, "berkas": f"{kode}.txt", "sha256": "abc123",
        "url": "https://asal.example/lama.pdf", "diunduh": "2026-08-31T00:00:00+00:00",
        "halaman": 58, "bytes": 900000,
        "percobaan_gagal": ["galat lama yang sudah tak relevan"],
    }]}), encoding="utf-8")

    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (_ for _ in ()).throw(OSError("galat baru")))
    rs.main(["x", str(tujuan)])

    m = json.loads((tujuan / "MANIFEST.json").read_text(encoding="utf-8"))
    e = next(b for b in m["berkas"] if b["kode"] == kode)
    assert e["sha256"] == "abc123" and e["berkas"] == f"{kode}.txt"
    assert e["dipertahankan_dari"] == "2026-08-31T00:00:00+00:00"
    assert any("galat baru" in g for g in e["percobaan_gagal"])
    assert not any("tak relevan" in g for g in e["percobaan_gagal"])


def test_penghitung_menggambarkan_keadaan_pustaka_bukan_satu_run(
        tmp_path, monkeypatch, tanpa_jeda):
    """KOREKSI. Unduhan ketiga melaporkan "berhasil 5, gagal 7" padahal
    sembilan naskah ada di direktori — pembacanya akan mengira pustakanya
    menyusut. Hasil per-run tetap dilaporkan, dengan namanya sendiri."""
    import json

    tujuan = tmp_path / "regulasi"
    tujuan.mkdir()
    kode = rs.MANIFES[0]["kode"]
    (tujuan / "MANIFEST.json").write_text(json.dumps({"berkas": [{
        "kode": kode, "berkas": f"{kode}.txt", "sha256": "abc",
        "diunduh": "2026-08-31T00:00:00+00:00",
    }]}), encoding="utf-8")
    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (_ for _ in ()).throw(OSError("mati")))
    rs.main(["x", str(tujuan)])

    m = json.loads((tujuan / "MANIFEST.json").read_text(encoding="utf-8"))
    # Satu berkas bertahan → pustaka memuat 1, bukan 0.
    assert m["berhasil"] == 1
    assert m["gagal"] == len(rs.MANIFES) - 1
    # Hasil run tetap terlaporkan terpisah: tak ada unduhan segar.
    assert m["unduhan_segar"] == 0
    assert m["unduhan_gagal"] == len(rs.MANIFES)


def test_manifes_lama_dipertahankan_saat_unduhan_gagal(tmp_path, monkeypatch,
                                                       tanpa_jeda):
    """Kegagalan jaringan sesaat tak boleh menghapus asal-usul berkas yang
    SUDAH pernah terunduh. Tanpa penjagaan ini, satu run yang kebetulan
    gagal akan mengganti seluruh manifes dengan daftar kegagalan — dan
    sha256 serta URL sumber berkas lama hilang selamanya, padahal berkas
    `.txt`-nya masih ada di direktori."""
    import json

    tujuan = tmp_path / "regulasi"
    tujuan.mkdir()
    kode = rs.MANIFES[0]["kode"]
    (tujuan / "MANIFEST.json").write_text(json.dumps({"berkas": [{
        "kode": kode, "judul": "lama", "guna": "lama",
        "berkas": f"{kode}.txt", "url": "https://asal.example/lama.pdf",
        "halaman": 58, "bytes": 900000, "sha256": "abc123",
    }]}), encoding="utf-8")

    monkeypatch.setattr(rs, "_ambil",
                        lambda u: (_ for _ in ()).throw(OSError("jaringan mati")))
    rs.main(["x", str(tujuan)])

    m = json.loads((tujuan / "MANIFEST.json").read_text(encoding="utf-8"))
    entri = next(b for b in m["berkas"] if b["kode"] == kode)
    assert entri["sha256"] == "abc123"
    assert entri["url"] == "https://asal.example/lama.pdf"
    assert entri["berkas"] == f"{kode}.txt"


def test_manifes_rusak_tidak_menggagalkan_seluruh_unduhan(tmp_path, monkeypatch,
                                                          tanpa_jeda):
    """MANIFEST.json yang korup (mis. run sebelumnya terpotong) harus
    diabaikan, bukan meledak — kalau tidak, satu berkas rusak mengunci
    seluruh pustaka."""
    tujuan = tmp_path / "regulasi"
    tujuan.mkdir()
    (tujuan / "MANIFEST.json").write_text("{bukan json", encoding="utf-8")
    monkeypatch.setattr(rs, "_ambil", lambda u: (b"%PDF-1.4", "application/pdf"))
    monkeypatch.setattr(rs, "ekstrak_teks", lambda b: (_TEKS_NASKAH, 4))
    assert rs.main(["x", str(tujuan)]) == 0
    assert (tujuan / f"{rs.MANIFES[0]['kode']}.txt").exists()


# ── Guard batang tubuh: paparan tentang peraturan ≠ peraturan ─────────────
#
# Lahir dari kegagalan nyata pada unduhan pertama. PMK 111/2016 kembali
# sebagai PAPARAN PELATIHAN DJKN berjudul sama: PDF sah, berlapis teks,
# ditautkan dari situs kementerian — lolos setiap guard yang ada. 29 halaman
# slide ber-bullet Wingdings tersimpan di direktori bukti, tampak persis
# seperti kutipan primer.

_NASKAH = """PERATURAN MENTERI KEUANGAN REPUBLIK INDONESIA
NOMOR 83/PMK.06/2016
Menimbang : a. bahwa dalam rangka mewujudkan akuntabilitas ...
MEMUTUSKAN:
Pasal 1
Dalam Peraturan Menteri ini yang dimaksud dengan ...
"""

_PAPARAN = """Pemindahtanganan Barang Milik Negara
Direktorat Jenderal Kekayaan Negara
Dasar Hukum Pengelolaan BMN
Ø Hibah/sumbangan
§ Penjualan
ü Pengguna Barang mengajukan permohonan
"""


def test_naskah_peraturan_diterima():
    assert rs.bukan_batang_tubuh(_NASKAH) == ""


def test_paparan_pelatihan_ditolak():
    sebab = rs.bukan_batang_tubuh(_PAPARAN)
    assert sebab
    assert "paparan" in sebab or "batang tubuh" in sebab


def test_ringkasan_tanpa_memutuskan_ditolak():
    """Sebagian ringkasan menyalin bagian "Menimbang" tetapi berhenti sebelum
    "MEMUTUSKAN" — satu penanda saja tak cukup."""
    teks = "Menimbang bahwa ... Peraturan ini mengatur Pasal 1 sampai Pasal 5."
    assert rs.bukan_batang_tubuh(teks)


def test_naskah_tanpa_pasal_bernomor_ditolak():
    """Kutipan konsiderans saja bukan batang tubuh."""
    teks = "Menimbang ... MEMUTUSKAN: Menetapkan Peraturan Menteri Keuangan."
    sebab = rs.bukan_batang_tubuh(teks)
    assert "pasal bernomor" in sebab


def test_teks_kosong_ditolak_bukan_meledak():
    assert rs.bukan_batang_tubuh("")
    assert rs.bukan_batang_tubuh(None)


def test_guard_menolak_di_alur_unduh_dan_lanjut_ke_sumber_berikutnya(
        monkeypatch, tanpa_jeda):
    """Paparan pada sumber pertama tak boleh menghentikan percobaan ke
    cermin berikutnya — justru di sanalah naskah aslinya berada."""
    monkeypatch.setattr(rs, "_ambil", lambda u: (_PDF_KOSONG, "application/pdf"))
    urut = iter([_PAPARAN + "x" * 600, _NASKAH + "y" * 600])
    monkeypatch.setattr(rs, "ekstrak_teks", lambda b: (next(urut), 29))
    r = rs.unduh_satu({"sumber": [("pdf", "https://x/paparan.pdf"),
                                  ("pdf", "https://x/naskah.pdf")]})
    assert r["ok"] is True and r["url"].endswith("naskah.pdf")
    assert any("batang tubuh" in g for g in r["galat"])


def test_sumber_paparan_pelatihan_dicabut_dari_manifes():
    """Sumber yang TERBUKTI mengembalikan paparan tak boleh tinggal di
    manifes hanya karena ia "sebuah sumber"."""
    semua = " ".join(u for e in rs.MANIFES for _, u in e["sumber"])
    assert "sibangkoman.pu.go.id" not in semua
