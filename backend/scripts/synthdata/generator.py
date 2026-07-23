"""Generator data sintetis aset BMN — digerakkan registry (adaptif).

Sumber kebenaran field = ``asset_fields.ASSET_SCALAR_FIELDS``. Setiap field
skalar aset punya "strategi" penghasil nilai di ``FIELD_STRATEGIES``. Karena
generator membaca daftar field dari registry yang sama dengan model/ekspor/
impor, data uji IKUT BERUBAH otomatis ketika field aplikasi bertambah —
inilah yang dijaga oleh ``tests/unit/test_synthdata_generator.py`` (drift
guard): menambah field di registry TANPA menambah strateginya akan
menggagalkan test, sehingga data uji selalu relevan dengan fitur terkini.

Sifat penting:
  • Deterministik    — ``seed`` sama → keluaran sama (repro di CI).
  • Bebas dependency — hanya pustaka standar (tak perlu Faker di CI).
  • Valid skema      — setiap record lolos ``AssetCreate`` (semua profil).
  • Realistis        — konteks OIKN/IKN (lihat ``valuebanks``).
  • Beranomali       — profil ``edge``/``mixed`` menyuntik kasus tepi.
"""
import os
import random
import sys
from datetime import date, timedelta

# Pastikan direktori backend ada di sys.path agar ``asset_fields`` &
# ``shared_utils`` bisa di-import baik saat dijalankan sebagai modul
# (``python -m scripts.synthdata``) maupun di bawah pytest.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from asset_fields import SCALAR_FIELD_NAMES  # noqa: E402

from . import valuebanks as vb  # noqa: E402
from .profiles import PROFIL, PROFIL_DEFAULT, maybe_anomali  # noqa: E402

# --- Daftar pilihan sah: ambil dari shared_utils bila tersedia (adaptif),
#     jatuh ke salinan lokal bila import gagal (mis. lingkungan tanpa env
#     backend). Mengambil dari aplikasi membuat data ikut valid saat opsi
#     aplikasi berubah. -----------------------------------------------------
try:
    from shared_utils import (  # noqa: E402
        VALID_CONDITIONS, VALID_INVENTORY_STATUSES, VALID_KLASIFIKASI,
        VALID_STATUSES, VALID_STIKER_SIZES, VALID_STIKER_STATUSES,
        VALID_SUB_KLASIFIKASI_ALL,
    )
except Exception:  # pragma: no cover - fallback pertahanan
    VALID_CONDITIONS = ["Baik", "Rusak Ringan", "Rusak Berat"]
    VALID_STATUSES = ["Aktif", "Idle", "Maintenance", "Nonaktif"]
    VALID_STIKER_STATUSES = ["Belum Terpasang", "Sudah Terpasang"]
    VALID_STIKER_SIZES = ["Kecil", "Sedang", "Besar"]
    VALID_INVENTORY_STATUSES = ["Belum Diinventarisasi", "Ditemukan",
                                "Tidak Ditemukan", "Berlebih", "Sengketa"]
    VALID_KLASIFIKASI = ["Kesalahan Pencatatan", "Tidak Ditemukan Lainnya"]
    VALID_SUB_KLASIFIKASI_ALL = ["Hilang / Dicuri", "Lainnya"]


# ─────────────────────────── helper penghasil nilai ───────────────────────────

def _nama_orang(rng, pakai_gelar=False):
    nama = f"{rng.choice(vb.NAMA_DEPAN)} {rng.choice(vb.NAMA_BELAKANG)}"
    if pakai_gelar:
        gd = rng.choice(vb.GELAR_DEPAN)
        gb = rng.choice(vb.GELAR_BELAKANG)
        nama = f"{(gd + ' ') if gd else ''}{nama}{(', ' + gb) if gb else ''}"
    return nama


def _nip(rng):
    # NIP ASN 18 digit: YYYYMMDD + YYYYMM + K + NNN (pola realistis, fiktif).
    thn_lahir = rng.randint(1975, 1998)
    bln, hari = rng.randint(1, 12), rng.randint(1, 28)
    thn_kerja = rng.randint(2005, 2022)
    bln_kerja = rng.randint(1, 12)
    kelamin = rng.choice([1, 2])
    urut = rng.randint(1, 20)
    return f"{thn_lahir}{bln:02d}{hari:02d}{thn_kerja}{bln_kerja:02d}{kelamin}{urut:03d}"


def _tanggal(rng, thn_min=2015, thn_max=2025):
    awal = date(thn_min, 1, 1)
    akhir = date(thn_max, 6, 30)
    delta = (akhir - awal).days
    return awal + timedelta(days=rng.randint(0, delta))


