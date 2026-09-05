"""Linimasa bulanan "Progres Inventarisasi" — helper MURNI, tanpa I/O dan DB.

Permintaan pemilik: *"pada laporan eksekutif aset berikan linimasa seperti di
laporan gabungan, persis seperti tampilan Progres Inventarisasi-nya."*

Grafiknya sudah ada, tetapi hidup sebagai dua ratus baris di dalam
`_build_satker_report_v2` — tak dapat dipakai laporan lain tanpa menyalinnya.
Menyalinnya berarti dua perhitungan yang harus sama selamanya, dan yang kedua
tak pernah ikut diperbaiki: persis cacat yang sudah dibayar `eselon1` (empat
salinan cabang bentuk) dan aturan eselon (dua salinan yang berbeda isi).

Modul ini memindahkannya ke satu tempat. Bentuk keluarannya tak berubah sama
sekali — laporan gabungan memakai modul ini dan tetap menghasilkan angka yang
sama persis.

Lima keputusan yang membentuk grafik ini, seluruhnya dipertahankan:

1. **Rumahnya adalah BMN TERCATAT, isinya capaian pemeriksaan.** Versi paling
   awal menggambar PERISTIWA per bulan. Grafiknya memang fluktuatif, tetapi tak
   pernah menjawab pertanyaan yang paling sering diajukan atas laporan berjudul
   "Progres Inventarisasi": berapa yang harus diperiksa, dan berapa yang sudah.
   Jarak keduanya adalah tunggakannya, dan pada grafik peristiwa jarak itu tak
   punya bentuk sama sekali.

2. **Rongganya tak berwarna.** Yang belum diperiksa sengaja digambar sebagai
   ruang kosong di dalam rumah — itulah tunggakan yang harus terlihat.

3. **Stok awal ikut dihitung.** BMN perolehan tahun-tahun sebelumnya tetap
   tercatat pada Januari tahun ini. Rumah yang dimulai dari nol menggambarkan
   satker seolah baru berdiri, dan tunggakan terbesarnya — justru yang warisan
   — lenyap dari grafik. Aset yang tanggal perolehannya tak terbaca juga masuk
   stok awal: ia jelas sudah tercatat, hanya kapannya yang tak diketahui.

4. **Bulan yang belum berjalan DIBEDAKAN dari bulan tanpa tambahan.** Keduanya
   sama-sama kosong, tetapi menjawab pertanyaan yang berbeda.

5. **Isi yang melampaui rumahnya digencet DAN dihitung.** Aset yang tanggal
   pemeriksaannya mendahului tanggal perolehannya adalah kekeliruan data, bukan
   keadaan yang mungkin. Grafik yang menggencet diam-diam menyembunyikan justru
   baris yang perlu dibetulkan.
"""
from datetime import datetime

BULAN_SINGKAT = ("JAN", "FEB", "MAR", "APR", "MEI", "JUN",
                 "JUL", "AGU", "SEP", "OKT", "NOV", "DES")

#: Warna irisan per kegiatan pada grafik kedua. Dua puluh irisan berwarna dalam
#: satu batang tak dapat dibedakan mata siapa pun, jadi hanya delapan kegiatan
#: terbesar yang diberi warna sendiri.
WARNA_KEGIATAN = ("#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626",
                  "#0891b2", "#db2777", "#65a30d")
WARNA_LAINNYA = "#94a3b8"

#: Field stempel waktu pemeriksaan pada aset (lihat inventarisasi_stempel.py).
FIELD_STEMPEL = "tanggal_inventarisasi"


def _tahun_bulan(teks):
    """`(tahun, bulan)` dari "YYYY-MM-DD…"; `(None, None)` bila tak terbaca."""
    try:
        d = datetime.strptime(str(teks or "")[:10], "%Y-%m-%d")
        return d.year, d.month
    except (ValueError, TypeError, OverflowError):
        return None, None


def bulan_mulai(act):
    """Tahun dan bulan kegiatan dimulai; `created_at` sebagai cadangan."""
    return _tahun_bulan((act or {}).get("tanggal_mulai")
                        or (act or {}).get("created_at"))


def tahun_tampil(kegiatan, sekarang=None):
    """Tahun yang ditampilkan: kegiatan TERBARU yang tahunnya sudah berjalan.

    Tahun mendatang sengaja dilewati. Satu salah ketik tanggal — "2062"
    alih-alih "2026" — akan memindahkan seluruh linimasa ke tahun itu dan
    menyisakan grafik kosong, sementara pekerjaan tahun ini tak terlihat sama
    sekali. Kekeliruan datanya tetap terlihat di tempat lain; yang tak boleh
    adalah satu baris salah menyandera seluruh grafik.
    """
    kini = (sekarang or datetime.now()).year
    tahun = [th for th, _ in (bulan_mulai(a) for a in (kegiatan or [])) if th]
    berjalan = [th for th in tahun if th <= kini]
    return max(berjalan) if berjalan else kini


