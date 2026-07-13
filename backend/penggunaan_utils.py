"""Logika murni PENGGUNAAN (Fase 3 — modul Penggunaan tahap awal).

Rekap aset per PEMEGANG (pengguna barang) lintas kegiatan, dibangun dari
field yang sudah dicatat modul inventarisasi: `user` (nama pemegang/
jabatan/operasional), `pengguna_nip`, `pengguna_melekat_ke`,
`pengguna_jabatan`, dan `bast_file_id` (BAST terunggah) — plus daftar
pantau BMN IDLE (PMK 120/2024: BMN yang tidak digunakan untuk tusi wajib
diklarifikasi lalu diserahkan ke Pengelola Barang bila benar idle).

Dasar: PMK 40/2024 (Penggunaan BMN) + PMK 120/2024 (BMN idle) — pustaka
§1 & §8. Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

# Jenis penetapan penggunaan (PMK 40/2024) → label Indonesia
JENIS_PSP = {
    "psp": "Penetapan Status Penggunaan (PSP)",
    "alih_status": "Alih Status Penggunaan",
    "penggunaan_sementara": "Penggunaan Sementara",
    "dioperasikan_pihak_lain": "Dioperasikan Pihak Lain",
    "penggunaan_bersama": "Penggunaan Bersama",
}


def validate_psp(data: dict, today_iso: str, draf: bool = False) -> list:
    """Validasi pencatatan SK penetapan penggunaan → daftar kesalahan.

    draf=True (usulan sebelum SK terbit): nomor/tanggal SK opsional —
    keduanya baru wajib saat transisi ke "ditetapkan".
    """
    from datetime import date

    errors = []
    tanggal = str(data.get("tanggal_sk") or "").strip()[:10]
    if not draf and not str(data.get("nomor_sk") or "").strip():
        errors.append("Nomor SK wajib diisi")
    if not draf or tanggal:
        try:
            t = date.fromisoformat(tanggal)
            hari_ini = date.fromisoformat((today_iso or "")[:10])
            if t > hari_ini:
                errors.append("Tanggal SK tidak boleh di masa depan")
        except ValueError:
            errors.append("Tanggal SK wajib (format YYYY-MM-DD)"
                          if not draf else
                          "Tanggal SK (bila diisi) harus berformat YYYY-MM-DD")
    if data.get("jenis") not in JENIS_PSP:
        pilihan = ", ".join(JENIS_PSP)
        errors.append(f"Jenis penetapan tidak dikenal (pilihan: {pilihan})")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset yang ditetapkan")
    return errors


# Alur pengajuan PSP (pustaka §13 — usulan sebelum SK terbit). SK lama
# tanpa field status dianggap sudah DITETAPKAN (SK terbit) agar data
# eksisting tetap sah tanpa migrasi.
STATUS_PENGAJUAN_PSP = {
    "draf": "Draf Usulan",
    "diajukan": "Diajukan ke Pejabat Penetap",
    "ditetapkan": "Ditetapkan (SK terbit)",
    "ditolak": "Ditolak",
}

TRANSISI_PENGAJUAN_PSP = {
    "draf": {"diajukan"},
    # "draf" dari diajukan = dikembalikan untuk perbaikan (catatan wajib)
    "diajukan": {"ditetapkan", "ditolak", "draf"},
    "ditetapkan": set(),
    "ditolak": set(),
}


def status_pengajuan_psp(sk: dict) -> str:
    """Status pengajuan; record lama tanpa field = ditetapkan."""
    s = str(sk.get("status_pengajuan") or "").strip()
    return s if s in STATUS_PENGAJUAN_PSP else "ditetapkan"


def validate_transisi_pengajuan_psp(sk: dict, ke: str, data: dict,
                                    today_iso: str) -> list:
    """Validasi pindah status pengajuan + syarat dokumen per tahap."""
    from datetime import date

    errors = []
    dari = status_pengajuan_psp(sk)
    if ke not in STATUS_PENGAJUAN_PSP:
        errors.append("Status tujuan tidak dikenal")
        return errors
    if ke not in TRANSISI_PENGAJUAN_PSP.get(dari, set()):
        errors.append(f"Transisi {dari} → {ke} tidak sah")
        return errors
    if ke == "ditetapkan":
        if not str(data.get("nomor_sk") or "").strip():
            errors.append("Nomor SK wajib diisi saat penetapan")
        try:
            t = date.fromisoformat(str(data.get("tanggal_sk") or "").strip()[:10])
            if t > date.fromisoformat((today_iso or "")[:10]):
                errors.append("Tanggal SK tidak boleh di masa depan")
        except ValueError:
            errors.append("Tanggal SK wajib (format YYYY-MM-DD) saat penetapan")
    if ke in {"ditolak", "draf"} and not str(data.get("catatan") or "").strip():
        errors.append("Catatan wajib diisi saat menolak/mengembalikan usulan")
    return errors


def rekap_psp(daftar_sk) -> dict:
    """Ringkasan register PSP: jumlah SK, per jenis/status, aset tercakup.

    Cakupan aset ter-PSP hanya menghitung SK yang sudah DITETAPKAN —
    draf/diajukan/ditolak belum menetapkan status penggunaan apa pun.
    """
    per_jenis = {k: 0 for k in JENIS_PSP}
    per_status = {k: 0 for k in STATUS_PENGAJUAN_PSP}
    aset_unik = set()
    for sk in daftar_sk or []:
        j = sk.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
        s = status_pengajuan_psp(sk)
        per_status[s] += 1
        if s == "ditetapkan":
            for a in sk.get("aset") or []:
                if a.get("asset_id"):
                    aset_unik.add(a["asset_id"])
    return {"jumlah_sk": len(daftar_sk or []), "per_jenis": per_jenis,
            "per_status": per_status, "aset_tercakup": len(aset_unik)}


# Status tiket penanganan BMN idle → label Indonesia
STATUS_IDLE = {
    "klarifikasi": "Klarifikasi (diteliti penggunaannya)",
    "digunakan_kembali": "Digunakan Kembali (bukan idle)",
    "usul_serah": "Diusulkan Serah ke Pengelola",
    "diserahkan": "Diserahkan ke Pengelola Barang",
}

TRANSISI_IDLE = {
    "klarifikasi": {"digunakan_kembali", "usul_serah"},
    "usul_serah": {"diserahkan"},
    "digunakan_kembali": set(),
    "diserahkan": set(),
}


def indikasi_idle(asset: dict):
    """(kandidat, alasan) — indikasi BMN idle dari data inventarisasi.

    Kandidat: aset berstatus Nonaktif ATAU tanpa pengguna tercatat.
    Aset Tidak Ditemukan bukan kandidat idle (jalurnya penelusuran/TGR
    di modul Penghapusan). Hanya penanda klarifikasi — keputusan idle
    final lewat penelitian (PMK 120/2024).
    """
    if str(asset.get("inventory_status") or "").strip() == "Tidak Ditemukan":
        return False, ""
    if str(asset.get("status") or "").strip() == "Nonaktif":
        return True, "Status aset Nonaktif"
    if not str(asset.get("user") or "").strip():
        return True, "Tanpa pengguna tercatat (indikasi tidak digunakan untuk tusi)"
    return False, ""


def validate_transisi_idle(dari: str, ke: str, data: dict) -> list:
    """Validasi pindah status tiket idle + dokumen wajib per tahap."""
    errors = []
    if ke not in STATUS_IDLE:
        errors.append("Status tujuan tidak dikenal")
        return errors
    if ke not in TRANSISI_IDLE.get(dari, set()):
        errors.append(f"Transisi {dari} → {ke} tidak sah")
        return errors
    if ke == "usul_serah" and not str(data.get("nomor_usulan") or "").strip():
        errors.append("Nomor surat usulan penyerahan wajib diisi")
    if ke == "diserahkan" and not str(data.get("nomor_bast_serah") or "").strip():
        errors.append("Nomor BAST penyerahan ke Pengelola wajib diisi")
    return errors


def rekap_idle(kandidat, tiket) -> dict:
    """Ringkasan dasbor idle: jumlah kandidat + tiket per status."""
    per_status = {k: 0 for k in STATUS_IDLE}
    for t in tiket or []:
        s = t.get("status")
        if s in per_status:
            per_status[s] += 1
    return {"kandidat": len(kandidat or []), "per_status": per_status,
            "tiket": len(tiket or [])}


HEADER_CSV_IDLE = [
    "kode_aset", "nup", "nama_aset", "alasan", "status", "nomor_usulan",
    "nomor_bast_serah", "keterangan", "dibuat_oleh", "tanggal_dibuat",
]


def baris_csv_idle(tiket_list) -> list:
    """Susun baris CSV register tiket BMN idle: [header, *data] — fungsi murni.

    Status diterjemahkan ke label; tanggal dipangkas 10 char; field hilang →
    string kosong. Tanpa Mongo/IO agar teruji unit (pola ekspor #158).
    """
    baris = [list(HEADER_CSV_IDLE)]
    for t in tiket_list or []:
        baris.append([
            t.get("asset_code") or "",
            t.get("NUP") or "",
            t.get("asset_name") or "",
            t.get("alasan") or "",
            STATUS_IDLE.get(t.get("status"), t.get("status") or ""),
            t.get("nomor_usulan") or "",
            t.get("nomor_bast_serah") or "",
            t.get("keterangan") or "",
            t.get("created_by") or "",
            str(t.get("created_at") or "")[:10],
        ])
    return baris


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


# ---------------------------------------------------------------------------
# Tiket proses Alih Status & Penggunaan Sementara (PMK 40/2024, riset
# #181) — register PROSES antar Pengguna Barang; SK final tetap dicatat
# di register SK PSP. Tenggat BAST ≤1 bulan / SK penghapusan ≤2 bulan /
# lapor ≤1 bulan HANYA pengingat internal (angka [perlu verifikasi]
# §14) — tidak memblokir input tanggal riil.
# ---------------------------------------------------------------------------

JENIS_PROSES_PENGGUNAAN = {
    "alih_status": "Alih Status Penggunaan",
    "penggunaan_sementara": "Penggunaan Sementara",
    "dioperasikan_pihak_lain": "Dioperasikan Pihak Lain",
    "penggunaan_bersama": "Penggunaan Bersama",
}

ARAH_PROSES = {"keluar": "Keluar (satker sebagai asal)",
               "masuk": "Masuk (satker sebagai penerima)"}

STATUS_PROSES = {
    "draf": "Draf",
    "diajukan": "Diajukan ke Pengelola",
    "disetujui": "Disetujui Pengelola",
    "ditolak": "Ditolak",
    "bast_selesai": "BAST selesai",
    "dihapus_dibukukan": "Dihapus & dibukukan pengguna baru",
    "berjalan": "Berjalan",
    "berakhir": "Berakhir",
}

# Penggunaan sementara ≤6 bulan boleh langsung berjalan (perjanjian antar
# Pengguna Barang tanpa persetujuan Pengelola — [perlu verifikasi]).
TRANSISI_PROSES = {
    "alih_status": {
        "draf": {"diajukan"},
        "diajukan": {"disetujui", "ditolak"},
        "disetujui": {"bast_selesai"},
        "bast_selesai": {"dihapus_dibukukan"},
        "dihapus_dibukukan": set(),
        "ditolak": set(),
    },
    "penggunaan_sementara": {
        "draf": {"diajukan"},
        "diajukan": {"disetujui", "berjalan", "ditolak"},
        "disetujui": {"berjalan"},
        "berjalan": {"berakhir"},
        "berakhir": set(),
        "ditolak": set(),
    },
    # Dioperasikan pihak lain (PENETAPAN Pengelola; pihak non-K/L) dan
    # penggunaan bersama (Eminen + Kolaborator; persetujuan Pengelola) —
    # keduanya berjangka, tanpa jalur pintas ≤6 bulan.
    "dioperasikan_pihak_lain": {
        "draf": {"diajukan"},
        "diajukan": {"disetujui", "ditolak"},
        "disetujui": {"berjalan"},
        "berjalan": {"berakhir"},
        "berakhir": set(),
        "ditolak": set(),
    },
    "penggunaan_bersama": {
        "draf": {"diajukan"},
        "diajukan": {"disetujui", "ditolak"},
        "disetujui": {"berjalan"},
        "berjalan": {"berakhir"},
        "berakhir": set(),
        "ditolak": set(),
    },
}


def validate_proses_penggunaan(data: dict) -> list:
    """Validasi tiket proses baru → daftar pesan kesalahan."""
    from datetime import date

    errors = []
    if data.get("jenis_proses") not in JENIS_PROSES_PENGGUNAAN:
        valid = ", ".join(JENIS_PROSES_PENGGUNAAN)
        errors.append(f"Jenis proses tidak dikenal (pilihan: {valid})")
    if data.get("arah") not in ARAH_PROSES:
        valid = ", ".join(ARAH_PROSES)
        errors.append(f"Arah tidak dikenal (pilihan: {valid})")
    if not str(data.get("pihak_asal") or "").strip():
        errors.append("Pihak asal wajib diisi")
    if not str(data.get("pihak_tujuan") or "").strip():
        errors.append("Pihak tujuan wajib diisi")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset dipilih")
    mulai = str(data.get("tanggal_mulai") or "").strip()[:10]
    akhir = str(data.get("tanggal_berakhir") or "").strip()[:10]
    berjangka = data.get("jenis_proses") in (
        "penggunaan_sementara", "dioperasikan_pihak_lain",
        "penggunaan_bersama")
    if berjangka:
        try:
            d_mulai = date.fromisoformat(mulai)
            d_akhir = date.fromisoformat(akhir)
            if d_akhir <= d_mulai:
                errors.append("Tanggal berakhir harus setelah tanggal mulai")
        except ValueError:
            errors.append("Proses berjangka wajib tanggal mulai/berakhir "
                          "berformat YYYY-MM-DD")
    return errors


def validate_transisi_proses(tiket: dict, ke: str) -> list:
    """Validasi perpindahan status tiket proses (per jenisnya)."""
    jenis = tiket.get("jenis_proses")
    peta = TRANSISI_PROSES.get(jenis, {})
    if ke not in STATUS_PROSES:
        valid = ", ".join(STATUS_PROSES)
        return [f"Status tujuan tidak dikenal (pilihan: {valid})"]
    if ke not in peta.get(tiket.get("status"), set()):
        return [f"Transisi {tiket.get('status')} → {ke} tidak diizinkan "
                f"untuk {jenis}"]
    return []


def info_proses_sementara(tiket: dict, today_iso: str) -> dict:
    """Pengingat penggunaan sementara BERJALAN → {berakhir, lewat,
    sisa_hari, saatnya_perpanjangan (≤90 hari)}."""
    from datetime import date

    kosong = {"berakhir": None, "lewat": False, "sisa_hari": None,
              "saatnya_perpanjangan": False}
    berjangka = tiket.get("jenis_proses") in (
        "penggunaan_sementara", "dioperasikan_pihak_lain",
        "penggunaan_bersama")
    if not berjangka or tiket.get("status") != "berjalan":
        return kosong
    berakhir = str(tiket.get("tanggal_berakhir") or "").strip()[:10]
    try:
        batas = date.fromisoformat(berakhir)
        hari_ini = date.fromisoformat(str(today_iso)[:10])
    except ValueError:
        return kosong
    sisa = (batas - hari_ini).days
    return {"berakhir": berakhir, "lewat": sisa < 0,
            "sisa_hari": max(0, sisa),
            "saatnya_perpanjangan": 0 <= sisa <= 90}


def rekap_proses_penggunaan(items, today_iso: str) -> dict:
    """Ringkasan tiket: per jenis, per status, berjalan & segera berakhir."""
    per_jenis = {k: 0 for k in JENIS_PROSES_PENGGUNAAN}
    per_status = {k: 0 for k in STATUS_PROSES}
    segera_berakhir = 0
    for t in items or []:
        j = t.get("jenis_proses")
        if j in per_jenis:
            per_jenis[j] += 1
        s = t.get("status")
        if s in per_status:
            per_status[s] += 1
        if info_proses_sementara(t, today_iso)["saatnya_perpanjangan"]:
            segera_berakhir += 1
    aktif = sum(v for s, v in per_status.items()
                if s not in ("dihapus_dibukukan", "berakhir", "ditolak"))
    return {"jumlah": len(items or []), "aktif": aktif,
            "segera_berakhir": segera_berakhir,
            "per_jenis": per_jenis, "per_status": per_status}


HEADER_CSV_PROSES = [
    "kode_aset", "nup", "nama_aset", "jenis_proses", "arah", "pihak_asal",
    "pihak_tujuan", "status", "status_tenggat", "nomor_permohonan",
    "tanggal_permohonan", "tanggal_mulai", "tanggal_berakhir", "keterangan",
    "dibuat_oleh",
]


def baris_csv_proses(tiket_list, today_iso) -> list:
    """Susun baris CSV register proses penggunaan: [header, *data] — murni.

    Tiket multi-aset di-flatten: SATU baris per aset (field tiket diulang).
    Jenis/arah/status diterjemahkan ke label; kolom status_tenggat dihitung
    via info_proses_sementara untuk tiket berjangka yang BERJALAN (Lewat
    tenggat / "N hari lagi" [+ "(perpanjang)" bila ≤90 hari]); tanpa itu
    kosong. Tanpa Mongo/IO agar teruji unit (pola ekspor #158).
    """
    baris = [list(HEADER_CSV_PROSES)]
    for t in tiket_list or []:
        info = info_proses_sementara(t, today_iso)
        if info.get("berakhir"):
            if info.get("lewat"):
                tenggat = "Lewat tenggat"
            else:
                sisa = info.get("sisa_hari")
                tenggat = f"{sisa} hari lagi"
                if info.get("saatnya_perpanjangan"):
                    tenggat += " (perpanjang)"
        else:
            tenggat = ""
        jenis = JENIS_PROSES_PENGGUNAAN.get(t.get("jenis_proses"),
                                            t.get("jenis_proses") or "")
        arah = ARAH_PROSES.get(t.get("arah"), t.get("arah") or "")
        status = STATUS_PROSES.get(t.get("status"), t.get("status") or "")
        aset_list = t.get("aset") or [{}]
        for a in aset_list:
            baris.append([
                a.get("asset_code") or "",
                a.get("NUP") or "",
                a.get("asset_name") or "",
                jenis, arah,
                t.get("pihak_asal") or "",
                t.get("pihak_tujuan") or "",
                status, tenggat,
                t.get("nomor_permohonan") or "",
                str(t.get("tanggal_permohonan") or "")[:10],
                str(t.get("tanggal_mulai") or "")[:10],
                str(t.get("tanggal_berakhir") or "")[:10],
                t.get("keterangan") or "",
                t.get("created_by") or "",
            ])
    return baris
