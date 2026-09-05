"""Struktur organisasi berjenjang (Eselon I–V) — helper MURNI, tanpa I/O.

Permintaan pemilik: *"sistem memang hanya support sampai eselon II saja, akan
tetapi buat lebih berkembang lagi agar dapat mengakomodir hingga eselon ke 5
dengan indukannya yang terkoneksi dengan master pegawai juga di struktur
organisasi ... eselon I dan II adalah default wajib, dan memudahkan jika
organisasi mulai berkembang ke depannya."*

Keadaan sebelum modul ini: eselon hidup sebagai **teks bebas** di tiga tempat
yang tak saling mengenal —

    pegawai                 eselon1 … eselon5   (lima kolom, RATA)
    assets                  eselon1, eselon2    (dua kolom)
    inventory_activities    [{nama, eselon2:[]}] (dua tingkat, bersarang)

Lima kolom teks tak dapat menyatakan bahwa "Bagian Umum" berada DI BAWAH "Biro
Umum" di bawah "Sekretariat Jenderal": keduanya hanya kebetulan ditulis pada
baris yang sama. Salah ketik satu huruf melahirkan unit baru yang tak pernah
ada, dan tak ada satu pun tempat yang dapat ditanyai "unit apa saja yang ada".

Modul ini menyediakan pohonnya. Empat keputusan yang membentuknya:

1. **`parent_id` satu-satunya yang disunting; `ancestors` dan `jalur`
   DITURUNKAN.** Menyimpan ketiganya sebagai sumber kebenaran terpisah adalah
   resep pohon yang saling bertentangan — pelajaran yang sudah dibayar modul
   spasial (`backend/spasial_utils.py`), dan idiomnya sengaja ditiru di sini
   supaya yang sudah mengenal satu langsung mengenal yang lain.

2. **Eselon I dan II WAJIB; III–V tumbuh belakangan.** Satker yang baru berdiri
   hanya punya dua tingkat, dan memaksanya membuat tingkat kosong palsu hanya
   untuk memenuhi rantai justru merusak datanya. Tetapi tingkat TIDAK BOLEH
   dilompati: unit Eselon III wajib berinduk pada Eselon II yang nyata. Inilah
   bedanya dengan pohon spasial, yang memang boleh melompat karena satker
   daerah lazim tak punya Blok atau Persil.

3. **Unit yang masih punya anak tak boleh dihapus.** Menghapusnya membuat
   anak-anaknya menggantung tanpa induk — terlihat sebagai unit Eselon III
   tanpa Eselon II, keadaan yang tak pernah sah dan tak pernah diminta siapa
   pun.

4. **Kedalaman dibatasi, dan siklus dihentikan.** Data pohon yang rusak tak
   boleh membuat permintaan menggantung selamanya; penelusuran berhenti pada
   siklus atau kedalaman berlebih dan mengembalikan apa yang sudah terkumpul.
"""

#: (ordinal, kode_baku, label) — ordinal MENAIK ke arah yang lebih dalam,
#: sama seperti registry spasial supaya perbandingannya berlaku sama.
LEVEL_ESELON = (
    (1, "ESELON1", "Eselon I"),
    (2, "ESELON2", "Eselon II"),
    (3, "ESELON3", "Eselon III"),
    (4, "ESELON4", "Eselon IV"),
    (5, "ESELON5", "Eselon V"),
)

#: Eselon I dan II wajib ada sebelum tingkat di bawahnya boleh dipakai.
LEVEL_WAJIB = (1, 2)
LEVEL_MIN = 1
LEVEL_MAKS = 5

_PETA_LEVEL = {b[0]: b for b in LEVEL_ESELON}
_LABEL = {b[0]: b[2] for b in LEVEL_ESELON}
_KODE_BAKU = {b[0]: b[1] for b in LEVEL_ESELON}

#: Field turunan pada pegawai/aset: eselon1 … eselon5.
FIELD_ESELON = tuple(f"eselon{n}" for n in range(LEVEL_MIN, LEVEL_MAKS + 1))

