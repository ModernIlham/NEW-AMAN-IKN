"""Bentuk Nota Dinas persediaan — judul, hal, kolom, dan pengantarnya, di SATU
tempat.

Sampai sekarang seluruhnya hidup sebagai literal di dalam badan route
`nota_dinas_persediaan`: judulnya, kalimat "Hal", nama kolom, lebar kolom, dan
dua paragraf pengantar. Selama hanya ADA satu jalur cetak, itu tak menimbulkan
masalah. Begitu nota dinas boleh DITERBITKAN — dibekukan ke register dengan
nomor surat, lalu dicetak ulang dari register — jalurnya menjadi dua, dan dua
salinan literal yang harus sepakat selamanya adalah persis pola yang berulang
kali menggigit repo ini (lihat `laporan_linimasa`, `organisasi_utils`).

Maka bentuknya dipindah ke sini lebih dulu, SEBELUM jalur kedua ditulis:
pratinjau dan dokumen terbit membaca spesifikasi yang sama, sehingga menambah
kolom atau memperbaiki kalimat cukup sekali dan mustahil hanya berlaku di satu
jalur.

MURNI — tanpa Mongo, tanpa ReportLab, tanpa impor route. Pemformat tanggal
diterima sebagai argumen justru supaya tetap begitu: pemanggil menyerahkan
`_fmt_tanggal_id` milik reports.py sehingga tanggalnya tetap bergaya Indonesia
tanpa modul ini ikut menarik seluruh modul laporan.
"""

JENIS_NOTA = ("kritis", "kedaluwarsa")

# Bidang yang BENAR-BENAR dicetak, per jenis. Register membekukan tepat ini —
# bukan seluruh baris peringatan — karena baris peringatan membawa bidang
# turunan (`lewat`, `n_layer`, ambang yang berlaku saat itu) yang tak muncul di
# dokumen, dan menyimpannya membuat register tampak menjanjikan kesetiaan yang
# tidak ia jamin.
FIELD_BEKU = {
    "kritis": ("id", "kode_barang", "nama_barang", "satuan", "stok",
               "batas_kritis", "jumlah_diusulkan"),
    "kedaluwarsa": ("id", "kode_barang", "nama_barang", "qty", "expired"),
}

_SPEK = {
    "kritis": {
        "judul": "NOTA DINAS\nPERMOHONAN USULAN PENGADAAN PERSEDIAAN",
        "hal": "Usulan Pengadaan Persediaan (Stok Kritis/Habis)",
        "berkas": "Nota_Dinas_Stok_Kritis",
        "perihal": "Nota Dinas Usulan Pengadaan Persediaan (Stok Kritis/Habis)",
        "sumber": ("habis", "kritis"),
        "headers": ["No", "Kode Barang", "Nama Barang", "Satuan", "Stok",
                    "Batas Kritis", "Jumlah Diusulkan"],
        "widths": [26, 112, 168, 52, 42, 58, 62],
    },
    "kedaluwarsa": {
        "judul": "NOTA DINAS\nPERMOHONAN TINDAK LANJUT PERSEDIAAN KEDALUWARSA",
        "hal": "Persediaan Kedaluwarsa / Segera Kedaluwarsa",
        "berkas": "Nota_Dinas_Kedaluwarsa",
        "perihal": "Nota Dinas Persediaan Kedaluwarsa / Segera Kedaluwarsa",
        "sumber": ("kedaluwarsa", "segera_kedaluwarsa"),
        "headers": ["No", "Kode Barang", "Nama Barang", "Jumlah",
                    "Kedaluwarsa"],
        "widths": [28, 130, 200, 55, 85],
    },
}


def spek(jenis) -> dict:
    """Spesifikasi bentuk untuk `jenis`, atau {} bila tak dikenal.

    Mengembalikan dict kosong — bukan melempar — karena pemanggilnya adalah
    route yang sudah menyaring `jenis` lewat pola Query; melempar di sini
    hanya memindahkan galat yang sama ke tempat yang lebih sulit dibaca.
    """
    return dict(_SPEK.get(str(jenis or ""), {}))


def judul(jenis) -> str:
    return spek(jenis).get("judul", "NOTA DINAS")


def hal(jenis) -> str:
    return spek(jenis).get("hal", "-")


