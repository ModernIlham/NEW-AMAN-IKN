"""Pustaka PASAL Berita Acara Serah Terima (BAST) — logika murni.

Dua lapis yang disusun di sini:

1. **Pasal konteks waktu & risiko** — berlaku pada semua BAST yang
   MEMINDAHKAN penguasaan barang ke pemegang. Menjawab pertanyaan lapangan
   yang selama ini menggantung: bagaimana kedudukan BMN di luar jam kerja,
   pada hari libur, saat lembur/piket, saat kerja fleksibel di luar kantor,
   dan saat perjalanan dinas — serta apa yang harus dilakukan bila terjadi
   kehilangan/kerusakan pada waktu-waktu itu.

2. **Pasal khusus per BIDANG kode barang** — kendaraan tidak dapat diikat
   dengan klausul yang sama dengan buku perpustakaan; komputer membawa
   risiko data, laboratorium membawa risiko B3, hewan dan tanaman justru
   menuntut perawatan pada hari libur. Pasal khusus HANYA muncul untuk
   bidang yang benar-benar ada pada BAST bersangkutan.

── Kunci pencocokan ─────────────────────────────────────────────────────────
Kode barang BMN berlapis (lihat `kodefikasi_utils`): golongan 1 digit,
**bidang 3 digit**, kelompok 5, sub kelompok 7, sub-sub kelompok 10. Sesuai
permintaan pemilik, kebijakan pasal disusun **per BIDANG** — bukan per
kelompok — supaya jumlah aturan tetap terkelola. Pencocokan memakai prefix
TERPANJANG lebih dulu (bidang "302" mengalahkan golongan "3"), pola yang sama
dengan rekomendasi kelengkapan dokumen di `frontend/src/lib/kelengkapanBmn.js`
sehingga satu barang dibaca dengan cara yang sama di seluruh aplikasi.

── Dasar penyusunan (riset Agustus 2026; rinci di
   docs/PUSTAKA-REGULASI-BMN.md §11C) ──────────────────────────────────────
- **PP 27/2014 jo. PP 28/2020**: BMN digunakan untuk penyelenggaraan tugas
  dan fungsi; Ps. 42 kewajiban mengamankan (administrasi, fisik, hukum);
  Ps. 43 penyimpanan bukti kepemilikan.
- **PMK 40/2024** (menggantikan PMK 246/2014): tata cara pelaksanaan
  penggunaan BMN — penggunaan di luar penyelenggaraan pemerintahan dilarang.
- **UU 1/2004 Ps. 59-64 jo. PP 38/2016**: tuntutan ganti kerugian negara
  terhadap pegawai negeri bukan bendahara, termasuk beban ahli waris.
- **PP 94/2021**: disiplin PNS — penyalahgunaan BMN berkonsekuensi hukuman
  disiplin.
- **PMK 97/PMK.06/2019 jo. PMK 43 Tahun 2025**: pengasuransian BMN (sifat
  "dapat"/selektif — karenanya klausul asuransi ditulis bersyarat).
- **UU 27/2022 (PDP)** untuk data pada perangkat komputer/komunikasi.

Norma "hanya hari dan jam kerja" untuk kendaraan dinas TIDAK berasal dari
satu PMK nasional, melainkan aturan internal instansi + prinsip PP 27/2014.
Karena itu klausulnya ditulis sebagai KAIDAH INTERNAL satker yang
dioperasionalkan lewat surat tugas/izin tertulis — bukan kutipan pasal.

MURNI: tanpa Mongo/IO, seluruhnya teruji unit.
"""

# Panjang prefix bidang (selaras kodefikasi_utils.LEVEL_LENGTHS[2]).
PANJANG_BIDANG = 3

