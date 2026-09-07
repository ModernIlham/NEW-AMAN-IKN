"""Grid + TIPOGRAFI stiker BMN — LOGIKA MURNI (teruji unit).

Dua hal yang diputuskan di sini, keduanya tanpa menyentuh ReportLab supaya
bisa diuji tanpa merender PDF:

1. **Grid** — ukuran stiker harus MEMANFAATKAN SEGALA RUANG kertas A4/A3:
   jumlah kolom & baris dipilih paling dekat ke ukuran target, lalu ukuran
   label DIRENTANGKAN sehingga grid mengisi penuh area cetak; sisa ruang
   hanya margin halaman + celah tipis antar kotak.
2. **Tipografi** — ukuran huruf per peran (hierarki), pemenggalan baris, dan
   penyusutan otomatis agar teks panjang tetap terbaca. Semua fungsi di sini
   menerima fungsi pengukur `ukur(teks, size) -> lebar_pt` sebagai parameter,
   jadi pemanggil boleh memakai `pdfmetrics.stringWidth` sementara uji unit
   memakai pengukur palsu yang deterministik.

Prinsip keterbacaan (permintaan pemilik: "rapi di SEMUA ukuran"):
- Hierarki tetap: kode barang > nama barang > sub-sub kelompok > baris
  identitas satker. Perbandingannya dipertahankan di semua ukuran stiker,
  jadi mata langsung menemukan kode barang lebih dulu.
- SATU DERET EMAS untuk seluruh keluarga: setiap ukuran huruf, di setiap
  ukuran stiker, adalah anak tangga `9 pt × φ^(k/8)`. Karena semua peran
  berangkat dari anak tangga yang sama, stiker kecil adalah stiker besar
  yang mengecil — bukan tujuh peran yang mengecil sendiri-sendiri.
- LANTAI ukuran huruf dikenakan SEKALI pada anak tangga dasar, bukan per
  peran. Lantai per-peran dulu membuat tiap peran mentok pada saat berbeda,
  sehingga di stiker kecil semuanya rata di ±5-6,6 pt dan hierarkinya hilang.
  Teks yang tak muat diselesaikan dengan pemenggalan baris, bukan dengan
  mengecilkan huruf tanpa batas.
- Teks panjang LANJUT KE BARIS BERIKUTNYA (nama barang & sub-sub kelompok),
  bukan dipotong di baris pertama.
"""

# Ukuran TARGET per pilihan (mm) — acuan pembulatan kolom/baris; dimensi
# akhir menyesuaikan kertas (lihat grid_optimal). `header` = tinggi kepala
# stiker pada ukuran target; tinggi kepala sebenarnya dihitung proporsional
# terhadap tinggi label nyata (lihat tinggi_header).
TARGET_STIKER = {
    "besar": {"w": 95, "h": 45, "header": 12},
    "sedang": {"w": 62, "h": 30, "header": 8.5},
    "kecil": {"w": 45, "h": 22, "header": 6.5},
}

#: Batas baris badan stiker. Nama barang paling banyak TIGA baris — permintaan
#: pemilik: *"terus ke atas hingga 3 baris saja maksimal panjangnya jika lebih
#: gunakan '...'"*. Di sini elipsis memang yang diminta: stiker ditempel di
#: barang fisik, dan nama yang mengalir sampai enam baris memakan ruang kode
#: barang yang justru jadi kunci pencocokannya.
MAKS_BARIS_NAMA = 3
MAKS_BARIS_SUBSUB = 2

MARGIN_MM = 6.0   # margin halaman
GAP_MM = 1.5      # celah tipis antar kotak (garis potong)

