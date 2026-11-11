"""Logika MURNI direktori pegawai luar: instansi eksternal & pihak ketiga.

Rencana: `docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md` (PGW-01; kode 5.6 dan
invarian 5.7). Dasar regulasi: `docs/PUSTAKA-REGULASI-BMN.md` §2.4d.

Modul ini tidak menyentuh database dan belum punya pemanggil. Ia hanya
memutuskan bentuk dokumen: kelompok, tataran (pusat/daerah), jenjang daerah,
field yang dinonaktifkan per kelompok, dan aturan penampungan agar instansi
dan satker tidak tercampur.

Ketergantungan satu arah: modul luar boleh membaca modul internal
(`pegawai_utils`, `pejabat_utils`), modul internal tidak pernah membaca
modul ini.
"""
import re

from pegawai_utils import validate_pegawai

# ── Kode referensi (5.6, dikunci PGW-00) ───────────────────────────────────
KELOMPOK_LUAR = {"eksternal": "Instansi Eksternal", "pihak_ketiga": "Pihak Ketiga"}

TATARAN_EKSTERNAL = {
    "pusat": "Pusat (Kementerian/Lembaga)",
    "daerah": "Daerah (Pemda)",
}

JENIS_INSTANSI = {
    "eksternal": {
        # Mencakup lembaga negara, LPNK, lembaga nonstruktural, TNI/Polri
        # (keputusan pemilik K13a).
        "kementerian_lembaga": "Kementerian/Lembaga",
        "pemerintah_provinsi": "Pemerintah Provinsi",
        "pemerintah_kabkota": "Pemerintah Kabupaten/Kota",
        "pemerintah_desa": "Pemerintah Desa",
    },
    "pihak_ketiga": {
        "bumn": "Badan Usaha Milik Negara",
        "bumd": "Badan Usaha Milik Daerah",
        "bumdes": "Badan Usaha Milik Desa",
        "badan_usaha_swasta": "Badan Usaha Swasta",
        "satuan_pendidikan_swasta": "Satuan Pendidikan Swasta",
        "koperasi": "Koperasi",
        "yayasan": "Yayasan",
        "badan_hukum_lain": "Badan Hukum/Lembaga Lain (bukan pengguna anggaran)",
        "kelompok_masyarakat": "Kelompok Masyarakat/Ormas",
        "perorangan": "Perorangan",
        "lembaga_internasional": "Pemerintah Negara Lain/Organisasi Internasional",
        "lainnya": "Lainnya",
    },
}

# Satu-satunya penentu tataran (invarian 11).
TATARAN_DARI_JENIS = {
    "kementerian_lembaga": "pusat",                                      # K13a
    "pemerintah_provinsi": "daerah",
    "pemerintah_kabkota": "daerah",
    "pemerintah_desa": "daerah",                                         # K13c
}

# Jenis daerah → jenis induk yang sah (None = tidak berinduk).
INDUK_DAERAH = {
    "pemerintah_provinsi": None,
    "pemerintah_kabkota": "pemerintah_provinsi",
    "pemerintah_desa": "pemerintah_kabkota",
}

KUNCI_IKON = ("internal", "eksternal_pusat", "eksternal_daerah", "pihak_ketiga")

PERAN_INSTANSI = {
    "pengguna_sementara": "Pengguna sementara BMN",
    "peminjam_pakai": "Peminjam pakai",
    "penyewa": "Penyewa",
    "mitra_kerja_sama": "Mitra KSP/BGS-BSG/KSPI/KETUPI",
    "pengoperasi": "Mengoperasikan BMN (pihak lain)",
    "penerima_pemindahtanganan": "Penerima pemindahtanganan",
    "penyedia": "Penyedia barang/jasa",
    "pelaksana_pemeliharaan": "Pelaksana pemeliharaan",
    "pendamping": "Tim pendamping/peneliti",
    "lainnya": "Lainnya",
}

KAPASITAS_BERTINDAK = {
    "pengurus_berwenang": "Pengurus yang berwenang mewakili badan",
    "penerima_kuasa": "Penerima kuasa",
    "petugas": "Petugas/karyawan (bukan wakil badan)",
    "diri_sendiri": "Bertindak untuk diri sendiri",
}

