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


def peta_psp_dari_sk(daftar_sk) -> dict:
    """asset_id → keterangan PSP resmi dari register SK. MURNI.

    HANYA SK berstatus **ditetapkan** yang dihitung: draf/diajukan/ditolak
    belum menetapkan status penggunaan apa pun, jadi aset di dalamnya belum
    boleh disebut ber-PSP (aturan yang sama dipakai `rekap_psp`).

    Bila satu aset tercakup beberapa SK ditetapkan (mis. PSP awal lalu alih
    status), yang menang adalah SK dengan `tanggal_sk` TERBARU — itulah
    status penggunaan yang berlaku sekarang.
    """
    peta = {}
    for sk in daftar_sk or []:
        if status_pengajuan_psp(sk) != "ditetapkan":
            continue
        nomor = str(sk.get("nomor_sk") or "").strip()
        if not nomor:
            continue
        info = {
            "no_psp": nomor,
            "tanggal": str(sk.get("tanggal_sk") or "").strip()[:10],
            "jenis": str(sk.get("jenis") or ""),
            "sumber": "register",
        }
        for a in sk.get("aset") or []:
            aid = str(a.get("asset_id") or "")
            if not aid:
                continue
            lama = peta.get(aid)
            if not lama or info["tanggal"] >= lama["tanggal"]:
                peta[aid] = info
    return peta


def info_psp_aset(aset: dict, dari_register: dict = None) -> dict:
    """Satu keterangan PSP untuk SATU aset — {} bila belum ber-PSP. MURNI.

    Dua sumber, dan urutannya disengaja:

    1. **Register SK PSP** (`db.psp`, hasil pencatatan di halaman Aset per
       Pemegang) menang. Itu keputusan yang dibuat DI DALAM aplikasi ini,
       lengkap dengan jejak pengajuan dan lampiran SK-nya.
    2. **Referensi SIMAN V2** (`assets.siman.referensi.no_psp`) jadi cadangan.
       Ia otoritatif dari sisi Pengelola Barang, tetapi hanya potret impor
       terakhir — bila keduanya ada, yang tercatat resmi yang ditampilkan.

    `sumber` ikut dikembalikan supaya layar bisa jujur menyebut asal angkanya
    alih-alih menyamarkan keduanya sebagai satu fakta.
    """
    from siman_utils import norm_no_psp

    aid = str((aset or {}).get("id") or "")
    reg = (dari_register or {}).get(aid)
    if reg and reg.get("no_psp"):
        return dict(reg)
    ref = (((aset or {}).get("siman") or {}).get("referensi") or {})
    no = norm_no_psp(ref.get("no_psp"))
    if not no:
        return {}
    return {
        "no_psp": no,
        "tanggal": str(ref.get("tanggal_psp") or "").strip()[:10],
        "jenis": str(ref.get("status_penggunaan") or ""),
        "sumber": "siman",
    }


HEADER_CSV_PSP = [
    "kode_aset", "nup", "nama_aset", "nomor_sk", "tanggal_sk", "jenis",
    "penetap", "status", "jumlah_lampiran", "keterangan", "dibuat_oleh",
]


def baris_csv_psp(sk_list) -> list:
    """Susun baris CSV register SK PSP: [header, *data] — fungsi murni.

    SK multi-aset di-flatten: SATU baris per aset (field SK diulang). Jenis
    & status pengajuan diterjemahkan ke label (record lama tanpa status =
    ditetapkan); tanggal SK dipangkas 10 char; jumlah lampiran dihitung;
    field hilang → string kosong. Tanpa Mongo/IO agar teruji unit (pola
    ekspor #158).
    """
    baris = [list(HEADER_CSV_PSP)]
    for sk in sk_list or []:
        jenis = JENIS_PSP.get(sk.get("jenis"), sk.get("jenis") or "")
        status = STATUS_PENGAJUAN_PSP.get(status_pengajuan_psp(sk), "")
        n_lampiran = len(sk.get("lampiran") or [])
        for a in sk.get("aset") or [{}]:
            baris.append([
                a.get("asset_code") or "",
                a.get("NUP") or "",
                a.get("asset_name") or "",
                sk.get("nomor_sk") or "",
                str(sk.get("tanggal_sk") or "")[:10],
                jenis,
                sk.get("penetap") or "",
                status,
                n_lampiran,
                sk.get("keterangan") or "",
                sk.get("created_by") or "",
            ])
    return baris


