"""Pengelompokan BERJENJANG untuk laporan — helper MURNI, tanpa I/O dan DB.

Permintaan pemilik: *"Per Kategori masih belum terbagi hingga ke per golongan,
bidang, kelompok, dan sub kelompok (dan bisa dipilih ingin ditampilkan seperti
apa), begitupun yang lokasi belum terbagi berdasarkan denah yang sudah
ditetapkan."*

Sebelumnya panel "Per Kategori" mengelompokkan menurut field `category` apa
adanya, dan "Per Lokasi" menurut field teks `location`. Keduanya rata — tak
punya jenjang sama sekali — padahal BMN justru diatur berjenjang di dua sumbu:

    Kodefikasi barang   Golongan → Bidang → Kelompok → Sub Kelompok
    Denah ruang         Kawasan → Gedung → Lantai → Ruangan

Bertanya "berapa banyak Peralatan dan Mesin" atau "berapa banyak yang ada di
Gedung A" tak dapat dijawab oleh daftar rata; keduanya menuntut pengelompokan
pada JENJANG yang dipilih pembacanya.

Tiga keputusan yang membentuk modul ini:

1. **Jenjang dipilih, tidak ditebak.** Golongan memberi delapan baris — terlalu
   kasar untuk ditindaklanjuti; Sub Kelompok bisa memberi ratusan — terlalu
   halus untuk dibaca sekali pandang. Yang benar bergantung pada pertanyaan
   yang sedang dibawa pembacanya, jadi ia yang memilih.

2. **Yang tak punya kode/penempatan DIKUMPULKAN, bukan dibuang.** Aset tanpa
   kode barang atau tanpa penempatan denah adalah justru yang paling perlu
   dibereskan. Membuangnya dari grafik membuat jumlah batang tak lagi sama
   dengan jumlah aset — dan selisihnya tak pernah ditanyakan siapa pun karena
   tak terlihat.

3. **Label diambil dari referensi, kodenya tetap ditulis.** Uraian saja membuat
   dua kelompok bernama mirip tak terbedakan; kode saja tak terbaca manusia.
   Keduanya ditulis berdampingan: `"301 — Alat Besar Darat"`.
"""

#: Kunci grup untuk aset yang tak punya kode/penempatan. Bukan string kosong:
#: label kosong pada batang terbaca sebagai kekeliruan render, bukan sebagai
#: keadaan data yang memang begitu.
TANPA_KODE = "(tanpa kode barang)"
TANPA_DENAH = "(belum ditempatkan di denah)"
#: Field teks `location` yang kosong. Dibedakan dari `TANPA_DENAH`: yang satu
#: berarti asetnya belum ditempatkan pada denah, yang lain berarti kolom lokasi
#: bebasnya memang belum diisi. Menyatukan keduanya menyembunyikan mana yang
#: sebenarnya kurang.
TANPA_LOKASI_TEKS = "(lokasi belum diisi)"
TANPA_ESELON = "(tanpa unit organisasi)"

#: Aset yang unitnya berada DI LUAR lingkup eselon kegiatan. Dikumpulkan,
#: bukan dibuang: kegiatan yang mencatat tupoksinya pada satu Biro tetapi
#: memuat aset Biro lain sedang menunjukkan salah satu dari dua hal — lingkup
#: yang belum lengkap, atau aset yang salah kegiatan. Keduanya perlu dilihat,
#: dan keduanya lenyap kalau barisnya disaring keluar diam-diam.
DI_LUAR_LINGKUP = "(di luar lingkup kegiatan)"


def potong_kode(kode, panjang: int) -> str:
    """Prefix kode sepanjang `panjang`; '' bila kodenya lebih pendek.

    Kode yang LEBIH PENDEK dari jenjang yang diminta tidak dipotong menjadi
    dirinya sendiri: aset berkode "3" tak dapat dijawab pada jenjang Bidang,
    dan memaksakannya akan mengarang bidang "3" yang tak pernah ada.
    """
    k = str(kode or "").strip()
    return k[:panjang] if len(k) >= panjang else ""


