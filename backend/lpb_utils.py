"""LAPORAN PENERIMAAN BARANG (LPB) — helper MURNI, tanpa I/O dan tanpa DB.

LPB adalah dokumen yang menyatakan "barang ini benar-benar DITERIMA satker,
sekian jumlahnya, dalam kondisi begini, pada tanggal itu". Selama ini AMAN
hanya menerbitkannya untuk PERSEDIAAN — padahal laptop, kendaraan, dan gedung
juga diterima lewat pintu yang sama dan menuntut bukti terima yang sama.

TIGA KEPUTUSAN YANG MENENTUKAN BENTUK MODUL INI
================================================

1. **Satu BAST bisa melahirkan DUA jenis catatan.** Satu kontrak pengadaan
   lazim memuat kertas HVS (persediaan) DAN printer (aset) sekaligus. Memaksa
   operator memilah sendiri lalu menekan dua tombol berbeda adalah pekerjaan
   yang komputer bisa lakukan tanpa salah — dan yang manusia PASTI salah
   sesekali. Karena itu pemilahan hidup di sini, sebagai fungsi murni yang
   bisa diuji, bukan tersebar di dua endpoint.

2. **Golongan barang ditentukan oleh DIGIT PERTAMA kode barang**, mengikuti
   kodefikasi BMN: golongan 1 = Persediaan, 2 = Tanah, 3 = Peralatan & Mesin,
   4 = Gedung & Bangunan, 5 = Jalan/Irigasi/Jaringan, 6 = Aset Tetap Lainnya,
   7 = KDP, 8 = Aset Tak Berwujud. Aturan ini SUDAH dipakai
   `daftarkan_persediaan`; di sini ia dinaikkan jadi satu tempat bernama
   supaya kedua jalur tak bisa lagi berbeda pendapat diam-diam.

3. **Barang tanpa kode bukan barang persediaan, dan bukan pula aset.** Ia
   barang yang BELUM BISA DICATAT. Menebaknya ke salah satu keranjang akan
   membuat satu baris BAST menghilang tanpa jejak — jadi ia jadi keranjang
   ketiga yang eksplisit, untuk dilaporkan balik ke operator.
"""

# Digit pertama kode barang → golongan BMN (kodefikasi Kemenkeu).
GOLONGAN_BARANG = {
    "1": "Persediaan",
    "2": "Tanah",
    "3": "Peralatan dan Mesin",
    "4": "Gedung dan Bangunan",
    "5": "Jalan, Irigasi, dan Jaringan",
    "6": "Aset Tetap Lainnya",
    "7": "Konstruksi Dalam Pengerjaan",
    "8": "Aset Tak Berwujud",
}

# Kategori LPB. Bukan sekadar label: menentukan kolom mana yang dicetak (NUP
# hanya bermakna untuk BMN) dan judul dokumennya. `gabungan` = satu LPB yang
# merangkum BANYAK BAST PPK-KPB sekaligus — aset dan persediaan dalam satu
# surat laporan (permintaan pemilik).
KATEGORI_LPB = {
    "persediaan": "Persediaan",
    "aset": "Barang Milik Negara (Aset Tetap)",
    "gabungan": "Gabungan Aset & Persediaan",
}


def golongan_kode(kode) -> str:
    """Digit pertama kode barang — '' bila kode kosong/tak berdigit."""
    k = str(kode or "").strip()
    return k[0] if k and k[0].isdigit() else ""


def label_golongan(kode) -> str:
    """Nama golongan BMN untuk kode barang; '' bila tak dikenali."""
    return GOLONGAN_BARANG.get(golongan_kode(kode), "")


def is_persediaan(kode) -> bool:
    """Kode barang termasuk golongan 1 (Persediaan)?

    Sengaja BUKAN `kode.startswith('1')` yang tersebar di pemanggil: kode
    kosong harus menjawab False di sini, dan pemanggil tak boleh menebak.
    """
    return golongan_kode(kode) == "1"


def sudah_tercatat(baris) -> bool:
    """Baris BAST ini sudah punya tujuan pencatatannya?

    `asset_id` = sudah jadi aset; `psd_item_id` = sudah masuk kartu stok.
    Salah satunya cukup — sebuah baris hanya boleh punya SATU tujuan.
    """
    b = baris or {}
    return bool(str(b.get("asset_id") or "").strip()
                or str(b.get("psd_item_id") or "").strip())


