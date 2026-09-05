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


def kelompokkan_kode(aset, panjang: int, ambil_kode, uraian_map=None):
    """[(label, [aset...])] terurut dari yang TERBANYAK.

    `ambil_kode(a)` mengembalikan kode barang aset. Aset yang kodenya lebih
    pendek dari `panjang` — termasuk yang kosong — masuk `TANPA_KODE` (lihat #2).
    """
    uraian_map = uraian_map or {}
    grup = {}
    for a in aset or []:
        prefix = potong_kode(ambil_kode(a), panjang)
        kunci = prefix or TANPA_KODE
        grup.setdefault(kunci, []).append(a)
    return _urut(grup, lambda k: (label_kode(k, uraian_map.get(k, ""))
                                  if k != TANPA_KODE else k))


def kelompokkan_denah(aset, level, peta_node):
    """[(label, [aset...])] menurut node denah pada `level` (kode_baku).

    `peta_node` = {node_id: {"level_nama": {KODE_BAKU: nama, ...}}} — hasil
    penelusuran leluhur node, disiapkan pemanggil (modul ini tak menyentuh DB).
    Aset tanpa penempatan, atau yang penempatannya tak punya leluhur di level
    itu, masuk `TANPA_DENAH` (lihat #2).
    """
    grup = {}
    for a in aset or []:
        lok = (a or {}).get("lokasi_spasial") or {}
        nama = ((peta_node.get(lok.get("node_id")) or {})
                .get("level_nama", {}).get(level, ""))
        grup.setdefault(nama or TANPA_DENAH, []).append(a)
    return _urut(grup, lambda k: k)


def _urut(grup, ke_label):
    """Terbanyak lebih dulu; kelompok "tanpa …" SELALU di akhir.

    Ia hampir selalu besar, dan menaruhnya di puncak membuat baris pertama
    grafik berisi keterangan yang paling tak informatif — sekaligus mendorong
    kelompok sungguhan turun dari pandangan pertama.
    """
    tanpa = {TANPA_KODE, TANPA_DENAH}
    urut = sorted(grup.items(),
                  key=lambda kv: (kv[0] in tanpa, -len(kv[1]), kv[0]))
    return [(ke_label(k), v) for k, v in urut]


def pilihan_jenjang(tersedia, label_map) -> list:
    """`[{"nilai", "label"}]` untuk pemilih jenjang di panel filter.

    `tersedia` = urutan nilai jenjang yang BENAR-BENAR ada pada data. Menawarkan
    jenjang yang tak dipakai satker itu hanya menawarkan grafik kosong.
    """
    return [{"nilai": str(v), "label": label_map.get(v, str(v))}
            for v in tersedia]


def jenjang_terpilih(diminta, sah, bawaan):
    """Nilai jenjang yang dipakai — `bawaan` bila permintaannya tak sah.

    Parameter dari query string tak pernah tepercaya: `?kat_level=99` harus
    jatuh ke bawaan, bukan menghasilkan grafik kosong yang tampak sah.
    """
    t = str(diminta or "").strip()
    for v in sah:
        if t == str(v):
            return v
    return bawaan
