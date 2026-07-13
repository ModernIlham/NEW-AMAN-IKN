"""Logika murni PENGAMANAN (Fase 3 — tahap awal: tertib administrasi data).

Dasbor "kesehatan data" per aset — pola penangkal kendala nyata satker
(pustaka §4: DBR tak mutakhir, barang tanpa label/foto/dokumen jadi
temuan BPK) — plus daftar pantau SENGKETA dari data yang sudah dicatat
modul inventarisasi (nomor perkara, pihak bersengketa).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

# Kunci kekurangan → label Indonesia (dipakai UI & endpoint)
JENIS_KEKURANGAN = {
    "foto": "Tanpa foto",
    "register": "Tanpa kode register",
    "lokasi": "Tanpa lokasi",
    "pengguna": "Tanpa pengguna",
    "bast": "Tanpa BAST",
}


def _terisi(v) -> bool:
    return bool(str(v or "").strip())


def ada_foto(asset: dict) -> bool:
    """Aset punya foto: GridFS-first, fallback foto inline legacy."""
    return bool(asset.get("photo_gridfs_ids") or asset.get("photos"))


def kekurangan_aset(asset: dict):
    """Daftar kunci kekurangan sebuah aset (subset JENIS_KEKURANGAN)."""
    out = []
    if not ada_foto(asset):
        out.append("foto")
    if not _terisi(asset.get("kode_register")):
        out.append("register")
    if not _terisi(asset.get("location")):
        out.append("lokasi")
    if not _terisi(asset.get("user")):
        out.append("pengguna")
    if not _terisi(asset.get("bast_file_id")):
        out.append("bast")
    return out


def is_sengketa(asset: dict) -> bool:
    """Aset dalam sengketa: status Sengketa ATAU ada nomor perkara/pihak."""
    return (asset.get("inventory_status") == "Sengketa"
            or _terisi(asset.get("nomor_perkara"))
            or _terisi(asset.get("pihak_bersengketa")))


def rekap_kesehatan(assets):
    """Ringkasan → (jumlah_per_kekurangan, jumlah_lengkap, daftar_sengketa).

    jumlah_per_kekurangan: {kunci: n}; lengkap = aset tanpa kekurangan
    apa pun; daftar_sengketa: dict ringkas per aset sengketa.
    """
    per = {k: 0 for k in JENIS_KEKURANGAN}
    lengkap = 0
    sengketa = []
    for a in assets or []:
        kurang = kekurangan_aset(a)
        for k in kurang:
            per[k] += 1
        if not kurang:
            lengkap += 1
        if is_sengketa(a):
            sengketa.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "nomor_perkara": str(a.get("nomor_perkara") or "").strip(),
                "pihak_bersengketa": str(a.get("pihak_bersengketa") or "").strip(),
                "keterangan": str(a.get("keterangan_sengketa") or "").strip(),
                "activity_id": a.get("activity_id"),
            })
    sengketa.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return per, lengkap, sengketa


# ---------------------------------------------------------------------------
# Register BMN bermasalah/sengketa (pustaka §11.3-11.4) — kategori kasus dan
# pipeline penanganan dari praktik DJKN; register ini bahan mentah laporan
# wasdal/CaLBMN, bukan kanal resmi dan tak berkekuatan hukum.
# ---------------------------------------------------------------------------

KATEGORI_KASUS = {
    "dikuasai_pihak_lain": "Dikuasai pihak lain",
    "sertipikat_pihak_lain": "Disertipikatkan/tumpang tindih pihak lain",
    "berperkara": "Sengketa/berperkara di pengadilan",
}

STATUS_KASUS = {
    "identifikasi": "Identifikasi",
    "mediasi": "Mediasi / non-litigasi",
    "blokir": "Pemblokiran sertipikat",
    "litigasi": "Litigasi",
    "selesai": "Selesai",
}

# Transisi maju boleh melompati tahap (mis. langsung litigasi); selesai
# terminal — kasus baru dibuka sebagai register baru bila muncul lagi.
TRANSISI_KASUS = {
    "identifikasi": {"mediasi", "blokir", "litigasi", "selesai"},
    "mediasi": {"blokir", "litigasi", "selesai"},
    "blokir": {"litigasi", "selesai"},
    "litigasi": {"selesai"},
    "selesai": set(),
}


def validate_kasus(data: dict) -> list:
    """Validasi pembukaan kasus baru → daftar pesan kesalahan."""
    errors = []
    if data.get("kategori") not in KATEGORI_KASUS:
        valid = ", ".join(KATEGORI_KASUS)
        errors.append(f"Kategori kasus tidak dikenal (pilihan: {valid})")
    if not str(data.get("uraian") or "").strip():
        errors.append("Uraian kasus wajib diisi")
    if not str(data.get("pihak_lawan") or "").strip():
        errors.append("Pihak lawan/penguasa wajib diisi")
    return errors


def validate_transisi_kasus(kasus: dict, ke: str) -> list:
    """Validasi perpindahan status kasus."""
    dari = kasus.get("status")
    if ke not in STATUS_KASUS:
        valid = ", ".join(STATUS_KASUS)
        return [f"Status tujuan tidak dikenal (pilihan: {valid})"]
    if ke not in TRANSISI_KASUS.get(dari, set()):
        return [f"Transisi {dari} → {ke} tidak diizinkan"]
    return []


def rekap_kasus(items) -> dict:
    """Ringkasan register kasus per status + per kategori + aktif."""
    per_status = {k: 0 for k in STATUS_KASUS}
    per_kategori = {k: 0 for k in KATEGORI_KASUS}
    for k in items or []:
        s = k.get("status")
        if s in per_status:
            per_status[s] += 1
        kat = k.get("kategori")
        if kat in per_kategori:
            per_kategori[kat] += 1
    aktif = sum(v for s, v in per_status.items() if s != "selesai")
    return {"jumlah": len(items or []), "aktif": aktif,
            "per_status": per_status, "per_kategori": per_kategori}


HEADER_CSV_KASUS = [
    "kode_aset", "nup", "nama_aset", "lokasi", "kategori", "status",
    "uraian", "pihak_lawan", "nomor_perkara", "pendamping",
    "tanggal_dibuat", "tanggal_perbarui", "dibuat_oleh",
]


def baris_csv_kasus(kasus_list) -> list:
    """Susun baris CSV register kasus BMN bermasalah: [header, *data] — murni.

    Kategori & status diterjemahkan ke label; tanggal dipangkas ke bagian
    tanggal (YYYY-MM-DD). Tanpa Mongo/IO agar teruji unit (pola ekspor
    #158).
    """
    baris = [list(HEADER_CSV_KASUS)]
    for k in kasus_list or []:
        baris.append([
            k.get("asset_code") or "",
            k.get("NUP") or "",
            k.get("asset_name") or "",
            k.get("lokasi") or "",
            KATEGORI_KASUS.get(k.get("kategori"), k.get("kategori") or ""),
            STATUS_KASUS.get(k.get("status"), k.get("status") or ""),
            k.get("uraian") or "",
            k.get("pihak_lawan") or "",
            k.get("nomor_perkara") or "",
            k.get("pendamping") or "",
            str(k.get("created_at") or "")[:10],
            str(k.get("updated_at") or "")[:10],
            k.get("created_by") or "",
        ])
    return baris


# ---------------------------------------------------------------------------
# Arsip dokumen kepemilikan per aset (pustaka §11.3) — PP 27/2014 Ps. 43:
# dokumen tanah/bangunan disimpan Pengelola Barang (KPKNL), selain itu oleh
# Pengguna Barang. Lokasi penyimpanan = pilihan informatif, bukan validasi
# keras (praktik penyimpanan tiap satker berbeda).
# ---------------------------------------------------------------------------

JENIS_DOKUMEN = {
    "sertipikat": "Sertipikat tanah (SHP a.n. Pemerintah RI c.q. K/L)",
    "bpkb": "BPKB kendaraan",
    "stnk": "STNK kendaraan",
    "imb_pbg": "IMB / PBG bangunan",
    "perolehan": "Dokumen perolehan (BAST/AJB/hibah)",
    "lainnya": "Dokumen lainnya",
}

LOKASI_SIMPAN = {
    "pengelola_barang": "Pengelola Barang (KPKNL/Kanwil DJKN)",
    "pengguna_barang": "Pengguna Barang (satker)",
}


def validate_dokumen(data: dict) -> list:
    """Validasi pencatatan dokumen kepemilikan → daftar pesan kesalahan."""
    from datetime import date

    errors = []
    if data.get("jenis") not in JENIS_DOKUMEN:
        valid = ", ".join(JENIS_DOKUMEN)
        errors.append(f"Jenis dokumen tidak dikenal (pilihan: {valid})")
    if not str(data.get("nomor") or "").strip():
        errors.append("Nomor dokumen wajib diisi")
    if data.get("lokasi_simpan") not in LOKASI_SIMPAN:
        valid = ", ".join(LOKASI_SIMPAN)
        errors.append(f"Lokasi penyimpanan tidak dikenal (pilihan: {valid})")
    berlaku = str(data.get("berlaku_sampai") or "").strip()
    if berlaku:
        try:
            date.fromisoformat(berlaku[:10])
        except ValueError:
            errors.append("Tanggal berlaku harus berformat YYYY-MM-DD")
    return errors


def rekap_dokumen(items, today_iso: str) -> dict:
    """Ringkasan arsip: total, per jenis, ber-lampiran, kedaluwarsa."""
    from datetime import date

    per_jenis = {k: 0 for k in JENIS_DOKUMEN}
    ber_lampiran = kedaluwarsa = 0
    try:
        hari_ini = date.fromisoformat(str(today_iso)[:10])
    except ValueError:
        hari_ini = None
    for d in items or []:
        j = d.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
        if d.get("lampiran"):
            ber_lampiran += 1
        berlaku = str(d.get("berlaku_sampai") or "").strip()[:10]
        if berlaku and hari_ini is not None:
            try:
                if date.fromisoformat(berlaku) < hari_ini:
                    kedaluwarsa += 1
            except ValueError:
                pass
    return {"jumlah": len(items or []), "per_jenis": per_jenis,
            "ber_lampiran": ber_lampiran, "kedaluwarsa": kedaluwarsa}


# Kategori target sertipikasi tanah BMN (pustaka §11.3, [perlu verifikasi]
# §14 butir 19 — definisi dari artikel DJKN, bukan teks regulasi):
# K1 lengkap siap SHP · K2 data kurang · K3 sengketa · K4 sudah sertipikat
# perlu pemutakhiran SIMAN. Berlaku untuk dokumen jenis "sertipikat" saja.
KATEGORI_SERTIPIKASI = {
    "belum": "Belum diproses",
    "proses": "Dalam proses BPN",
    "k1": "K1 — lengkap, siap SHP",
    "k2": "K2 — data belum lengkap",
    "k3": "K3 — sengketa/berperkara",
    "k4": "K4 — sudah sertipikat, perlu pemutakhiran SIMAN",
    "shp_terbit": "SHP terbit a.n. Pemerintah RI",
}


def validate_kategori_sertipikasi(data: dict) -> list:
    """Kategori sertipikasi hanya sah untuk dokumen jenis sertipikat."""
    kategori = str(data.get("kategori_sertipikasi") or "").strip()
    if not kategori:
        return []
    if data.get("jenis") != "sertipikat":
        return ["Kategori sertipikasi hanya untuk dokumen jenis sertipikat"]
    if kategori not in KATEGORI_SERTIPIKASI:
        valid = ", ".join(KATEGORI_SERTIPIKASI)
        return [f"Kategori sertipikasi tidak dikenal (pilihan: {valid})"]
    return []


def rekap_sertipikasi(items) -> dict:
    """Hitung dokumen sertipikat per kategori sertipikasi (+tanpa kategori)."""
    per = {k: 0 for k in KATEGORI_SERTIPIKASI}
    tanpa = 0
    for d in items or []:
        if d.get("jenis") != "sertipikat":
            continue
        kategori = str(d.get("kategori_sertipikasi") or "").strip()
        if kategori in per:
            per[kategori] += 1
        else:
            tanpa += 1
    return {"per_kategori": per, "tanpa_kategori": tanpa,
            "jumlah_sertipikat": tanpa + sum(per.values())}


# ---------------------------------------------------------------------------
# Checklist pengamanan per aset per jenis objek (pustaka §11.2 —
# [perlu verifikasi] §14 butir 18: butir dari artikel DJKN & KMK 21/2012,
# bukan teks regulasi; checklist AMAN alat bantu internal, bukan bukti
# hukum pelaksanaan pengamanan).
# ---------------------------------------------------------------------------

JENIS_OBJEK_CHECKLIST = {
    "tanah": "Tanah",
    "gedung_bangunan": "Gedung / Bangunan",
    "kendaraan": "Kendaraan bermotor",
    "lainnya": "BMN selain tanah/bangunan",
}

# (kunci, label, aspek fisik/administrasi/hukum)
BUTIR_CHECKLIST = {
    "tanah": [
        ("patok_batas", "Patok/tanda batas terpasang", "fisik"),
        ("pagar", "Pagar pengaman", "fisik"),
        ("plang_nama", "Plang/papan nama kepemilikan", "fisik"),
        ("arsip_perolehan", "Arsip dokumen perolehan lengkap", "administrasi"),
        ("sertipikat", "Sertipikat a.n. Pemerintah RI c.q. K/L", "hukum"),
    ],
    "gedung_bangunan": [
        ("pagar_papan", "Pagar & papan nama", "fisik"),
        ("penjagaan", "Penjagaan/satpam atau CCTV", "fisik"),
        ("apar", "APAR tersedia dan berfungsi", "fisik"),
        ("arsip_bangunan", "Arsip IMB/PBG + BAST/dokumen pembangunan", "administrasi"),
        ("bukti_kepemilikan", "Bukti kepemilikan a.n. Pemerintah RI", "hukum"),
    ],
    "kendaraan": [
        ("kunci_alarm", "Kunci pengaman/alarm berfungsi", "fisik"),
        ("simpan_kantor", "Disimpan di lingkungan kantor (pool)", "fisik"),
        ("arsip_bpkb_stnk", "Arsip BPKB + salinan STNK", "administrasi"),
        ("atas_nama_pemerintah", "BPKB/STNK atas nama pemerintah", "hukum"),
        ("pajak_hidup", "Pajak kendaraan dibayar tepat waktu", "hukum"),
    ],
    "lainnya": [
        ("simpan_terkunci", "Disimpan di ruangan/gudang terkunci", "fisik"),
        ("apar_gudang", "APAR tersedia di area penyimpanan", "fisik"),
        ("tercatat_dbr", "Tercatat di DBR/DBL ruangan", "administrasi"),
        ("dokumen_perolehan", "Dokumen perolehan (BAST) tersimpan", "administrasi"),
    ],
}


def validate_checklist(data: dict) -> list:
    """Validasi isian checklist pengamanan → daftar pesan kesalahan."""
    errors = []
    jenis = data.get("jenis_objek")
    if jenis not in JENIS_OBJEK_CHECKLIST:
        valid = ", ".join(JENIS_OBJEK_CHECKLIST)
        errors.append(f"Jenis objek tidak dikenal (pilihan: {valid})")
        return errors
    butir = data.get("butir")
    if not isinstance(butir, dict) or not butir:
        errors.append("Isian butir checklist wajib diisi")
        return errors
    sah = {k for k, _, _ in BUTIR_CHECKLIST[jenis]}
    asing = set(butir) - sah
    if asing:
        errors.append(f"Butir tidak dikenal untuk jenis {jenis}: "
                      + ", ".join(sorted(asing)))
    return errors


def skor_checklist(item: dict) -> dict:
    """Skor satu checklist → {terpenuhi, total, persen}."""
    jenis = item.get("jenis_objek")
    daftar = BUTIR_CHECKLIST.get(jenis, [])
    butir = item.get("butir") or {}
    terpenuhi = sum(1 for k, _, _ in daftar if butir.get(k))
    total = len(daftar)
    persen = round(terpenuhi / total * 100) if total else 0
    return {"terpenuhi": terpenuhi, "total": total, "persen": persen}


def rekap_checklist(items) -> dict:
    """Ringkasan checklist: jumlah, penuh (100%), per jenis."""
    per_jenis = {k: 0 for k in JENIS_OBJEK_CHECKLIST}
    penuh = 0
    for c in items or []:
        j = c.get("jenis_objek")
        if j in per_jenis:
            per_jenis[j] += 1
        if skor_checklist(c)["persen"] == 100:
            penuh += 1
    return {"jumlah": len(items or []), "penuh": penuh,
            "per_jenis": per_jenis}


# ---------------------------------------------------------------------------
# Register polis Asuransi BMN (pustaka §11.5) — dasar PMK 43 Tahun 2025
# (mencabut PMK 97/2019). Kategori objek dari siaran pers DJKN, [perlu
# verifikasi] §14 butir 20. Register pendamping: bukan kanal resmi SIMAN,
# bukan penerbitan polis, bukan laporan resmi pengasuransian.
# ---------------------------------------------------------------------------

KATEGORI_OBJEK_ASURANSI = {
    "program_preferen": "BMN Program — Preferen",
    "program_nonpreferen": "BMN Program — Nonpreferen",
    "nonprogram_mandatory": "BMN Nonprogram — Mandatory",
    "nonprogram_luar_negeri": "BMN Nonprogram — Luar Negeri",
    "nonprogram_opsional": "BMN Nonprogram — Opsional",
}

SUMBER_DANA_PREMI = {
    "dipa": "DIPA K/L",
    "pfb": "Pooling Fund Bencana (PFB)",
}

# Ambang pengingat perpanjangan polis (hari kalender sebelum berakhir).
AMBANG_SEGERA_BERAKHIR = 90


def validate_polis(data: dict) -> list:
    """Validasi pencatatan polis asuransi → daftar pesan kesalahan."""
    from datetime import date

    errors = []
    if not str(data.get("nomor_polis") or "").strip():
        errors.append("Nomor polis wajib diisi")
    if data.get("kategori_objek") not in KATEGORI_OBJEK_ASURANSI:
        valid = ", ".join(KATEGORI_OBJEK_ASURANSI)
        errors.append(f"Kategori objek tidak dikenal (pilihan: {valid})")
    if data.get("sumber_dana") not in SUMBER_DANA_PREMI:
        valid = ", ".join(SUMBER_DANA_PREMI)
        errors.append(f"Sumber dana premi tidak dikenal (pilihan: {valid})")
    mulai = str(data.get("mulai") or "").strip()[:10]
    berakhir = str(data.get("berakhir") or "").strip()[:10]
    try:
        d_mulai = date.fromisoformat(mulai)
        d_akhir = date.fromisoformat(berakhir)
        if d_akhir <= d_mulai:
            errors.append("Tanggal berakhir harus setelah tanggal mulai")
    except ValueError:
        errors.append("Tanggal mulai/berakhir harus berformat YYYY-MM-DD")
    for k, label in (("nilai_pertanggungan", "Nilai pertanggungan"),
                     ("premi", "Premi")):
        try:
            if float(data.get(k) or 0) < 0:
                errors.append(f"{label} tidak boleh negatif")
        except (TypeError, ValueError):
            errors.append(f"{label} harus angka")
    return errors


def info_polis(polis: dict, today_iso: str) -> dict:
    """Status masa berlaku polis → {status, sisa_hari}.

    Status: akan_datang / aktif / segera_berakhir (≤90 hari) / berakhir.
    """
    from datetime import date

    kosong = {"status": None, "sisa_hari": None}
    try:
        mulai = date.fromisoformat(str(polis.get("mulai") or "")[:10])
        akhir = date.fromisoformat(str(polis.get("berakhir") or "")[:10])
        hari_ini = date.fromisoformat(str(today_iso)[:10])
    except ValueError:
        return kosong
    if hari_ini < mulai:
        return {"status": "akan_datang", "sisa_hari": (akhir - hari_ini).days}
    sisa = (akhir - hari_ini).days
    if sisa < 0:
        return {"status": "berakhir", "sisa_hari": 0}
    if sisa <= AMBANG_SEGERA_BERAKHIR:
        return {"status": "segera_berakhir", "sisa_hari": sisa}
    return {"status": "aktif", "sisa_hari": sisa}


def rekap_polis(items, today_iso: str) -> dict:
    """Ringkasan polis per status masa berlaku + total nilai aktif."""
    per_status = {"akan_datang": 0, "aktif": 0, "segera_berakhir": 0,
                  "berakhir": 0}
    nilai_aktif = 0.0
    for p in items or []:
        info = info_polis(p, today_iso)
        st = info["status"]
        if st in per_status:
            per_status[st] += 1
        if st in ("aktif", "segera_berakhir"):
            try:
                nilai_aktif += float(p.get("nilai_pertanggungan") or 0)
            except (TypeError, ValueError):
                pass
    return {"jumlah": len(items or []), "per_status": per_status,
            "nilai_pertanggungan_aktif": nilai_aktif}


# Label status masa berlaku polis (dipakai endpoint list, ekspor, & test).
STATUS_POLIS = {
    "akan_datang": "Akan datang",
    "aktif": "Aktif",
    "segera_berakhir": "Segera berakhir",
    "berakhir": "Berakhir",
}

HEADER_CSV_POLIS = [
    "kode_aset", "nup", "nama_aset", "nomor_polis", "penanggung",
    "kategori_objek", "nilai_pertanggungan", "premi", "sumber_dana",
    "mulai", "berakhir", "status", "sisa_hari", "keterangan", "dibuat_oleh",
]


def baris_csv_polis(polis_list, today_iso) -> list:
    """Susun baris CSV register polis asuransi BMN: [header, *data] — murni.

    Kategori objek/sumber dana/status diterjemahkan ke label; nilai
    pertanggungan & premi dibulatkan rupiah; status masa berlaku + sisa
    hari dihitung via info_polis. Tanpa Mongo/IO agar teruji unit (pola
    ekspor #158).
    """
    def _rp(x):
        try:
            return int(round(float(x or 0)))
        except (TypeError, ValueError):
            return 0

    baris = [list(HEADER_CSV_POLIS)]
    for p in polis_list or []:
        info = info_polis(p, today_iso)
        sisa = info.get("sisa_hari")
        baris.append([
            p.get("asset_code") or "",
            p.get("NUP") or "",
            p.get("asset_name") or "",
            p.get("nomor_polis") or "",
            p.get("penanggung") or "",
            KATEGORI_OBJEK_ASURANSI.get(p.get("kategori_objek"),
                                        p.get("kategori_objek") or ""),
            _rp(p.get("nilai_pertanggungan")),
            _rp(p.get("premi")),
            SUMBER_DANA_PREMI.get(p.get("sumber_dana"),
                                  p.get("sumber_dana") or ""),
            str(p.get("mulai") or "")[:10],
            str(p.get("berakhir") or "")[:10],
            STATUS_POLIS.get(info.get("status"), info.get("status") or ""),
            sisa if sisa is not None else "",
            p.get("keterangan") or "",
            p.get("created_by") or "",
        ])
    return baris
