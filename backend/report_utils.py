"""Perhitungan murni untuk laporan eksekutif — LOGIKA MURNI (tanpa DB/IO).

Dipisah dari routes/reports.py agar dapat diuji unit tanpa WeasyPrint/Mongo.
"""


#: Satu-satunya nilai `stiker_status` yang berarti "stikernya sudah menempel".
#: Formulir aset hanya menawarkan dua nilai — "Belum Terpasang" dan
#: "Sudah Terpasang" (lihat AssetForm.jsx dan models.py) — dan SELURUH
#: perhitungan stiker wajib membandingkan dengan konstanta ini, bukan dengan
#: teksnya sendiri-sendiri.
#:
#: Sebabnya konkret: laporan gabungan satker pernah membandingkan dengan
#: "Terpasang" (tanpa "Sudah"). Nilai itu tak pernah ada di basis data, jadi
#: kartu "Ditemukan, Stiker Terpasang" SELALU nol dan "Ditemukan, Belum
#: Berstiker" selalu memuat seluruh temuan — salah yang tak menimbulkan galat
#: apa pun, hanya angka yang tenang dan keliru.
STIKER_TERPASANG = "Sudah Terpasang"


def berstiker(aset) -> bool:
    """Apakah stiker aset ini sudah terpasang.

    Dipakai bersama oleh setiap penghitung stiker supaya perbandingannya
    hanya ditulis SATU kali; lihat STIKER_TERPASANG.
    """
    return (aset or {}).get("stiker_status") == STIKER_TERPASANG


def hitung_status_stiker(assets):
    """(terpasang, belum, pct) status pemasangan stiker atas SELURUH aset.

    'Sudah Terpasang' = terpasang; SELAIN itu (termasuk kosong/None/'Belum
    Terpasang') = belum. Persen atas total aset. MURNI (teruji unit).

    Perbaikan bug: sebelumnya `belum` dihitung sebagai (jumlah 'Ditemukan' −
    terpasang), sehingga aset yang belum diinventarisasi (justru yang belum
    berstiker) tak terhitung dan `belum` bisa 0 walau ada aset tanpa stiker.
    """
    lst = assets or []
    total = len(lst)
    terpasang = sum(1 for a in lst if berstiker(a))
    belum = total - terpasang
    pct = int(terpasang / total * 100) if total else 0
    return terpasang, belum, pct


_TANPA_PENGGUNA = "Tanpa Pengguna / NIP"


def distribusi_pengguna(assets, pegawai_by_nip=None):
    """Distribusi aset per pengguna — KEY = NIP/NIK, tampilan = nama pengguna.

    - Pengelompokan by field aset `pengguna_nip` (NIP/NIK). Aset tanpa NIP
      dikumpulkan pada satu grup "Tanpa Pengguna / NIP".
    - Nama tampilan: prioritas nama pegawai dari master (`pegawai_by_nip[nip]`),
      fallback field aset `user`, lalu "(nama tak dicatat)".
    - `unit_kerja` dari master (bila NIP terdaftar). `terdaftar` = NIP ada di
      master pegawai.
    Kembalikan `(rows, ringkas)` — rows terurut nilai desc → count desc → nama;
    ringkas = {jumlah_pengguna, jumlah_tak_terdaftar, ada_tanpa_nip}. MURNI.
    """
    peg = pegawai_by_nip or {}
    grup = {}
    for a in (assets or []):
        a = a or {}
        nip = str(a.get("pengguna_nip") or "").strip()
        key = nip or "__tanpa__"
        g = grup.get(key)
        if g is None:
            master = peg.get(nip) if nip else None
            if nip:
                nama = (str((master or {}).get("nama") or "").strip()
                        or str(a.get("user") or "").strip()
                        or "(nama tak dicatat)")
            else:
                nama = _TANPA_PENGGUNA
            g = grup[key] = {
                "nip": nip, "nama": nama,
                "unit_kerja": str((master or {}).get("unit_kerja") or "").strip(),
                "terdaftar": bool(master) if nip else False,
                "tanpa_nip": not nip,
                "count": 0, "value": 0.0,
            }
        g["count"] += 1
        try:
            g["value"] += float(a.get("purchase_price", 0) or 0)
        except (ValueError, TypeError):
            pass
    rows = sorted(grup.values(),
                  key=lambda r: (-r["value"], -r["count"], (r["nama"] or "").lower()))
    ringkas = {
        "jumlah_pengguna": sum(1 for r in rows if not r["tanpa_nip"]),
        "jumlah_tak_terdaftar": sum(1 for r in rows if r["nip"] and not r["terdaftar"]),
        "ada_tanpa_nip": any(r["tanpa_nip"] for r in rows),
    }
    return rows, ringkas