def label_kode(kode: str, uraian: str) -> str:
    """`"301 — Alat Besar Darat"`; kodenya saja bila uraian tak diketahui.

    Uraian yang tak ditemukan TIDAK diganti tanda tanya atau dikosongkan —
    kodenya sendiri sudah keterangan yang sah, dan referensi yang belum lengkap
    bukan alasan menyembunyikan asetnya.
    """
    k = str(kode or "").strip()
    u = str(uraian or "").strip()
    return f"{k} — {u}" if k and u else (k or u)


def _hierarki(aset, kunci_fns, label_fns, depth=0):
    """Baris berjenjang: induk, lalu anak-anaknya, lalu induk berikutnya.

    Rekursif atas daftar fungsi kunci — satu per jenjang yang dipilih. Tiap
    baris membawa `depth` supaya template dapat menjoroknya; tanpa itu, lima
    jenjang dalam satu panel terbaca sebagai satu daftar rata yang kebetulan
    memuat angka berulang.
    """
    if not kunci_fns:
        return []
    grup = {}
    for a in aset or []:
        grup.setdefault(kunci_fns[0](a), []).append(a)
    keluar = []
    for kunci, isi in _urut_mentah(grup):
        keluar.append({"kunci": kunci, "label": label_fns[0](kunci),
                       "aset": isi, "depth": depth})
        keluar += _hierarki(isi, kunci_fns[1:], label_fns[1:], depth + 1)
    return keluar


def _urut_mentah(grup):
    """Terbanyak dulu; kelompok "tanpa …" selalu di akhir (lihat `_urut`)."""
    tanpa = {TANPA_KODE, TANPA_DENAH, TANPA_ESELON, DI_LUAR_LINGKUP}
    return sorted(grup.items(),
                  key=lambda kv: (kv[0] in tanpa, -len(kv[1]), kv[0]))


def baris_hierarki_kode(aset, panjangs, ambil_kode, uraian_map=None):
    """Satu panel BERJENJANG, bukan satu panel per jenjang.

    Permintaan pemilik: *"buat agar filternya tidak dibagi menjadi kartu
    terpisah akan tetapi buat hierarkinya."* Panel terpisah per jenjang
    memaksa pembacanya mencocokkan sendiri baris mana milik baris mana —
    "301 — Alat Besar" pada satu panel dan "30101 — Alat Besar Darat" pada
    panel lain tak punya garis yang menghubungkannya. Satu panel berjenjang
    menuliskannya sebagai induk-anak, dan hubungan itu jadi terbaca.

    `panjangs` = panjang prefix tiap jenjang terpilih, dari terluas ke
    terdalam. Boleh melompat (Golongan lalu Kelompok) — anaknya tetap
    bersarang di bawah induknya.
    """
    uraian_map = uraian_map or {}

    def kunci(n):
        return lambda a: potong_kode(ambil_kode(a), n) or TANPA_KODE

    def label(kunci_nilai):
        return (kunci_nilai if kunci_nilai == TANPA_KODE
                else label_kode(kunci_nilai, uraian_map.get(kunci_nilai, "")))

    return _hierarki(aset, [kunci(n) for n in panjangs],
                     [label] * len(panjangs))


def baris_hierarki_denah(aset, levels, peta_node):
    """Satu panel berjenjang untuk denah: Gedung → Lantai → Ruangan."""
    def kunci(level):
        def ambil(a):
            lok = (a or {}).get("lokasi_spasial") or {}
            return ((peta_node.get(lok.get("node_id")) or {})
                    .get("level_nama", {}).get(level, "")) or TANPA_DENAH
        return ambil

    return _hierarki(aset, [kunci(lv) for lv in levels],
                     [lambda k: k] * len(levels))