def _kode_barang(rng, kategori):
    gol = vb.KODE_GOLONGAN.get(kategori, "3")
    return (f"{gol}.{rng.randint(1, 20):02d}.{rng.randint(1, 15):02d}."
            f"{rng.randint(1, 30):02d}.{rng.randint(1, 999):03d}")


def _merek_untuk(rng, kategori, nama_barang):
    n = nama_barang.lower()
    if kategori == "Alat Angkutan" or "kendaraan" in n or "sepeda" in n:
        return rng.choice(vb.MEREK_KENDARAAN)
    if any(k in n for k in ("meja", "kursi", "lemari", "sofa", "rak",
                            "filing", "brankas", "whiteboard")):
        return rng.choice(vb.MEREK_MEBEL)
    if kategori in ("Tanah", "Gedung dan Bangunan",
                    "Jalan, Irigasi dan Jaringan"):
        return ""  # aset tak bermerek
    return rng.choice(vb.MEREK_ELEKTRONIK)


def _koordinat_ikn(rng):
    lat = rng.uniform(vb.IKN_LAT_MIN, vb.IKN_LAT_MAX)
    lng = rng.uniform(vb.IKN_LNG_MIN, vb.IKN_LNG_MAX)
    return f"{lat:.6f}", f"{lng:.6f}"


# ───────────── konteks aset koheren (dihitung sekali per record) ─────────────

def _bangun_konteks(rng, index):
    """Tentukan inti aset yang saling konsisten sebelum mengisi tiap field."""
    kategori = rng.choice(vb.KATEGORI)
    daftar_barang = vb.BARANG_PER_KATEGORI.get(
        kategori, sum(vb.BARANG_PER_KATEGORI.values(), []))
    barang = rng.choice(daftar_barang)
    tgl_beli = _tanggal(rng)
    melekat = rng.choice(["Individual", "Jabatan", "Operasional"])
    inv = rng.choices(
        VALID_INVENTORY_STATUSES,
        weights=[38, 34, 12, 8, 8][:len(VALID_INVENTORY_STATUSES)], k=1)[0]
    lat, lng = _koordinat_ikn(rng)
    return {
        "index": index,
        "kategori": kategori,
        "barang": barang,
        "tgl_beli": tgl_beli,
        "melekat": melekat,
        "inv": inv,
        "lat": lat,
        "lng": lng,
        "nama_pengguna": _nama_orang(rng),
        "nip": _nip(rng),
    }


# ───────────────────────── strategi per field registry ─────────────────────────
# Setiap entri: (jenis_anomali, fungsi(rng, ctx) -> str).
#   jenis ∈ {teks, tanggal, angka, koordinat} → memilih bank anomali yang pas.

def _s(jenis, fn):
    return {"jenis": jenis, "fn": fn}