# ── TANGGA EMAS: SATU skala untuk seluruh keluarga stiker ────────────────
#
# Permintaan pemilik: *"sesuaikan lagi ukuran font di setiap ukuran stiker
# agar seolah-olah merupakan pengecilan penyesuaian dari font di stiker besar
# hingga ke yang terkecil ... mungkin bisa dengan Golden Ratio (1,618) atau
# fibonacci agar terlihat natural semua ukurannya"*.
#
# Model lama memberi TIAP PERAN acuan, lantai, dan langit-langitnya sendiri.
# Akibatnya tiap peran menyentuh lantainya pada saat yang berbeda: di stiker
# kecil SEMUA peran mentok lantai, hierarkinya rata (kode 6,6 · nama 6,0 ·
# sub-sub 5,5 — selisihnya tak terlihat mata) dan hurufnya menyusut jauh
# lebih sedikit daripada stikernya sendiri (stiker 0,49× tetapi huruf
# 0,56–0,73×), sehingga stiker kecil terasa penuh sesak.
#
# Sekarang SELURUH ukuran huruf di seluruh ukuran stiker adalah anak tangga
# dari SATU deret emas. Satu langkah = φ^(1/8) ≈ 1,062 — φ utuh (1,618) jauh
# terlalu lompat untuk tujuh peran yang harus hidup berdampingan dalam satu
# kotak beberapa sentimeter; seperlapan-φ memberi tangga halus yang tetap
# menutup satu putaran emas penuh setiap delapan langkah.
#
# Perbandingan lama pada stiker BESAR ternyata sudah nyaris persis duduk di
# tangga ini (simpangan terbesar 2,3% pada NUP), jadi stiker besar yang sudah
# disetujui pemilik praktis tak berubah; yang diperbaiki adalah bagaimana ia
# MENGECIL.
RASIO_EMAS = 1.618033988749895
LANGKAH_EMAS = RASIO_EMAS ** 0.125     # φ^(1/8) ≈ 1,062 — satu anak tangga
ACUAN_PT = 9.0                         # ukuran peran "nama" di anak tangga 0

#: Lantai & langit-langit CETAK. Lantai dikenakan pada peran terkecil yang
#: muncul di stiker sungguhan (`sub` = baris kode satker di kepala), bukan
#: per peran sendiri-sendiri — itulah sebabnya hierarkinya tak lagi rata saat
#: mengecil: yang dijepit adalah SATU anak tangga dasar, seluruh tangga ikut
#: bergeser utuh. `label` sengaja tak ikut menahan lantai: ia cuma keterangan
#: garis ukur di stiker CONTOH yang tak pernah ditempel (penggambarnya
#: memberi lantai sendiri).
LANTAI_CETAK_PT = 4.0
ATAP_CETAK_PT = 15.0

#: Posisi tiap peran pada tangga emas, dihitung dari peran "nama" (= 0).
#: Jarak inilah hierarki stiker: kode barang empat langkah di atas nama
#: (φ^0,5 ≈ 1,272× — kode barang yang dicari mata lebih dulu), sub-sub
#: kelompok dua langkah di bawahnya, baris kode satker tiga langkah.
LANGKAH_PERAN = {
    "kode": 4,        # kode barang — puncak hierarki
    "instansi": 1,    # judul kepala stiker
    "nup": 0,         # NUP, sebaris dengan kode barang
    "nama": 0,        # nama barang — acuan tangga
    "subsub": -2,     # sub-sub kelompok — MENGALAH saat sempit, lihat bawah
    "sub": -3,        # baris kedua kepala (nama/kode satker)
    "label": -6,      # keterangan garis ukur (stiker CONTOH saja)
}

#: SUB-SUB KELOMPOK adalah peran yang MENGALAH saat ruang sempit — itu sudah
#: berlaku untuk jatah barisnya (lihat `rencana_badan`), dan kini juga untuk
#: ukuran hurufnya. Pada stiker yang lega ia naik satu anak tangga; hanya pada
#: stiker sempit ia turun kembali.
#:
#: Sebabnya bukan perbandingan, melainkan RUANG KOSONG: dengan langkah yang
#: sama (0,887× nama) sub-sub terbaca pas di stiker kecil yang padat, tetapi
#: tenggelam di stiker besar yang menyisakan pita kosong di tengah badan.
#: Pemilik menagihnya begitu: *"agak besarkan lagi khusus di bagian sub-sub
#: kelompoknya ... cukup di bagian sedang dan besar saja, yang stiker kecil
#: sudah pas sempurna"*.
#:
#: SATU anak tangga, dan itu memang batasnya: dua anak tangga menaruh sub-sub
#: tepat sebesar nama barang, dan hierarki "nama > sub-sub" hilang.
#:
#: Ambangnya TINGGI FISIK, bukan nama ukuran atau anak tangga — supaya A4 dan
#: A3 memutuskan sama. Stiker sedang keluar 30,3 mm (A4) / 30,0 mm (A3),
#: stiker kecil 22,4 / 22,6 mm; 26 mm berjarak ±4 mm dari keduanya.
LANGKAH_SUBSUB_LEGA = 1
TINGGI_SUBSUB_LEGA_MM = 26.0

#: Inset tepi stiker. Ikut mengecil bersama stikernya (φ^6 ≈ 17,94 bagian
#: dari sisi pendek) dengan LANTAI absolut: toleransi mesin potong itu
#: besaran fisik, bukan perbandingan — stiker sekecil apa pun tetap butuh
#: jarak yang sama dari garis potong. Angka lantainya = inset QR yang lama,
#: supaya teks dan QR kini memakai SATU inset yang sama.
PAD_MIN_MM = 1.8


