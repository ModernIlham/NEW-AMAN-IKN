"""Berapa tempat teken tambahan yang dibawa Surat Pernyataan Tanggung Jawab.

Permintaan pemilik: *"pada aset pemegang, apabila disertakan surat pernyataan
tanggung jawab maka otomatis menambah +1 tempat dalam meneken dokumen tersebut
sesuai nama penandatangan."*

BAST yang menyertakan SPTJ mencetak SATU LEMBAR TERSENDIRI untuk tiap penyata
— dan lembar itu menuntut tanda tangan orangnya sendiri. Selama ini
`jumlah_ttd` setiap penanda tangan selalu 1, sehingga lembar pernyataan terbit
KOSONG: dokumen resmi yang tampak lengkap padahal belum diteken. Persis
kelalaian yang gerbang kelengkapan (ttd_kelengkapan.py) dibuat untuk mencegah
— tetapi gerbang itu hanya menagih angka yang DIDEKLARASIKAN, dan tak ada yang
mendeklarasikannya.

SUMBERNYA SATU. Jumlahnya diturunkan dari `bast_pasal.daftar_penyata` — fungsi
yang SAMA yang dipakai `bast_pdf` untuk mencetak lembarnya. Menghitung sendiri
di sini akan melahirkan dua pendapat tentang "berapa lembar", dan yang satu
akan diam-diam berbeda dari yang tercetak.

MURNI: tanpa DB, tanpa I/O.
"""


def _nama_baku(nama) -> str:
    """Nama tanpa spasi ganda & tanpa beda kapital — untuk dibandingkan."""
    return " ".join(str(nama or "").split()).casefold()


def _sama_orang(a, b) -> bool:
    """Dua entri menunjuk orang yang sama?

    NIP menang BILA KEDUANYA punya. Kalau salah satu tak berNIP — dan itu
    lazim: daftar penyata mengambil identitas dari blok pihak yang kadang
    hanya berisi nama — perbandingan jatuh ke nama yang dinormalkan.

    Versi pertama modul ini memakai satu kunci tunggal ("nip bila ada, jika
    tidak nama") dan itu KELIRU: penanda tangan berNIP tak pernah cocok
    dengan lembar pernyataan yang hanya bernama, sehingga lembar orang itu
    tak pernah menambah tempat teken — persis kelalaian yang hendak dicegah.
    """
    nip_a = str((a or {}).get("nip") or "").strip()
    nip_b = str((b or {}).get("nip") or "").strip()
    if nip_a and nip_b:
        return nip_a == nip_b
    na, nb = _nama_baku((a or {}).get("nama")), _nama_baku((b or {}).get("nama"))
    return bool(na) and na == nb


def lembar_untuk(signer, penyata) -> int:
    """Berapa lembar SPTJ yang menuntut tanda tangan orang ini.

    Satu orang bisa memegang LEBIH DARI SATU lembar (BAST operasional dengan
    penanggung jawab yang juga Pihak Kedua), jadi ini hitungan, bukan penanda
    ada/tidak. Lembar tanpa identitas apa pun dilewati — menebak pemiliknya
    akan menambah tempat teken pada orang yang salah.
    """
    n = 0
    for p in penyata or []:
        if not isinstance(p, dict):
            continue
        if not str(p.get("nama") or "").strip() and not str(p.get("nip") or "").strip():
            continue
        if _sama_orang(signer, p):
            n += 1
    return n


def jumlah_ttd_dengan_pernyataan(signer, penyata) -> int:
    """Berapa tempat yang harus diteken seorang penanda tangan.

    1 untuk blok tanda tangan dokumen utamanya, ditambah satu untuk TIAP
    lembar pernyataan atas namanya.
    """
    return 1 + lembar_untuk(signer, penyata)


def terapkan_lembar_pernyataan(signers, penyata) -> list:
    """Daftar penanda tangan dengan `jumlah_ttd` yang sudah memperhitungkan
    SPTJ. Daftar dikembalikan BARU — masukan tak disentuh.

    `penyata` kosong (BAST tanpa SPTJ) → setiap orang tetap 1, yaitu perilaku
    sebelum fitur ini ada.
    """
    return [{**s, "jumlah_ttd": jumlah_ttd_dengan_pernyataan(s, penyata)}
            for s in (signers or []) if isinstance(s, dict)]
