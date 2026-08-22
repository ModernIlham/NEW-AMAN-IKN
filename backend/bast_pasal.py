"""Pustaka PASAL Berita Acara Serah Terima (BAST) — logika murni.

Naskah BAST wajib muat **maksimal 2 halaman termasuk tanda tangan**. Karena
itu pustaka ini disusun PADAT: satu gagasan satu butir, tanpa mengulang apa
yang sudah dinyatakan di pasal lain. Yang disediakan:

1. `butir_waktu(jenis)` — kedudukan BMN pada jam kerja, di luar jam kerja,
   hari libur, kerja di luar kantor, dan perjalanan dinas. Digabung ke dalam
   pasal Tanggung Jawab oleh pemanggil (dulu pasal tersendiri).
2. `butir_khusus_bidang(kode)` — kekhususan per **BIDANG** kode barang, satu
   butir per bidang (dulu satu PASAL per bidang berisi 3-6 butir).
3. `butir_risiko(jenis)` — kehilangan/kerusakan, ganti rugi, keadaan kahar.

── Kunci pencocokan ─────────────────────────────────────────────────────────
Kode barang BMN berlapis (lihat `kodefikasi_utils`): golongan 1 digit,
**bidang 3 digit**, kelompok 5, sub kelompok 7, sub-sub kelompok 10. Sesuai
permintaan pemilik, kebijakan disusun **per BIDANG**. Pencocokan memakai
prefix TERPANJANG lebih dulu (bidang "302" mengalahkan golongan "3"), pola
yang sama dengan `frontend/src/lib/kelengkapanBmn.js`.

── Dasar penyusunan (riset Agustus 2026; rinci di
   docs/PUSTAKA-REGULASI-BMN.md §11C) ──────────────────────────────────────
PP 27/2014 jo. PP 28/2020 (Ps. 42-43) · PMK 40/2024 · UU 1/2004 Ps. 59-64 jo.
PP 38/2016 (ganti rugi) · PP 94/2021 (disiplin) · PMK 97/2019 jo. PMK 43/2025
(asuransi, sifat "dapat" → klausul klaim bersyarat) · UU 27/2022 (PDP).

Norma "hanya hari dan jam kerja" untuk kendaraan dinas TIDAK berasal dari satu
PMK nasional, melainkan aturan internal instansi di atas prinsip PP 27/2014 —
karena itu ditulis sebagai kaidah internal yang dioperasionalkan lewat surat
tugas/izin tertulis, bukan kutipan pasal.

MURNI: tanpa Mongo/IO, seluruhnya teruji unit.
"""

# Panjang prefix bidang (selaras kodefikasi_utils.LEVEL_LENGTHS[2]).
PANJANG_BIDANG = 3

# Jenis BAST yang MEMINDAHKAN penguasaan ke pemegang — butir konteks waktu &
# risiko hanya relevan di sini. Pada BAST pengembalian barang justru kembali
# ke satker, sehingga kewajiban penggunaan tidak lagi dibebankan.
JENIS_PENGUASAAN = (
    "penggunaan_melekat",
    "mutasi_pengguna",
    "operasional_unit",
    "penggunaan_sementara",
    "lainnya",
)


def bidang_kode(kode) -> str:
    """Prefix BIDANG (3 digit) dari kode barang; "" bila kode tak memadai.
    Kode pendek dikembalikan apa adanya agar tetap cocok ke aturan golongan."""
    s = "".join(ch for ch in str(kode or "") if ch.isdigit())
    return s[:PANJANG_BIDANG] if s else ""


def butir_waktu(jenis: str):
    """Butir konteks waktu & tempat — DUA butir padat yang menyerap seluruh
    isi pasal lama: kedinasan di dalam/di luar jam kerja, hari libur, lembur/
    piket, kerja di luar kantor, perjalanan dinas, pencatatan barang keluar,
    dan larangan pemakaian non-kedinasan. [] bila penguasaan tidak beralih."""
    if jenis not in JENIS_PENGUASAAN:
        return []
    return [
        "BMN digunakan semata-mata untuk kepentingan kedinasan. Penggunaan di "
        "luar jam kerja, pada hari libur, atau di luar kantor — termasuk "
        "lembur, piket, kerja fleksibel, dan perjalanan dinas — dilaksanakan "
        "berdasarkan surat tugas/izin tertulis atasan, tetap menjadi tanggung "
        "jawab PIHAK KEDUA, dan pengeluaran barang dari kantor dicatat pada "
        "buku keluar-masuk barang.",
        "Penggunaan untuk kepentingan pribadi, usaha, politik praktis, atau "
        "pihak lain di luar kedinasan DILARANG pada waktu kapan pun, dan "
        "dapat dikenai hukuman disiplin sesuai ketentuan.",
    ]