def grid_optimal(page_w_mm, page_h_mm, target_w_mm, target_h_mm,
                 margin_mm=MARGIN_MM, gap_mm=GAP_MM):
    """(kolom, baris, lebar_label, tinggi_label) dalam mm — grid mengisi
    PENUH area cetak: kolom/baris = pembulatan terdekat ke ukuran target,
    label direntangkan menutup sisa ruang. MURNI."""
    avail_w = float(page_w_mm) - 2 * margin_mm
    avail_h = float(page_h_mm) - 2 * margin_mm
    kolom = max(1, round((avail_w + gap_mm) / (float(target_w_mm) + gap_mm)))
    baris = max(1, round((avail_h + gap_mm) / (float(target_h_mm) + gap_mm)))
    lw = (avail_w - (kolom - 1) * gap_mm) / kolom
    lh = (avail_h - (baris - 1) * gap_mm) / baris
    return kolom, baris, lw, lh


def kelompokkan_per_ukuran(aset_list, default="sedang"):
    """Kelompokkan aset menurut field `stiker_ukuran`-nya (mode cetak
    "sesuai pilihan per aset"). Nilai kosong/tak dikenal → `default`.
    Kembalikan list (ukuran, [aset...]) berurut besar → sedang → kecil,
    hanya kelompok berisi. MURNI."""
    kelompok = {"besar": [], "sedang": [], "kecil": []}
    for a in (aset_list or []):
        u = str((a or {}).get("stiker_ukuran") or "").strip().lower()
        if u not in kelompok:
            u = default
        kelompok[u].append(a)
    return [(u, kelompok[u]) for u in ("besar", "sedang", "kecil")
            if kelompok[u]]


def tinggi_header(tinggi_label_mm, ukuran):
    """Tinggi kepala stiker (mm) PROPORSIONAL terhadap tinggi label nyata.

    Label direntangkan mengisi kertas, jadi tinggi nyatanya tak persis sama
    dengan target; memakai angka `header` target apa adanya membuat kepala
    terlihat terlalu tebal/tipis pada kertas tertentu. MURNI."""
    t = TARGET_STIKER.get(str(ukuran or "").lower()) or TARGET_STIKER["sedang"]
    return float(tinggi_label_mm) * (t["header"] / t["h"])


def _pt(langkah):
    """Ukuran huruf (pt) pada anak tangga emas ke-`langkah`. MURNI."""
    return ACUAN_PT * (LANGKAH_EMAS ** langkah)


def anak_tangga(lebar_mm, tinggi_mm):
    """Anak tangga emas untuk label seukuran `lebar × tinggi` mm.

    Skala diambil dari dimensi label NYATA (sisi yang paling menekan yang
    menentukan, supaya label lebar-pendek tak memakai huruf yang tak muat
    tingginya), lalu DIBULATKAN ke anak tangga terdekat — jadi tiap ukuran
    stiker mendarat di rung yang bersih, bukan di angka acak hasil pembagian
    kertas. Rung dijepit sekali di sini, dan karena semua peran berangkat
    dari rung yang sama, hierarkinya tak bisa rata saat mentok. MURNI."""
    import math
    t = TARGET_STIKER["besar"]
    skala = min(float(lebar_mm) / t["w"], float(tinggi_mm) / t["h"])
    if skala <= 0:
        return 0
    n = round(math.log(skala) / math.log(LANGKAH_EMAS))
    ln_langkah = math.log(LANGKAH_EMAS)
    n_min = (math.ceil(math.log(LANTAI_CETAK_PT / ACUAN_PT) / ln_langkah)
             - LANGKAH_PERAN["sub"])
    n_maks = (math.floor(math.log(ATAP_CETAK_PT / ACUAN_PT) / ln_langkah)
              - LANGKAH_PERAN["kode"])
    return int(min(max(n, n_min), max(n_min, n_maks)))


