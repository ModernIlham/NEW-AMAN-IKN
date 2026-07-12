"""Logika murni PENGGUNAAN (Fase 3 — modul Penggunaan tahap awal).

Rekap aset per PEMEGANG (pengguna barang) lintas kegiatan, dibangun dari
field yang sudah dicatat modul inventarisasi: `user` (nama pemegang/
jabatan/operasional), `pengguna_nip`, `pengguna_melekat_ke`,
`pengguna_jabatan`, dan `bast_file_id` (BAST terunggah).

Dasar: PMK 40/2024 (Penggunaan BMN) — pustaka §1; masterplan Fase 3:
"data pengguna+BAST dari modul inventarisasi menjadi data awal".
Fungsi murni tanpa Mongo/IO agar teruji unit.
"""


def kunci_pemegang(asset: dict):
    """Kunci identitas pemegang: (nama_norm, nip). None bila tanpa pengguna.

    Nama dinormalkan (trim + satu spasi + lower) supaya "Budi  Santoso" dan
    "budi santoso" tergabung; NIP kosong tetap membentuk kunci tersendiri
    per nama (dua orang beda NIP tidak boleh tercampur).
    """
    nama = " ".join(str(asset.get("user") or "").split())
    if not nama:
        return None
    nip = str(asset.get("pengguna_nip") or "").strip()
    return (nama.lower(), nip)


def rekap_pemegang(assets):
    """Rekap per pemegang → list terurut (jumlah aset terbanyak dulu).

    Tiap entri: nama (tampilan pertama yang dijumpai), nip, melekat_ke
    (moda terbanyak), jabatan (bila ada), jumlah_aset, jumlah_bast
    (aset ber-BAST terunggah), kegiatan (set id kegiatan → jumlah),
    lengkap (True bila SEMUA asetnya ber-BAST dan NIP terisi).
    """
    agg = {}
    for a in assets or []:
        key = kunci_pemegang(a)
        if key is None:
            continue
        e = agg.setdefault(key, {
            "nama": " ".join(str(a.get("user") or "").split()),
            "nip": key[1],
            "jabatan": "",
            "_melekat": {},
            "jumlah_aset": 0,
            "jumlah_bast": 0,
            "_kegiatan": set(),
        })
        e["jumlah_aset"] += 1
        if str(a.get("bast_file_id") or "").strip():
            e["jumlah_bast"] += 1
        jab = str(a.get("pengguna_jabatan") or "").strip()
        if jab and not e["jabatan"]:
            e["jabatan"] = jab
        melekat = str(a.get("pengguna_melekat_ke") or "").strip()
        if melekat:
            e["_melekat"][melekat] = e["_melekat"].get(melekat, 0) + 1
        act = str(a.get("activity_id") or "").strip()
        if act:
            e["_kegiatan"].add(act)

    hasil = []
    for e in agg.values():
        melekat = max(e["_melekat"], key=e["_melekat"].get) if e["_melekat"] else ""
        hasil.append({
            "nama": e["nama"],
            "nip": e["nip"],
            "jabatan": e["jabatan"],
            "melekat_ke": melekat,
            "jumlah_aset": e["jumlah_aset"],
            "jumlah_bast": e["jumlah_bast"],
            "jumlah_kegiatan": len(e["_kegiatan"]),
            "lengkap": bool(e["nip"]) and e["jumlah_bast"] == e["jumlah_aset"],
        })
    hasil.sort(key=lambda x: (-x["jumlah_aset"], x["nama"].lower()))
    return hasil