# Jenis BAST yang MEMINDAHKAN penguasaan ke pemegang — pasal konteks waktu &
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

    Kode pendek (hanya golongan) dikembalikan apa adanya supaya tetap bisa
    dicocokkan ke aturan tingkat golongan. MURNI."""
    s = "".join(ch for ch in str(kode or "") if ch.isdigit())
    if not s:
        return ""
    return s[:PANJANG_BIDANG]


# ── Pasal konteks waktu & risiko (semua BAST penguasaan) ────────────────────

def pasal_waktu_penggunaan(jenis: str):
    """(judul, butir) — kedudukan BMN pada jam kerja, di luar jam kerja, hari
    libur, kerja di luar kantor, dan perjalanan dinas. None bila jenis BAST
    tidak memindahkan penguasaan."""
    if jenis not in JENIS_PENGUASAAN:
        return None
    return ("WAKTU, TEMPAT, DAN KEADAAN PENGGUNAAN", [
        "BMN digunakan SEMATA-MATA untuk penyelenggaraan tugas dan fungsi "
        "satuan kerja, baik pada hari dan jam kerja maupun di luar jam kerja "
        "sepanjang untuk kepentingan kedinasan.",
        "Penggunaan di luar jam kerja, pada hari libur/cuti bersama, atau di "
        "luar lingkungan kantor — termasuk lembur, piket, penugasan "
        "insidentil, kerja fleksibel, dan perjalanan dinas — tetap menjadi "
        "tanggung jawab PIHAK KEDUA dan dilaksanakan berdasarkan surat "
        "tugas/surat perintah/izin tertulis atasan langsung.",
        "Membawa BMN keluar lingkungan kantor untuk keperluan kedinasan "
        "dicatat pada buku keluar-masuk barang dan BMN dikembalikan ke tempat "
        "penyimpanan setelah keperluan selesai, kecuali BMN yang menurut "
        "sifatnya melekat pada pemegang untuk menunjang tugas sehari-hari.",
        "Penggunaan BMN untuk kepentingan pribadi, usaha, politik praktis, "
        "atau kepentingan pihak lain di luar kedinasan DILARANG — pada jam "
        "kerja maupun di luar jam kerja — dan dapat dikenai hukuman disiplin "
        "sesuai ketentuan peraturan perundang-undangan.",
        "Selama perjalanan dinas, PIHAK KEDUA wajib menjaga BMN yang dibawa, "
        "termasuk pengamanannya di kendaraan, penginapan, dan tempat tujuan, "
        "serta segera melaporkan bila terjadi kehilangan atau kerusakan di "
        "perjalanan.",
    ])


def pasal_risiko(jenis: str):
    """(judul, butir) — pelaporan kehilangan/kerusakan (termasuk yang terjadi
    di luar jam kerja), ganti rugi, keadaan kahar, dan asuransi."""
    if jenis not in JENIS_PENGUASAAN:
        return None
    return ("KEHILANGAN, KERUSAKAN, DAN KEADAAN KAHAR", [
        "Kehilangan atau kerusakan BMN wajib dilaporkan secara tertulis "
        "kepada PIHAK KESATU paling lambat 1x24 jam sejak diketahui. Apabila "
        "kejadian berlangsung di luar jam kerja atau pada hari libur, "
        "pelaporan pertama dapat disampaikan secara lisan/elektronik dan "
        "dituangkan tertulis pada hari kerja berikutnya.",
        "Laporan kehilangan dilengkapi kronologi dan Surat Keterangan "
        "Kehilangan dari kepolisian sebagai dasar penelusuran dan proses "
        "lebih lanjut.",
        "Kerugian negara yang timbul karena kelalaian PIHAK KEDUA "
        "diselesaikan melalui tuntutan ganti kerugian sesuai Undang-Undang "
        "Nomor 1 Tahun 2004 dan Peraturan Pemerintah Nomor 38 Tahun 2016; "
        "kewajiban tersebut dapat beralih kepada ahli waris sesuai ketentuan.",
        "Kerusakan atau kehilangan akibat KEADAAN KAHAR (bencana alam, "
        "kebakaran, kerusuhan, atau sebab lain di luar kemampuan manusia) "
        "yang dibuktikan dengan surat keterangan instansi berwenang dan "
        "bukan karena kelalaian, diproses sesuai ketentuan pengelolaan BMN "
        "dan tidak dibebankan sebagai kelalaian PIHAK KEDUA.",
        "Terhadap BMN yang diasuransikan, PIHAK KEDUA wajib membantu "
        "kelengkapan proses klaim; keikutsertaan asuransi tidak menghapus "
        "kewajiban pengamanan dan pelaporan pada butir-butir di atas.",
        "Penyusutan nilai dan keausan akibat pemakaian wajar dalam rangka "
        "kedinasan bukan merupakan kelalaian PIHAK KEDUA.",
    ])


# ── Pasal KHUSUS per bidang ────────────────────────────────────────────────
# Kunci = prefix kode barang (bidang 3 digit; golongan 1 digit sebagai jaring
# terakhir). Nilai = (nama bidang, judul pasal, butir-butir).

PASAL_BIDANG = {
    # ── Golongan 2 — Tanah ─────────────────────────────────────────────────
    "2": ("Tanah", "KETENTUAN KHUSUS TANAH", [
        "PIHAK KEDUA menjaga batas bidang tanah (patok/pagar/plang nama), "
        "melarang penguasaan pihak lain tanpa alas hak, dan segera melaporkan "
        "indikasi penyerobotan atau sengketa kepada PIHAK KESATU.",
        "Tanah dilarang dimanfaatkan pihak lain (sewa, pinjam pakai, kerja "
        "sama) tanpa persetujuan pejabat berwenang sesuai ketentuan "
        "pemanfaatan BMN.",
        "Sertipikat dan dokumen kepemilikan tetap disimpan pemegang dokumen "
        "yang berwenang; PIHAK KEDUA hanya menerima salinan untuk keperluan "
        "pengelolaan lapangan.",
    ]),

    # ── Golongan 3 — Peralatan dan Mesin ───────────────────────────────────
    "3": ("Peralatan dan Mesin", "KETENTUAN KHUSUS PERALATAN DAN MESIN", [
        "Peralatan dioperasikan sesuai buku manual/petunjuk pabrikan oleh "
        "personel yang memahami pengoperasiannya.",
        "Perbaikan, penggantian suku cadang, dan pemeliharaan berkala "
        "dikoordinasikan dengan PIHAK KESATU; PIHAK KEDUA dilarang membongkar "
        "atau memodifikasi peralatan tanpa persetujuan tertulis.",
    ]),
    "301": ("Alat Besar", "KETENTUAN KHUSUS ALAT BESAR", [
        "Alat besar hanya dioperasikan oleh operator yang ditunjuk dan "
        "memiliki kompetensi/lisensi operator yang masih berlaku, dengan "
        "menerapkan ketentuan keselamatan dan kesehatan kerja.",
        "Pengoperasian di luar jam kerja atau di luar lokasi kerja yang "
        "ditetapkan hanya dilakukan atas surat perintah tertulis, disertai "
        "pencatatan jam operasi (log book) dan pemeriksaan sebelum-sesudah "
        "pengoperasian.",
        "Pemindahan alat antar lokasi memperhatikan ketentuan pengangkutan "
        "dan perizinan yang berlaku, serta dilaporkan kepada PIHAK KESATU.",
    ]),
    "302": ("Alat Angkutan", "KETENTUAN KHUSUS KENDARAAN DINAS", [
        "Kendaraan dinas digunakan untuk kepentingan kedinasan pada hari dan "
        "jam kerja. Penggunaan di luar jam kerja, pada hari libur, atau ke "
        "luar kota HANYA dapat dilakukan berdasarkan surat tugas/izin "
        "tertulis pejabat yang berwenang, dan dilarang untuk kepentingan "
        "pribadi termasuk mudik, rekreasi, atau kegiatan keluarga.",
        "Pengemudi wajib memiliki Surat Izin Mengemudi yang sesuai dan masih "
        "berlaku serta menaati peraturan lalu lintas. Pelanggaran lalu lintas, "
        "denda/tilang, dan kecelakaan yang terjadi pada penggunaan di luar "
        "kepentingan kedinasan menjadi tanggung jawab pribadi PIHAK KEDUA.",
        "Di luar jam kerja kendaraan disimpan di tempat penyimpanan/pool yang "
        "ditetapkan satuan kerja, kecuali diizinkan tertulis untuk disimpan "
        "di tempat lain karena kebutuhan tugas.",
        "PIHAK KEDUA memastikan STNK berlaku, pajak kendaraan dibayar tepat "
        "waktu, dan pemeliharaan berkala (servis, ban, rem) dilaksanakan; "
        "BPKB tetap disimpan satuan kerja sesuai ketentuan penyimpanan "
        "dokumen kepemilikan BMN.",
        "Dilarang mengubah bentuk, warna, identitas kendaraan, atau memasang "
        "atribut non-kedinasan; pemakaian bahan bakar dan biaya operasional "
        "mengikuti ketentuan yang berlaku pada satuan kerja.",
        "Kecelakaan wajib dilaporkan segera beserta laporan kepolisian; "
        "apabila kendaraan diasuransikan, proses klaim dikoordinasikan dengan "
        "PIHAK KESATU.",
    ]),
    "303": ("Alat Bengkel dan Alat Ukur",
            "KETENTUAN KHUSUS ALAT BENGKEL DAN ALAT UKUR", [
        "Alat ukur dipelihara ketelitiannya melalui kalibrasi berkala; hasil "
        "kalibrasi terakhir menjadi bagian kelengkapan barang saat "
        "dikembalikan.",
        "Penggunaan alat bengkel menerapkan ketentuan keselamatan kerja "
        "(alat pelindung diri, prosedur pengoperasian) dan alat disimpan "
        "kembali di tempatnya setelah selesai digunakan.",
    ]),
    "305": ("Alat Kantor dan Rumah Tangga",
            "KETENTUAN KHUSUS ALAT KANTOR DAN RUMAH TANGGA", [
        "Barang ditempatkan pada ruangan sebagaimana tercatat dalam Daftar "
        "Barang Ruangan; pemindahan antar ruangan dilaporkan kepada penanggung "
        "jawab ruangan dan PIHAK KESATU agar pencatatan tetap mutakhir.",
        "Barang tidak dibawa keluar lingkungan kantor kecuali untuk keperluan "
        "kedinasan dengan izin tertulis dan pencatatan keluar-masuk barang.",
        "Pemakaian di luar jam kerja untuk kegiatan kantor (rapat, lembur, "
        "kegiatan hari libur) tetap dalam pengawasan penanggung jawab ruangan.",
    ]),
    "306": ("Alat Studio, Komunikasi dan Pemancar",
            "KETENTUAN KHUSUS ALAT STUDIO, KOMUNIKASI DAN PEMANCAR", [
        "Peralatan digunakan untuk peliputan/komunikasi kedinasan; peminjaman "
        "untuk kegiatan di luar jam kerja atau di luar kantor dijadwalkan dan "
        "dicatat, serta dikembalikan lengkap dengan aksesorinya (lensa, "
        "baterai, kartu memori, mikrofon).",
        "Perangkat komunikasi radio dioperasikan pada kanal/frekuensi yang "
        "sah sesuai izin yang dimiliki instansi dan tidak digunakan untuk "
        "keperluan di luar kedinasan.",
        "Berkas foto/video hasil kegiatan kedinasan merupakan dokumentasi "
        "instansi; PIHAK KEDUA menyerahkan salinannya dan tidak "
        "menyebarluaskannya tanpa izin.",
    ]),
    "307": ("Alat Kedokteran dan Kesehatan",
            "KETENTUAN KHUSUS ALAT KEDOKTERAN DAN KESEHATAN", [
        "Alat dioperasikan oleh tenaga kesehatan/teknisi yang berwenang "
        "sesuai kompetensinya, dengan memperhatikan sterilitas dan prosedur "
        "penggunaan.",
        "Kalibrasi/pengujian berkala dan pemeliharaan preventif dilaksanakan "
        "sesuai jadwal; alat yang tidak laik pakai dihentikan penggunaannya "
        "dan segera dilaporkan.",
        "Penanganan limbah dan bahan habis pakai mengikuti ketentuan "
        "pengelolaan limbah medis yang berlaku.",
    ]),
    "308": ("Alat Laboratorium", "KETENTUAN KHUSUS ALAT LABORATORIUM", [
        "Alat dioperasikan personel terlatih sesuai prosedur operasional "
        "baku laboratorium, termasuk penggunaan alat pelindung diri.",
        "Kalibrasi berkala dilaksanakan dan sertifikatnya disimpan sebagai "
        "kelengkapan barang.",
        "Penyimpanan dan penanganan bahan berbahaya dan beracun (B3) serta "
        "limbahnya mengikuti ketentuan yang berlaku; kejadian tumpahan atau "
        "kecelakaan kerja dilaporkan segera termasuk bila terjadi di luar "
        "jam kerja.",
    ]),
    "309": ("Alat Persenjataan", "KETENTUAN KHUSUS ALAT PERSENJATAAN", [
        "Penguasaan, penyimpanan, dan penggunaan tunduk pada ketentuan "
        "perizinan dan pengamanan khusus yang berlaku; di luar jam tugas "
        "barang disimpan pada tempat penyimpanan yang ditetapkan.",
        "Pemindahan dan pengeluaran barang dari tempat penyimpanan dicatat "
        "dan hanya atas perintah pejabat berwenang.",
    ]),
    "310": ("Komputer", "KETENTUAN KHUSUS KOMPUTER DAN PERANGKAT KERJA", [
        "Perangkat dapat dibawa dan digunakan di luar kantor maupun di luar "
        "jam kerja untuk menunjang tugas kedinasan (lembur, piket, kerja "
        "fleksibel, perjalanan dinas) sepanjang sesuai penugasan; "
        "pengamanannya sepenuhnya menjadi tanggung jawab PIHAK KEDUA.",
        "PIHAK KEDUA mengaktifkan pengamanan akses (kata sandi/PIN), tidak "
        "meminjamkan perangkat kepada pihak yang tidak berhak, dan tidak "
        "meninggalkan perangkat tanpa pengawasan di tempat umum atau di dalam "
        "kendaraan.",
        "Data dan informasi instansi yang tersimpan pada perangkat merupakan "
        "milik instansi dan wajib dijaga kerahasiaannya, termasuk data pribadi "
        "sesuai ketentuan pelindungan data pribadi.",
        "Dilarang memasang perangkat lunak tanpa lisensi yang sah atau "
        "mengubah konfigurasi keamanan perangkat.",
        "Pada saat pengembalian, PIHAK KEDUA menyerahkan data kedinasan, "
        "menonaktifkan akun pribadi, dan memastikan perangkat bersih dari "
        "data pribadi.",
    ]),
    "315": ("Alat Keselamatan Kerja",
            "KETENTUAN KHUSUS ALAT KESELAMATAN KERJA", [
        "Alat diperiksa kesiapannya secara berkala dan diganti sebelum masa "
        "berlaku/kedaluwarsanya habis; alat yang telah terpakai atau "
        "kedaluwarsa segera dilaporkan untuk penggantian.",
        "Alat ditempatkan pada titik yang mudah dijangkau dan tidak "
        "dipindahkan tanpa sepengetahuan penanggung jawab ruangan.",
    ]),

    # ── Golongan 4 — Gedung dan Bangunan ───────────────────────────────────
    "4": ("Gedung dan Bangunan", "KETENTUAN KHUSUS GEDUNG DAN BANGUNAN", [
        "PIHAK KEDUA menjaga keamanan dan kebersihan bangunan beserta "
        "instalasi yang melekat, serta memastikan penguncian dan pemadaman "
        "peralatan listrik pada saat bangunan tidak digunakan (di luar jam "
        "kerja dan hari libur).",
        "Perubahan bentuk, penambahan/pengurangan bangunan, atau perubahan "
        "peruntukan ruangan hanya dilakukan atas persetujuan pejabat "
        "berwenang dan dicatat sebagai perubahan data BMN.",
        "Pemakaian ruang/bangunan oleh pihak lain (kegiatan non-kedinasan) "
        "hanya dapat dilakukan melalui mekanisme pemanfaatan BMN sesuai "
        "ketentuan, bukan izin lisan.",
        "Gangguan keamanan, kebocoran, korsleting, atau kebakaran dilaporkan "
        "segera kepada PIHAK KESATU dan petugas berwenang, termasuk bila "
        "terjadi di luar jam kerja.",
    ]),

    # ── Golongan 5 — Jalan, Irigasi, dan Jaringan ──────────────────────────
    "5": ("Jalan, Irigasi, dan Jaringan",
          "KETENTUAN KHUSUS JALAN, IRIGASI, DAN JARINGAN", [
        "Serah terima bersifat penguasaan pengelolaan; PIHAK KEDUA menjaga "
        "keutuhan jalur/jaringan, kelengkapan rambu dan pengaman, serta "
        "melarang pemanfaatan pihak lain tanpa izin.",
        "Gangguan, kerusakan, atau pemutusan jaringan dilaporkan segera — "
        "termasuk di luar jam kerja — mengingat sifat layanannya berjalan "
        "terus-menerus.",
    ]),

    # ── Golongan 6 — Aset Tetap Lainnya ────────────────────────────────────
    "6": ("Aset Tetap Lainnya", "KETENTUAN KHUSUS ASET TETAP LAINNYA", [
        "Barang disimpan pada tempat yang sesuai sifatnya dan tidak "
        "dipindahkan tanpa sepengetahuan PIHAK KESATU.",
    ]),
    "601": ("Bahan Perpustakaan", "KETENTUAN KHUSUS BAHAN PERPUSTAKAAN", [
        "Bahan perpustakaan digunakan untuk menunjang tugas kedinasan dan "
        "dicatat pada kartu/berkas peminjaman; kerusakan atau kehilangan "
        "diganti dengan judul dan edisi yang sama atau setara.",
        "Bahan pustaka langka/koleksi khusus tidak dibawa keluar lingkungan "
        "kantor tanpa izin tertulis.",
    ]),
    "602": ("Barang Bercorak Kesenian/Kebudayaan",
            "KETENTUAN KHUSUS BARANG BERCORAK KESENIAN/KEBUDAYAAN", [
        "Barang ditempatkan pada kondisi penyimpanan yang menjaga "
        "keawetannya (terlindung dari sinar matahari langsung, kelembapan, "
        "dan benturan) dan tidak dipindahkan tanpa izin tertulis.",
        "Pembersihan/perawatan dilakukan dengan cara yang tidak merusak "
        "keaslian barang; kerusakan sekecil apa pun segera dilaporkan.",
    ]),
    "603": ("Hewan", "KETENTUAN KHUSUS HEWAN", [
        "Pemberian pakan, air, dan perawatan kesehatan dilakukan SETIAP HARI "
        "termasuk pada hari libur dan di luar jam kerja; PIHAK KEDUA "
        "mengatur petugas pengganti bila berhalangan.",
        "Kesakitan, kelahiran, kematian, atau hilangnya hewan dilaporkan "
        "kepada PIHAK KESATU pada kesempatan pertama disertai keterangan "
        "petugas/dokter hewan yang berwenang sebagai dasar pencatatan.",
    ]),
    "604": ("Biota Perairan", "KETENTUAN KHUSUS BIOTA PERAIRAN", [
        "Pemeliharaan kualitas air, pakan, dan peralatan pendukung "
        "dilaksanakan setiap hari termasuk hari libur; kegagalan sistem "
        "(aerasi/sirkulasi) ditangani segera dan dilaporkan.",
    ]),
    "605": ("Tanaman", "KETENTUAN KHUSUS TANAMAN", [
        "Penyiraman, pemupukan, dan pengendalian hama dilakukan secara rutin "
        "termasuk pada hari libur; kematian atau kerusakan tanaman dilaporkan "
        "sebagai dasar pencatatan.",
    ]),

    # ── Golongan 8 — Aset Tak Berwujud ─────────────────────────────────────
    "8": ("Aset Tak Berwujud", "KETENTUAN KHUSUS ASET TAK BERWUJUD", [
        "Penggunaan tunduk pada ketentuan lisensi: jumlah pemasangan, "
        "jangka waktu, dan lingkup pemakaian tidak boleh dilampaui.",
        "Dilarang menggandakan, mengalihkan, atau memberikan akses kepada "
        "pihak lain tanpa izin; kunci lisensi/akun dikembalikan dan "
        "dinonaktifkan dari perangkat PIHAK KEDUA pada saat pengembalian.",
    ]),
}


def pasal_khusus_bidang(kode_list, maks: int = 5):
    """Daftar (judul, butir) pasal khusus untuk bidang yang HADIR pada BAST.

    - Pencocokan prefix TERPANJANG: bidang (3 digit) mengalahkan golongan
      (1 digit), sehingga kendaraan tidak jatuh ke klausul umum Peralatan
      dan Mesin.
    - Terurut menurut kode bidang → naskah dokumen deterministik (dua unduhan
      dokumen yang sama tak boleh berbeda urutan pasalnya).
    - `maks` membatasi jumlah blok agar BAST tetap ringkas; bila melebihi,
      pemanggil menerima informasinya lewat `pasal_khusus_ringkas` sehingga
      pemotongan TIDAK pernah senyap.

    MURNI (teruji unit)."""
    terpilih = {}
    for kode in kode_list or []:
        bidang = bidang_kode(kode)
        if not bidang:
            continue
        # prefix terpanjang lebih dulu: "302" → "30" → "3"
        for n in range(len(bidang), 0, -1):
            kunci = bidang[:n]
            if kunci in PASAL_BIDANG:
                terpilih[kunci] = PASAL_BIDANG[kunci]
                break
    urut = sorted(terpilih.items())
    return [(judul, butir) for _k, (_nama, judul, butir) in urut][:maks]


def pasal_khusus_ringkas(kode_list, maks: int = 5):
    """(dipakai, tersisa) — jumlah blok pasal khusus yang tercetak dan yang
    TIDAK tercetak karena batas `maks`. Dipakai pemanggil untuk menyatakan
    pemotongan secara terbuka pada dokumen. MURNI."""
    semua = pasal_khusus_bidang(kode_list, maks=10_000)
    dipakai = min(len(semua), max(0, maks))
    return dipakai, max(0, len(semua) - dipakai)


def nama_bidang_terpakai(kode_list):
    """Nama bidang (manusiawi) yang aturannya terpakai — untuk catatan kaki
    dokumen dan pesan UI. Terurut, tanpa duplikat. MURNI."""
    hasil, lihat = [], set()
    for kode in kode_list or []:
        bidang = bidang_kode(kode)
        for n in range(len(bidang), 0, -1):
            kunci = bidang[:n]
            if kunci in PASAL_BIDANG:
                if kunci not in lihat:
                    lihat.add(kunci)
                    hasil.append((kunci, PASAL_BIDANG[kunci][0]))
                break
    return [nama for _k, nama in sorted(hasil)]
