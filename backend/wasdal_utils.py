"""Logika murni WASDAL (PMK 207/PMK.06/2021 — pustaka §8).

Dasbor pemantauan Wasdal tingkat KPB: mesin aturan ringan yang membaca
register yang SUDAH ada (aset, pemanfaatan, usulan penghapusan,
pemindahtanganan, pemeliharaan) dan menghasilkan TEMUAN per lima objek
pemantauan PMK 207 — penggunaan, pemanfaatan, pemindahtanganan (termasuk
penghapusan), penatausahaan, pengamanan & pemeliharaan. Bahan pra-isi
laporan wasdal semesteran; kanal resmi pelaporan tetap SIMAN v2.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pemanfaatan_utils import (
    LABEL_STATUS_PERJANJIAN, dokumen_kurang, status_perjanjian,
)
from penghapusan_utils import JALUR_KANDIDAT, jalur_kandidat
from pemindahtanganan_utils import peringatan_pt

# Kunci objek pemantauan → label Indonesia (urutan tampil dasbor)
OBJEK_WASDAL = {
    "penggunaan": "Penggunaan",
    "pemanfaatan": "Pemanfaatan",
    "pemindahtanganan": "Pemindahtanganan & Penghapusan",
    "penatausahaan": "Penatausahaan",
    "pengamanan_pemeliharaan": "Pengamanan & Pemeliharaan",
}

# Kunci jenis temuan → label Indonesia (dipakai UI & endpoint)
JENIS_TEMUAN = {
    "pemegang_tanpa_bast": "Pemegang tercatat tanpa BAST terunggah",
    "tanpa_pengguna": "Tanpa pengguna tercatat (indikasi tidak digunakan)",
    "perjanjian_berakhir": "Perjanjian pemanfaatan berakhir",
    "dokumen_pemanfaatan_kurang": "Dokumen pemanfaatan belum lengkap",
    "usulan_hapus_berlarut": "Usulan penghapusan berlarut",
    "kandidat_belum_diusulkan": "Kandidat hapus belum diusulkan",
    "tenggat_lelang": "Tenggat lelang pemindahtanganan",
    "tanpa_kondisi": "Kondisi belum dicatat",
    "tanpa_nilai": "Nilai perolehan belum dicatat",
    "tanpa_koordinat": "Koordinat belum dicatat",
    "sengketa": "Dalam sengketa",
    "rusak_tanpa_pemeliharaan": "Rusak tanpa pemeliharaan tahun berjalan",
}

# Objek pemantauan tiap jenis temuan (setiap jenis tepat satu objek)
OBJEK_PER_JENIS = {
    "pemegang_tanpa_bast": "penggunaan",
    "tanpa_pengguna": "penggunaan",
    "perjanjian_berakhir": "pemanfaatan",
    "dokumen_pemanfaatan_kurang": "pemanfaatan",
    "usulan_hapus_berlarut": "pemindahtanganan",
    "kandidat_belum_diusulkan": "pemindahtanganan",
    "tenggat_lelang": "pemindahtanganan",
    "tanpa_kondisi": "penatausahaan",
    "tanpa_nilai": "penatausahaan",
    "tanpa_koordinat": "penatausahaan",
    "sengketa": "pengamanan_pemeliharaan",
    "rusak_tanpa_pemeliharaan": "pengamanan_pemeliharaan",
}

# Usulan penghapusan yang belum berujung SK melewati ambang ini = berlarut
AMBANG_BERLARUT_HARI = 90


def _terisi(v) -> bool:
    return bool(str(v or "").strip())


def _tgl(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _identitas(asset: dict) -> dict:
    return {"asset_id": asset.get("id"),
            "asset_code": asset.get("asset_code"),
            "NUP": asset.get("NUP"),
            "asset_name": asset.get("asset_name")}


def periode_wasdal(today_iso: str) -> dict:
    """Periode laporan wasdal berjalan → {tahun, semester, label}."""
    hari = _tgl(today_iso) or date(1970, 1, 1)
    sem = 1 if hari.month <= 6 else 2
    romawi = "I" if sem == 1 else "II"
    return {"tahun": hari.year, "semester": sem,
            "label": f"Semester {romawi} {hari.year}"}


def temuan_penggunaan(assets):
    """Objek PENGGUNAAN: pemegang tanpa BAST; aset tanpa pengguna."""
    out = []
    for a in assets or []:
        if _terisi(a.get("user")):
            if not _terisi(a.get("bast_file_id")):
                out.append({"jenis": "pemegang_tanpa_bast", **_identitas(a),
                            "detail": f"Pemegang: {str(a.get('user')).strip()}"})
        else:
            out.append({"jenis": "tanpa_pengguna", **_identitas(a),
                        "detail": ""})
    return out


def temuan_pemanfaatan(items, today_iso: str):
    """Objek PEMANFAATAN: perjanjian berakhir / dokumen kurang."""
    out = []
    for p in items or []:
        status = status_perjanjian(p, today_iso)
        ident = {"pemanfaatan_id": p.get("id"),
                 "bentuk": p.get("bentuk"),
                 "pihak": p.get("pihak"),
                 "asset_name": p.get("asset_name")}
        if status == "berakhir":
            out.append({"jenis": "perjanjian_berakhir", **ident,
                        "detail": f"Berakhir {p.get('berakhir') or '-'}"})
        elif status == "tidak_lengkap":
            out.append({"jenis": "dokumen_pemanfaatan_kurang", **ident,
                        "detail": "; ".join(dokumen_kurang(p))})
    return out


def temuan_pemindahtanganan(assets, usulan_hapus, usulan_pt, today_iso: str,
                            ambang_hari: int = AMBANG_BERLARUT_HARI):
    """Objek PEMINDAHTANGANAN & PENGHAPUSAN.

    Tiga aturan: usulan penghapusan aktif melewati ambang hari (berlarut),
    kandidat hapus (RB/Tidak Ditemukan) tanpa usulan aktif, dan peringatan
    tenggat lelang pemindahtanganan (peringatan_pt).
    """
    out = []
    hari_ini = _tgl(today_iso)
    ada_usulan = set()
    for u in usulan_hapus or []:
        if u.get("status") in ("diusulkan", "diproses"):
            ada_usulan.add(u.get("asset_id"))
            mulai = _tgl(u.get("tanggal_usulan")) or _tgl(u.get("created_at"))
            if hari_ini and mulai and (hari_ini - mulai).days > ambang_hari:
                out.append({
                    "jenis": "usulan_hapus_berlarut",
                    "usulan_id": u.get("id"), "asset_id": u.get("asset_id"),
                    "asset_name": u.get("asset_name"),
                    "detail": (f"{(hari_ini - mulai).days} hari sejak usulan "
                               f"({u.get('status')})")})
    for a in assets or []:
        jalur = jalur_kandidat(a)
        if jalur and a.get("id") not in ada_usulan:
            out.append({"jenis": "kandidat_belum_diusulkan", **_identitas(a),
                        "detail": JALUR_KANDIDAT[jalur][0]})
    for u in usulan_pt or []:
        for w in peringatan_pt(u, today_iso):
            out.append({"jenis": "tenggat_lelang",
                        "usulan_id": u.get("id"), "bentuk": u.get("bentuk"),
                        "pihak": u.get("pihak"), "detail": w})
    return out


def temuan_penatausahaan(assets):
    """Objek PENATAUSAHAAN: kondisi/nilai/koordinat belum dicatat."""
    out = []
    for a in assets or []:
        if not _terisi(a.get("condition")):
            out.append({"jenis": "tanpa_kondisi", **_identitas(a), "detail": ""})
        try:
            bernilai = float(a.get("purchase_price") or 0) > 0
        except (TypeError, ValueError):
            bernilai = False
        if not bernilai:
            out.append({"jenis": "tanpa_nilai", **_identitas(a), "detail": ""})
        if not (_terisi(a.get("koordinat_latitude"))
                and _terisi(a.get("koordinat_longitude"))):
            out.append({"jenis": "tanpa_koordinat", **_identitas(a),
                        "detail": ""})
    return out


def temuan_pengamanan_pemeliharaan(assets, pemeliharaan, tahun: int):
    """Objek PENGAMANAN & PEMELIHARAAN.

    Sengketa (status/nomor perkara/pihak) + aset Rusak Ringan/Berat tanpa
    catatan pemeliharaan pada tahun berjalan.
    """
    from pengamanan_utils import is_sengketa

    dirawat = set()
    for r in pemeliharaan or []:
        if str(r.get("tanggal") or "")[:4] == str(tahun):
            dirawat.add(r.get("asset_id"))
    out = []
    for a in assets or []:
        if is_sengketa(a):
            out.append({"jenis": "sengketa", **_identitas(a),
                        "detail": str(a.get("nomor_perkara") or "").strip()})
        kondisi = str(a.get("condition") or "").strip()
        if kondisi in ("Rusak Ringan", "Rusak Berat") and a.get("id") not in dirawat:
            out.append({"jenis": "rusak_tanpa_pemeliharaan", **_identitas(a),
                        "detail": kondisi})
    return out


def susun_temuan(assets, pemanfaatan, usulan_hapus, usulan_pt,
                 pemeliharaan, today_iso: str,
                 ambang_hari: int = AMBANG_BERLARUT_HARI) -> dict:
    """Seluruh temuan terkelompok per objek → {objek: [temuan...]}."""
    tahun = periode_wasdal(today_iso)["tahun"]
    semua = (temuan_penggunaan(assets)
             + temuan_pemanfaatan(pemanfaatan, today_iso)
             + temuan_pemindahtanganan(assets, usulan_hapus, usulan_pt,
                                       today_iso, ambang_hari)
             + temuan_penatausahaan(assets)
             + temuan_pengamanan_pemeliharaan(assets, pemeliharaan, tahun))
    per_objek = {k: [] for k in OBJEK_WASDAL}
    for t in semua:
        t["label"] = JENIS_TEMUAN[t["jenis"]]
        per_objek[OBJEK_PER_JENIS[t["jenis"]]].append(t)
    return per_objek


def rekap_wasdal(per_objek: dict) -> dict:
    """Ringkasan dasbor: jumlah temuan per objek + per jenis + total."""
    per_o = {k: len(per_objek.get(k) or []) for k in OBJEK_WASDAL}
    per_jenis = {}
    for temuan in (per_objek or {}).values():
        for t in temuan:
            per_jenis[t["jenis"]] = per_jenis.get(t["jenis"], 0) + 1
    return {"per_objek": per_o, "per_jenis": per_jenis,
            "total": sum(per_o.values())}


# Ekspor label status perjanjian agar UI wasdal tak impor ganda
LABEL_STATUS_PEMANFAATAN = LABEL_STATUS_PERJANJIAN
