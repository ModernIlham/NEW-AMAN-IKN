"""Logika murni WASDAL (PMK 207/PMK.06/2021 — pustaka §8).

Dasbor pemantauan Wasdal tingkat KPB: mesin aturan ringan yang membaca
register yang SUDAH ada (aset, pemanfaatan, usulan penghapusan,
pemindahtanganan, pemeliharaan) dan menghasilkan TEMUAN per lima objek
pemantauan PMK 207 — penggunaan, pemanfaatan, pemindahtanganan (termasuk
penghapusan), penatausahaan, pengamanan & pemeliharaan. Bahan pra-isi
laporan wasdal semesteran; kanal resmi pelaporan tetap SIMAN v2.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date, timedelta

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


# ── Penertiban KPB (PMK 207: selesai ≤15 hari kerja — pustaka §8.3) ──
SUMBER_PENERTIBAN = {
    "pemantauan": "Hasil pemantauan KPB",
    "permintaan_pengelola": "Surat permintaan Pengelola",
    "apip_bpk": "Temuan APIP/BPK",
}

STATUS_PENERTIBAN = {"berjalan": "Berjalan", "selesai": "Selesai"}

TENGGAT_HARI_KERJA = 15


def tambah_hari_kerja(mulai_iso: str, hari_kerja: int = TENGGAT_HARI_KERJA):
    """Tanggal setelah N hari kerja (Senin–Jumat; libur nasional tidak
    dihitung — tenggat regulasi tetap acuan, ini pendekatan konservatif)."""
    mulai = _tgl(mulai_iso)
    if not mulai or hari_kerja < 0:
        return None
    d, sisa = mulai, hari_kerja
    while sisa > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            sisa -= 1
    return d.isoformat()


def sisa_hari_kerja(dari_iso: str, sampai_iso: str):
    """Jumlah hari kerja dari `dari` (eksklusif) sampai `sampai` (inklusif);
    None bila tanggal tidak valid, 0 bila sudah lewat/sama."""
    dari, sampai = _tgl(dari_iso), _tgl(sampai_iso)
    if not dari or not sampai:
        return None
    if sampai <= dari:
        return 0
    d, n = dari, 0
    while d < sampai:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def status_tenggat_penertiban(tiket: dict, today_iso: str) -> dict:
    """Info tenggat tiket → {lewat, sisa_hari_kerja} (hanya tiket berjalan)."""
    if tiket.get("status") != "berjalan":
        return {"lewat": False, "sisa_hari_kerja": None}
    tenggat, hari_ini = _tgl(tiket.get("tenggat")), _tgl(today_iso)
    if not tenggat or not hari_ini:
        return {"lewat": False, "sisa_hari_kerja": None}
    if hari_ini > tenggat:
        return {"lewat": True, "sisa_hari_kerja": 0}
    return {"lewat": False,
            "sisa_hari_kerja": sisa_hari_kerja(today_iso, tiket.get("tenggat"))}


def validate_penertiban(data: dict) -> list:
    """Validasi input tiket penertiban baru → daftar pesan kesalahan."""
    errors = []
    if data.get("sumber") not in SUMBER_PENERTIBAN:
        errors.append("Sumber penertiban tidak dikenal")
    if data.get("objek") and data["objek"] not in OBJEK_WASDAL:
        errors.append("Objek pemantauan tidak dikenal")
    if not _terisi(data.get("uraian")):
        errors.append("Uraian penertiban wajib diisi")
    if not _tgl(data.get("tanggal_dasar")):
        errors.append("Tanggal dasar tidak valid (YYYY-MM-DD)")
    return errors


def validate_selesai_penertiban(tiket: dict, data: dict) -> list:
    """Validasi penyelesaian tiket: harus berjalan + tindak lanjut terisi."""
    errors = []
    if tiket.get("status") != "berjalan":
        errors.append("Tiket sudah selesai")
    if not _terisi(data.get("tindak_lanjut")):
        errors.append("Uraian tindak lanjut wajib diisi")
    return errors


def rekap_penertiban(items, today_iso: str) -> dict:
    """Ringkasan register penertiban: total, berjalan, selesai, lewat tenggat."""
    items = items or []
    berjalan = [t for t in items if t.get("status") == "berjalan"]
    lewat = sum(1 for t in berjalan
                if status_tenggat_penertiban(t, today_iso)["lewat"])
    return {"total": len(items), "berjalan": len(berjalan),
            "selesai": sum(1 for t in items if t.get("status") == "selesai"),
            "lewat_tenggat": lewat}


# ── Pemantauan insidentil (PMK 207 §8.3: pelaksanaan ≤10 hari kerja,
#    hasil dilaporkan ≤5 hari kerja sejak tanggal BA) ──
PEMICU_INSIDENTIL = {
    "informasi_masyarakat": "Informasi masyarakat",
    "pemberitaan_media": "Pemberitaan media",
    "hasil_audit": "Hasil audit APIP/BPK",
}

STATUS_INSIDENTIL = {
    "berjalan": "Berjalan",
    "ba_terbit": "BA terbit",
    "dilaporkan": "Dilaporkan",
}

TENGGAT_PELAKSANAAN_HK = 10
TENGGAT_LAPOR_HK = 5


def validate_insidentil(data: dict) -> list:
    """Validasi pembukaan pemantauan insidentil baru."""
    errors = []
    if data.get("pemicu") not in PEMICU_INSIDENTIL:
        errors.append("Pemicu pemantauan tidak dikenal")
    if data.get("objek") and data["objek"] not in OBJEK_WASDAL:
        errors.append("Objek pemantauan tidak dikenal")
    if not _terisi(data.get("uraian")):
        errors.append("Uraian pemantauan wajib diisi")
    if not _tgl(data.get("tanggal_mulai")):
        errors.append("Tanggal mulai tidak valid (YYYY-MM-DD)")
    return errors


def validate_ba_insidentil(tiket: dict, data: dict) -> list:
    """Validasi penerbitan BA: tiket berjalan + nomor & tanggal BA."""
    errors = []
    if tiket.get("status") != "berjalan":
        errors.append("BA hanya dapat diterbitkan pada tiket berjalan")
    if not _terisi(data.get("nomor_ba")):
        errors.append("Nomor BA wajib diisi")
    if not _tgl(data.get("tanggal_ba")):
        errors.append("Tanggal BA tidak valid (YYYY-MM-DD)")
    if not _terisi(data.get("hasil")):
        errors.append("Ringkasan hasil pemantauan wajib diisi")
    return errors


def validate_lapor_insidentil(tiket: dict, data: dict) -> list:
    """Validasi pelaporan hasil: tiket ber-BA + tanggal lapor."""
    errors = []
    if tiket.get("status") != "ba_terbit":
        errors.append("Pelaporan hanya untuk tiket dengan BA terbit")
    if not _tgl(data.get("tanggal_lapor")):
        errors.append("Tanggal lapor tidak valid (YYYY-MM-DD)")
    return errors


def info_tenggat_insidentil(tiket: dict, today_iso: str) -> dict:
    """Tenggat aktif tiket insidentil per statusnya.

    berjalan  → tenggat pelaksanaan (mulai + 10 hari kerja)
    ba_terbit → tenggat lapor (tanggal BA + 5 hari kerja)
    dilaporkan → tidak ada tenggat aktif.
    """
    status = tiket.get("status")
    if status == "berjalan":
        tenggat = tambah_hari_kerja(tiket.get("tanggal_mulai"),
                                    TENGGAT_PELAKSANAAN_HK)
        tahap = "pelaksanaan"
    elif status == "ba_terbit":
        tenggat = tambah_hari_kerja(tiket.get("tanggal_ba"), TENGGAT_LAPOR_HK)
        tahap = "lapor"
    else:
        return {"tahap": None, "tenggat": None, "lewat": False,
                "sisa_hari_kerja": None}
    hari_ini = _tgl(today_iso)
    batas = _tgl(tenggat)
    if not batas or not hari_ini:
        return {"tahap": tahap, "tenggat": tenggat, "lewat": False,
                "sisa_hari_kerja": None}
    if hari_ini > batas:
        return {"tahap": tahap, "tenggat": tenggat, "lewat": True,
                "sisa_hari_kerja": 0}
    return {"tahap": tahap, "tenggat": tenggat, "lewat": False,
            "sisa_hari_kerja": sisa_hari_kerja(today_iso, tenggat)}


def rekap_insidentil(items, today_iso: str) -> dict:
    """Ringkasan register insidentil: jumlah per status + lewat tenggat."""
    items = items or []
    per_status = {k: 0 for k in STATUS_INSIDENTIL}
    lewat = 0
    for t in items:
        st = t.get("status")
        if st in per_status:
            per_status[st] += 1
        if info_tenggat_insidentil(t, today_iso)["lewat"]:
            lewat += 1
    return {"total": len(items), **per_status, "lewat_tenggat": lewat}


# Ekspor label status perjanjian agar UI wasdal tak impor ganda
LABEL_STATUS_PEMANFAATAN = LABEL_STATUS_PERJANJIAN