def butir_risiko(jenis: str):
    """Butir kehilangan/kerusakan — TIGA butir padat (dulu enam)."""
    if jenis not in JENIS_PENGUASAAN:
        return []
    return [
        "Kehilangan atau kerusakan dilaporkan tertulis kepada PIHAK KESATU "
        "paling lambat 1x24 jam sejak diketahui; bila terjadi di luar jam "
        "kerja atau hari libur, laporan pertama dapat lisan/elektronik dan "
        "dituangkan tertulis pada hari kerja berikutnya, dilengkapi kronologi "
        "serta Surat Keterangan Kehilangan dari kepolisian untuk kasus hilang.",
        "Kerugian negara karena kelalaian PIHAK KEDUA diselesaikan melalui "
        "tuntutan ganti kerugian sesuai Undang-Undang Nomor 1 Tahun 2004 dan "
        "Peraturan Pemerintah Nomor 38 Tahun 2016, dan dapat beralih kepada "
        "ahli waris sesuai ketentuan.",
        "Kerusakan/kehilangan karena keadaan kahar yang dibuktikan surat "
        "keterangan instansi berwenang serta keausan pemakaian wajar bukan "
        "kelalaian PIHAK KEDUA; terhadap BMN yang diasuransikan, PIHAK KEDUA "
        "membantu kelengkapan klaim.",
    ]


# ── Kekhususan per bidang — SATU butir padat per bidang ────────────────────
# Kunci = prefix kode barang (bidang 3 digit; golongan 1 digit sebagai jaring
# terakhir). Nilai = (nama bidang, kalimat kewajiban).

