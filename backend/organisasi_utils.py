"""Struktur organisasi berjenjang (Eselon I–V) — helper MURNI, tanpa I/O.

Permintaan pemilik: *"sistem memang hanya support sampai eselon II saja, akan
tetapi buat lebih berkembang lagi agar dapat mengakomodir hingga eselon ke 5
dengan indukannya yang terkoneksi dengan master pegawai juga di struktur
organisasi ... eselon I dan II adalah default wajib, dan memudahkan jika
organisasi mulai berkembang ke depannya."*

Eselon hidup di empat tempat, dan hanya SATU di antaranya berbentuk pohon:

    unit_kerja              {nama_unit, eselon, parent_id}   ← pohonnya
    pegawai                 eselon1 … eselon5   (lima kolom teks, RATA)
    assets                  eselon1, eselon2    (dua kolom teks)
    inventory_activities    [{nama, eselon2:[]}] (dua tingkat, bersarang)

Modul ini TIDAK membuat pohon kedua. Koleksi `unit_kerja` sudah menyimpannya
sejak awal; yang belum ada adalah satu tempat yang memutuskan apa yang sah di
atasnya. Sebelum ini aturannya tersebar: sebagian di `unit_kerja_utils.
validate_unit`, sebagian lagi ditulis ulang sebagai `if` di dalam rutenya —
dua salinan yang sudah berbeda isi (rute menolak Eselon I berinduk dengan
pesan "harus Eselon 0", yang bukan tingkat mana pun).

Bentuk dokumen di sini SENGAJA sama persis dengan koleksinya — `nama_unit`,
`eselon`, `parent_id` — bukan bentuk baru yang lebih rapi. Lapisan penerjemah
antara modul dan koleksinya adalah tempat ketiga yang harus ikut benar, dan
tempat ketiga itu tak pernah ikut diperbarui.

Empat keputusan yang membentuk modul ini:

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
    nama = str(u.get("nama_unit") or "").strip()
    level = _int(u.get("eselon"))
    if not nama:
        return False, "Nama unit wajib diisi"
    if not level_sah(level):
        return False, (f"Eselon '{u.get('eselon')}' tidak sah — "
                       f"harus {LEVEL_MIN}–{LEVEL_MAKS} (Eselon I–V)")
    if level == LEVEL_MIN:
        if induk:
            return False, f"{label_level(level)} adalah puncak; ia tak berinduk"
        return True, ""
    if not induk:
        return False, (f"{label_level(level)} wajib berinduk pada "
                       f"{label_level(level - 1)}")
    if not parent_level_sah(induk.get("eselon"), level):
        return False, (
            f"{label_level(level)} harus berinduk pada "
            f"{label_level(level - 1)}, bukan "
            f"{label_level(induk.get('eselon')) or 'unit tanpa eselon'} — "
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
    nama = [str((peta_unit.get(i) or {}).get("nama_unit") or "").strip()
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
        lv = _int(u.get("eselon"))
        if lv and level_sah(lv):
            keluar[f"eselon{lv}"] = str(u.get("nama_unit") or "").strip()
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


def keturunan(unit_id, semua_unit) -> set:
    """Seluruh id yang berada DI BAWAH `unit_id`, sedalam apa pun.

    Ditelusuri turun per tingkat, bukan dengan rekursi per simpul: pohon yang
    rusak (anak menunjuk induk yang menunjuk balik kepadanya) menghentikan
    rekursi hanya lewat batas kedalaman, sementara di sini simpul yang sudah
    terkumpul tak pernah ditelusuri dua kali.
    """
    anak_dari = {}
    for u in semua_unit or []:
        anak_dari.setdefault((u or {}).get("parent_id"), []).append(
            (u or {}).get("id"))
    keluar, antre = set(), list(anak_dari.get(unit_id) or [])
    while antre:
        i = antre.pop()
        if not i or i in keluar or i == unit_id:
            continue
        keluar.add(i)
        antre += anak_dari.get(i) or []
    return keluar


def validasi_pindah(unit_id, calon_induk_id, semua_unit):
    """(ok, pesan). Bolehkah unit ini dipindahkan ke bawah induk itu?

    Dua hal yang membuat pohonnya berhenti menjadi pohon:

    - **Berinduk pada diri sendiri.** Terbaca sepele, tetapi ia satu klik saja
      di layar yang menampilkan seluruh unit sebagai calon induk.
    - **Berinduk pada keturunannya sendiri.** Inilah yang melahirkan gelang:
      Biro Umum di bawah Bagian TU yang di bawah Biro Umum. Setelahnya tak ada
      satu pun unit pada gelang itu yang punya jalur ke puncak, dan setiap
      penelusuran hanya berhenti karena batas kedalaman — bukan karena selesai.

    Selama SETIAP sisi pohon memenuhi aturan tingkat, gelang sepanjang apa pun
    mustahil: gelang menuntut selisih tingkat -1 di tiap sisi, dan jumlah
    selisih mengelilingi gelang harus nol. Pemeriksaan ini karenanya tak
    terjangkau lewat rute yang ada sekarang — ia menjaga dua hal lain: baris
    lama yang dibuat sebelum aturan tingkat ditegakkan, dan kemungkinan aturan
    itu dilonggarkan kelak bila ada satker yang strukturnya memang melompat.
    """
    if not calon_induk_id:
        return True, ""
    if calon_induk_id == unit_id:
        return False, "Unit tak dapat menjadi induk bagi dirinya sendiri"
    if calon_induk_id in keturunan(unit_id, semua_unit):
        return False, ("Induk yang dipilih berada DI BAWAH unit ini — "
                       "pemindahan itu membuat strukturnya melingkar")
    return True, ""


def validasi_perubahan(unit_lama, unit_baru, induk_baru, semua_unit):
    """(ok, pesan). Seluruh aturan penyuntingan satu unit, dalam satu tempat.

    Sebelum ada penyuntingan, unit yang salah ketik dan sudah punya anak tak
    dapat diperbaiki sama sekali: menghapusnya ditolak karena masih membawahi,
    dan tak ada jalan lain. Satu-satunya jalan keluar adalah membongkar seluruh
    cabangnya lalu menyusunnya ulang — kerja yang besarnya tak sebanding dengan
    satu huruf yang keliru.

    Yang TIDAK boleh diubah adalah eselon unit yang masih membawahi: anak-
    anaknya divalidasi terhadap eselon induknya saat mereka dibuat, dan
    mengubahnya belakangan membuat seluruh cabang itu melanggar aturan tanpa
    satu pun di antaranya ikut diperiksa. Pindahkan dulu yang di bawahnya.
    """
    lama, baru = unit_lama or {}, unit_baru or {}
    # Diperiksa PALING DULU meski bukan yang paling umum: mengubah eselon unit
    # beranak selalu ikut melanggar aturan tingkat, dan pesan tingkat itu
    # menyebut akibatnya, bukan sebabnya — "Eselon III harus berinduk pada
    # Eselon II" tak memberi tahu siapa pun bahwa yang salah adalah mengubah
    # eselon unit yang masih membawahi.
    if _int(lama.get("eselon")) != _int(baru.get("eselon")) \
            and punya_anak(lama.get("id"), semua_unit):
        return False, ("Eselon unit ini tak dapat diubah selama ia masih "
                       "membawahi unit lain — pindahkan dulu yang di bawahnya")
    ok, pesan = validasi_unit(baru, induk_baru)
    if not ok:
        return False, pesan
    return validasi_pindah(lama.get("id"), (induk_baru or {}).get("id"),
                           semua_unit)


def filter_jalur(field_map, sampai_level) -> dict:
    """`{eselon1: …, …, eselonN: …}` — jalur nama sampai tingkat itu.

    Dipakai untuk MENEMUKAN baris pegawai/aset milik satu unit, yang menyimpan
    unitnya sebagai nama, bukan sebagai id. Nama saja tak cukup: dua Bagian
    Tata Usaha di bawah dua Biro berbeda adalah dua unit berlainan yang
    kebetulan bernama sama, dan mencocokkan `eselon3` saja akan menyeret
    keduanya. Yang mencukupi adalah nama BESERTA leluhurnya.

    Tingkat yang kosong dilewati, bukan dicocokkan sebagai string kosong:
    baris pegawai lama kerap tak mengisi seluruh tingkat, dan menuntut ""
    membuatnya tak pernah cocok.
    """
    n = _int(sampai_level) or 0
    keluar = {}
    for lv in range(LEVEL_MIN, min(n, LEVEL_MAKS) + 1):
        v = str((field_map or {}).get(f"eselon{lv}") or "").strip()
        if v:
            keluar[f"eselon{lv}"] = v
    return keluar


def perubahan_jalur(fe_lama, fe_baru, batas_level=LEVEL_MAKS):
    """`(set_field, hapus_field)` supaya jalur lama menjadi jalur baru.

    Kolom yang tingkatnya tak lagi terpakai DIHAPUS, tidak dibiarkan berisi
    nama lama: unit yang naik dari Eselon III ke Eselon II meninggalkan
    `eselon3` yang menyebut unit yang sudah tak ada di sana, dan kolom seperti
    itu terbaca sebagai unit ketiga yang tak pernah ada.
    """
    setel, hapus = {}, []
    for lv in range(LEVEL_MIN, min(_int(batas_level) or LEVEL_MAKS,
                                   LEVEL_MAKS) + 1):
        k = f"eselon{lv}"
        lama = str((fe_lama or {}).get(k) or "").strip()
        baru = str((fe_baru or {}).get(k) or "").strip()
        if lama == baru:
            continue
        if baru:
            setel[k] = baru
        elif lama:
            hapus.append(k)
    return setel, hapus


def cari_unit(nama, level, semua_unit, parent_id=None):
    """Unit dengan nama itu pada tingkat itu; None bila tak ada/mendua.

    Nama dibandingkan tanpa memedulikan besar-kecil huruf dan spasi tepi,
    sebab yang dicocokkan adalah teks yang pernah diketik tangan. Nama yang
    MENDUA pada satu tingkat dan satu induk dikembalikan sebagai None, bukan
    dipilih yang pertama: menebak di antara dua unit yang sama-sama sah
    menghasilkan lingkup yang salah tanpa satu pun tanda.
    """
    kunci = str(nama or "").strip().casefold()
    if not kunci:
        return None
    cocok = [u for u in (semua_unit or [])
             if str((u or {}).get("nama_unit") or "").strip().casefold() == kunci
             and _int((u or {}).get("eselon")) == _int(level)
             and (parent_id is None or (u or {}).get("parent_id") == parent_id)]
    return cocok[0] if len(cocok) == 1 else None


def cocokkan_lingkup_teks(eselon_lama, semua_unit):
    """`(ids, tak_cocok)` — ubah lingkup yang DIKETIK menjadi rujukan pohon.

    Bentuk lamanya `[{nama, eselon2: [nama, …]}, …]` (kadang `[nama, …]`):
    teks bebas yang diketik pada form kegiatan, tak pernah dihubungkan dengan
    master unit mana pun. Fungsi ini mencocokkannya sekali, supaya kegiatan
    lama tak perlu diisi ulang tangan.

    Bila sebuah Eselon I menyebut Eselon II di bawahnya, yang masuk lingkup
    adalah Eselon II itu — BUKAN Eselon I-nya. Mencatat induknya akan menarik
    seluruh saudara yang justru sengaja tak disebut, dan lingkup yang melebar
    diam-diam adalah kebalikan dari yang diminta.

    Nama yang tak ditemukan dikembalikan pada `tak_cocok`, tidak dibuang:
    salah ketik pada data lama harus terlihat oleh yang memperbaikinya.
    """
    ids, tak_cocok = [], []
    for baris in normalkan_eselon_teks(eselon_lama):
        nama1, anak = baris["nama"], baris["eselon2"]
        u1 = cari_unit(nama1, 1, semua_unit)
        if not u1:
            tak_cocok.append(nama1)
            # Eselon I tak dikenal: anaknya pun tak dapat dipastikan induknya.
            tak_cocok += anak
            continue
        if not anak:
            ids.append(u1["id"])
            continue
        for nama2 in anak:
            u2 = cari_unit(nama2, 2, semua_unit, parent_id=u1["id"])
            if u2:
                ids.append(u2["id"])
            else:
                tak_cocok.append(f"{nama1} / {nama2}")
    # Urutan kedatangan dipertahankan; duplikat dibuang.
    unik, terlihat = [], set()
    for i in ids:
        if i not in terlihat:
            terlihat.add(i)
            unik.append(i)
    return unik, tak_cocok


def lingkup_kegiatan(act, semua_unit) -> list:
    """Lingkup unit sebuah kegiatan — rujukan pohon bila ada, teks bila belum.

    Permintaan pemilik: *"buat sistem tampil sesuai eselon yang dicatat di
    dalam kegiatan sehingga tetap menyajikan data sesuai dengan tupoksinya."*

    `lingkup_unit` (daftar id) menang bila terisi. Kegiatan lama yang belum
    dipetakan jatuh ke pencocokan teksnya, sehingga laporannya tetap terbatas
    sebagaimana selama ini — bukan mendadak melebar ke seluruh satker hanya
    karena field barunya masih kosong.
    """
    a = act or {}
    dipilih = [str(i).strip() for i in (a.get("lingkup_unit") or []) if str(i).strip()]
    if dipilih:
        sah = {str((u or {}).get("id")) for u in (semua_unit or [])}
        return [i for i in dipilih if i in sah]
    ids, _ = cocokkan_lingkup_teks(a.get("eselon1") or [], semua_unit)
    return ids


def aset_dalam_lingkup(aset, lingkup_ids, peta_unit, peta_parent) -> bool:
    """Apakah aset ini berada di dalam salah satu unit lingkup kegiatannya.

    Aset menyimpan unitnya sebagai lima kolom teks, bukan sebagai id, jadi
    pencocokannya lewat JALUR: aset berada di dalam sebuah unit lingkup bila
    seluruh nama pada jalur unit itu — leluhurnya beserta namanya sendiri —
    sama persis dengan kolom eselon aset pada tingkat yang sama.

    Cara ini sekaligus menangani keturunan tanpa kode tambahan: aset sebuah
    Subbagian tetap membawa nama Bironya di `eselon2`, sehingga ia cocok dengan
    lingkup "Biro Umum" pada prefiks yang sama. Itulah arti membawahi.

    Lingkup KOSONG berarti seluruhnya — kegiatan yang belum mencatat lingkup
    tak boleh mendadak kehilangan seluruh datanya.
    """
    if not lingkup_ids:
        return True
    a = aset or {}
    for uid in lingkup_ids:
        fe = field_eselon(uid, peta_unit, peta_parent)
        lv = _int((peta_unit.get(uid) or {}).get("eselon"))
        if not lv or not level_sah(lv):
            continue
        jalur = filter_jalur(fe, lv)
        # Unit lingkup yang NAMANYA sendiri kosong tak dapat dikenali pada
        # kolom aset. Jalurnya lalu menyusut menjadi jalur INDUKNYA, dan
        # lingkup "Biro tanpa nama" diam-diam berlaku sebagai lingkup
        # "Sekretariat Jenderal" — melebar satu tingkat ke atas, menarik
        # seluruh Biro saudaranya, tanpa satu pun tanda pada laporannya.
        # Jalur kosong lebih buruk lagi: `all()` atas nol syarat bernilai
        # benar, sehingga SETIAP aset dianggap masuk.
        if f"eselon{lv}" not in jalur:
            continue
        if all(str(a.get(k) or "").strip() == v for k, v in jalur.items()):
            return True
    return False


def normalkan_eselon_teks(nilai) -> list:
    """Satukan bentuk lingkup eselon warisan menjadi `[{nama, eselon2: […]}]`.

    Bentuk ini hidup di dua rupa sekaligus di basis data — daftar STRING dan
    daftar DICT bersarang — karena penulisnya ada tiga dan tak semuanya sepakat:

        routes/satker.py  PUT admin            → ["Setjen", …]
        routes/satker.py  daftar-dari-kegiatan → [{nama, eselon2: […]}, …]
        routes/activities.py auto-registrasi   → [{nama, eselon2: […]}, …]

    Akibatnya setiap PEMBACA harus tahu keduanya, dan tiap pembaca menulis
    ulang cabang `isinstance(es, dict)`-nya sendiri — empat salinan yang
    masing-masing bisa keliru sendiri-sendiri. Yang benar adalah satu tempat
    yang tahu, dan penulis yang menyimpan satu bentuk saja.

    Bentuk dict yang dipilih, bukan string, karena ia yang membawa lebih
    banyak: string tak punya tempat untuk Eselon II di bawahnya, sehingga
    mengubah dict menjadi string membuang data, sedangkan sebaliknya tidak.

    Baris tanpa nama dibuang: ia tak dapat dirujuk, tak dapat dicocokkan
    dengan master unit, dan pada tabel identitas laporan ia tercetak sebagai
    baris kosong bernomor.
    """
    keluar = []
    for baris in (nilai or []):
        if isinstance(baris, str):
            nama, anak = baris.strip(), []
        elif isinstance(baris, dict):
            nama = str(baris.get("nama") or "").strip()
            anak = [str(x or "").strip()
                    for x in (baris.get("eselon2") or []) if str(x or "").strip()]
        else:
            continue
        if nama:
            keluar.append({"nama": nama, "eselon2": anak})
    return keluar


def pohon_terurut(semua_unit) -> list:
    """Daftar RATA berurut pohon: `[{...unit, depth, jalur}]`.

    Cerminan `frontend/src/lib/pohonUnit.js#susunPohonUnit`, dengan tiga
    keputusan yang sama:

    1. **Urutannya urutan pohon, bukan urutan datang** — induk selalu
       mendahului anaknya, saudara diurutkan menurut eselon lalu nama.
    2. **Unit yatim tetap muncul, sebagai akar.** `parent_id` yang menunjuk
       unit terhapus membuat cabangnya tak terjangkau dari puncak mana pun;
       menyembunyikannya berarti unit yang ada di basis data tak pernah
       tercetak di laporan mana pun.
    3. **Penelusuran dibatasi.** Simpul yang sudah dikunjungi tak pernah
       dikunjungi ulang, sehingga pohon yang melingkar berhenti sendiri.
    """
    daftar = [u for u in (semua_unit or []) if u and u.get("id")]
    dikenal = {u["id"] for u in daftar}
    anak_dari = {}
    for u in daftar:
        induk = u.get("parent_id")
        kunci = induk if induk in dikenal else ""
        anak_dari.setdefault(kunci, []).append(u)
    for arr in anak_dari.values():
        arr.sort(key=lambda u: (str(u.get("eselon") or ""),
                                str(u.get("nama_unit") or "").casefold()))

    keluar, dikunjungi = [], set()

    def turun(induk_id, depth, jalur_induk):
        for u in anak_dari.get(induk_id, []):
            if u["id"] in dikunjungi:
                continue
            dikunjungi.add(u["id"])
            nama = str(u.get("nama_unit") or "").strip()
            jalur = f"{jalur_induk}{PEMISAH_JALUR}{nama}" if jalur_induk else nama
            keluar.append({**u, "depth": depth, "jalur": jalur})
            turun(u["id"], depth + 1, jalur)

    turun("", 0, "")
    for u in daftar:
        if u["id"] not in dikunjungi:
            keluar.append({**u, "depth": 0,
                           "jalur": str(u.get("nama_unit") or "").strip()})
    return keluar