def baris_hierarki_lokasi(aset, levels, peta_node, dengan_teks=True):
    """Denah dari terluas ke terdalam, lalu lokasi TEKS BEBAS sebagai daun.

    Permintaan pemilik: *"lakukan hal yang sama disemua distribusi lokasi
    sesuai hierarki di peta denah juga dari awal hingga akhir, dan terakhir
    data lokasi sekarang."*

    Denah menjawab "di gedung mana"; field teks `location` menjawab "tertulis
    di mana" — dan keduanya kerap tak sama. Menaruh teks itu sebagai jenjang
    TERDALAM membuat selisihnya terbaca: satu Ruangan denah yang di bawahnya
    berisi tiga tulisan berbeda ("Lt.2", "Lantai 2", "lantai dua") menunjukkan
    persis pekerjaan pembersihan yang tersisa, dan itu tak pernah terlihat
    selama keduanya berdiri sebagai dua grafik terpisah.

    `levels` kosong berarti belum ada satu pun aset yang ditempatkan di denah;
    yang tersisa hanya jenjang teksnya, dan panelnya jatuh menjadi daftar rata
    seperti sebelumnya.
    """
    def kunci_denah(level):
        def ambil(a):
            lok = (a or {}).get("lokasi_spasial") or {}
            return ((peta_node.get(lok.get("node_id")) or {})
                    .get("level_nama", {}).get(level, "")) or TANPA_DENAH
        return ambil

    def kunci_teks(a):
        return str((a or {}).get("location") or "").strip() or TANPA_LOKASI_TEKS

    kunci_fns = [kunci_denah(lv) for lv in (levels or [])]
    if dengan_teks:
        kunci_fns.append(kunci_teks)
    if not kunci_fns:
        return []
    return _rapatkan_rantai_kosong(
        _hierarki(aset, kunci_fns, [lambda k: k] * len(kunci_fns)),
        {TANPA_DENAH, TANPA_LOKASI_TEKS})


def _punya_saudara_sebelumnya(baris, i):
    """Adakah baris lain sedalam `baris[i]` di bawah induk yang sama, SEBELUMnya?

    Menengok ke belakang saja sudah cukup — dan itu bukan penyederhanaan yang
    kebetulan selamat: `_urut_mentah` selalu menaruh kelompok "(tanpa …)"
    PALING AKHIR di antara saudaranya, jadi saudaranya — bila ada — pasti sudah
    terlewati. Pemanggilnya hanya menanyakan baris "(tanpa …)".

    Penelusurannya berhenti pada baris yang lebih DANGKAL: itulah batas
    induknya, sehingga cabang lain tak pernah terhitung sebagai saudara.
    """
    b = baris[i]
    for j in range(i - 1, -1, -1):
        if baris[j]["depth"] < b["depth"]:
            return False
        if baris[j]["depth"] == b["depth"]:
            return True
    return False


def _rapatkan_rantai_kosong(baris, kosong):
    """Buang baris "(tanpa …)" yang ANAK TUNGGAL, lalu RAPATKAN kedalamannya.

    Aset yang belum ditempatkan di denah melahirkan satu baris "(belum
    ditempatkan di denah)" pada SETIAP jenjang denah — empat jenjang berarti
    empat baris beruntun yang cacahnya persis sama dan tak menyatakan satu pun
    hal baru. Yang menyatakan sesuatu hanya yang pertama.

    Bedanya dengan `_buang_ekor_kosong`: di sini rantainya berada di PANGKAL,
    bukan di ekor, sehingga keturunannya masih ada di bawah. Kedalaman mereka
    ikut dirapatkan — kalau tidak, sebuah baris menjorok empat tingkat di bawah
    induk yang cuma satu tingkat di atasnya, dan jorokan berhenti menggambarkan
    apa pun.

    Yang punya SAUDARA tetap dipertahankan: di situ ia menyatakan sesuatu yang
    nyata — sekian aset di Gedung ini belum ditempatkan pada Lantai mana pun,
    sementara sisanya sudah.
    """
    if not baris:
        return baris
    keluar, dibuang = [], []
    for i, b in enumerate(baris):
        dibuang = [d for d in dibuang if d < b["depth"]]
        if (b["depth"] > 0 and b["label"] in kosong
                and not _punya_saudara_sebelumnya(baris, i)):
            dibuang.append(b["depth"])
            continue
        keluar.append({**b, "depth": b["depth"] - len(dibuang)})
    return keluar


