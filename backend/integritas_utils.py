"""Logika murni integritas data lintas-modul (§5A Prinsip 1).

Register hilir (usulan penghapusan, pemeliharaan, pemindahtanganan, dll.)
menyimpan SNAPSHOT identitas aset (`asset_code`/`NUP`/`asset_name`) saat record
dibuat. Bila master aset kelak DIEDIT (mis. NUP dikoreksi), snapshot itu jadi
BASI → laporan/telusur silang bisa memakai identitas usang.

Modul ini hanya membandingkan dua dict (snapshot vs master terkini) — tanpa
Mongo/IO agar teruji unit. Pemanggil (endpoint read-only) yang mengambil data.
"""

# Field identitas yang di-snapshot di register hilir.
FIELD_IDENTITAS = ("asset_code", "NUP", "asset_name")


def _norm(v) -> str:
    """Normalisasi nilai identitas untuk pembanding: string ter-strip; None/""
    dianggap sama (abaikan beda None vs kosong vs spasi tepi)."""
    return str(v if v is not None else "").strip()


def identitas_drift(snapshot, master, fields=FIELD_IDENTITAS) -> dict:
    """Bandingkan snapshot identitas aset (di register hilir) dengan master aset
    TERKINI. Kembalikan dict ``{field: {"snapshot": s, "master": m}}`` HANYA
    untuk field yang BERBEDA (basi). Kosong ``{}`` = konsisten.

    Perbandingan memakai nilai ter-strip (None/""/spasi tepi setara) sehingga
    tak ada 'drift' palsu karena beda kosong. `snapshot`/`master` None/kosong →
    ``{}`` (tak ada pembanding — kasus 'master hilang' ditangani pemanggil).
    """
    if not snapshot or not master:
        return {}
    out = {}
    for f in fields:
        s = _norm(snapshot.get(f))
        m = _norm(master.get(f))
        if s != m:
            out[f] = {"snapshot": s, "master": m}
    return out


def drift_identitas_daftar(aset_list, master_by_id):
    """Deteksi identitas basi untuk DAFTAR snapshot aset (mis. `pemindahtanganan
    .aset[]`). Bandingkan tiap baris dengan master via `master_by_id`
    (dict `{asset_id: master}`) → daftar temuan:
    `{asset_id, masalah: "aset_master_hilang"|"snapshot_basi", snapshot?/drift?}`.
    Baris yang konsisten TIDAK dimasukkan. Fungsi murni — pemanggil menyiapkan
    `master_by_id` (batch, hindari N+1).
    """
    out = []
    for row in aset_list or []:
        aid = str(row.get("asset_id") or "")
        master = master_by_id.get(aid)
        if not master:
            out.append({
                "asset_id": aid, "masalah": "aset_master_hilang",
                "snapshot": {f: row.get(f) for f in FIELD_IDENTITAS},
            })
            continue
        drift = identitas_drift(row, master)
        if drift:
            out.append({"asset_id": aid, "masalah": "snapshot_basi",
                        "drift": drift})
    return out


def drift_identitas_tunggal(snapshot, master):
    """Temuan identitas untuk SATU snapshot (register yang membekukan identitas
    per record, mis. `jadwal_pemeliharaan`) vs master aset TERKINI:
    `{"masalah": "aset_master_hilang", "snapshot": {...}}` bila master tak ada;
    `{"masalah": "snapshot_basi", "drift": {...}}` bila ada field basi; `None`
    bila konsisten. Fungsi murni — pemanggil menyiapkan master & menyertakan
    konteks (asset_id dll)."""
    if not master:
        return {"masalah": "aset_master_hilang",
                "snapshot": {f: (snapshot or {}).get(f) for f in FIELD_IDENTITAS}}
    drift = identitas_drift(snapshot, master)
    if drift:
        return {"masalah": "snapshot_basi", "drift": drift}
    return None


def hitung_masalah(temuan):
    """Ringkas daftar temuan (mis. dari `drift_identitas_daftar`) → dict hitungan
    per nilai field `masalah`, mis. `{"snapshot_basi": 2, "aset_master_hilang":
    1}`. Fungsi murni — memudahkan endpoint integritas menyajikan ringkasan
    konsisten."""
    out = {}
    for t in temuan or []:
        m = (t or {}).get("masalah")
        if m:
            out[m] = out.get(m, 0) + 1
    return out


def gabung_temuan_integritas(bagian):
    """Gabungkan hasil beberapa cek integritas jadi SATU ringkasan dasbor
    (kapstone §5A gap #8). `bagian`: daftar dict per-cek/register berbentuk
    minimal ``{"register": str, "jumlah": int, "per_masalah": {masalah: n}}``.

    Kembalikan ``{"total_temuan": int, "per_masalah": {...gabungan lintas-cek},
    "jumlah_cek": int, "jumlah_cek_bermasalah": int, "bagian": [...apa adanya]}``.
    Fungsi murni — pemanggil (endpoint) menjalankan scan Mongo tiap register lalu
    menyusun `bagian`; ini menyatukan total agar dasbor konsisten tanpa menyentuh
    endpoint detail per register.
    """
    total = 0
    per_masalah = {}
    n_bermasalah = 0
    bagian = list(bagian or [])
    for b in bagian:
        jml = (b or {}).get("jumlah", 0) or 0
        total += jml
        if jml:
            n_bermasalah += 1
        for m, c in ((b or {}).get("per_masalah") or {}).items():
            per_masalah[m] = per_masalah.get(m, 0) + (c or 0)
    return {"total_temuan": total, "per_masalah": per_masalah,
            "jumlah_cek": len(bagian), "jumlah_cek_bermasalah": n_bermasalah,
            "bagian": bagian}