def perihal_agenda(jenis) -> str:
    """Perihal untuk buku agenda Persuratan — kalimat utuh satu baris.

    Sengaja BUKAN `judul`, yang memuat baris baru: perihal masuk ke daftar
    surat dan ke pesan penanda tangan, dan judul dua baris di sana terbaca
    sebagai dua entri.
    """
    return spek(jenis).get("perihal", "Nota Dinas Persediaan")


def nama_berkas(jenis, nomor="") -> str:
    """Nama berkas PDF. Nomor surat ikut bila ada — berkas nota terbit yang
    hanya bernama "Nota_Dinas_Stok_Kritis.pdf" akan saling menimpa di folder
    unduhan begitu nota kedua terbit pada bulan yang sama.
    """
    dasar = spek(jenis).get("berkas", "Nota_Dinas")
    aman = "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in str(nomor or "").strip())
    return f"{dasar}_{aman}.pdf" if aman else f"{dasar}.pdf"


def headers(jenis) -> list:
    return list(spek(jenis).get("headers", []))


def widths(jenis) -> list:
    return list(spek(jenis).get("widths", []))


def baris_terpilih(jenis, data, ids=()) -> list:
    """Baris peringatan untuk `jenis`, disaring ke `ids` bila diberikan.

    `ids` menyaring dan BUKAN menyisipkan: id yang tak ada di daftar peringatan
    diabaikan diam-diam, sehingga pemanggil tak bisa memasukkan barang yang
    sebenarnya tidak kritis/kedaluwarsa dengan mengarang idnya.
    """
    rows = []
    for kunci in spek(jenis).get("sumber", ()):
        rows.extend((data or {}).get(kunci) or [])
    pilih = {str(s).strip() for s in (ids or ()) if str(s).strip()}
    return [r for r in rows if r.get("id") in pilih] if pilih else rows


def bekukan(jenis, rows) -> list:
    """Snapshot baris untuk register — hanya `FIELD_BEKU[jenis]`.

    Nota dinas yang sudah bernomor adalah naskah yang terbit; mencetaknya ulang
    dari peringatan yang dihitung ulang akan menghasilkan daftar yang BERBEDA
    setiap kali stok bergerak, sementara nomornya tetap sama. Yang beredar dan
    yang tercetak lalu berselisih tanpa satu pun tanda.
    """
    field = FIELD_BEKU.get(str(jenis or ""), ())
    return [{k: r.get(k) for k in field} for r in (rows or [])]


def teks_jumlah(nilai) -> str:
    """Jumlah usulan untuk dicetak — "-" bila belum diisi.

    Petugas boleh menerbitkan nota tanpa mengisi jumlahnya (kadang jumlahnya
    memang ditentukan kemudian oleh pejabat pengadaan). Yang TIDAK boleh
    adalah menebak angkanya: nol yang tercetak sebagai "0" terbaca sebagai
    permintaan nol unit, dan angka karangan berbasis batas kritis akan
    terbaca sebagai permintaan resmi yang tak pernah diketik siapa pun.
    """
    try:
        n = int(nilai)
    except (TypeError, ValueError):
        return "-"
    return str(n) if n > 0 else "-"


def urai_pilihan(entri) -> tuple:
    """`["b1", "b2:10"]` → `({"b1", "b2"}, {"b2": 10})`.

    SATU format untuk dua jalur: parameter kueri `ids` pada pratinjau (dipisah
    koma) dan daftar `ids` pada penerbitan. Dua bentuk kawat untuk maksud yang
    sama adalah dua parser yang harus sepakat selamanya — dan yang satu selalu
    ketinggalan saat yang lain diperbaiki.

    Entri tanpa `:jumlah` tetap sah (perilaku lama), begitu pula jumlah yang
    tak masuk akal: ia DIABAIKAN, bukan dibulatkan diam-diam menjadi nol —
    angka yang dikarang dari masukan rusak akan tercetak di naskah resmi.
    """
    ids, jumlah = set(), {}
    for e in (entri or []):
        teks = str(e or "").strip()
        if not teks:
            continue
        kunci, _, angka = teks.partition(":")
        kunci = kunci.strip()
        if not kunci:
            continue
        ids.add(kunci)
        try:
            n = int(str(angka).strip())
        except (TypeError, ValueError):
            continue
        if n > 0:
            jumlah[kunci] = n
    return ids, jumlah