def tandai_batang_daun(baris):
    """Beri `bar_pct` HANYA pada jenjang terdalam; kembalikan `baris`.

    Bekerja atas baris SIAP-TAMPIL (`{"count", "depth", …}`), bukan atas
    keluaran `_hierarki` yang masih membawa daftar asetnya.

    Permintaan pemilik: *"untuk barchart disetiap data sub sub kelompok jangan
    dihilangkan."* Pada baris PENGELOMPOKAN batang membandingkan induk dengan
    anaknya — dua besaran yang salah satunya memuat yang lain — sehingga
    panjangnya tak pernah berarti apa pun. Pada baris terdalam ia
    membandingkan sesama saudara, dan di sanalah panjangnya berarti.

    Acuannya cacah terbesar SESAMA daun, bukan total keseluruhan: dibagi
    total, seluruh batang menjadi sisa yang tak terbaca begitu satu cabang
    mendominasi.
    """
    if not baris:
        return baris
    daun = max(b["depth"] for b in baris)
    maks = max((b["count"] for b in baris if b["depth"] == daun), default=0)
    for b in baris:
        if b["depth"] == daun and maks:
            b["bar_pct"] = round(b["count"] / maks * 100)
    return baris


def pilihan_jenjang(tersedia, label_map) -> list:
    """`[{"nilai", "label"}]` untuk pemilih jenjang di panel filter.

    `tersedia` = urutan nilai jenjang yang BENAR-BENAR ada pada data. Menawarkan
    jenjang yang tak dipakai satker itu hanya menawarkan grafik kosong.
    """
    return [{"nilai": str(v), "label": label_map.get(v, str(v))}
            for v in tersedia]


def level_eselon_berdata(aset) -> tuple:
    """Tingkat eselon yang BENAR-BENAR terisi pada sekumpulan aset, menaik.

    Dipakai memilih jenjang yang layak ditawarkan dan dijadikan bawaan.
    Menawarkan jenjang yang tak berisi apa-apa hanya menawarkan grafik kosong,
    dan grafik kosong terbaca sebagai laporan yang gagal dimuat.
    """
    from organisasi_utils import LEVEL_MAKS, LEVEL_MIN
    ada = set()
    for a in aset or []:
        for n in range(LEVEL_MIN, LEVEL_MAKS + 1):
            if n not in ada and str((a or {}).get(f"eselon{n}") or "").strip():
                ada.add(n)
    return tuple(sorted(ada))


def _int_level(v):
    from organisasi_utils import LEVEL_MAKS, LEVEL_MIN
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return n if LEVEL_MIN <= n <= LEVEL_MAKS else None