def ukuran_font(lebar_mm, tinggi_mm):
    """Ukuran huruf (pt) per peran untuk label seukuran `lebar × tinggi` mm.

    Semuanya anak tangga dari SATU deret emas: `ACUAN_PT × φ^((n + s)/8)`
    dengan `n` rung ukuran stiker dan `s` rung peran. Konsekuensinya —
    dan inilah yang diminta pemilik — perbandingan antar ukuran stiker SAMA
    untuk setiap peran: stiker kecil benar-benar stiker besar yang mengecil,
    bukan tujuh peran yang masing-masing mengecil sendiri-sendiri.

    SATU pengecualian, atas permintaan pemilik: sub-sub kelompok naik satu
    anak tangga pada stiker yang lega (lihat `TINGGI_SUBSUB_LEGA_MM`). Ia
    tetap anak tangga emas — yang berbeda hanya rung-nya, bukan deretnya.
    MURNI."""
    n = anak_tangga(lebar_mm, tinggi_mm)
    langkah = dict(LANGKAH_PERAN)
    if float(tinggi_mm) >= TINGGI_SUBSUB_LEGA_MM:
        langkah["subsub"] += LANGKAH_SUBSUB_LEGA
    return {peran: round(_pt(n + s), 2) for peran, s in langkah.items()}


def padding_stiker(tinggi_mm):
    """Inset tepi stiker (mm) — jarak teks & QR dari garis potong.

    Dulu 1,6 mm mati untuk teks dan 1,8 mm untuk QR di SEMUA ukuran: pada
    stiker besar teks jadi terasa menempel garis sementara QR tidak, dan
    ketidakserasian itulah yang dikeluhkan pemilik. Kini satu angka untuk
    keduanya, ikut mengecil bersama stikernya sampai lantai fisik. MURNI."""
    return max(PAD_MIN_MM, float(tinggi_mm) / (RASIO_EMAS ** 6))


def _penggal_kata(kata, lebar, ukur, size):
    """Penggal SATU kata yang lebih lebar daripada baris (mis. kode panjang
    tanpa spasi) menjadi beberapa potongan yang muat. MURNI."""
    potongan, kini = [], ""
    for huruf in kata:
        if kini and ukur(kini + huruf, size) > lebar:
            potongan.append(kini)
            kini = huruf
        else:
            kini += huruf
    if kini:
        potongan.append(kini)
    return potongan or [kata]


def _potong_elipsis(teks, lebar, ukur, size, elipsis="..."):
    """Potong `teks` sampai muat termasuk elipsis. MURNI."""
    if ukur(teks, size) <= lebar:
        return teks
    inti = teks
    while inti and ukur(inti.rstrip(" .,;:-") + elipsis, size) > lebar:
        inti = inti[:-1]
    return (inti.rstrip(" .,;:-") + elipsis) if inti else ""


def bagi_baris(teks, lebar, ukur, size, maks_baris=3):
    """Pecah `teks` menjadi maksimal `maks_baris` baris selebar `lebar` pt.

    Teks yang belum habis LANJUT KE BARIS BERIKUTNYA (bukan dipotong di baris
    pertama seperti perilaku lama); baru bila jatah baris habis, sisa terakhir
    diberi elipsis. MURNI — `ukur(teks, size)` disuntikkan pemanggil."""
    kata_semua = str(teks or "").strip()[:400].split()
    if not kata_semua or lebar <= 0 or maks_baris <= 0:
        return []
    semua, kini = [], ""
    for kata in kata_semua:
        coba = f"{kini} {kata}".strip()
        if ukur(coba, size) <= lebar:
            kini = coba
            continue
        if kini:
            semua.append(kini)
            kini = ""
        if ukur(kata, size) <= lebar:
            kini = kata
        else:
            potongan = _penggal_kata(kata, lebar, ukur, size)
            semua.extend(potongan[:-1])
            kini = potongan[-1]
    if kini:
        semua.append(kini)
    if len(semua) <= maks_baris:
        return semua
    dipakai = semua[:maks_baris]
    sisa = " ".join(semua[maks_baris:])
    dipakai[-1] = _potong_elipsis(f"{dipakai[-1]} {sisa}".strip(), lebar,
                                  ukur, size)
    return dipakai


def muat_satu_baris(teks, lebar, ukur, size, size_min, langkah=0.94):
    """(teks, size) yang muat dalam SATU baris selebar `lebar` pt.

    Huruf dikecilkan bertahap sampai `size_min`; bila masih tak muat barulah
    teksnya dipotong ber-elipsis. Dipakai untuk nama instansi & baris kedua
    kepala stiker — nama instansi panjang tak boleh meluber keluar kotak.
    MURNI."""
    teks = str(teks or "").strip()
    if not teks or lebar <= 0:
        return "", size
    kini = float(size)
    while ukur(teks, kini) > lebar and kini > size_min:
        kini = max(float(size_min), kini * langkah)
    if ukur(teks, kini) <= lebar:
        return teks, kini
    return _potong_elipsis(teks, lebar, ukur, kini), kini