PASAL_BIDANG = {
    # Golongan 2 — Tanah
    "2": ("Tanah",
          "menjaga batas dan patok/plang, melarang penguasaan pihak lain "
          "tanpa alas hak, melaporkan indikasi sengketa, serta tidak "
          "memanfaatkan tanah untuk pihak lain tanpa persetujuan berwenang"),

    # Golongan 3 — Peralatan dan Mesin
    "3": ("Peralatan dan Mesin",
          "mengoperasikan sesuai buku manual dan tidak membongkar/memodifikasi "
          "atau memperbaiki di luar jalur resmi tanpa persetujuan tertulis"),
    "301": ("Alat Besar",
            "memastikan alat hanya dioperasikan operator yang ditunjuk dan "
            "berkompetensi/berlisensi dengan penerapan keselamatan kerja, "
            "mencatat jam operasi, serta memperoleh izin tertulis untuk "
            "pengoperasian di luar jam atau lokasi kerja"),
    "302": ("Kendaraan Dinas",
            "menggunakan kendaraan untuk kedinasan pada hari dan jam kerja — "
            "pemakaian di luar jam kerja, pada hari libur, atau ke luar kota "
            "hanya dengan surat tugas/izin tertulis dan dilarang untuk "
            "keperluan pribadi; memastikan pengemudi memiliki Surat Izin "
            "Mengemudi yang sah, menanggung sendiri tilang dan kecelakaan pada "
            "pemakaian non-dinas, menyimpan kendaraan di pool di luar jam "
            "kerja kecuali diizinkan, menjaga STNK/pajak/servis tetap berlaku "
            "(BPKB disimpan satuan kerja), serta tidak mengubah identitas "
            "kendaraan"),
    "303": ("Alat Bengkel dan Alat Ukur",
            "menjaga ketelitian melalui kalibrasi berkala dan menerapkan "
            "prosedur keselamatan kerja saat penggunaan"),
    "305": ("Alat Kantor dan Rumah Tangga",
            "menempatkan barang sesuai Daftar Barang Ruangan dan melaporkan "
            "setiap pemindahan antar ruangan kepada penanggung jawab ruangan"),
    "306": ("Alat Studio, Komunikasi dan Pemancar",
            "menggunakan untuk peliputan/komunikasi kedinasan pada kanal yang "
            "sah, mengembalikan lengkap dengan aksesorinya, serta memperlakukan "
            "hasil dokumentasi sebagai milik instansi"),
    "307": ("Alat Kedokteran dan Kesehatan",
            "memastikan alat dioperasikan tenaga berwenang sesuai prosedur, "
            "menjaga kalibrasi berkala, menghentikan penggunaan alat yang "
            "tidak laik pakai, dan menangani limbah medis sesuai ketentuan"),
    "308": ("Alat Laboratorium",
            "memastikan alat dioperasikan personel terlatih ber-alat pelindung "
            "diri sesuai prosedur baku, menjaga kalibrasi berkala, serta "
            "menangani bahan berbahaya dan limbahnya sesuai ketentuan"),
    "309": ("Alat Persenjataan",
            "mematuhi ketentuan perizinan dan pengamanan khusus, menyimpan "
            "barang pada tempat yang ditetapkan, dan mengeluarkannya hanya "
            "atas perintah pejabat berwenang"),
    "310": ("Komputer dan Perangkat Kerja",
            "mengamankan perangkat yang boleh dibawa dan dipakai di luar "
            "kantor maupun di luar jam kerja untuk kedinasan — mengaktifkan "
            "kata sandi/PIN, tidak meminjamkannya kepada yang tidak berhak, "
            "tidak meninggalkannya tanpa pengawasan di tempat umum atau di "
            "dalam kendaraan — menjaga kerahasiaan data instansi termasuk data "
            "pribadi, tidak memasang perangkat lunak tanpa lisensi, serta "
            "menyerahkan data kedinasan dan menonaktifkan akun pribadi saat "
            "pengembalian"),
    "315": ("Alat Keselamatan Kerja",
            "memeriksa kesiapan alat secara berkala, mengusulkan penggantian "
            "sebelum masa berlakunya habis, dan tidak memindahkannya dari "
            "titik penempatan"),

    # Golongan 4 — Gedung dan Bangunan
    "4": ("Gedung dan Bangunan",
          "menjaga keamanan/kebersihan bangunan beserta instalasinya, "
          "memastikan penguncian dan pemadaman peralatan listrik saat tidak "
          "digunakan, tidak mengubah bentuk/peruntukan tanpa persetujuan "
          "berwenang, serta melaporkan gangguan atau kebakaran segera"),

    # Golongan 5 — Jalan, Irigasi, dan Jaringan
    "5": ("Jalan, Irigasi, dan Jaringan",
          "menjaga keutuhan jalur/jaringan beserta rambu dan pengamannya serta "
          "melaporkan gangguan segera mengingat layanannya berjalan "
          "terus-menerus"),

    # Golongan 6 — Aset Tetap Lainnya
    "6": ("Aset Tetap Lainnya",
          "menyimpan barang sesuai sifatnya dan tidak memindahkannya tanpa "
          "sepengetahuan PIHAK KESATU"),
    "601": ("Bahan Perpustakaan",
            "mencatat peminjaman, mengganti bahan yang rusak/hilang dengan "
            "judul dan edisi sama atau setara, serta tidak membawa keluar "
            "koleksi khusus tanpa izin tertulis"),
    "602": ("Barang Bercorak Kesenian/Kebudayaan",
            "menjaga kondisi penyimpanan (terlindung dari sinar matahari "
            "langsung, kelembapan, dan benturan) serta merawat tanpa merusak "
            "keaslian barang"),
    "603": ("Hewan",
            "memberi pakan, air, dan perawatan kesehatan SETIAP HARI termasuk "
            "hari libur dengan menyiapkan petugas pengganti bila berhalangan, "
            "serta melaporkan kesakitan, kelahiran, kematian, atau hilangnya "
            "hewan pada kesempatan pertama"),
    "604": ("Biota Perairan",
            "menjaga kualitas air, pakan, dan peralatan pendukung setiap hari "
            "termasuk hari libur serta menangani kegagalan sistem aerasi/"
            "sirkulasi segera"),
    "605": ("Tanaman",
            "melakukan penyiraman, pemupukan, dan pengendalian hama secara "
            "rutin termasuk hari libur serta melaporkan kematian/kerusakan "
            "tanaman"),

    # Golongan 8 — Aset Tak Berwujud
    "8": ("Aset Tak Berwujud",
          "mematuhi batas lisensi (jumlah pemasangan, jangka waktu, lingkup "
          "pemakaian), tidak menggandakan atau memberikan akses kepada pihak "
          "lain, serta mengembalikan/menonaktifkan kunci lisensi saat selesai"),
}