def jenjang_eselon_satker(akar=None, level_berdata=()):
    """`(sah, bawaan)` jenjang unit organisasi untuk satker berpuncak `akar`.

    Bawaannya dulu TETAPAN Eselon II, dengan alasan Eselon I terlalu kasar
    untuk menunjuk siapa yang bertanggung jawab atas barangnya. Alasannya
    benar; patokannya yang keliru — pada satker Eselon III seperti Lapas,
    Eselon II bukan tingkat yang lebih halus melainkan tingkat milik instansi
    induknya, yang tak berisi apa pun. Panelnya terbuka kosong, dan panel
    kosong terbaca sebagai laporan yang gagal dimuat.

    Maknanya kini RELATIF: satu tingkat DI BAWAH puncak satkernya. Untuk satker
    kantor pusat hasilnya tetap Eselon II — persis seperti sebelumnya.

Aturannya diterapkan pada puncak EFEKTIF — tingkat terdangkal yang benar-benar
    berisi, bila puncak yang dinyatakan ternyata kosong. Satker yang belum
    menyatakan tingkatnya terbaca berpuncak Eselon I sementara datanya mulai di
    Eselon III; menyodorkan panel kosong padahal datanya ada di tingkat sebelah
    adalah kekeliruan yang sama, hanya berpindah tempat. Bila satu tingkat di
    bawah puncak efektif itu pun kosong, puncak efektifnya sendiri yang
    dipakai — panel satu baris masih mengabarkan sesuatu; panel kosong tidak.

    `sah` memuat seluruh tingkat milik satker ini DITAMBAH tingkat di atasnya
    yang terlanjur berisi. Yang terakhir bukan kelonggaran melainkan syarat:
    satker yang baru menyatakan dirinya Eselon III masih menyimpan aset ber-
    `eselon1`, dan menutup jenjang itu membuat datanya tak dapat dilihat sama
    sekali — hilang dari laporan tetapi tetap hidup di basis data.
    """
    from organisasi_utils import LEVEL_MAKS, level_akar
    a = level_akar(akar)
    berdata = {n for n in (_int_level(v) for v in (level_berdata or []))
               if n is not None}
    sah = set(range(a, LEVEL_MAKS + 1)) | berdata
    if not berdata:
        return tuple(sorted(sah)), min(a + 1, LEVEL_MAKS)
    akar_efektif = _akar_efektif(a, berdata)
    bawaan = (akar_efektif + 1 if akar_efektif + 1 in berdata
              else akar_efektif)
    return tuple(sorted(sah)), bawaan


def _akar_efektif(akar: int, berdata: set) -> int:
    """Puncak yang BENAR-BENAR berisi: puncaknya sendiri bila berdata, kalau
    tidak yang terdangkal di bawahnya, kalau tidak yang terdangkal di atasnya
    (sisa data lama pada satker yang tingkatnya baru diturunkan)."""
    if akar in berdata:
        return akar
    lebih_dalam = sorted(n for n in berdata if n > akar)
    return lebih_dalam[0] if lebih_dalam else min(berdata)


def level_kelompok_eselon(akar=None, level_berdata=()) -> int:
    """Tingkat TUNGGAL untuk mengelompokkan ringkasan eksekutif.

    Ringkasan mengelompokkan aset menurut `eselon1` dan menamai sisanya "Tanpa
    Eselon I". Pada satker Eselon III seluruh asetnya jatuh ke keranjang itu —
    satu batang berlabel "tanpa", yang tak mengabarkan apa pun kecuali bahwa
    pertanyaannya salah alamat.

    Yang dipakai kini tingkat PUNCAK satkernya. Bila puncaknya tak berisi
    sementara tingkat lain berisi — satker yang belum menyatakan tingkatnya,
    padahal pegawainya sudah mengisi mulai Eselon III — yang dipakai tingkat
    terdangkal yang berdata, sehingga laporannya tetap mengabarkan sesuatu
    alih-alih satu batang "tanpa".
    """
    from organisasi_utils import level_akar
    a = level_akar(akar)
    berdata = {n for n in (_int_level(v) for v in (level_berdata or []))
               if n is not None}
    return a if not berdata else _akar_efektif(a, berdata)


def jenjang_terpilih_banyak(diminta, sah, bawaan) -> list:
    """Jenjang yang dipakai — bisa LEBIH DARI SATU sekaligus.

    Permintaan pemilik: *"Jenjang Lokasi dan kategori jadikan juga pilihan
    dapat memilih [lebih] dari 1."* Memilih Golongan DAN Bidang menghasilkan
    dua panel berdampingan, sehingga sebaran kasar dan halus dapat dibandingkan
    tanpa memuat laporannya dua kali.

    Urutannya mengikuti `sah` (dari terluas ke terdalam), BUKAN urutan
    kedatangan parameter: panel yang berpindah tempat setiap kali query
    string-nya disusun ulang membuat dua cetakan laporan yang sama terlihat
    berbeda.

    Nilai tak sah dibuang diam-diam; bila tak satu pun tersisa, `bawaan` yang
    dipakai — halaman tanpa panel apa pun akan terbaca sebagai laporan yang
    gagal dimuat, bukan sebagai pilihan yang keliru.
    """
    if diminta is None:
        diminta = []
    if isinstance(diminta, (str, int)):
        diminta = [diminta]
    minta = {str(v).strip() for v in diminta}
    dipakai = [v for v in sah if str(v) in minta]
    return dipakai or ([bawaan] if bawaan else [])