DASAR_KEWENANGAN = {
    "anggaran_dasar": "Anggaran dasar/akta",
    "surat_kuasa": "Surat kuasa",
    "surat_tugas": "Surat tugas/penunjukan",
    "tidak_ada": "Tidak ada",
}

# Kapasitas yang mewakili badan; keduanya harus bisa menunjukkan dasarnya.
KAPASITAS_WAKIL_BADAN = frozenset({"pengurus_berwenang", "penerima_kuasa"})

LABEL_TINGKAT = {
    "eksternal_pusat": {"instansi": "Kementerian/Lembaga", "satker": "Satker",
                        "level": "Eselon"},
    "eksternal_daerah": {"instansi": "Pemda",                            # K12
                         "satker": "Perangkat Daerah", "level": "Eselon"},
    "pihak_ketiga": {"instansi": "Badan/Pihak", "satker": "Unit/Cabang",
                     "level": "Tingkat"},
}

# ── Field per kelompok (3.7) ───────────────────────────────────────────────
# 3.7d — data pribadi tanpa keperluan BMN; tidak dikumpulkan bagi kedua
# kelompok luar (keputusan pemilik K8; UU 27/2022 Ps. 16(2) huruf a).
FIELD_PRIBADI_LUAR = ("tempat_lahir", "agama", "status_perkawinan",
                      "pendidikan_terakhir", "npwp", "nama_bank", "no_rekening")

# 3.7c — persis daftarnya, dikelompokkan seperti di rencana.
_FIELD_KHUSUS_ASN = (
    "pangkat_golongan", "kategori_pegawai", "jenis_jabatan", "eselon",
    "jenis_pelaksana", "jabatan_pelaksana", "tmt_jabatan",
    "tanggal_akhir_jabatan", "status_pegawai_satker",
    "status_pegawai_instansi", "kode_satker_lengkap", "unit_organisasi",
)
_FIELD_TENAGA_SATKER = ("sub_kategori_non_asn", "jenis_kontrak_non_asn",
                        "perusahaan_penyedia")
_FIELD_AHLI_WARIS = ("ahli_waris_nama", "ahli_waris_hubungan",
                     "ahli_waris_kontak", "pemberitahuan_ahli_waris_tanggal",
                     "pemberitahuan_ahli_waris_nomor")
_FIELD_KONTRAK = ("nomor_kontrak", "tgl_mulai_kontrak", "tgl_selesai_kontrak")

FIELD_NONAKTIF = {
    "eksternal": FIELD_PRIBADI_LUAR,
    "pihak_ketiga": (_FIELD_KHUSUS_ASN + _FIELD_TENAGA_SATKER
                     + FIELD_PRIBADI_LUAR + _FIELD_AHLI_WARIS + _FIELD_KONTRAK),
}

FIELD_KHUSUS_PIHAK_KETIGA = ("kapasitas_bertindak", "dasar_kewenangan_jenis",
                             "dasar_kewenangan_nomor", "dasar_kewenangan_tanggal")

FIELD_KHUSUS_BADAN = ("nomor_induk", "npwp", "dasar_pendirian_nomor",
                      "dasar_pendirian_tanggal", "badan_penyelenggara")

FIELD_ESELON = tuple(f"eselon{n}" for n in range(1, 6))

FIELD_JENJANG = ("provinsi_id", "provinsi_nama", "kabkota_id", "kabkota_nama")

# Sebutan field yang dimanfaatkan ulang (3.7b). Nama field tetap.
LABEL_FIELD = {
    "pihak_ketiga": {
        "nip": "NIK",
        "jabatan": "Jabatan pada badan",
        "alamat": "Alamat korespondensi",
        "eselon1": "Tingkat I", "eselon2": "Tingkat II", "eselon3": "Tingkat III",
        "eselon4": "Tingkat IV", "eselon5": "Tingkat V",
        "unit_kerja": "Unit pada badan",
    },
}

_TGL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _s(nilai) -> str:
    return str(nilai or "").strip()