def _terpilih(kode_list):
    """{kunci: (nama, kalimat)} untuk bidang yang HADIR — prefix terpanjang
    menang; terurut menurut kode bidang (naskah deterministik)."""
    hasil = {}
    for kode in kode_list or []:
        bidang = bidang_kode(kode)
        if not bidang:
            continue
        for n in range(len(bidang), 0, -1):
            kunci = bidang[:n]
            if kunci in PASAL_BIDANG:
                hasil[kunci] = PASAL_BIDANG[kunci]
                break
    return dict(sorted(hasil.items()))


def butir_khusus_bidang(kode_list, maks: int = 4):
    """Butir kekhususan siap cetak: "Nama Bidang — PIHAK KEDUA wajib …".

    Satu butir per bidang yang hadir (dulu satu PASAL per bidang) supaya
    naskah tetap 2 halaman. `maks` membatasi jumlah butir; sisanya dilaporkan
    lewat `sisa_bidang` agar pemotongan TIDAK pernah senyap. MURNI."""
    urut = list(_terpilih(kode_list).values())[:maks]
    return [f"<b>{nama}</b> — PIHAK KEDUA wajib {kalimat}." for nama, kalimat
            in urut]


def sisa_bidang(kode_list, maks: int = 4):
    """(dipakai, nama_bidang_sisa) — bidang yang tak tercetak karena `maks`."""
    nama = [n for n, _ in _terpilih(kode_list).values()]
    dipakai = min(len(nama), max(0, maks))
    return dipakai, nama[dipakai:]


def nama_bidang_terpakai(kode_list):
    """Nama bidang (manusiawi) yang aturannya terpakai — terurut, unik."""
    return [nama for nama, _ in _terpilih(kode_list).values()]


# ── PENANGGUNG JAWAB TAMBAHAN (BAST Operasional Unit/Tempat/Tugas) ───────────
#
# Permintaan pemilik: *"ketika memiliki penanggung jawab tambahan per
# unit/tempat/tugas, tambahkan informasi aset yang terceklist di aset yang
# diserahterimakan dan juga informasi di output PDF-nya di Pasal 2… tambahkan
# informasi NIP/NIK penanggung jawabnya dan informasi barang apa saja yang
# melekat ke masing-masing penanggung jawabnya, buat dalam bentuk tabel agar
# lebih mudah dibaca dan dipahami."*
#
# Sebelumnya keduanya dirangkai menjadi SATU KALIMAT di dalam pasal:
#
#   "Penanggung jawab pada unit/tempat tugas: Budi (Lantai 3); Sari (Gudang)."
#
# Kalimat itu tak menyebut NIP/NIK sama sekali — jadi dokumen resmi menamai
# orang tanpa pengenal yang bisa diverifikasi — dan tak menyebut barang mana
# yang menjadi tanggung jawab siapa. Padahal justru itu yang dicari orang saat
# membuka BAST setahun kemudian: siapa memegang apa.
MAKS_PJ_TAMBAHAN = 30


def label_bmn(a) -> str:
    """`kode·NUP — nama` untuk kolom BMN pada tabel penanggung jawab.

    Kode dan NUP dirapatkan dengan '·' (bukan spasi) supaya satu identitas
    barang tak pernah patah menjadi dua baris di kolom sempit — BAST dibatasi
    dua halaman, dan tiap baris yang patah memakan jatah baris berikutnya.
    """
    a = a or {}
    kode = str(a.get("asset_code") or "").strip()
    nup = str(a.get("NUP") or "").strip()
    nama = str(a.get("asset_name") or "").strip()
    kiri = "·".join(x for x in (kode, nup) if x)
    return " — ".join(x for x in (kiri, nama) if x) or "-"


def _peta_aset(aset) -> dict:
    return {str((a or {}).get("id") or ""): (a or {})
            for a in (aset or []) if str((a or {}).get("id") or "")}


def baris_pj_tambahan(pj_list, aset) -> list:
    """Baris tabel penanggung jawab tambahan beserta BMN yang melekat padanya.

    → [{no, nama, nip, unit, aset: [id, …]}]

    Baris tanpa nama DIBUANG dan penomorannya rapat — formulir menyisakan
    baris kosong setiap kali operator menekan "tambah" lalu berpindah pikiran,
    dan baris kosong yang ikut tercetak membuat dokumen resmi tampak salah
    isi. MURNI.
    """
    peta = _peta_aset(aset)
    keluar = []
    for p in (pj_list or []):
        p = p or {}
        nama = str(p.get("nama") or "").strip()
        if not nama:
            continue
        keluar.append({
            "no": len(keluar) + 1,
            "nama": nama,
            "nip": str(p.get("nip") or "").strip() or "-",
            "unit": str(p.get("unit_tempat_tugas") or "").strip() or "-",
            "aset": [str(x) for x in (p.get("asset_ids") or [])
                     if str(x or "") in peta],
        })
    return keluar


