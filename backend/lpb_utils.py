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


def baris_lpb_dari_aset(aset_dibuat) -> list:
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