# Status tiket penanganan BMN idle → label Indonesia
STATUS_IDLE = {
    "klarifikasi": "Klarifikasi (diteliti penggunaannya)",
    "digunakan_kembali": "Digunakan Kembali (bukan idle)",
    "usul_serah": "Diusulkan Serah ke Pengelola",
    "diserahkan": "Diserahkan ke Pengelola Barang",
}

TRANSISI_IDLE = {
    "klarifikasi": {"digunakan_kembali", "usul_serah"},
    # usul_serah boleh mundur ke digunakan_kembali: Pengelola menolak /
    # satker batal menyerahkan → BMN dipakai lagi (jurnal 402 Penggunaan
    # kembali; usul_serah sendiri berjurnal 401 Penghentian dari Penggunaan).
    "usul_serah": {"diserahkan", "digunakan_kembali"},
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


def bast_perlu_perbarui(asset: dict) -> bool:
    """True bila aset ber-BAST namun **kode/nama SEKARANG berbeda** dari yang
    di-snapshot saat BAST dilampirkan (mis. setelah reklasifikasi kodefikasi
    atau penyesuaian nama barang) — artinya BAST terakhir merujuk data lama.

    Aset TANPA snapshot (BAST era lama sebelum fitur ini) TIDAK ditandai —
    konservatif, tanpa positif palsu. MURNI (teruji unit)."""
    a = asset or {}
    if not str(a.get("bast_file_id") or "").strip():
        return False
    snap = a.get("bast_snapshot")
    if not isinstance(snap, dict) or not snap:
        return False
    kode_sama = (str(a.get("asset_code") or "").strip()
                 == str(snap.get("kode") or "").strip())
    nama_sama = (" ".join(str(a.get("asset_name") or "").split())
                 == " ".join(str(snap.get("nama") or "").split()))
    return not (kode_sama and nama_sama)


def snapshot_bast(asset: dict) -> dict:
    """Snapshot kode & nama aset saat BAST dilampirkan (untuk deteksi BAST
    usang bila kode/nama berubah kemudian). MURNI."""
    a = asset or {}
    return {"kode": str(a.get("asset_code") or "").strip(),
            "nama": str(a.get("asset_name") or "").strip()}


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
    # ALIH STATUS ARAH MASUK (ASET-TRANSFER-MASUK): barang datang dari
    # Pengguna Barang lain — belum ada di db.assets, jadi tiket memakai
    # daftar barang manual, bukan asset_ids. Kasus lain tetap asset_ids.
    if (data.get("jenis_proses") == "alih_status"
            and data.get("arah") == "masuk"):
        barang = data.get("barang_masuk") or []
        if not barang:
            errors.append("Minimal satu barang masuk (kode + nama) — barang "
                          "belum tercatat di pembukuan penerima")
        for i, b in enumerate(barang, start=1):
            if not str(b.get("asset_code") or "").strip():
                errors.append(f"Barang #{i}: kode barang wajib diisi")
            if not str(b.get("asset_name") or "").strip():
                errors.append(f"Barang #{i}: nama barang wajib diisi")
            import math
            try:
                nb = float(b.get("nilai") or 0)
            except (TypeError, ValueError):
                nb = None
            if nb is None:
                errors.append(f"Barang #{i}: nilai harus angka")
            elif not math.isfinite(nb):
                # inf lolos cek `< 0` lalu meledakkan int(nilai) saat
                # barang dibukukan; NaN meracuni pembukuan.
                errors.append(f"Barang #{i}: nilai harus angka terhingga")
            elif nb < 0:
                errors.append(f"Barang #{i}: nilai tidak boleh negatif")
    elif not data.get("asset_ids"):
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


def build_asset_alih_keluar_projection(tiket, now_iso):
    """Proyeksi master aset saat tiket ALIH STATUS arah KELUAR mencapai status
    terminal `dihapus_dibukukan` (Prinsip 3: transaksi = jurnal, master =
    proyeksi — pola build_asset_penghapusan_projection #234).

    Aset telah beralih ke Pengguna Barang lain & dibukukan di sana → keluar
    dari pembukuan satker: `dihapus=True` + subdoc `penghapusan` (bentuk sama
    dgn penghapusan SK agar tombstone LBKP/CaLBMN menghitung mutasi KURANG
    pada periode SK; `jalur` membedakan asal). Kembalikan None bila bukan
    kasusnya (arah masuk / status lain / jenis bukan alih_status). MURNI.
    """
    t = tiket or {}
    if (t.get("jenis_proses") != "alih_status" or t.get("arah") != "keluar"
            or t.get("status") != "dihapus_dibukukan"):
        return None
    return {
        "dihapus": True,
        "penghapusan": {
            "status": "sk_terbit",
            "usulan_id": "",
            "jalur": "alih_status_keluar",
            "tiket_id": str(t.get("id") or ""),
            "nomor_sk": str(t.get("nomor_sk_penghapusan") or "").strip(),
            "tanggal_sk": str(t.get("tanggal_sk_penghapusan") or "").strip()[:10],
            "diproyeksikan_pada": now_iso,
        },
    }


# ---------------------------------------------------------------------------
# Henti guna MANDIRI (ASET-HENTI-MANDIRI). Jurnal 401/402 selama ini hanya
# terbit lewat jalur BMN idle (usul_serah / digunakan_kembali) — penghentian
# penggunaan aktif ber-SK/BA di LUAR jalur idle (mis. menunggu proses lain,
# dihentikan sementara) tidak punya register dan tidak berjurnal.
# ---------------------------------------------------------------------------
STATUS_HENTI_GUNA = {
    "dihentikan": "Dihentikan dari Penggunaan (401)",
    "digunakan_kembali": "Digunakan Kembali (402)",
}


def validate_henti_guna_baru(data: dict) -> list:
    """Pencatatan penghentian: SK/BA + alasan wajib — penghentian tanpa
    dasar dokumen adalah temuan."""
    errors = []
    if not str(data.get("nomor_dokumen") or "").strip():
        errors.append("Nomor SK/BA penghentian penggunaan wajib diisi")
    if len(str(data.get("alasan") or "").strip()) < 5:
        errors.append("Alasan penghentian wajib diisi (minimal 5 karakter)")
    return errors


def validate_gunakan_kembali(data: dict) -> list:
    """Penggunaan kembali juga berdokumen (SK/BA)."""
    if not str(data.get("nomor_dokumen") or "").strip():
        return ["Nomor SK/BA penggunaan kembali wajib diisi"]
    return []


def build_asset_transfer_masuk(tiket, barang, now_iso, new_id):
    """Dokumen aset BARU yang DIBUKUKAN saat tiket ALIH STATUS arah MASUK
    mencapai status terminal `dihapus_dibukukan` (ASET-TRANSFER-MASUK).

    Kebalikan build_asset_alih_keluar_projection: sisi keluar menandai aset
    keluar buku + jurnal 302; sisi masuk selama ini TIDAK berefek apa pun —
    barang kiriman Pengguna Barang lain tak pernah masuk pembukuan. Field
    inti diisi agar aset langsung sah di daftar/laporan; rincian lain
    dilengkapi lewat form aset setelah dibukukan. MURNI (id dari pemanggil).
    """
    import math
    t = tiket or {}
    b = barang or {}
    try:
        nilai = float(b.get("nilai") or 0)
    except (TypeError, ValueError):
        nilai = 0
    if not math.isfinite(nilai):
        # Jaring terakhir untuk tiket lama yang tercatat sebelum validasi:
        # int(inf/NaN) meledak dan membatalkan pembukuan di tengah loop.
        nilai = 0
    return {
        "id": new_id,
        "asset_code": str(b.get("asset_code") or "").strip(),
        "NUP": str(b.get("NUP") or b.get("nup") or "").strip(),
        "asset_name": str(b.get("asset_name") or "").strip(),
        "category": (str(b.get("kategori") or "").strip()
                     or "Peralatan dan Mesin"),
        "purchase_price": str(int(nilai)),
        "condition": "Baik",
        "status": "Aktif",
        "inventory_status": "Belum Diinventarisasi",
        "location": "", "user": "",
        "activity_id": "",
        "kode_satker": str(t.get("kode_satker") or "").strip(),
        "dihapus": False,
        # Jejak perolehan (masterplan Bab 5: dokumen sumber = simpul).
        "perolehan_transfer": {
            "tiket_id": str(t.get("id") or ""),
            "pihak_asal": str(t.get("pihak_asal") or "").strip(),
            "nomor_bast": str(t.get("nomor_bast") or "").strip(),
            "nomor_sk": str(t.get("nomor_sk_penghapusan") or "").strip(),
            "dicatat_pada": now_iso,
        },
        "version": 1,
        "created_by": str(t.get("created_by") or ""),
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def build_asset_idle_serah_projection(tiket, now_iso):
    """Proyeksi master aset saat tiket BMN IDLE mencapai status terminal
    `diserahkan` (ke Pengelola Barang). Aset keluar dari pembukuan satker:
    `dihapus=True` + subdoc `penghapusan` (nomor dokumen = BAST serah;
    tanggal = tanggal transisi agar LBKP menghitung mutasi KURANG pada
    periode serah). Kembalikan None bila status bukan `diserahkan`. MURNI.
    """
    t = tiket or {}
    if t.get("status") != "diserahkan":
        return None
    return {
        "dihapus": True,
        "penghapusan": {
            "status": "sk_terbit",
            "usulan_id": "",
            "jalur": "idle_diserahkan",
            "tiket_id": str(t.get("id") or ""),
            "nomor_sk": str(t.get("nomor_bast_serah") or "").strip(),
            "tanggal_sk": str(now_iso or "")[:10],
            "diproyeksikan_pada": now_iso,
        },
    }


def kelompokkan_psp_siman(aset_rows, nomor_sk_tercatat=None,
                          asset_id_tercakup=None) -> list:
    """Kelompokkan aset ber-PSP resmi menurut SIMAN V2 per nomor PSP (W5).

    Data `assets.siman.referensi.no_psp/tanggal_psp/status_penggunaan` hasil
    impor SIMAN selama ini tersimpan tanpa dibaca modul manapun — padahal
    itu bukti PSP otoritatif. Fungsi ini menyiapkan kandidat pencatatan
    1-klik ke register SK PSP:

    - aset_rows: dokumen aset (proyeksi ringan) yang punya no_psp.
    - nomor_sk_tercatat: set nomor SK yang SUDAH ada di register psp
      (dinormalkan: strip + upper) → kelompok ditandai `sudah_tercatat`.
    - asset_id_tercakup: set asset_id yang sudah tercakup SK psp manapun →
      per kelompok dihitung `aset_belum` (yang layak diprefill).

    Kembalian: list kelompok terurut tanggal_psp terbaru dulu, tiap item
    {no_psp, tanggal_psp, status_penggunaan, aset[], aset_belum[], jumlah,
    sudah_tercatat}. MURNI.
    """
    # Placeholder "belum PSP" (mis. "-", "Tidak Ada Inputan") disaring di
    # sini juga — referensi lama di DB bisa berasal dari impor sebelum
    # penyaringan di parse ada. Tanpa ini, barang belum ter-PSP menggerombol
    # jadi satu "kelompok PSP" palsu bernomor "-".
    from siman_utils import norm_no_psp

    tercatat = {str(n or "").strip().upper()
                for n in (nomor_sk_tercatat or set()) if str(n or "").strip()}
    tercakup = set(asset_id_tercakup or set())
    kelompok = {}
    for a in aset_rows or []:
        ref = ((a.get("siman") or {}).get("referensi") or {})
        no = norm_no_psp(ref.get("no_psp"))
        if not no:
            continue
        k = kelompok.setdefault(no, {
            "no_psp": no,
            "tanggal_psp": str(ref.get("tanggal_psp") or "").strip(),
            "status_penggunaan": str(ref.get("status_penggunaan") or "").strip(),
            "aset": [], "aset_belum": [],
        })
        # Tanggal/status terisi dari aset mana pun yang punya nilainya
        if not k["tanggal_psp"] and str(ref.get("tanggal_psp") or "").strip():
            k["tanggal_psp"] = str(ref.get("tanggal_psp") or "").strip()
        if (not k["status_penggunaan"]
                and str(ref.get("status_penggunaan") or "").strip()):
            k["status_penggunaan"] = str(ref.get("status_penggunaan") or "").strip()
        baris = {"asset_id": str(a.get("id") or ""),
                 "asset_code": str(a.get("asset_code") or ""),
                 "NUP": str(a.get("NUP") or ""),
                 "asset_name": str(a.get("asset_name") or "")}
        k["aset"].append(baris)
        if baris["asset_id"] and baris["asset_id"] not in tercakup:
            k["aset_belum"].append(baris)
    hasil = []
    for k in kelompok.values():
        k["jumlah"] = len(k["aset"])
        k["sudah_tercatat"] = k["no_psp"].strip().upper() in tercatat
        hasil.append(k)
    hasil.sort(key=lambda x: (x["tanggal_psp"], x["no_psp"]), reverse=True)
    return hasil


# ── Golongan tanggung jawab pada "Daftar Barang yang Digunakan" ─────────────
#
# Permintaan pemilik: *"pada output PDF DAFTAR BARANG YANG DIGUNAKAN tolong
# bedakan dan bagi terhadap barang BMN BAST yang sudah disahkan dan diunggah
# buktinya ... dan dibagi per jenis BAST-nya. Jika melekat ke individu dan
# jabatan berarti memang menjadi tanggung jawabnya; untuk yang operasional
# maka perpanjangan tangan atau jadi pendelegasian dan izin sesuai nama-nama
# yang menjadi penanggung jawabnya dan ikut bertanggung jawab dalam penjagaan
# barang tersebut. Dan jika dari awal digunakan untuk operasional dan langsung
# menggunakan nama penandatangan maka hampir sama dengan tusinya."*
#
# Satu daftar datar menyamakan tiga hal yang bobot hukumnya berbeda: barang
# yang melekat pada orangnya, barang unit yang ia jaga sebagai perpanjangan
# tangan, dan barang yang belum berdasar apa pun. Dokumen ini ditandatangani
# pemegang DAN KPB; menyamakan ketiganya membuat orang meneken tanggung jawab
# yang bukan miliknya.
#
# APA YANG DIANGGAP "SAH". Bukan tebakan: pada `routes/bast.py`, mengunggah
# bukti tanda tangan ITULAH pengesahannya — ia menyetel `bast_file_id` pada
# tiap aset objek BAST dan menaikkan nomor agenda dari "dibooking" ke
# "disahkan". Karena itu `bast_file_id` terisi = sudah disahkan DAN buktinya
# terunggah, dua syarat yang diminta pemilik sekaligus. Tanda tangan yang
# kemudian DICABUT (`bast_terakhir.tt_dicabut`) membatalkannya kembali.

GOLONGAN_TJ = (
    ("melekat", "Melekat pada Pemegang (Individu/Jabatan)",
     "Penguasaan beralih kepada pemegang secara pribadi. Pemeliharaan, "
     "keamanan, dan pengembalian dalam keadaan baik menjadi tanggung "
     "jawabnya sendiri."),
    ("tusi", "Operasional atas Nama Sendiri (setara tugas dan fungsi)",
     "BAST operasional yang sejak semula diteken atas nama pemegang ini "
     "sendiri, sehingga bobot tanggung jawabnya mendekati barang yang "
     "melekat — melekat pada tugas dan fungsinya, bukan pada orangnya."),
    ("delegasi", "Operasional — Pendelegasian/Perpanjangan Tangan",
     "Barang unit/tempat/tugas yang penanggung jawabnya diteken pihak lain. "
     "Pemegang di sini bertindak sebagai perpanjangan tangan atas izin "
     "tersebut dan IKUT bertanggung jawab menjaga barangnya, tanpa "
     "penguasaan pribadi."),
    ("sementara", "Penggunaan Sementara (berjangka waktu)",
     "Pinjam pakai internal yang berakhir pada waktu yang diperjanjikan."),
    ("lain", "Ber-BAST Sah — Jenis Lain",
     "Ber-BAST sah namun jenisnya di luar keempat golongan di atas."),
    ("tanpa_bast", "Belum Ber-BAST Sah",
     "Belum ada BAST yang disahkan dan buktinya terunggah, atau tanda "
     "tangannya dicabut. Barang tetap didaftarkan karena benar berada pada "
     "pemegang, tetapi BELUM dapat dibebankan sebagai tanggung jawabnya."),
)

_TJ_MELEKAT = frozenset({"penggunaan_melekat", "mutasi_pengguna"})


def bast_sah(asset: dict) -> bool:
    """BAST aset ini sudah disahkan DAN buktinya terunggah. MURNI.

    Satu syarat, bukan dua: mengunggah bukti tanda tangan itulah yang
    mengesahkan (lihat `unggah_bukti_bast` di routes/bast.py). Tanda tangan
    yang dicabut kemudian membatalkannya.
    """
    a = asset or {}
    if not str(a.get("bast_file_id") or "").strip():
        return False
    terakhir = a.get("bast_terakhir")
    if isinstance(terakhir, dict) and terakhir.get("tt_dicabut"):
        return False
    return True


def golongan_tj(asset: dict, nama_pemegang: str = "") -> str:
    """Kunci golongan tanggung jawab satu aset. MURNI.

    `nama_pemegang` dipakai HANYA untuk membedakan operasional atas nama
    sendiri dari pendelegasian: bila penerima BAST-nya orang yang sama,
    ia meneken untuk dirinya sendiri.
    """
    if not bast_sah(asset):
        return "tanpa_bast"
    terakhir = (asset or {}).get("bast_terakhir")
    jenis = str((terakhir or {}).get("jenis") or "").strip()
    if jenis in _TJ_MELEKAT:
        return "melekat"
    if jenis == "penggunaan_sementara":
        return "sementara"
    if jenis == "operasional_unit":
        penerima = " ".join(str((terakhir or {}).get("penerima") or "").split()).lower()
        pemegang = " ".join(str(nama_pemegang or "").split()).lower()
        return "tusi" if penerima and pemegang and penerima == pemegang else "delegasi"
    return "lain"


def kelompokkan_tanggung_jawab(assets, nama_pemegang: str = ""):
    """Bagi aset pemegang menjadi golongan tanggung jawab. MURNI.

    → list `(kunci, judul, keterangan, [aset])` menurut urutan `GOLONGAN_TJ`,
    HANYA golongan yang berisi. Urutan aset di dalam tiap golongan
    dipertahankan apa adanya — pemanggil yang mengurutkannya (per bidang
    kode barang, selaras BAST induk).
    """
    ember = {k: [] for k, _j, _t in GOLONGAN_TJ}
    for a in assets or []:
        ember[golongan_tj(a, nama_pemegang)].append(a)
    return [(k, judul, ket, ember[k])
            for k, judul, ket in GOLONGAN_TJ if ember[k]]