def rujukan_pasal1(ids, urutan) -> str:
    """Rujukan BMN sebagai NOMOR URUT pada tabel Pasal 1 — "1, 4, 7".

    Mengulang `kode·NUP — nama` di kolom ini akan membuat satu penanggung
    jawab bermuatan lima barang memakan lima baris, dan naskah yang dibatasi
    dua halaman kehabisan ruang pada penanggung jawab kedua. Nomor urutnya
    sudah tercetak di halaman yang sama, jadi rujukan sependek ini tak
    kehilangan satu pun informasi.

    `urutan`: peta {id aset → nomor urut SEBAGAIMANA TERCETAK}. Sengaja
    diterima dari pemanggil, bukan dihitung ulang di sini: tabel Pasal 1
    menomori barang menurut pengelompokan bidang, dan menghitung ulang
    urutannya di tempat kedua adalah cara paling pasti melahirkan rujukan
    yang menunjuk barang yang salah tanpa satu pun galat.
    """
    nomor = sorted({urutan[str(x)] for x in (ids or []) if str(x) in (urutan or {})})
    return ", ".join(str(n) for n in nomor)


def bmn_tanpa_pj(pj_list, aset) -> list:
    """BMN yang tak melekat pada penanggung jawab tambahan mana pun.

    Dinyatakan terus terang di bawah tabel, bukan didiamkan: pembaca yang
    melihat tabel berisi 3 dari 10 barang berhak tahu ke mana 7 sisanya —
    jawabannya PIHAK KEDUA selaku penanggung jawab unit.
    """
    diambil = set()
    for p in (pj_list or []):
        if not str((p or {}).get("nama") or "").strip():
            continue
        for x in ((p or {}).get("asset_ids") or []):
            diambil.add(str(x or ""))
    return [a for a in (aset or [])
            if str((a or {}).get("id") or "") not in diambil]


def validate_pj_tambahan(pj_list, asset_ids) -> list:
    """Daftar pesan kesalahan untuk penanggung jawab tambahan. MURNI.

    Tiga aturan, semuanya tentang dokumen yang akan dibaca orang lain:

    1. Baris yang MENGAKU berisi (NIP/unit/aset terisi) tapi tanpa nama akan
       hilang senyap dari cetakan — operator mengira sudah mencatatnya.
    2. BMN yang dilekatkan harus termasuk yang diserahterimakan. Melekatkan
       barang di luar daftar berarti BAST menyatakan tanggung jawab atas
       barang yang tak pernah diserahkan.
    3. Satu BMN hanya boleh melekat pada SATU penanggung jawab. Dua nama pada
       satu barang membuat pertanyaan "siapa yang memegang ini" — pertanyaan
       yang justru dijawab dokumen ini — kembali tak terjawab.
    """
    errors = []
    daftar = list(pj_list or [])
    if len(daftar) > MAKS_PJ_TAMBAHAN:
        errors.append(f"Penanggung jawab tambahan maksimal {MAKS_PJ_TAMBAHAN}; "
                      f"terkirim {len(daftar)}")
    sah = {str(x or "") for x in (asset_ids or [])}
    pemilik = {}
    for i, p in enumerate(daftar, 1):
        p = p or {}
        nama = str(p.get("nama") or "").strip()
        ids = [str(x or "") for x in (p.get("asset_ids") or [])]
        if not nama:
            if str(p.get("nip") or "").strip() or \
                    str(p.get("unit_tempat_tugas") or "").strip() or ids:
                errors.append(f"Penanggung jawab tambahan baris {i} belum "
                              "bernama — isi namanya atau hapus barisnya")
            continue
        for x in ids:
            if x not in sah:
                errors.append(f"BMN yang dilekatkan pada {nama} tidak termasuk "
                              "aset yang diserahterimakan")
                break
        for x in ids:
            if x in pemilik and pemilik[x] != nama:
                errors.append(f"Satu BMN dilekatkan pada dua penanggung jawab "
                              f"({pemilik[x]} dan {nama})")
                break
        for x in ids:
            pemilik.setdefault(x, nama)
    return errors