FIELD_STRATEGIES = {
    "asset_code": _s("teks", lambda r, c: _kode_barang(r, c["kategori"])),
    "NUP": _s("angka", lambda r, c: str(r.randint(1, 9999))),
    "asset_name": _s("teks", lambda r, c: c["barang"]),
    "category": _s("teks", lambda r, c: c["kategori"]),
    "brand": _s("teks", lambda r, c: _merek_untuk(r, c["kategori"], c["barang"])),
    "model": _s("teks", lambda r, c: f"Tipe-{r.choice('ABCXYZ')}{r.randint(100, 999)}"),
    "kode_register": _s("teks", lambda r, c: f"REG{r.randint(10**5, 10**6 - 1)}"),
    "serial_number": _s("teks", lambda r, c: f"SN{r.randint(10**7, 10**8 - 1)}"),
    "purchase_date": _s("tanggal", lambda r, c: c["tgl_beli"].isoformat()),
    "purchase_price": _s("angka", lambda r, c: str(r.randint(1, 500) * 100_000)),
    "location": _s("teks", lambda r, c: r.choice(vb.LOKASI)),
    "eselon1": _s("teks", lambda r, c: r.choice(vb.ESELON1)),
    "eselon2": _s("teks", lambda r, c: r.choice(vb.ESELON2)),
    "user": _s("teks", lambda r, c: c["nama_pengguna"]),
    "pengguna_melekat_ke": _s("teks", lambda r, c: c["melekat"]),
    "pengguna_jabatan": _s("teks", lambda r, c: (
        r.choice(vb.JABATAN) if c["melekat"] == "Jabatan" else "")),
    "pengguna_nip": _s("angka", lambda r, c: (
        c["nip"] if c["melekat"] != "Operasional" else "")),
    "operasional_jenis": _s("teks", lambda r, c: (
        r.choice(["Kegiatan/Acara/Kebutuhan", "Ruangan"])
        if c["melekat"] == "Operasional" else "")),
    "nomor_bast": _s("teks", lambda r, c: (
        f"BAST-{r.randint(1, 999):03d}/OIKN/{c['tgl_beli'].year}"
        if r.random() < 0.5 else "")),
    "condition": _s("teks", lambda r, c: r.choice(VALID_CONDITIONS)),
    "status": _s("teks", lambda r, c: r.choice(VALID_STATUSES)),
    "nomor_spm": _s("teks", lambda r, c: (
        f"SPM-{r.randint(1, 9999):04d}/{c['tgl_beli'].year}"
        if r.random() < 0.5 else "")),
    "perolehan_dari_nama": _s("teks", lambda r, c: (
        r.choice(vb.SUPPLIER) if r.random() < 0.6 else "")),
    "nomor_kontrak": _s("teks", lambda r, c: (
        f"KTR-{r.randint(1, 999):03d}/PPK/{c['tgl_beli'].year}"
        if r.random() < 0.5 else "")),
    "cara_bayar_kontrak": _s("teks", lambda r, c: (
        r.choice(["LS", "UP", "TUP", "Kontraktual", "Sekaligus"])
        if r.random() < 0.5 else "")),
    "nomor_bukti_perolehan": _s("teks", lambda r, c: (
        f"BAST/{r.randint(1, 999):03d}" if r.random() < 0.4 else "")),
    "supplier": _s("teks", lambda r, c: (
        r.choice(vb.SUPPLIER) if r.random() < 0.6 else "")),
    "notes": _s("teks", lambda r, c: (
        r.choice(["", "", "Kondisi baik saat pemeriksaan.",
                  "Perlu pemeliharaan berkala.",
                  "Ditempatkan di ruang kerja lantai 2.",
                  "Hasil pengadaan tahun berjalan."]))),
    "stiker_status": _s("teks", lambda r, c: r.choice(VALID_STIKER_STATUSES)),
    "stiker_ukuran": _s("teks", lambda r, c: (
        r.choice(VALID_STIKER_SIZES) if r.random() < 0.5 else "")),
    "inventory_status": _s("teks", lambda r, c: c["inv"]),
    "klasifikasi_tidak_ditemukan": _s("teks", lambda r, c: (
        r.choice(VALID_KLASIFIKASI) if c["inv"] == "Tidak Ditemukan" else "")),
    "sub_klasifikasi": _s("teks", lambda r, c: (
        r.choice(VALID_SUB_KLASIFIKASI_ALL) if c["inv"] == "Tidak Ditemukan" else "")),
    "uraian_tidak_ditemukan": _s("teks", lambda r, c: (
        "Aset tidak ditemukan di lokasi pencatatan saat opname fisik."
        if c["inv"] == "Tidak Ditemukan" else "")),
    "tindak_lanjut": _s("teks", lambda r, c: (
        r.choice(["Usulan penghapusan", "Pelacakan ulang",
                  "Koreksi pencatatan SIMAK", "Menunggu keputusan pimpinan"])
        if c["inv"] == "Tidak Ditemukan" else "")),
    "koordinat_latitude": _s("koordinat", lambda r, c: (
        c["lat"] if c["inv"] in ("Ditemukan", "Berlebih", "Sengketa") else "")),
    "koordinat_longitude": _s("koordinat", lambda r, c: (
        c["lng"] if c["inv"] in ("Ditemukan", "Berlebih", "Sengketa") else "")),
    "kronologis": _s("teks", lambda r, c: (
        "Ditemukan saat penelusuran fisik; dicatat sebagai temuan."
        if c["inv"] in ("Berlebih", "Sengketa") else "")),
    "keterangan_berlebih": _s("teks", lambda r, c: (
        "Aset fisik ada namun belum tercatat di SIMAK-BMN."
        if c["inv"] == "Berlebih" else "")),
    "asal_usul_berlebih": _s("teks", lambda r, c: (
        r.choice(["Hibah belum dicatat", "Pengadaan belum dibukukan",
                  "Transfer masuk belum diproses"])
        if c["inv"] == "Berlebih" else "")),
    "nomor_perkara": _s("teks", lambda r, c: (
        f"PDT.G/{r.randint(1, 500)}/{c['tgl_beli'].year}/PN.Bpp"
        if c["inv"] == "Sengketa" else "")),
    "pihak_bersengketa": _s("teks", lambda r, c: (
        r.choice(["Pihak ketiga (masyarakat)", "Badan usaha swasta",
                  "Pemerintah daerah"]) if c["inv"] == "Sengketa" else "")),
    "keterangan_sengketa": _s("teks", lambda r, c: (
        "Terdapat klaim kepemilikan; proses hukum berjalan."
        if c["inv"] == "Sengketa" else "")),
    "garansi_hingga": _s("tanggal", lambda r, c: (
        (c["tgl_beli"] + timedelta(days=365 * r.randint(1, 5))).isoformat()
        if r.random() < 0.4 else "")),
    "garansi_jenis": _s("teks", lambda r, c: (
        r.choice(["Resmi Distributor", "Toko", "Internasional"])
        if r.random() < 0.4 else "")),
}