def pilah_barang_perolehan(barang, hanya_belum_tercatat: bool = True) -> dict:
    """Baris barang BAST → tiga keranjang tujuan pencatatan.

    - `persediaan`  — golongan 1: masuk stok lewat jurnal FIFO.
    - `aset`        — golongan 2–8: jadi draft aset ber-NUP.
    - `tanpa_kode`  — kode kosong: TIDAK BISA dicatat ke mana pun. Bukan
                      kesalahan operator yang perlu dihukum dengan diam;
                      dikembalikan apa adanya supaya layar bisa berkata
                      "tiga baris ini butuh kode barang dulu".

    `hanya_belum_tercatat` (bawaan True) MENGABAIKAN baris yang sudah punya
    `asset_id`/`psd_item_id`. Ini bukan kenyamanan, melainkan penutup JALAN
    BUNTU (temuan audit adversarial): dulu baris yang sudah jadi aset tetap
    dihitung sebagai "aset", sehingga gerbang `activity_id` di
    `catat_semua_barang` menuntut kegiatan untuk pekerjaan yang sudah selesai —
    sementara layar TIDAK merender dropdown-nya karena ia menghitung baris yang
    BELUM tertaut. Hasilnya galat 400 yang menyuruh memilih sesuatu yang tak
    pernah muncul, dan sisi persediaan BAST setengah-jalan macet permanen.

    Tiap keranjang memuat `(indeks_asli, baris)` — indeksnya dipertahankan
    karena `POST /pengadaan/{id}/tautkan` mengalamatkan baris dengan indeks,
    dan keranjang yang kehilangan indeks membuat hasil tak bisa ditautkan
    balik ke baris yang melahirkannya.
    """
    hasil = {"persediaan": [], "aset": [], "tanpa_kode": []}
    for i, b in enumerate(barang or []):
        row = b or {}
        if hanya_belum_tercatat and sudah_tercatat(row):
            continue
        kode = str(row.get("kode") or "").strip()
        if not kode:
            hasil["tanpa_kode"].append((i, row))
        elif is_persediaan(kode):
            hasil["persediaan"].append((i, row))
        else:
            hasil["aset"].append((i, row))
    return hasil