def sematkan_jumlah(rows, jumlah=None) -> list:
    """Tempelkan `jumlah_diusulkan` ke tiap baris — SALINAN, bukan di tempat.

    Baris yang masuk berasal dari hasil `peringatan_persediaan`, dan objek yang
    sama dipakai pemanggil lain (banner peringatan, cacah di layar). Menulis ke
    dalamnya berarti nota dinas diam-diam mengubah data yang bukan miliknya.
    """
    peta = jumlah or {}
    return [{**r, "jumlah_diusulkan": peta.get(str(r.get("id") or ""))}
            for r in (rows or [])]


def isi_tabel(jenis, rows, fmt_tanggal=None) -> list:
    """Isi tabel (tanpa baris kepala) sebagai teks siap cetak."""
    fmt = fmt_tanggal or (lambda v: str(v or ""))
    out = []
    for i, r in enumerate(rows or []):
        if jenis == "kritis":
            out.append([str(i + 1), str(r.get("kode_barang") or ""),
                        str(r.get("nama_barang") or ""),
                        str(r.get("satuan") or "-"), str(r.get("stok")),
                        str(r.get("batas_kritis") or 0),
                        teks_jumlah(r.get("jumlah_diusulkan"))])
        elif jenis == "kedaluwarsa":
            exp = str(r.get("expired") or "")
            out.append([str(i + 1), str(r.get("kode_barang") or ""),
                        str(r.get("nama_barang") or ""), str(r.get("qty")),
                        (fmt(exp) or exp)])
    return out


# Sebanyak ini barang disebut namanya di pesan penanda tangan; sisanya
# diringkas. Angkanya SENGAJA sama dengan `routes.ttd.MAKS_BARANG_RINGKAS` —
# diimpor dari sana akan membuat modul murni ini menarik seluruh modul TTD.
MAKS_BARANG_PESAN = 3


def ringkas_nota(nota) -> dict:
    """Nota dinas → ringkasan untuk pesan WA/email penanda tangan.

    `_ringkas_dokumen` mengembalikan {} untuk `doc_type` yang tak dikenalnya,
    dan itu tak terlihat sebagai galat: tautannya tetap benar, pesannya cuma
    menyusut jadi "judul + tautan". Penanda tangan lalu harus membuka tautan
    sekadar untuk tahu dokumen apa itu — dan setelah berbulan-bulan tak ada
    jejak yang bisa dicari di riwayat percakapannya. Persis keluhan yang sudah
    diperbaiki untuk BAST, lalu terulang pada LPB.
    """
    d = nota or {}
    items = d.get("items") or []
    try:
        jumlah = int(d.get("jumlah_barang") or 0)
    except (TypeError, ValueError):
        jumlah = 0
    penanda = str(d.get("kpb_nama") or "").strip()
    return {
        "nomor": str(d.get("nomor") or "").strip(),
        "perihal": perihal_agenda(d.get("jenis")),
        "tanggal": str(d.get("tanggal") or "")[:10],
        "pihak": ([f"{penanda} (Kuasa Pengguna Barang)"] if penanda else []),
        "barang": [{"kode": str((b or {}).get("kode_barang") or "").strip(),
                    "nup": "",
                    "nama": str((b or {}).get("nama_barang") or "").strip()}
                   for b in items[:MAKS_BARANG_PESAN]],
        # Panjang `items` bisa terpotong proyeksi pembacaan; jumlahnya tidak
        # boleh ikut menyusut — angka itu bermakna "berapa barang di nota".
        "jumlah_barang": jumlah or len(items),
    }


# ── Naskah: kepala lampiran dan narasi ─────────────────────────────────

JUDUL_LAMPIRAN = "LAMPIRAN NOTA DINAS"


def label_lampiran(ada_lampiran) -> str:
    """Isi baris "Lampiran" pada kepala naskah.

    Menyebut "1 (satu) berkas" pada naskah yang daftarnya justru tercetak di
    badan surat adalah keterangan yang salah: pembaca akan mencari berkas yang
    tak pernah ada, dan pengarsip akan mencatat lampiran yang tak pernah
    dikirim. Karena itu nilainya diturunkan dari keadaan naskah yang BENAR-
    BENAR tersusun, bukan dari ada-tidaknya barang.
    """
    return "1 (satu) berkas" if ada_lampiran else "-"