def susun_header(nama_instansi, baris2, lebar, tinggi, f_instansi, f_sub,
                 ukur_tebal, ukur_biasa):
    """Susun kepala stiker: nama instansi (boleh 2 baris) + baris kedua.

    Urutan usaha untuk nama instansi yang panjang:
    1. satu baris dengan huruf penuh;
    2. satu baris dengan huruf disusutkan (sampai lantai keterbacaan);
    3. DUA baris — hanya bila tinggi kepala memang cukup;
    4. terakhir barulah dipotong ber-elipsis.

    Kembalikan dict {baris: [...], size, baris2, size2}. MURNI."""
    nama = str(nama_instansi or "").strip()
    lantai = max(LANTAI_CETAK_PT, f_instansi * 0.72)
    tinggi_sub = (f_sub * 1.25) if str(baris2 or "").strip() else 0.0
    muat_dua_baris = tinggi >= f_instansi * 2.1 + tinggi_sub

    baris = []
    size = float(f_instansi)
    if nama:
        satu, size_satu = muat_satu_baris(nama, lebar, ukur_tebal, f_instansi,
                                          lantai)
        if satu == nama:
            baris, size = [nama], size_satu
        elif muat_dua_baris:
            dua = bagi_baris(nama, lebar, ukur_tebal, f_instansi, maks_baris=2)
            baris, size = dua, float(f_instansi)
        else:
            baris, size = [satu], size_satu

    teks2, size2 = "", float(f_sub)
    if str(baris2 or "").strip():
        teks2, size2 = muat_satu_baris(str(baris2).strip(), lebar, ukur_biasa,
                                       f_sub,
                                       max(LANTAI_CETAK_PT, f_sub * 0.75))
    return {"baris": baris, "size": size, "baris2": teks2, "size2": size2}


def rencana_badan(tinggi_badan, f, sisakan=0.0):
    """Jatah baris badan stiker: `{"subsub": n, "nama": n}`.

    Susunannya (permintaan pemilik): KODE BARANG di atas, SUB-SUB KELOMPOK
    tepat di bawahnya sebagai keterangan kode itu, lalu NAMA BARANG menempel
    ke DASAR stiker dan tumbuh ke atas — maksimal tiga baris.

    Sub-sub kelompok menerangkan kode, jadi ia harus menempel pada kode; dulu
    ia terlempar ke bawah nama barang dan terbaca seolah keterangan nama.

    Nama barang yang menempel dasar membuat seluruh stiker punya garis dasar
    yang sama: sepuluh stiker berjajar, nama barangnya sejajar semua, dan mata
    petugas menyusuri satu baris alih-alih naik-turun mengikuti panjang nama.

    Saat ruang mepet, NAMA didahulukan — itu yang dicari petugas saat
    mencocokkan barang fisik; sub-sub kelompok mengalah lebih dulu. MURNI."""
    sisa = float(tinggi_badan) - float(sisakan) - f["kode"] * 1.32
    tinggi_nama = f["nama"] * 1.18
    tinggi_sub = f["subsub"] * 1.16
    if sisa < tinggi_nama:
        return {"nama": 1 if sisa > 0 else 0, "subsub": 0}
    # Satu baris nama dulu (yang paling dicari), baru satu baris sub-sub,
    # baru sisanya dibagi: nama sampai tiga baris, sub-sub sampai dua.
    n_nama, n_sub = 1, 0
    sisa -= tinggi_nama
    if sisa >= tinggi_sub:
        n_sub = 1
        sisa -= tinggi_sub
    while n_nama < MAKS_BARIS_NAMA and sisa >= tinggi_nama:
        n_nama += 1
        sisa -= tinggi_nama
    while 1 <= n_sub < MAKS_BARIS_SUBSUB and sisa >= tinggi_sub:
        n_sub += 1
        sisa -= tinggi_sub
    return {"nama": n_nama, "subsub": n_sub}


def format_dimensi(lebar_mm, tinggi_mm):
    """Teks dimensi stiker gaya Indonesia (koma desimal) — dipakai pada
    stiker CONTOH agar pemesan tahu ukuran per satuan. MURNI."""
    import math

    def satu(n):
        # Pembulatan setengah-KE-ATAS yang eksplisit: format "%.1f" memakai
        # pembulatan bankir (98,25 → 98,2) yang membingungkan pada label ukur.
        return f"{math.floor(float(n) * 10 + 0.5) / 10:.1f}".replace(".", ",")
    return f"{satu(lebar_mm)} × {satu(tinggi_mm)} mm"