# ── Nama kunci (anti-ganda) ────────────────────────────────────────────────
# Singkatan bentuk usaha yang ditulis berbeda-beda di depan atau belakang
# nama. Sengaja TIDAK memuat "koperasi"/"yayasan": keduanya pembeda nama
# yang sah ("Koperasi Maju" dan "Yayasan Maju" adalah dua badan), dan nama
# kunci dipakai indeks unik.
_BENTUK_BADAN = ("pt", "persero", "tbk", "cv", "ud", "fa", "firma")
_RE_BUKAN_HURUF = re.compile(r"[^0-9a-z]+")


def nama_kunci(nama) -> str:
    """Bentuk pembanding nama instansi/satker: huruf kecil, tanpa tanda baca,
    spasi tunggal, dan tanpa singkatan bentuk badan di depan/belakang.

    `"PT. Telkom Indonesia"` dan `"Telkom  Indonesia, PT"` sama. Kata bentuk
    badan di TENGAH nama dibiarkan, karena di sana ia bagian dari nama.
    """
    kata = _RE_BUKAN_HURUF.sub(" ", _s(nama).lower()).split()
    while kata and kata[0] in _BENTUK_BADAN:
        kata.pop(0)
    while kata and kata[-1] in _BENTUK_BADAN:
        kata.pop()
    return " ".join(kata)


# ── Kelompok, tataran, jenjang ─────────────────────────────────────────────
def jenis_cocok(kelompok, jenis) -> bool:
    return _s(jenis) in JENIS_INSTANSI.get(_s(kelompok), {})


def tataran_dari_jenis(kelompok, jenis) -> str:
    """Tataran eksternal dari jenisnya; kosong untuk pihak ketiga dan jenis
    yang tak dikenal (invarian 11)."""
    if _s(kelompok) != "eksternal":
        return ""
    return TATARAN_DARI_JENIS.get(_s(jenis), "")


def kunci_ikon(kelompok, tataran="") -> str:
    """Salah satu KUNCI_IKON. Kelompok kosong/tak dikenal → internal."""
    k = _s(kelompok)
    if k == "pihak_ketiga":
        return "pihak_ketiga"
    if k == "eksternal":
        return "eksternal_daerah" if _s(tataran) == "daerah" else "eksternal_pusat"
    return "internal"


def periksa_jenjang_daerah(doc, induk=None) -> list:
    """Invarian 12 untuk SATU instansi terhadap calon induknya.

    `induk` adalah dokumen instansi yang ditunjuk `induk_id` (atau None bila
    tak ditemukan/kosong). Lingkaran rantai diperiksa pemanggil yang punya
    akses ke seluruh rantai; di sini cukup larangan menunjuk diri sendiri.
    """
    d = doc or {}
    jenis = _s(d.get("jenis"))
    induk_id = _s(d.get("induk_id"))
    errors = []
    if jenis not in INDUK_DAERAH:
        if induk_id:
            errors.append("Hanya pemerintah kabupaten/kota dan desa yang berinduk")
        return errors
    jenis_induk = INDUK_DAERAH[jenis]
    if jenis_induk is None:
        if induk_id:
            errors.append("Pemerintah provinsi tidak berinduk")
        return errors
    label_induk = JENIS_INSTANSI["eksternal"][jenis_induk]
    if not induk_id:
        errors.append(f"{JENIS_INSTANSI['eksternal'][jenis]} wajib berinduk "
                      f"{label_induk}")
        return errors
    if induk_id == _s(d.get("id")):
        errors.append("Instansi tidak boleh menjadi induk dirinya sendiri")
        return errors
    if not induk:
        errors.append(f"{label_induk} induk belum tercatat")
        return errors
    if _s(induk.get("jenis")) != jenis_induk:
        errors.append(f"Induk harus berjenis {label_induk}")
    return errors


