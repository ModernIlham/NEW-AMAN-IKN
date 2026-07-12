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