def baris_hierarki_eselon(aset, levels, di_luar=None):
    """Satu panel berjenjang untuk unit organisasi: Eselon I → … → Eselon V.

    Permintaan pemilik: *"buat sistem tampil sesuai eselon yang dicatat di
    dalam kegiatan sehingga tetap menyajikan data sesuai dengan tupoksinya."*

    Sebelumnya analisis eselon berupa DUA panel rata — "Per Eselon I" dan "Per
    Eselon II" — yang tak punya satu pun garis penghubung. Pembacanya harus
    mencocokkan sendiri Biro mana milik Kementerian mana, persis cacat yang
    sudah diperbaiki pada panel kategori dan lokasi.

    `levels` = daftar nomor tingkat terpilih (1..5), dari terluas ke terdalam.
    Boleh melompat; anaknya tetap bersarang di bawah induknya.

    `di_luar` = himpunan id aset yang unitnya berada di luar lingkup kegiatan.
    Aset itu dikumpulkan pada satu kelompok tersendiri di jenjang teratas,
    TIDAK disaring keluar: jumlah batang harus tetap sama dengan jumlah aset,
    dan selisih yang tak terlihat tak pernah ditanyakan siapa pun.
    """
    di_luar = di_luar or set()

    def kunci(lv):
        def ambil(a):
            if lv == levels[0] and (a or {}).get("id") in di_luar:
                return DI_LUAR_LINGKUP
            return str((a or {}).get(f"eselon{lv}") or "").strip() or TANPA_ESELON
        return ambil

    if not levels:
        return []
    return _buang_ekor_kosong(
        _hierarki(aset, [kunci(lv) for lv in levels],
                  [lambda k: k] * len(levels)))


def _buang_ekor_kosong(baris):
    """Buang baris "(tanpa …)" yang merupakan ANAK TUNGGAL induknya.

    Jalur eselon lazim putus di tengah: satker mencatat aset sampai Eselon II
    dan berhenti. Pada panel lima tingkat, tiap unit tanpa anak lalu melahirkan
    rantai "(tanpa unit organisasi)" sedalam sisa jenjangnya — tiga baris
    tambahan yang cacahnya persis sama dengan induknya dan tak menyatakan satu
    pun hal baru.

    Yang DIPERTAHANKAN adalah baris "(tanpa …)" yang punya saudara: di situ ia
    menyatakan sesuatu yang nyata — sekian aset di bawah Biro ini belum
    ditempatkan pada Bagian mana pun, sementara sisanya sudah. Itu justru
    selisih yang perlu dilihat.
    """
    kosong = {TANPA_ESELON, DI_LUAR_LINGKUP}
    keluar = []
    for i, b in enumerate(baris):
        if b["label"] not in kosong or b["depth"] == 0:
            keluar.append(b)
            continue
        # Saudara = baris lain pada depth yang sama, di bawah induk yang sama.
        # Induknya adalah baris terdekat sebelumnya dengan depth lebih dangkal;
        # pencarian berhenti di situ, jadi cabang lain tak pernah terhitung.
        punya_saudara = False
        for j in range(i - 1, -1, -1):
            if baris[j]["depth"] < b["depth"]:
                break
            if baris[j]["depth"] == b["depth"]:
                punya_saudara = True
                break
        if not punya_saudara:
            for j in range(i + 1, len(baris)):
                if baris[j]["depth"] < b["depth"]:
                    break
                if baris[j]["depth"] == b["depth"]:
                    punya_saudara = True
                    break
        if punya_saudara:
            keluar.append(b)
    return keluar