def salinan_jenjang(doc, induk=None) -> dict:
    """Salinan provinsi_*/kabkota_* untuk sebuah instansi dari induknya.

    Provinsi menyalin dirinya sendiri sebagai provinsi; kab/kota menyalin
    provinsi dari induknya dan dirinya sebagai kab/kota; desa menyalin
    kab/kota induknya beserta provinsi yang sudah tersalin pada induk itu.
    Selain daerah → semua kosong. Hasil selalu string, tidak pernah None.
    """
    d = doc or {}
    i = induk or {}
    jenis = _s(d.get("jenis"))
    kosong = {k: "" for k in FIELD_JENJANG}
    if jenis == "pemerintah_provinsi":
        return {**kosong, "provinsi_id": _s(d.get("id")),
                "provinsi_nama": _s(d.get("nama"))}
    if jenis == "pemerintah_kabkota":
        return {**kosong, "provinsi_id": _s(i.get("id")),
                "provinsi_nama": _s(i.get("nama")),
                "kabkota_id": _s(d.get("id")), "kabkota_nama": _s(d.get("nama"))}
    if jenis == "pemerintah_desa":
        return {"provinsi_id": _s(i.get("provinsi_id")),
                "provinsi_nama": _s(i.get("provinsi_nama")),
                "kabkota_id": _s(i.get("id")), "kabkota_nama": _s(i.get("nama"))}
    return kosong


# ── Instansi & satker ──────────────────────────────────────────────────────
def validate_instansi_luar(doc) -> list:
    d = doc or {}
    errors = []
    kelompok = _s(d.get("kelompok"))
    jenis = _s(d.get("jenis"))
    if kelompok not in KELOMPOK_LUAR:
        errors.append("Kelompok harus Instansi Eksternal atau Pihak Ketiga")
    elif not jenis:
        errors.append("Jenis instansi wajib diisi")
    elif not jenis_cocok(kelompok, jenis):
        errors.append(f"Jenis instansi tidak cocok dengan kelompok "
                      f"{KELOMPOK_LUAR[kelompok]}")
    if not _s(d.get("nama")):
        errors.append("Nama instansi wajib diisi")
    for p in d.get("peran") or []:
        if _s(p) not in PERAN_INSTANSI:
            errors.append(f"Peran instansi tidak dikenal: {p}")
    tgl = _s(d.get("dasar_pendirian_tanggal"))
    if tgl and not _TGL_RE.match(tgl[:10]):
        errors.append("Tanggal dasar pendirian harus format YYYY-MM-DD")
    return errors


def bersihkan_instansi_luar(payload) -> dict:
    """Dokumen instansi yang disimpan: field turunan dihitung ulang, field
    milik kelompok lain dikosongkan. Induk & salinan jenjang diisi pemanggil
    lewat `salinan_jenjang` sesudah induknya dibaca."""
    p = dict(payload or {})
    kelompok = _s(p.get("kelompok"))
    jenis = _s(p.get("jenis"))
    p["kelompok"] = kelompok
    p["jenis"] = jenis
    p["nama"] = _s(p.get("nama"))
    p["nama_kunci"] = nama_kunci(p["nama"])
    p["tataran"] = tataran_dari_jenis(kelompok, jenis)
    p["kode_referensi"] = _s(p.get("kode_referensi"))
    if jenis not in INDUK_DAERAH or INDUK_DAERAH[jenis] is None:
        p["induk_id"] = ""
    else:
        p["induk_id"] = _s(p.get("induk_id"))
    p["peran"] = sorted({_s(x) for x in (p.get("peran") or []) if _s(x)})
    if kelompok != "pihak_ketiga":
        for f in FIELD_KHUSUS_BADAN:
            p[f] = ""
    else:
        for f in FIELD_KHUSUS_BADAN:
            p[f] = _s(p.get(f))
    p["wadah"] = bool(p.get("wadah")) and jenis == "perorangan"
    return p


def validate_satker_luar(doc) -> list:
    d = doc or {}
    errors = []
    if not _s(d.get("instansi_id")):
        errors.append("Satker wajib berada di satu instansi")
    if not _s(d.get("nama_satker")):
        errors.append("Nama satker wajib diisi")
    es = _s(d.get("eselon_satker"))
    if es and es not in {str(n) for n in range(1, 6)}:
        errors.append("Eselon satker harus 1–5")
    return errors