def bulan_terakhir_berjalan(tahun, sekarang=None):
    """Bulan terakhir yang sudah berjalan pada tahun itu (0–12).

    Jam yang SAMA dengan tanggal cetak laporannya. Memakai jam berbeda membuat
    laporan bertanggal 1 Oktober memuat grafik yang berhenti di September —
    dua tanggal berbeda pada satu dokumen, tanpa penjelasan.
    """
    kini = sekarang or datetime.now()
    if tahun > kini.year:
        return 0                     # seluruh tahunnya belum berjalan
    if tahun == kini.year:
        return kini.month
    return 12                        # tahun lampau ditampilkan penuh


def _kumpulkan(kegiatan, aset, tahun):
    """Cacah mentah per bulan, sebelum diakumulasikan."""
    kosong = lambda: [0] * 12                                   # noqa: E731
    d = {"tambah": kosong(), "temu": kosong(), "lain": kosong(),
         "ada_kegiatan": [False] * 12, "stok_awal": 0, "temu_awal": 0,
         "lain_awal": 0, "berstempel": 0, "perkiraan": 0,
         "awal_keg": {}, "tambah_keg": {}}
    per_keg = {}
    for a in (aset or []):
        per_keg.setdefault(a.get("activity_id"), []).append(a)

    for act in (kegiatan or []):
        th_act, bl_act = bulan_mulai(act)
        aid = (act or {}).get("id", "")
        d["awal_keg"].setdefault(aid, 0)
        d["tambah_keg"].setdefault(aid, [0] * 12)
        if th_act == tahun and bl_act:
            d["ada_kegiatan"][bl_act - 1] = True
        for a in per_keg.get((act or {}).get("id"), []):
            # Sisi RUMAH: kapan aset ini tercatat.
            th_p, bl_p = _tahun_bulan(a.get("purchase_date"))
            if th_p == tahun and bl_p:
                d["tambah"][bl_p - 1] += 1
                d["tambah_keg"][aid][bl_p - 1] += 1
            elif th_p is None or th_p < tahun:
                d["stok_awal"] += 1
                d["awal_keg"][aid] += 1
            # Perolehan bertahun MENDATANG tidak dihitung di mana pun: ia belum
            # menjadi stok tahun ini, dan menaruhnya di stok awal akan
            # menyatakan barang yang belum ada sebagai sudah ada.

            # Sisi ISI: kapan aset ini diperiksa, dan hasilnya.
            status = a.get("inventory_status") or "Belum Diinventarisasi"
            if status == "Belum Diinventarisasi":
                continue
            th_i, bl_i = _tahun_bulan(a.get(FIELD_STEMPEL))
            if th_i and bl_i:
                d["berstempel"] += 1
            else:
                th_i, bl_i = th_act, bl_act
                d["perkiraan"] += 1
            kunci = "temu" if status == "Ditemukan" else "lain"
            if th_i == tahun and bl_i:
                d[kunci][bl_i - 1] += 1
            elif th_i is not None and th_i < tahun:
                d[f"{kunci}_awal"] += 1
    return d


