"""Pengelompokan Data Aset, sesudah filter/sort dan SEBELUM paginasi foto.

Satu dasar per unduhan. Urutan kelompok mengikuti kemunculan pertama pada
hasil sort; urutan aset di dalam kelompok tidak diubah. Tidak membuang aset
tanpa kode/lokasi/identitas/PSP dan tidak memodifikasi dokumen sumber.
"""
import math

from asset_sorting import ASSET_SORT_OPTIONS
from kodefikasi_utils import LEVEL_LENGTHS, LEVEL_LABELS, normalize_kode, GOLONGAN_DEFAULTS

GROUP_OPTIONS = {
    "": "Biasa (tanpa pengelompokan)",
    **{f"kode_{n}": label for n, label in LEVEL_LABELS.items()},
    "lokasi": "Lokasi", "pemegang": "Pemegang", "spm": "SPM",
    **{f"eselon{n}": f"Eselon {n}" for n in range(1, 6)},
    "supplier": "Supplier", "perolehan": "Perolehan", "psp": "PSP",
}


def validasi_pilihan(group_by, sort_by):
    if group_by not in GROUP_OPTIONS:
        raise ValueError("Pilihan pengelompokan Data Aset tidak dikenal")
    if sort_by not in ASSET_SORT_OPTIONS:
        raise ValueError("Pilihan urutan Data Aset tidak dikenal")


def _teks(value):
    return " ".join(str(value if value is not None else "").split())


def _kunci(aset, mode, uraian, pegawai, format_tanggal):
    if not mode:
        return ("semua",), ""
    if mode.startswith("kode_"):
        n = int(mode[-1])
        kode = normalize_kode(aset.get("asset_code"))
        panjang = LEVEL_LENGTHS[n]
        if not kode.isdigit() or len(kode) < panjang:
            return ("kosong",), f"{LEVEL_LABELS[n]} belum tersedia"
        kode = kode[:panjang]
        nama = _teks(uraian.get(kode))
        return ("kode", kode), f"{kode} - {nama}" if nama else kode
    if mode.startswith("eselon"):
        n = int(mode[-1])
        # Nama daun sama di dua induk tidak boleh tergabung.
        jalur = tuple(_teks(aset.get(f"eselon{i}")) for i in range(1, n + 1))
        label = " > ".join(v or f"Eselon {i} belum diisi" for i, v in enumerate(jalur, 1))
        return ("eselon", *jalur), label
    if mode == "pemegang":
        nomor = _teks(aset.get("pengguna_nip"))
        nama = _teks(aset.get("user"))
        if nomor:
            nama = _teks((pegawai.get(nomor) or {}).get("nama")) or nama or "Nama belum diisi"
            return ("nomor", nomor), f"{nama} (Identitas: {nomor})"
        return (("nama", nama.casefold()), nama + " (tanpa nomor identitas)") if nama else (("kosong",), "Belum ada pemegang")
    if mode == "psp":
        psp = aset.get("psp") or {}
        nomor, tanggal = _teks(psp.get("no_psp")), _teks(psp.get("tanggal"))
        if not nomor:
            return ("kosong",), "Belum memiliki PSP"
        label_tanggal = format_tanggal(tanggal) if format_tanggal else tanggal
        return ("psp", nomor, tanggal), nomor + (f" / {label_tanggal}" if label_tanggal else "")
    field = {"lokasi": "location", "spm": "nomor_spm", "supplier": "supplier",
             "perolehan": "perolehan_dari_nama"}[mode]
    nilai = _teks(aset.get(field))
    return (("nilai", nilai), nilai) if nilai else (("kosong",), f"{GROUP_OPTIONS[mode]} belum diisi")


def irisan_kelompok(aset, mode="", row_slice=None, uraian=None, pegawai=None, format_tanggal=None):
    """Kembalikan aset irisan + metadata kelompok (indeks lokal dan global).

Tidak merender/mengambil foto; hanya aset irisan yang boleh di-embed oleh
pemanggil. Metadata jumlah/nilai kelompok tetap meliputi seluruh hasil filter.
"""
    if mode not in GROUP_OPTIONS:
        raise ValueError("Pilihan pengelompokan Data Aset tidak dikenal")
    referensi = {**dict(GOLONGAN_DEFAULTS), **(uraian or {})}
    kelompok = {}
    for a in aset:
        key, label = _kunci(a, mode, referensi, pegawai or {}, format_tanggal)
        g = kelompok.setdefault(key, {"label": label, "rows": [], "value": 0.0})
        g["rows"].append(a)
        try:
            nilai = float(a.get("purchase_price") or 0)
            if math.isfinite(nilai):
                g["value"] += nilai
        except (ValueError, TypeError):
            pass
    start, end = row_slice or (0, len(aset))
    rows, meta, offset = [], [], 0
    for g in kelompok.values():
        count = len(g["rows"])
        lo, hi = max(start, offset), min(end, offset + count)
        if lo < hi:
            part = g["rows"][lo - offset:hi - offset]
            meta.append({"label": g["label"], "count": count, "part_count": len(part),
                         "value_fmt": f"{int(g['value']):,}".replace(",", "."),
                         "start": len(rows), "end": len(rows) + len(part),
                         "offset": lo, "lanjutan": lo > offset})
            rows.extend(part)
        offset += count
    return rows, meta