def _sebutan_daftar(terlampir) -> str:
    """"sebagaimana daftar terlampir" vs "sebagaimana daftar berikut".

    Surat yang menulis "terlampir" sementara tabelnya tercetak tepat di
    bawahnya membuat pembaca mencari halaman yang tak ada.
    """
    return "sebagaimana daftar terlampir" if terlampir else \
        "sebagaimana daftar berikut"


def narasi(jenis, tanggal_teks="", jumlah=0, horizon_hari=30, seleksi=False,
           terlampir=False) -> list:
    """Paragraf pengantar naskah — daftar string, satu paragraf per elemen.

    Ditulis panjang dan formal dengan sengaja. Nota dinas yang langsung
    melompat ke tabel tidak menjelaskan MENGAPA pengadaan diperlukan, sehingga
    pejabat yang menerimanya harus menyimpulkan sendiri urgensinya — dan
    dokumen yang tak menyatakan alasannya sulit dipertanggungjawabkan ketika
    kelak diperiksa.
    """
    j = str(jenis or "")
    tgl = str(tanggal_teks or "").strip()
    per_tanggal = f"per {tgl}" if tgl else "pada saat ini"
    daftar = _sebutan_daftar(terlampir)
    n = int(jumlah or 0)

    if j == "kritis":
        paragraf = [
            "Dalam rangka menjaga kelancaran pelaksanaan tugas dan fungsi "
            "serta mendukung tertib administrasi perkantoran dan mutu "
            "pelayanan pada satuan kerja ini, ketersediaan barang persediaan "
            "pada gudang perlu senantiasa dipertahankan pada tingkat yang "
            "memadai.",

            f"Berdasarkan hasil pemantauan atas catatan persediaan "
            f"{per_tanggal}, terdapat {n} jenis barang yang stoknya telah "
            f"HABIS atau berada pada/di bawah batas kritis, {daftar}. Apabila "
            f"kondisi tersebut tidak segera ditindaklanjuti, kegiatan "
            f"perkantoran sehari-hari serta pelayanan kepada unit kerja lain "
            f"berpotensi terhambat.",

            "Sehubungan dengan hal tersebut, dimohon kesediaan Saudara untuk "
            "memproses usulan pengadaan barang persediaan dimaksud sesuai "
            "ketentuan peraturan perundang-undangan yang berlaku, dengan "
            "memperhatikan kebutuhan riil serta ketersediaan anggaran pada "
            "tahun berjalan.",
        ]
    elif j == "kedaluwarsa":
        paragraf = [
            "Dalam rangka menjaga tertib pengelolaan Barang Milik Negara "
            "serta mencegah kerugian negara akibat barang persediaan yang "
            "tidak lagi layak pakai, persediaan yang mendekati masa "
            "kedaluwarsa perlu diawasi dan ditindaklanjuti secara berkala.",

            f"Berdasarkan hasil pemantauan atas catatan persediaan "
            f"{per_tanggal}, terdapat {n} catatan barang yang telah "
            f"kedaluwarsa atau akan kedaluwarsa dalam {horizon_hari} hari ke "
            f"depan, {daftar}. Barang dalam kondisi tersebut tidak dapat "
            f"digunakan untuk mendukung pelaksanaan tugas dan berpotensi "
            f"membebani nilai persediaan apabila dibiarkan.",

            "Sehubungan dengan hal tersebut, dimohon kesediaan Saudara untuk "
            "menindaklanjuti melalui pemakaian prioritas, pemindahan kepada "
            "unit kerja yang masih membutuhkan, atau pengusulan penghapusan "
            "sesuai ketentuan peraturan perundang-undangan yang berlaku.",
        ]
    else:
        return []

    if seleksi:
        # Dokumen resmi harus menyebut bahwa daftarnya SELEKSI, bukan seluruh
        # temuan. Tanpa kalimat ini pembaca menyimpulkan tak ada barang lain
        # yang bermasalah — dan kesimpulan itulah yang ia bawa ke tindak
        # lanjut.
        paragraf.append(
            "Perlu kami sampaikan bahwa daftar dimaksud memuat barang yang "
            "DIPILIH untuk diusulkan; barang lain yang berada dalam kondisi "
            "serupa sengaja tidak disertakan pada naskah ini.")

    paragraf.append(
        "Demikian disampaikan. Atas perhatian dan kerja sama Saudara, "
        "diucapkan terima kasih.")
    return paragraf