def hitung(kegiatan, aset, sekarang=None) -> dict:
    """Seluruh data grafik "Progres Inventarisasi" untuk satu himpunan aset.

    `kegiatan` = daftar kegiatan penyumbangnya (satu untuk laporan eksekutif,
    banyak untuk laporan gabungan). `aset` = seluruh asetnya.
    """
    waktu = sekarang or datetime.now()
    tahun = tahun_tampil(kegiatan, waktu)
    batas = bulan_terakhir_berjalan(tahun, waktu)
    d = _kumpulkan(kegiatan, aset, tahun)

    baris, puncak, janggal = [], 0, 0
    kum_catat, kum_temu, kum_lain = d["stok_awal"], d["temu_awal"], d["lain_awal"]
    for i in range(12):
        berjalan = (i + 1) <= batas
        tambahan = d["tambah"][i] if berjalan else 0
        if berjalan:
            kum_catat += tambahan
            kum_temu += d["temu"][i]
            kum_lain += d["lain"][i]
        diperiksa = kum_temu + kum_lain
        if diperiksa > kum_catat:
            janggal = max(janggal, diperiksa - kum_catat)
            diperiksa = kum_catat
        temu = min(kum_temu, diperiksa)
        puncak = max(puncak, kum_catat if berjalan else 0)
        baris.append({
            "bulan": BULAN_SINGKAT[i],
            "tercatat": kum_catat if berjalan else 0,
            "tambahan": tambahan,
            "ditemukan": temu if berjalan else 0,
            "periksa_lain": (diperiksa - temu) if berjalan else 0,
            "belum": (kum_catat - diperiksa) if berjalan else 0,
            "mulai": d["ada_kegiatan"][i],
            "belum_berjalan": not berjalan,
        })
    # Tinggi batang dihitung DI SINI, bukan di template: aritmetika di dalam
    # Jinja mudah membagi nol tanpa terlihat.
    for b in baris:
        b["h_tercatat"] = round(b["tercatat"] / puncak * 100) if puncak else 0

    akhir = baris[batas - 1] if batas else None
    n_lini = d["berstempel"] + d["perkiraan"]
    return {
        "baris": baris,
        "ada": puncak > 0,
        "tahun": tahun,
        "bulan_terakhir": batas,
        "tahun_berjalan": tahun >= waktu.year,
        "stok_awal": d["stok_awal"],
        "tambah_tahun": sum(d["tambah"]),
        "akhir_tercatat": akhir["tercatat"] if akhir else 0,
        "akhir_diperiksa": ((akhir["ditemukan"] + akhir["periksa_lain"])
                            if akhir else 0),
        "akhir_belum": akhir["belum"] if akhir else 0,
        "janggal": janggal,
        "pct_stempel": (round(d["berstempel"] / n_lini * 100, 1)
                        if n_lini else 0),
        "perkiraan": d["perkiraan"],
        # Bahan grafik kedua (irisan per kegiatan) — dipakai laporan gabungan.
        "awal_keg": d["awal_keg"],
        "tambah_keg": d["tambah_keg"],
    }


def iris_per_kegiatan(hasil, nama_kegiatan) -> tuple:
    """`(baris, legenda, ada)` — rumah yang SAMA, diiris menurut kegiatannya.

    Rumahnya persis rumah grafik utama — tinggi tiap bulan sama sampai ke
    piksel — tetapi isinya menjawab pertanyaan yang lain: kegiatan MANA yang
    menyumbang stok itu, dan sejak bulan berapa.

    Digambar hanya bila kegiatannya LEBIH DARI SATU: pada satu kegiatan,
    irisannya identik dengan rumahnya sendiri — grafik yang tak menambahkan apa
    pun, hanya satu halaman lagi untuk dilewati.
    """
    awal, tambah = hasil["awal_keg"], hasil["tambah_keg"]
    total = lambda i: awal.get(i, 0) + sum(tambah.get(i, []))   # noqa: E731
    urut = sorted(set(awal) | set(tambah),
                  key=lambda i: (-total(i), (nama_kegiatan or {}).get(i, "")))
    berisi = [i for i in urut if total(i) > 0]
    berwarna = berisi[:len(WARNA_KEGIATAN)]
    lain = berisi[len(WARNA_KEGIATAN):]

    legenda = [{"nama": (nama_kegiatan or {}).get(i) or i,
                "warna": WARNA_KEGIATAN[n], "n": total(i)}
               for n, i in enumerate(berwarna)]
    if lain:
        legenda.append({"nama": f"{len(lain)} kegiatan lainnya",
                        "warna": WARNA_LAINNYA,
                        "n": sum(total(i) for i in lain)})

    baris, kum = [], {i: awal.get(i, 0) for i in urut}
    for i in range(12):
        berjalan = (i + 1) <= hasil["bulan_terakhir"]
        if berjalan:
            for aid in urut:
                kum[aid] += tambah.get(aid, [0] * 12)[i]
        segmen = []
        if berjalan:
            for n, aid in enumerate(berwarna):
                if kum[aid]:
                    segmen.append({"n": kum[aid], "warna": WARNA_KEGIATAN[n],
                                   "nama": (nama_kegiatan or {}).get(aid) or aid})
            sisa = sum(kum[aid] for aid in lain)
            if sisa:
                segmen.append({"n": sisa, "warna": WARNA_LAINNYA,
                               "nama": f"{len(lain)} kegiatan lainnya"})
        pokok = hasil["baris"][i]
        baris.append({"bulan": pokok["bulan"], "tercatat": pokok["tercatat"],
                      "tambahan": pokok["tambahan"],
                      "h_tercatat": pokok["h_tercatat"],
                      "belum_berjalan": pokok["belum_berjalan"],
                      "mulai": pokok["mulai"], "segmen": segmen})
    return baris, legenda, hasil["ada"] and len(berisi) > 1
