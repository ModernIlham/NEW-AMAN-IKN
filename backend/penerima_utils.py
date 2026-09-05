"""Validasi PENERIMA terhadap Master Pegawai — satu pintu untuk seluruh serah
terima.

Aturannya sudah ada dan sudah benar, tetapi hidup sebagai satu blok di dalam
badan `routes/bast.py`. Ketika serah terima barang persediaan membutuhkan
aturan yang SAMA PERSIS, menyalinnya berarti dua tempat yang harus sepakat
selamanya — dan yang paling mudah tercecer justru cabang penolakannya, yang
jarang dijalankan dan karena itu jarang diperiksa orang.

Tiga tingkat perlakuan, sengaja tidak seragam:

* **NIP tak terdaftar → peringatan.** Master Pegawai bisa saja belum lengkap;
  memblokir transaksi karenanya menghukum pengurus barang atas pekerjaan
  bagian kepegawaian.
* **Berstatus meninggal dunia → DITOLAK.** Secara hukum mustahil almarhum
  menerima serah terima. Ini satu-satunya cabang yang memblokir.
* **Pensiun/mutasi/nonaktif → peringatan.** Bisa jadi memang tepat (serah
  terima justru dilakukan karena yang bersangkutan pindah), jadi keputusannya
  diserahkan kepada operator — tetapi ia harus tahu.

Menerima `db` sebagai argumen agar dapat diuji tanpa server.
"""


class PenerimaMeninggal(Exception):
    """Penerima berstatus meninggal dunia — transaksi harus ditolak.

    Exception, bukan nilai kembalian, supaya cabang ini MUSTAHIL terlewat:
    pemanggil yang lupa memeriksa flag akan tetap gagal, bukan diam-diam
    mencatat serah terima kepada almarhum.
    """

    def __init__(self, pesan):
        super().__init__(pesan)
        self.pesan = pesan


def pesan_almarhum(nama, konteks="serah terima") -> str:
    return (f"{nama} berstatus Meninggal Dunia di Master Pegawai — tidak "
            f"dapat dijadikan penerima {konteks}. Gunakan alur pengembalian "
            f"BMN almarhum (penyerah: ahli waris/atasan) atau pilih penerima "
            f"lain.")


async def periksa_penerima(db, scope_query, nip, konteks="serah terima"):
    """→ `(pegawai_atau_None, peringatan)`; melempar `PenerimaMeninggal`.

    `scope_query` adalah fungsi satu-argumen yang membungkus filter dengan
    isolasi satker (biasanya `partial(scope_query_field_satker, user)`).
    Diserahkan pemanggil, BUKAN disimpulkan di sini: flag "terdaftar" dan nama
    penerima harus berasal dari Master Pegawai SATKER INI, bukan seluruh
    instansi, dan modul ini tak boleh menebak siapa penggunanya.

    NIP kosong → `(None, "")`. Bukan galat: penerima berupa unit kerja atau
    pihak luar memang tak punya NIP, dan memaksakannya akan menutup jalur yang
    sah.
    """
    from pegawai_utils import is_aktif, is_meninggal

    n = str(nip or "").strip()
    if not n:
        return None, ""
    peg = await db.pegawai.find_one(
        scope_query({"nip": n}),
        {"_id": 0, "nama": 1, "nip": 1, "status": 1, "jabatan": 1,
         "unit_kerja": 1, "status_kepegawaian": 1,
         "eselon1": 1, "eselon2": 1, "eselon3": 1, "eselon4": 1, "eselon5": 1})
    if not peg:
        return None, (f"NIP {n} belum terdaftar di Master Pegawai — periksa "
                      f"ejaan atau daftarkan dulu")
    if is_meninggal(peg):
        raise PenerimaMeninggal(
            pesan_almarhum(str(peg.get("nama") or n), konteks))
    if not is_aktif(peg):
        st = str(peg.get("status") or "").strip() or "nonaktif"
        return peg, (f"Penerima ({peg.get('nama') or n}) berstatus {st} di "
                     f"Master Pegawai — pastikan {konteks} ini memang tepat")
    return peg, ""


def snapshot_penerima(pegawai, unit_teks="") -> dict:
    """Identitas penerima yang DIBEKUKAN ke dalam jurnal/dokumen.

    Dibekukan, bukan di-join saat cetak: pegawai pindah unit dan berganti
    jabatan, sementara bukti pengeluaran barang harus tetap menyebut keadaan
    saat barang itu benar-benar diserahkan.

    `unit_teks` (isian bebas operator) dipakai HANYA bila pegawainya tak punya
    unit tercatat. Mendahulukan isian bebas akan membuat dokumen menyebut unit
    yang diketik seseorang alih-alih unit yang sesungguhnya di master.
    """
    p = pegawai or {}
    unit = str(p.get("unit_kerja") or "").strip()
    if not unit:
        from pegawai_utils import unit_kerja_terdalam
        unit = str(unit_kerja_terdalam(p) or "").strip()
    return {
        "penerima_nama": str(p.get("nama") or "").strip(),
        "penerima_nip": str(p.get("nip") or "").strip(),
        "penerima_jabatan": str(p.get("jabatan") or "").strip(),
        "penerima_unit": unit or str(unit_teks or "").strip(),
        "penerima_status_kepegawaian": str(
            p.get("status_kepegawaian") or "").strip(),
        "penerima_terdaftar": bool(p),
    }