def _angka(v, bawaan=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return bawaan


def baris_lpb_dari_aset(aset_dibuat, sumber=None) -> list:
    """Aset draft yang baru dibuat → baris tabel LPB.

    `aset_dibuat` = daftar dict berisi minimal asset_code/NUP/asset_name +
    `harga_satuan` baris BAST asalnya. Satu unit = satu baris ber-NUP: itulah
    seluruh gunanya LPB aset — membuktikan NUP mana saja yang benar-benar
    masuk, bukan sekadar "printer 5 unit".

    JUMLAH TIDAK SELALU 1 (temuan audit adversarial). Pemecahan per-NUP di
    `buat_draft_aset_dari_perolehan` hanya berlaku untuk jumlah bulat 2..50;
    di luar itu (100 kursi, atau 2,5 ton) satu draft mewakili SELURUH baris
    BAST. Mematok `jumlah: 1` membuat LPB — dokumen resmi yang menyatakan
    berapa banyak barang diterima — menyebut 1 unit padahal 100 datang, dan
    total nilainya ikut mengecil seratus kali lipat. Karena itu pemanggil
    boleh menitipkan `jumlah_bast`; bila ada, itulah yang dicetak.

    `sumber` = snapshot register asalnya (lihat `snapshot_sumber`), dilekatkan
    ke SETIAP baris. LPB dari satu BAST memang hanya punya satu sumber, jadi
    bundelnya tercetak sekali di bawah tabel — bukan berulang per baris.
    Gunanya: tanggal kedatangan, PPK berikut NIP-nya, dan No. Bukti/Faktur
    berdiri di area tabel, tempat pemeriksa membacanya bersama barangnya —
    sehingga kepala surat berhenti mengulangnya (`kepala_tercakup`).
    """
    baris = []
    for a in aset_dibuat or []:
        d = a or {}
        harga = _angka(d.get("harga_satuan"))
        jml = _angka(d.get("jumlah_bast"), 1.0) or 1.0
        # Angka bulat dicetak tanpa ekor desimal (100, bukan 100.0).
        jml = int(jml) if float(jml).is_integer() else jml
        baris.append({
            "asset_id": str(d.get("id") or d.get("asset_id") or ""),
            "kode_barang": str(d.get("asset_code") or "").strip(),
            "nup": str(d.get("NUP") or d.get("nup") or "").strip(),
            "nama_barang": str(d.get("asset_name") or "").strip(),
            "golongan": label_golongan(d.get("asset_code")),
            "jumlah": jml, "satuan": str(d.get("satuan") or "Unit"),
            "harga_satuan": harga, "total": round(harga * float(jml), 2),
            "keterangan": str(d.get("keterangan") or "Kondisi Baik & Lengkap"),
            **({"sumber": dict(sumber)} if sumber else {}),
        })
    return baris


def snapshot_sumber(perolehan) -> dict:
    """Penyedia, PPK, dan dokumen pengadaan satu register → dict datar.

    MURNI. Dibekukan ke dalam baris LPB supaya dokumen yang sudah terbit tak
    berubah isinya ketika registernya kelak disunting.
    """
    from pengadaan_dokumen import bersihkan_dokumen

    d = perolehan or {}
    return {
        "penyedia": str(d.get("pihak") or "").strip(),
        "ppk_nama": str(d.get("ppk_nama") or "").strip(),
        "ppk_nip": str(d.get("ppk_nip") or "").strip(),
        # Status kepegawaian PPK ikut DIBEKUKAN supaya aturan privasi NIP
        # (Non-ASN/NIK tak dicetak) bisa ditegakkan dari keadaan SAAT dokumen
        # terbit — sama seperti yang dilakukan kepala surat LPB.
        "ppk_status_kepegawaian": str(d.get("ppk_status_kepegawaian") or "").strip(),
        "nomor_bast_ppk": str(((d.get("bast_ppk") or {}).get("nomor")) or "").strip(),
        "nomor_bast": str(d.get("nomor_bast") or "").strip(),
        # Tanggal BAST penyedia → PPK = saat barangnya DATANG. Dibekukan per
        # register karena satu LPB gabungan merangkum banyak BAST dengan
        # tanggal berbeda-beda; satu tanggal di kepala surat tak bisa mewakili
        # semuanya.
        "tanggal_bast": str(d.get("tanggal_bast") or "").strip()[:10],
        "sifat": str(d.get("sifat") or "").strip(),
        **bersihkan_dokumen(d),
    }


def bundel_sumber(sumber) -> str:
    """Satu baris ringkas: penyedia · PPK · sifat · dokumen · BAST asalnya.

    Digabung menjadi SATU untai, bukan kolom-kolom tersendiri. Tabel LPB sudah
    berisi delapan kolom; menambah enam kolom dokumen akan menyempitkan nama
    barang sampai tak terbaca, dan sebagian besar barisnya akan kosong karena
    tiap register hanya memakai satu jalur pembayaran. Yang kosong tidak ikut
    dicetak. MURNI.
    """
    from pengadaan_dokumen import (
        DOKUMEN_PENGADAAN, JENIS_UP, SIFAT_PENGADAAN,
    )

    from pegawai_utils import baris_identitas_ttd
    from pelaporan_utils import tanggal_id_singkat

    s = sumber or {}
    bagian = []
    if s.get("penyedia"):
        bagian.append(f"Penyedia: {s['penyedia']}")
    if s.get("ppk_nama"):
        ppk = f"PPK: {s['ppk_nama']}"
        # NIP PPK MENEMPEL pada barisnya (permintaan pemilik). Satu LPB
        # gabungan merangkum banyak BAST dengan PPK yang bisa berbeda; NIP di
        # kepala surat hanya bisa menyebut satu orang.
        #
        # Melewati `baris_identitas_ttd` — ATURAN SISTEM yang sama dengan blok
        # tanda tangan: Non-ASN dan nomor berformat NIK tidak dicetak.
        nip = baris_identitas_ttd(s.get("ppk_nip"),
                                  s.get("ppk_status_kepegawaian"))
        if nip:
            ppk += f" ({nip[0]})"
        bagian.append(ppk)
    if s.get("tanggal_bast"):
        bagian.append("Tgl kedatangan: "
                      + (tanggal_id_singkat(s["tanggal_bast"]) or s["tanggal_bast"]))
    sifat = str(s.get("sifat") or "").strip()
    if sifat in SIFAT_PENGADAAN:
        bagian.append(SIFAT_PENGADAAN[sifat].split(" (")[0])
    for d in DOKUMEN_PENGADAAN:
        v = str(s.get(d["kunci"]) or "").strip()
        if not v:
            continue
        bagian.append(f"{d['label']}: "
                      + (JENIS_UP.get(v, v) if d["kunci"] == "jenis_up" else v))
    asal = (f"BAST PPK-KPB {s['nomor_bast_ppk']}" if s.get("nomor_bast_ppk")
            else (f"BAST {s['nomor_bast']}" if s.get("nomor_bast") else ""))
    if asal:
        bagian.append(asal)
    return " · ".join(bagian)


def rentang_nup(nups) -> str:
    """Rentang NUP dari sekumpulan nomor: "1", "1–3", atau "1, 4–6". MURNI.

    Pemilik meminta kolom NUP menyebut "dari nomor berapa sampai berapa".
    Mencetak seluruh nomor satu per satu membuat kolomnya melar pada perolehan
    berisi puluhan unit; mencetak nomor PERTAMA saja — perilaku lama — membuat
    dokumen berkata "5 printer diterima" tanpa bisa membuktikan printer YANG
    MANA. Rentang menjawab keduanya, dan celah di tengahnya tetap terlihat.
    """
    angka = sorted({int(x) for x in (nups or [])
                    if str(x).strip().lstrip("-").isdigit()})
    if not angka:
        return ""
    potong, mulai, akhir = [], angka[0], angka[0]
    for n in angka[1:]:
        if n == akhir + 1:
            akhir = n
            continue
        potong.append((mulai, akhir))
        mulai = akhir = n
    potong.append((mulai, akhir))
    return ", ".join(str(a) if a == b else f"{a}\u2013{b}" for a, b in potong)


def baris_lpb_gabungan(perolehan_list) -> list:
    """Seluruh baris barang dari BANYAK perolehan → baris tabel LPB gabungan.

    LPB gabungan merangkum semua BAST PPK-KPB dalam SATU surat laporan —
    aset maupun persediaan, apa adanya per baris BAST. Tiap baris membawa
    keterangan nomor BAST PPK-KPB asalnya (fallback: nomor BAST penyedia)
    supaya pemeriksa bisa menelusuri setiap baris kembali ke dokumen serah
    terimanya tanpa membuka register.

    NUP hanya terisi untuk baris yang sudah tertaut aset — dan itu pun NUP
    unit PERTAMA (pemecahan per-NUP hanya menautkan balik unit pertamanya).
    Dokumen ini rekap penerimaan, bukan pengganti LPB per-NUP; rinciannya
    tetap di LPB aset masing-masing BAST.
    """
    baris = []
    for p in perolehan_list or []:
        d = p or {}
        ref = str(((d.get("bast_ppk") or {}).get("nomor")) or "").strip()
        sumber = (f"BAST PPK-KPB {ref}" if ref
                  else f"BAST {str(d.get('nomor_bast') or '-').strip()}")
        for b in d.get("barang") or []:
            row = b or {}
            harga = _angka(row.get("harga_satuan"))
            jml = _angka(row.get("jumlah"), 1.0) or 1.0
            jml = int(jml) if float(jml).is_integer() else jml
            baris.append({
                "asset_id": str(row.get("asset_id") or ""),
                "kode_barang": str(row.get("kode") or "").strip(),
                "nup": str(row.get("NUP") or "").strip(),
                "nama_barang": str(row.get("uraian") or "").strip(),
                "golongan": label_golongan(row.get("kode")),
                "jumlah": jml, "satuan": "",
                "harga_satuan": harga, "total": round(harga * float(jml), 2),
                "keterangan": sumber,
                # Keterangan SUMBER yang melekat pada baris ini — penyedia,
                # PPK, dan dokumen pengadaannya. Dilekatkan PER BARIS, bukan
                # sekali di kepala surat: LPB gabungan merangkum banyak BAST
                # sekaligus, dan satu kepala surat hanya bisa menyebut satu
                # penyedia. Pembaca yang ingin tahu barang ini datang dari
                # rekanan mana harus bisa membacanya di barisnya sendiri.
                "sumber": snapshot_sumber(d),
                "perolehan_id": str(d.get("id") or ""),
            })
    return baris


def total_nilai_lpb(items) -> float:
    """Jumlah kolom Total pada tabel LPB."""
    return sum(_angka((b or {}).get("total")) for b in items or [])


def ringkas_pencatatan(hasil_aset, hasil_persediaan, tanpa_kode=0) -> dict:
    """Gabungkan hasil dua jalur pencatatan jadi satu ringkasan untuk layar.

    Operator menekan SATU tombol; ia berhak melihat SATU jawaban. Angka gagal
    dan daftar alasannya tetap dibawa apa adanya — jalur massal di aplikasi
    ini memang tak transaksional (Mongo standalone), dan menyembunyikan
    kegagalan sebagian justru bentuk kebohongan yang paling mahal di sini.
    """
    a = hasil_aset or {}
    p = hasil_persediaan or {}
    gagal = list(a.get("gagal") or []) + list(p.get("gagal") or [])
    return {
        "aset_dibuat": int(a.get("dibuat") or 0),
        "aset_dilewati_tertaut": int(a.get("dilewati_tertaut") or 0),
        "persediaan_masuk": int(p.get("masuk") or 0),
        "persediaan_master_baru": int(p.get("dibuat_master") or 0),
        "persediaan_dilewati_terdaftar": int(p.get("dilewati_sudah_terdaftar") or 0),
        "tanpa_kode": int(tanpa_kode or 0),
        "gagal": gagal[:40],
        "total_gagal": len(gagal),
    }


def pesan_ringkas(r) -> str:
    """Ringkasan satu kalimat untuk toast — bahasa manusia, bukan JSON."""
    r = r or {}
    bagian = []
    if r.get("aset_dibuat"):
        bagian.append(f"{r['aset_dibuat']} aset")
    if r.get("persediaan_masuk"):
        bagian.append(f"{r['persediaan_masuk']} barang persediaan")
    inti = " dan ".join(bagian) if bagian else "tidak ada barang baru"
    ekor = []
    if r.get("tanpa_kode"):
        ekor.append(f"{r['tanpa_kode']} baris belum berkode barang")
    if r.get("total_gagal"):
        ekor.append(f"{r['total_gagal']} gagal")
    return f"Tercatat: {inti}" + (f" ({'; '.join(ekor)})" if ekor else "")


# Awalan keterangan yang DIBANGKITKAN SENDIRI saat LPB gabungan terbit
# (routes/pengadaan.py). Nomor-nomor sesudahnya sudah tercetak pula pada
# bundel sumber di area tabel.
AWALAN_KETERANGAN_GABUNGAN = "Gabungan seluruh BAST PPK-KPB:"


def nilai_berulang(nilai, teks_tabel) -> bool:
    """True bila `nilai` sudah tercetak apa adanya di area tabel. MURNI.

    Dipakai kepala surat LPB untuk MENJATUHKAN barisnya sendiri. Penyedia,
    PPK, dan NIP-nya kini muncul pada bundel sumber di dalam/di bawah tabel;
    mencetaknya lagi di kepala membuat pembaca membandingkan dua tempat yang
    selalu sama — dan yang selalu sama berhenti dibaca.
    """
    v = str(nilai or "").strip()
    return bool(v) and v in str(teks_tabel or "")


# Kunci kepala surat LPB yang BISA dijatuhkan karena barisnya sudah membawa
# keterangan yang sama. Bukan sekadar daftar label: tiap kunci menunjuk field
# di snapshot sumber baris, dan itulah yang menentukan "sudah tercetak" berarti
# apa (lihat `kepala_tercakup`).
FIELD_KEPALA_LPB = {
    "penyedia": "penyedia",
    "ppk_nama": "ppk_nama",
    "tanggal": "tanggal_bast",
}


def kepala_tercakup(items) -> set:
    """Kunci kepala surat LPB yang sudah tercetak pada SETIAP baris tabel.

    Permintaan pemilik: *"pada header informasi mengenai tanggal kedatangan,
    PPK, dan No. Bukti/Faktur masih ada, tolong hapus karena sudah ada di
    informasi setiap row bagian BAST yang ada."*

    SYARATNYA "SETIAP", BUKAN "ADA SATU". Satu LPB gabungan bisa memuat BAST
    yang PPK-nya tercatat dan BAST lain yang tidak. Menjatuhkan baris kepala
    karena sebagian baris sudah menyebutnya akan MENGHILANGKAN keterangan bagi
    baris yang belum — pemangkasan pengulangan tak boleh berubah jadi
    kehilangan informasi. Karena itu satu baris yang tak membawanya sudah cukup
    untuk mempertahankan kepala suratnya.

    `ppk_nip` diperiksa lewat `baris_identitas_ttd`, bukan lewat ada-tidaknya
    nomor: aturan sistem melarang NIP Non-ASN/NIK dicetak, jadi baris yang
    punya nomor tetapi tak boleh mencetaknya BELUM mencakup apa pun.

    MURNI. → himpunan kunci dari `FIELD_KEPALA_LPB` + "ppk_nip".
    """
    from pegawai_utils import baris_identitas_ttd

    rows = [b for b in (items or []) if isinstance(b, dict)]
    if not rows:
        return set()
    tercakup = set(FIELD_KEPALA_LPB) | {"ppk_nip"}
    for b in rows:
        s = b.get("sumber") or {}
        if not isinstance(s, dict):
            s = {}
        for kunci, field in FIELD_KEPALA_LPB.items():
            if not str(s.get(field) or "").strip():
                tercakup.discard(kunci)
        if not baris_identitas_ttd(s.get("ppk_nip"),
                                  s.get("ppk_status_kepegawaian")):
            tercakup.discard("ppk_nip")
    return tercakup


def keterangan_berulang(keterangan, teks_tabel) -> bool:
    """True HANYA bila keterangan sekadar mengulang nomor BAST yang sudah
    tercetak. MURNI.

    Sengaja SEMPIT: hanya keterangan berbentuk bangkitan sendiri
    ("Gabungan seluruh BAST PPK-KPB: A; B") yang seluruh nomornya sudah ada
    di area tabel. Keterangan yang DITULIS OPERATOR selalu bertahan — membuang
    kalimat orang karena kebetulan memuat nomor yang sama adalah kehilangan
    informasi, bukan pemangkasan pengulangan.
    """
    k = str(keterangan or "").strip()
    if not k.startswith(AWALAN_KETERANGAN_GABUNGAN):
        return False
    sisa = k[len(AWALAN_KETERANGAN_GABUNGAN):]
    nomor = [n.strip() for n in sisa.split(";") if n.strip()]
    teks = str(teks_tabel or "")
    return bool(nomor) and all(n in teks for n in nomor)


# ── NUP versus kuantitas BAST ───────────────────────────────────────────────
#
# Permintaan pemilik: *"pada saat LPB akan dibuat pastikan untuk dapat
# mengingatkan tentang NUP dan pastikan sesuai dengan jumlahnya."*
#
# BMN ber-jumlah N seharusnya menjadi N aset ber-NUP masing-masing. Jalur
# pencatatan memecahnya HANYA bila jumlahnya bilangan bulat 2..50; di luar itu
# — pecahan, atau lebih dari 50 — seluruh baris menjadi SATU NUP dan sisanya
# cuma jadi catatan teks pada `notes`.
#
# Selisih itu tidak pernah menghasilkan galat: LPB tetap terbit, jurnalnya
# tetap tertulis, dan yang membacanya berbulan kemudian melihat "1 unit"
# untuk 100 rim yang benar-benar datang. Modul ini membuatnya TERLIHAT di
# detik pencatatan, saat masih bisa diperbaiki.

BATAS_PECAH_NUP = 50


def unit_per_baris(jumlah) -> int:
    """Berapa aset ber-NUP yang dibentuk dari SATU baris BAST. MURNI.

    Inilah aturan yang benar-benar dipakai jalur pencatatan — didefinisikan
    di sini supaya peringatan dan pelaksanaannya tak pernah berselisih.
    Sebelumnya aturan ini hanya hidup sebagai satu baris di dalam
    `buat_draft_aset_dari_perolehan`, sehingga tak ada cara memperingatkan
    tanpa menyalinnya.
    """
    import math
    try:
        j = float(jumlah if jumlah is not None else 1)
    except (TypeError, ValueError):
        return 1
    # NaN/Infinity DIPERIKSA lebih dulu: `int(nan)` melempar ValueError, dan
    # `nan != int(nan)` sudah meledak sebelum sempat dinilai. Jalur API
    # menolaknya lewat validator, tetapi helper murni ini juga dipanggil atas
    # data yang SUDAH tersimpan — termasuk data era lama.
    if not math.isfinite(j):
        return 1
    if j != int(j) or not (2 <= j <= BATAS_PECAH_NUP):
        return 1
    return int(j)


def _angka_aman(v, bawaan=0.0) -> float:
    try:
        return float(v if v is not None else bawaan)
    except (TypeError, ValueError):
        return bawaan


def porsi_baris(jumlah, n_unit) -> float:
    """Berapa bagian SATU baris BAST yang diwakili oleh SATU draft aset. MURNI.

    Pemecahan per-NUP hanya berlaku untuk jumlah bulat 2..50 (`unit_per_baris`).
    Di luar itu — 100 kursi, atau 2,5 ton besi — SATU draft berdiri untuk
    SELURUH baris, karena register aset tak punya field kuantitas sama sekali:
    satu record = satu NUP = satu barang.

    Angka inilah yang menentukan TIGA hal yang dulu dihitung sendiri-sendiri
    dan karenanya sempat berselisih:

      1. `jumlah_bast` pada baris LPB — sudah benar sejak awal;
      2. nilai perolehan draft (`purchase_price`) — dulu SELALU harga satuan,
         sehingga satu record yang berdiri untuk 100 kursi tercatat seharga
         satu kursi;
      3. nilai entri jurnal Buku Barang — cacat yang sama, sehingga Neraca
         kurang catat sebesar (jumlah − 1) × harga satuan.

    → 1.0 bila barisnya dipecah per unit; jumlah baris itu sendiri bila tidak.
    """
    if n_unit and n_unit > 1:
        return 1.0
    try:
        j = float(jumlah if jumlah is not None else 1)
    except (TypeError, ValueError):
        return 1.0
    import math
    # Sejalan dengan `unit_per_baris`: nilai tak-hingga/NaN tak boleh menjadi
    # pengali nilai rupiah — satu baris cacat akan meracuni seluruh Neraca.
    if not math.isfinite(j) or j <= 0:
        return 1.0
    return j


def peringatan_nup(barang, aset_dibuat) -> list:
    """Peringatan NUP untuk baris jalur ASET. MURNI.

    → [{kode, uraian, jumlah_bast, nup_terbentuk, sebab, pesan}]

    Dua jenis selisih yang keduanya bergejala nihil:

    `kuantitas_tak_terwakili` — barisnya utuh diproses, tetapi kuantitasnya
    tak bisa dipecah menjadi NUP (pecahan, atau di atas batas). Satu NUP
    berdiri mewakili banyak unit.

    `nup_kurang` — pemecahan berhenti di tengah (mis. kode kembar ditolak),
    sehingga NUP yang terbentuk lebih sedikit daripada yang direncanakan.

    Baris yang MEMANG tak diproses — sudah tertaut, tanpa kode, atau
    bergolongan persediaan — bukan selisih dan tidak dilaporkan di sini.
    """
    dibuat = aset_dibuat or []
    per_kode = {}
    for a in dibuat:
        k = str((a or {}).get("asset_code") or "").strip()
        per_kode[k] = per_kode.get(k, 0) + 1

    keluar = []
    for b in barang or []:
        row = b or {}
        kode = str(row.get("kode") or "").strip()
        if not kode or is_persediaan(kode) or str(row.get("asset_id") or "").strip():
            continue
        jumlah = _angka_aman(row.get("jumlah"), 1.0)
        rencana = unit_per_baris(jumlah)
        terbentuk = min(per_kode.get(kode, 0), rencana)
        per_kode[kode] = max(0, per_kode.get(kode, 0) - terbentuk)
        uraian = str(row.get("uraian") or "").strip() or "(tanpa uraian)"
        jml_teks = f"{jumlah:g}"
        if terbentuk < rencana:
            keluar.append({
                "kode": kode, "uraian": uraian, "jumlah_bast": jumlah,
                "nup_terbentuk": terbentuk, "sebab": "nup_kurang",
                "pesan": (f"{uraian} ({kode}): {terbentuk} dari {rencana} NUP "
                          "terbentuk — sisanya gagal dan TIDAK masuk LPB."),
            })
            continue
        if rencana == 1 and jumlah != 1:
            sebab = ("pecahan" if jumlah != int(jumlah)
                     else "melebihi_batas")
            alasan = ("jumlahnya pecahan"
                      if sebab == "pecahan"
                      else f"jumlahnya melebihi {BATAS_PECAH_NUP} unit")
            keluar.append({
                "kode": kode, "uraian": uraian, "jumlah_bast": jumlah,
                "nup_terbentuk": 1, "sebab": sebab,
                "pesan": (f"{uraian} ({kode}): BAST menyebut {jml_teks} unit "
                          f"tetapi hanya 1 NUP terbentuk karena {alasan}. "
                          "Pecah barisnya bila tiap unit perlu NUP sendiri."),
            })
    return keluar