def bersihkan_satker_luar(payload, instansi=None) -> dict:
    """Satker luar menyalin kelompok, tataran, jenis, nama instansi, dan
    salinan jenjangnya dari instansi induk — tidak pernah dari klien
    (aturan penampungan 2 dan 4). Kunci `kode_satker` dibuang: tak ada
    dokumen luar yang membawanya (invarian 6)."""
    p = dict(payload or {})
    i = instansi or {}
    p["nama_satker"] = _s(p.get("nama_satker"))
    p["nama_kunci"] = nama_kunci(p["nama_satker"])
    p["kode_luar"] = _s(p.get("kode_luar"))
    p.pop("kode_satker", None)
    if i:
        p["instansi_id"] = _s(i.get("id"))
        p["instansi_nama"] = _s(i.get("nama"))
        p["kelompok"] = _s(i.get("kelompok"))
        p["jenis"] = _s(i.get("jenis"))
        p["tataran"] = tataran_dari_jenis(p["kelompok"], p["jenis"])
        for f in FIELD_JENJANG:
            p[f] = _s(i.get(f))
    if p.get("kelompok") != "eksternal":
        p["kode_satker_lengkap"] = ""
    return p


# ── Orang luar ─────────────────────────────────────────────────────────────
def sesuaikan_orang_luar(doc, kelompok, jenis_instansi) -> dict:
    """Bentuk dokumen orang luar menurut kelompok & jenis instansinya.

    eksternal    : tujuh field pribadi + field khusus pihak ketiga dikosongkan;
                   sisanya (kontrak, pangkat, eselon) utuh — sama dengan internal.
    pihak_ketiga : status_kepegawaian dipaksa non_asn; seluruh field 3.7c
                   dikosongkan.
    perorangan   : kapasitas dipaksa diri_sendiri; eselon1..5 dan unit kosong.
    Kunci `kode_satker` dibuang — ia kunci isolasi INTERNAL; tak ada dokumen
    luar yang membawanya (invarian 6).
    """
    d = dict(doc or {})
    k = _s(kelompok)
    for f in FIELD_NONAKTIF.get(k, ()):
        d[f] = ""
    if k == "eksternal":
        for f in FIELD_KHUSUS_PIHAK_KETIGA:
            d[f] = ""
    elif k == "pihak_ketiga":
        d["status_kepegawaian"] = "non_asn"
        for f in FIELD_KHUSUS_PIHAK_KETIGA:
            d[f] = _s(d.get(f))
        if _s(jenis_instansi) == "perorangan":
            d["kapasitas_bertindak"] = "diri_sendiri"
            for f in FIELD_ESELON:
                d[f] = ""
            d["unit_kerja"] = ""
    d.pop("kode_satker", None)
    return d


def validate_orang_luar(doc, kelompok, jenis_instansi) -> list:
    """Galat yang menolak simpan. Peringatan (tidak menolak) ada di
    `peringatan_orang_luar`."""
    d = doc or {}
    errors = list(validate_pegawai(d))
    k = _s(kelompok)
    if k not in KELOMPOK_LUAR:
        errors.append("Kelompok orang luar tidak dikenal")
        return errors
    if not jenis_cocok(k, jenis_instansi):
        errors.append("Jenis instansi tidak cocok dengan kelompok orang ini")
    if not _s(d.get("satker_luar_id")):
        errors.append("Orang luar wajib berada di satu satker")
    if k == "pihak_ketiga":
        kap = _s(d.get("kapasitas_bertindak"))
        if kap and kap not in KAPASITAS_BERTINDAK:
            errors.append(f"Kapasitas bertindak tidak dikenal: {kap}")
        if _s(jenis_instansi) == "perorangan" and kap and kap != "diri_sendiri":
            errors.append("Perorangan hanya bertindak untuk diri sendiri")
        dasar = _s(d.get("dasar_kewenangan_jenis"))
        if dasar and dasar not in DASAR_KEWENANGAN:
            errors.append(f"Dasar kewenangan tidak dikenal: {dasar}")
        tgl = _s(d.get("dasar_kewenangan_tanggal"))
        if tgl and not _TGL_RE.match(tgl[:10]):
            errors.append("Tanggal dasar kewenangan harus format YYYY-MM-DD")
    return errors


