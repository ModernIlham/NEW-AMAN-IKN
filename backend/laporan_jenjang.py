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
    tanpa = {TANPA_KODE, TANPA_DENAH}
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


def pilihan_jenjang(tersedia, label_map) -> list:
    """`[{"nilai", "label"}]` untuk pemilih jenjang di panel filter.

    `tersedia` = urutan nilai jenjang yang BENAR-BENAR ada pada data. Menawarkan
    jenjang yang tak dipakai satker itu hanya menawarkan grafik kosong.
    """
    return [{"nilai": str(v), "label": label_map.get(v, str(v))}
            for v in tersedia]


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


