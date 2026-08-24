"""Gerbang "dokumen ber-register WAJIB bersatker" — helper MURNI.

MASALAH YANG DIPECAHKAN
=======================

Laporan pemilik: *"pada saat mengganti role masih ada kebocoran data di
registrasi persuratan saat pembuatan LPB."*

`scope_query_field_satker` SENGAJA meloloskan dokumen berstempel `""` — itu
konvensi kompatibilitas untuk data era lama, sebelum stempel satker ada. Yang
benar untuk data lama menjadi lubang untuk data BARU: dokumen yang hari ini
ditulis dengan kode kosong akan tampil di register SETIAP satker.

Jalannya begini. Super-admin PUSAT tidak terikat satker mana pun
(`kode_satker` = ""); selama ia belum memilih "Satker Aktif",
`kode_satker_user(user)` mengembalikan "". Seluruh penerbitan otomatis —
nomor LPB, nota dinas, surat persetujuan — memakai pola:

    kode = str(kode_dokumen or "").strip() or kode_satker_user(user)

sehingga hasilnya "" begitu dokumen sumbernya pun belum berkode.

DAN KERUSAKANNYA BUKAN SEKADAR TAMPILAN. `_seed_agenda` di persuratan
memperlakukan surat tanpa stempel sebagai milik satker yang membacanya
("konvensi lama menganggapnya miliknya"). Satu surat pusat berstempel ""
karena itu MENGHABISKAN satu nomor agenda di buku SETIAP satker — diukur
langsung: satker yang baru menerbitkan surat pertamanya mendapat nomor 002,
karena 001 sudah ditempati surat yang bukan miliknya.

KEPUTUSAN
=========

Dokumen yang mendarat di register ber-scope satker WAJIB membawa satker yang
sungguhan. Bila tak dapat ditentukan, penerbitannya DITOLAK dengan petunjuk —
bukan distempel "" diam-diam.

Menolak, bukan menebak: nomor surat resmi adalah posisi dalam buku agenda
SEBUAH satker. Nomor tanpa satker bukan nomor yang kurang lengkap, melainkan
nomor yang tak punya arti — dan menebak satkernya akan menaruh surat resmi di
buku yang salah, kesalahan yang jauh lebih sulit diperbaiki daripada satu
penolakan yang bisa langsung ditindaklanjuti.

Data LAMA tak tersentuh: modul ini hanya dipanggil pada jalur PENERBITAN.
"""

# Ditulis sekali di sini supaya seluruh jalur penerbitan menolak dengan
# kalimat yang sama — penolakan yang berbeda-beda di tiap modul membuat
# operator mengira ia menghadapi masalah yang berbeda-beda pula.
PETUNJUK_SATKER = (
    "Pilih \"Satker Aktif\" lebih dulu (menu satker di kanan atas), lalu "
    "ulangi. Akun pusat tidak terikat satker mana pun, sehingga sistem tak "
    "tahu di buku agenda satker mana dokumen ini harus terbit.")


def satker_pertama_terisi(*kandidat) -> str:
    """Kode satker pertama yang benar-benar terisi dari deret kandidat.

    Urutan kandidat adalah urutan KEWENANGAN, dan pemanggil yang menentukan:
    satker DOKUMEN SUMBER lebih dipercaya daripada satker pemanggil, karena
    super-admin boleh mengerjakan dokumen satker lain dan dokumen itu harus
    tetap terbit di buku agenda pemiliknya.
    """
    for k in kandidat:
        s = str(k or "").strip()
        if s:
            return s
    return ""


def pesan_satker_wajib(kode, dokumen: str = "dokumen") -> str:
    """"" bila `kode` sah; kalimat penolakan bila kosong.

    Mengembalikan PESAN, bukan melempar: modul ini murni, dan pemanggil di
    lapisan HTTP-lah yang tahu status apa yang pantas (400 untuk permintaan
    langsung; ditelan diam-diam pada jalur yang memang menoleransi gagal
    booking).
    """
    if str(kode or "").strip():
        return ""
    return (f"Penerbitan {dokumen} membutuhkan satker. {PETUNJUK_SATKER}")