def peringatan_orang_luar(doc, kelompok) -> list:
    """Peringatan yang tidak menolak simpan: wakil badan tanpa bukti
    dasarnya, dan petugas yang bukan wakil sah badan."""
    d = doc or {}
    if _s(kelompok) != "pihak_ketiga":
        return []
    out = []
    kap = _s(d.get("kapasitas_bertindak"))
    dasar = _s(d.get("dasar_kewenangan_jenis"))
    if kap in KAPASITAS_WAKIL_BADAN and (
            not dasar or dasar == "tidak_ada"
            or not _s(d.get("dasar_kewenangan_nomor"))):
        out.append(f"{KAPASITAS_BERTINDAK[kap]} sebaiknya dilengkapi dasar "
                   f"kewenangan beserta nomornya")
    if kap == "petugas":
        out.append("Petugas bukan wakil sah badan — tidak dapat menandatangani "
                   "serah terima atas nama badan")
    return out


def periksa_penampungan(satker_lama, satker_baru) -> list:
    """Pindah orang antarsatker hanya dalam kelompok yang sama (invarian 9).
    Pindah antartataran (pusat ↔ daerah) juga ditolak (invarian 11)."""
    lama = satker_lama or {}
    baru = satker_baru or {}
    if not baru:
        return ["Satker tujuan tidak ditemukan"]
    if not lama:
        return []
    errors = []
    if _s(lama.get("kelompok")) != _s(baru.get("kelompok")):
        errors.append("Orang luar hanya dapat dipindah ke satker sekelompok — "
                      "penyesuaian field antarkelompok berbeda")
    elif _s(lama.get("tataran")) != _s(baru.get("tataran")):
        errors.append("Orang tidak dapat dipindah antara instansi pusat dan "
                      "daerah")
    return errors


def label_unit_orang(doc) -> str:
    """Satu baris tempat seseorang bekerja.

    Internal (tanpa `kelompok`): `unit_kerja` apa adanya. Luar:
    "instansi — satker — unit"; kab/kota dan desa menyebut provinsinya agar
    nama satker tidak pernah lepas dari instansinya (aturan penampungan 7).
    """
    d = doc or {}
    if _s(d.get("kelompok")) not in KELOMPOK_LUAR:
        return _s(d.get("unit_kerja"))
    instansi = _s(d.get("instansi_nama"))
    prov = _s(d.get("provinsi_nama"))
    jenis = _s(d.get("jenis_instansi"))
    if prov and jenis in ("pemerintah_kabkota", "pemerintah_desa") \
            and prov not in instansi:
        instansi = f"{instansi}, {prov}"
    bagian = [instansi, _s(d.get("satker_luar_nama")), _s(d.get("unit_kerja"))]
    hasil = []
    for b in bagian:
        if b and b not in hasil:
            hasil.append(b)
    return " — ".join(hasil)


# ── Impor/ekspor per kelompok (PGW-04) ─────────────────────────────────────
# `pegawai_utils.HEADER_IMPOR` dan penormalnya TIDAK disunting: header luar
# diturunkan darinya, dan baris luar dipetakan kembali ke header baku lalu
# diserahkan ke `baris_impor_ke_pegawai` — satu penormal, bukan dua.

# Sebutan kolom pihak ketiga (3.7b) → header baku.
SEBUTAN_KOLOM_PIHAK_KETIGA = {
    "NIP/NIK/NRP": "NIK",
    "Jabatan": "Jabatan pada Badan",
    "Alamat": "Alamat Korespondensi",
    "Eselon 1": "Tingkat I", "Eselon 2": "Tingkat II", "Eselon 3": "Tingkat III",
    "Eselon 4": "Tingkat IV", "Eselon 5": "Tingkat V",
    "Unit Kerja": "Unit pada Badan",
}
KOLOM_KHUSUS_PIHAK_KETIGA = {
    "Kapasitas Bertindak": "kapasitas_bertindak",
    "Dasar Kewenangan": "dasar_kewenangan_jenis",
    "Nomor Dasar Kewenangan": "dasar_kewenangan_nomor",
    "Tgl Dasar Kewenangan": "dasar_kewenangan_tanggal",
}
_ENUM_KHUSUS = {"kapasitas_bertindak": KAPASITAS_BERTINDAK,
                "dasar_kewenangan_jenis": DASAR_KEWENANGAN}