PEMISAH_JALUR = " / "

#: Batas kedalaman penelusuran induk. Pohon lima tingkat tak pernah
#: membutuhkannya; ia ada untuk menghentikan data yang rusak.
BATAS_RANTAI = 16


def label_level(level) -> str:
    """"Eselon III" untuk 3; '' bila levelnya tak dikenal."""
    return _LABEL.get(_int(level), "")


def kode_baku_level(level) -> str:
    return _KODE_BAKU.get(_int(level), "")


def daftar_level() -> list:
    """Registry terurut dari TERLUAS ke terdalam, untuk pemilih di layar."""
    return [{"level": o, "kode_baku": k, "label": lb, "wajib": o in LEVEL_WAJIB}
            for o, k, lb in LEVEL_ESELON]


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def level_sah(level) -> bool:
    n = _int(level)
    return n is not None and LEVEL_MIN <= n <= LEVEL_MAKS


def parent_level_sah(level_induk, level_anak) -> bool:
    """Induk WAJIB tepat SATU tingkat di atas anaknya.

    Tingkat tidak boleh dilompati: unit Eselon III berinduk pada Eselon II
    yang nyata, bukan langsung pada Eselon I. Bedanya dengan pohon spasial —
    yang memang boleh melompat — adalah eselon merupakan struktur yang
    ditetapkan peraturan, bukan kebiasaan setempat: "Eselon III di bawah
    Eselon I" bukan penyederhanaan, melainkan pernyataan yang keliru.
    """
    a, i = _int(level_anak), _int(level_induk)
    if a is None or i is None or not level_sah(a) or not level_sah(i):
        return False
    return i == a - 1


def validasi_unit(unit, induk=None):
    """(ok, pesan). Periksa satu unit terhadap induknya SEBELUM disimpan.

    `induk` = dokumen unit induk, atau None bila tak ada. Fungsi murni —
    pemanggil yang mengambilnya dari basis data.
    """
    u = unit or {}
    nama = str(u.get("nama") or "").strip()
    level = _int(u.get("level"))
    if not nama:
        return False, "Nama unit wajib diisi"
    if not level_sah(level):
        return False, (f"Level '{u.get('level')}' tidak sah — "
                       f"harus {LEVEL_MIN}–{LEVEL_MAKS} (Eselon I–V)")
    if level == LEVEL_MIN:
        if induk:
            return False, f"{label_level(level)} adalah puncak; ia tak berinduk"
        return True, ""
    if not induk:
        return False, (f"{label_level(level)} wajib berinduk pada "
                       f"{label_level(level - 1)}")
    if not parent_level_sah(induk.get("level"), level):
        return False, (
            f"{label_level(level)} harus berinduk pada "
            f"{label_level(level - 1)}, bukan "
            f"{label_level(induk.get('level')) or 'unit tanpa level'} — "
            "tingkat tidak boleh dilompati")
    return True, ""


def rantai_induk(unit_id, peta_parent, batas: int = BATAS_RANTAI) -> list:
    """Daftar id leluhur dari yang TERJAUH ke induk langsung.

    `peta_parent` = {id_anak: id_induk}. Berhenti pada siklus atau kedalaman
    berlebih dan mengembalikan apa yang sudah terkumpul — data pohon rusak
    tidak boleh membuat permintaan menggantung selamanya.
    """
    naik, kini, terlihat = [], peta_parent.get(unit_id), {unit_id}
    while kini and kini not in terlihat and len(naik) < batas:
        naik.append(kini)
        terlihat.add(kini)
        kini = peta_parent.get(kini)
    naik.reverse()
    return naik


def turunkan_ancestors(unit_id, parent_id, peta_parent) -> list:
    """`ancestors` untuk satu unit — SELALU diturunkan, tak pernah disimpan
    sebagai kebenaran terpisah (lihat #1)."""
    if not parent_id:
        return []
    peta = dict(peta_parent or {})
    peta[unit_id] = parent_id
    return rantai_induk(unit_id, peta)