# ───────────────────────────── API publik ─────────────────────────────

def generate_asset(rng, profil_cfg, index=0, activity_id=None):
    """Hasilkan satu record aset (dict siap POST /api/assets)."""
    ctx = _bangun_konteks(rng, index)
    rasio = profil_cfg.get("rasio_anomali", 0.0)
    record = {}
    for name in SCALAR_FIELD_NAMES:
        strat = FIELD_STRATEGIES.get(name)
        if strat is None:
            # Field baru di registry belum punya strategi — jangan crash;
            # isi placeholder. (test_synthdata_generator menagih strateginya.)
            record[name] = ""
            continue
        nilai = strat["fn"](rng, ctx)
        anom = maybe_anomali(rng, strat["jenis"], rasio)
        record[name] = anom if anom is not None else nilai
    if activity_id is not None:
        record["activity_id"] = activity_id
    return record


def generate_assets(count, seed=42, profile=PROFIL_DEFAULT, activity_id=None):
    """Hasilkan ``count`` record aset. Deterministik terhadap ``seed``.

    Profil ``edge``/``mixed`` dapat menyuntik duplikat (asset_code, NUP) untuk
    menguji jalur keunikan di server.
    """
    if profile not in PROFIL:
        raise ValueError(f"Profil tak dikenal: {profile!r}. Pilih dari {list(PROFIL)}")
    cfg = PROFIL[profile]
    rng = random.Random(seed)
    records = []
    for i in range(count):
        rec = generate_asset(rng, cfg, index=i, activity_id=activity_id)
        # Duplikasi sengaja (uji keunikan) untuk sebagian kecil record.
        if (cfg.get("izinkan_duplikat") and records and rng.random() < 0.02):
            korban = rng.choice(records)
            rec["asset_code"] = korban["asset_code"]
            rec["NUP"] = korban["NUP"]
        records.append(rec)
    return records


def generate_pegawai(count, seed=42):
    """Record Master Pegawai ringkas (nama, NIP, jabatan, unit)."""
    rng = random.Random(seed + 1)
    out = []
    for _ in range(count):
        out.append({
            "nama": _nama_orang(rng, pakai_gelar=True),
            "nip": _nip(rng),
            "jabatan": rng.choice(vb.JABATAN),
            "eselon1": rng.choice(vb.ESELON1),
            "eselon2": rng.choice(vb.ESELON2),
            "status_kepegawaian": rng.choice(["PNS", "PPPK", "Non-ASN"]),
        })
    return out


def generate_satker(count=None, seed=42):
    """Record satker (nama + kode 6 digit + kode lengkap 20 digit fiktif)."""
    rng = random.Random(seed + 2)
    base = list(vb.SATKER)
    if count:
        base = [rng.choice(vb.SATKER) for _ in range(count)]
    out = []
    for nama, kode6 in base:
        kode20 = kode6 + "".join(str(rng.randint(0, 9)) for _ in range(14))
        out.append({"nama": nama, "kode_satker": kode6, "kode_satker_lengkap": kode20})
    return out


def generate_activity(count, seed=42):
    """Record kegiatan inventarisasi realistis."""
    rng = random.Random(seed + 3)
    out = []
    for _ in range(count):
        tahun = rng.randint(2023, 2025)
        tpl = rng.choice(vb.NAMA_KEGIATAN)
        nama = tpl.format(sem=rng.choice(["I", "II"]), tahun=tahun,
                          tw=rng.choice(["I", "II", "III", "IV"]),
                          eselon=rng.choice(vb.ESELON1))
        out.append({
            "name": nama,
            "tahun": tahun,
            "eselon1": rng.choice(vb.ESELON1),
        })
    return out


PROFIL_TERSEDIA = tuple(PROFIL.keys())