def _field_header(header: str) -> str:
    from pegawai_utils import KOLOM_IMPOR
    return KOLOM_IMPOR.get(str(header or "").strip().lower(), "")


def header_impor_luar(kelompok) -> list:
    """Header templat/ekspor orang luar.

    eksternal    : HEADER_IMPOR tanpa tujuh kolom pribadi (3.7d), urutan sama.
    pihak_ketiga : HEADER_IMPOR tanpa kolom field 3.7c, dengan sebutan 3.7b,
                   lalu empat kolom kapasitas & dasar kewenangan.
    """
    from pegawai_utils import HEADER_IMPOR
    k = _s(kelompok)
    nonaktif = set(FIELD_NONAKTIF.get(k, ()))
    dasar = [h for h in HEADER_IMPOR if _field_header(h) not in nonaktif]
    if k != "pihak_ketiga":
        return dasar
    return [SEBUTAN_KOLOM_PIHAK_KETIGA.get(h, h) for h in dasar] + \
        list(KOLOM_KHUSUS_PIHAK_KETIGA)


def _baku_dan_khusus(raw):
    """Pisahkan satu baris berkas luar menjadi (baris ber-header baku,
    field khusus pihak ketiga). Header dicocokkan tanpa peduli huruf besar."""
    balik = {v.lower(): k for k, v in SEBUTAN_KOLOM_PIHAK_KETIGA.items()}
    khusus_peta = {k.lower(): v for k, v in KOLOM_KHUSUS_PIHAK_KETIGA.items()}
    baku, khusus = {}, {}
    for header, nilai in (raw or {}).items():
        kunci = str(header or "").strip()
        rendah = kunci.lower()
        if rendah in khusus_peta:
            khusus[khusus_peta[rendah]] = nilai
        else:
            baku[balik.get(rendah, kunci)] = nilai
    return baku, khusus


def _norm_enum(nilai, peta) -> str:
    v = _s(nilai)
    if not v:
        return ""
    rendah = v.lower()
    if rendah in peta:
        return rendah
    for kode, uraian in peta.items():
        if uraian.lower() == rendah or kode.replace("_", " ") == rendah:
            return kode
    return v


def baris_impor_luar(raw, kelompok):
    """(doc, peringatan) untuk satu baris berkas orang luar."""
    from pegawai_utils import baris_impor_ke_pegawai
    baku, khusus = _baku_dan_khusus(raw)
    doc, peringatan = baris_impor_ke_pegawai(baku)
    for field in KOLOM_KHUSUS_PIHAK_KETIGA.values():
        nilai = khusus.get(field, "")
        if field in _ENUM_KHUSUS:
            nilai = _norm_enum(nilai, _ENUM_KHUSUS[field])
        elif field == "dasar_kewenangan_tanggal":
            nilai = _s(nilai)[:10]
        doc[field] = _s(nilai)
    return doc, peringatan


def field_dipasok_luar(raw) -> set:
    """Padanan `field_dipasok_baris` untuk berkas luar (sebutan pihak ketiga
    dan kolom khusus ikut dikenali)."""
    from pegawai_utils import field_dipasok_baris
    baku, khusus = _baku_dan_khusus(raw)
    dipasok = field_dipasok_baris(baku)
    dipasok.update(f for f, v in khusus.items() if _s(v))
    return dipasok


def baris_ekspor_luar(doc, kelompok) -> list:
    """Satu baris ekspor selaras `header_impor_luar(kelompok)`."""
    from pegawai_utils import HEADER_IMPOR, baris_ekspor_pegawai
    per_header = dict(zip(HEADER_IMPOR, baris_ekspor_pegawai(doc)))
    balik = {v: k for k, v in SEBUTAN_KOLOM_PIHAK_KETIGA.items()}
    d = doc or {}
    out = []
    for h in header_impor_luar(kelompok):
        if h in KOLOM_KHUSUS_PIHAK_KETIGA:
            field = KOLOM_KHUSUS_PIHAK_KETIGA[h]
            nilai = _s(d.get(field))
            if field in _ENUM_KHUSUS:
                nilai = _ENUM_KHUSUS[field].get(nilai, nilai)
            out.append(nilai)
        else:
            out.append(per_header.get(balik.get(h, h), ""))
    return out