def jalur_nama(unit_id, peta_unit, peta_parent) -> str:
    """`"Setjen / Biro Umum / Bagian Rumah Tangga"` — leluhur lalu dirinya."""
    ids = rantai_induk(unit_id, peta_parent) + [unit_id]
    nama = [str((peta_unit.get(i) or {}).get("nama") or "").strip()
            for i in ids]
    return PEMISAH_JALUR.join(n for n in nama if n)


def punya_anak(unit_id, semua_unit) -> bool:
    return any((u or {}).get("parent_id") == unit_id for u in (semua_unit or []))


def boleh_hapus(unit_id, semua_unit):
    """(ok, pesan). Unit yang masih punya anak tak boleh dihapus (lihat #3)."""
    anak = [u for u in (semua_unit or []) if (u or {}).get("parent_id") == unit_id]
    if anak:
        return False, (f"Unit ini masih membawahi {len(anak)} unit; "
                       "pindahkan atau hapus yang di bawahnya lebih dulu")
    return True, ""


def field_eselon(unit_id, peta_unit, peta_parent) -> dict:
    """`{eselon1: …, eselon2: …}` — label tiap tingkat pada rantai unit ini.

    Inilah jembatan ke data yang sudah ada: `pegawai` dan `assets` menyimpan
    eselon sebagai kolom teks, dan kolom-kolom itu tetap dipakai laporan,
    ekspor, dan impor CSV. Menurunkannya dari pohon membuat keduanya tak lagi
    dapat saling bertentangan — teksnya kini BAYANGAN pohon, bukan sumber
    kebenaran kedua.

    Tingkat yang tak ada pada rantai dikembalikan sebagai string kosong, bukan
    dihilangkan: kunci yang hilang dan kunci yang kosong ditangani berbeda oleh
    pemanggil, dan bentuk yang berubah-ubah adalah sumber cacat diam.
    """
    keluar = {f: "" for f in FIELD_ESELON}
    if not unit_id:
        return keluar
    for i in rantai_induk(unit_id, peta_parent) + [unit_id]:
        u = peta_unit.get(i) or {}
        lv = _int(u.get("level"))
        if lv and level_sah(lv):
            keluar[f"eselon{lv}"] = str(u.get("nama") or "").strip()
    return keluar


def unit_terdalam(field_map) -> str:
    """Label eselon TERDALAM yang terisi (5→1) — satu nama untuk ditampilkan.

    Dipakai layar dan rekap agar data berjenjang tetap punya satu label unit;
    pola yang sama dengan `pegawai_utils.unit_kerja_terdalam`.
    """
    f = field_map or {}
    for n in range(LEVEL_MAKS, LEVEL_MIN - 1, -1):
        v = str(f.get(f"eselon{n}") or "").strip()
        if v:
            return v
    return ""


def dalam_lingkup(unit_id, lingkup_ids, peta_parent) -> bool:
    """Apakah unit ini berada DI DALAM salah satu unit lingkup kegiatan.

    Permintaan pemilik: *"buat sistem tampil sesuai eselon yang dicatat di
    dalam kegiatan sehingga tetap menyajikan data sesuai dengan tupoksinya dan
    tidak membingungkan akibat semakin banyak data input."*

    Lingkup KOSONG berarti SELURUHNYA — kegiatan yang belum mencatat lingkup
    tak boleh mendadak kehilangan seluruh datanya. Unit lingkup mencakup
    dirinya sendiri DAN seluruh keturunannya: mencatat "Biro Umum" sebagai
    lingkup berarti Bagian dan Subbagian di bawahnya ikut, sebab itulah arti
    membawahi.
    """
    if not lingkup_ids:
        return True
    if not unit_id:
        return False
    lingkup = set(lingkup_ids)
    if unit_id in lingkup:
        return True
    return any(i in lingkup for i in rantai_induk(unit_id, peta_parent))
