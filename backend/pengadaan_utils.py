"""Logika murni PENGADAAN (Perpres 16/2018 jo. 46/2025 — pustaka §10).

Register perolehan per dokumen (BAST/kontrak) tingkat satker: jenis
perolehan selaras kode transaksi SAKTI (101/102/103/105 — referensi,
bukan pencatatan resmi), checklist kelengkapan dokumen sumber (penangkal
temuan BPK "BAST tercecer"), daftar barang dengan tautan ke aset master
dan penanda ekstrakomptabel di bawah ambang PMK 181/2016.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pemeliharaan_utils import indikasi_kapitalisasi
from pembukuan_utils import parse_harga

# Jenis perolehan → (label, kode transaksi SAKTI sebagai referensi)
JENIS_PEROLEHAN = {
    "pembelian": ("Pembelian (APBN)", "101"),
    "transfer_masuk": ("Transfer Masuk (antar entitas)", "102"),
    "hibah_masuk": ("Hibah Masuk (pemda/swasta)", "103"),
    "pembangunan": ("Penyelesaian Pembangunan", "105/113"),
}

# Kunci dokumen sumber → label Indonesia
LABEL_DOKUMEN_SUMBER = {
    "kontrak": "Kontrak/SPK",
    "baphp": "BAPHP",
    "bast": "BAST",
    "kuitansi": "Kuitansi/Faktur",
    "sp2d": "SP2D",
    "naskah_hibah": "Naskah Hibah",
    "mphl_bjs": "MPHL-BJS",
}

# Checklist dokumen sumber wajib per jenis perolehan (pustaka §10.2)
DOKUMEN_PEROLEHAN = {
    "pembelian": ("kontrak", "baphp", "bast", "kuitansi", "sp2d"),
    "transfer_masuk": ("bast",),
    "hibah_masuk": ("naskah_hibah", "bast", "mphl_bjs"),
    "pembangunan": ("kontrak", "baphp", "bast", "sp2d"),
}


def _tgl(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (TypeError, ValueError):
        return None


def validate_perolehan(data: dict, today_iso: str) -> list:
    """Validasi register perolehan baru → daftar pesan kesalahan."""
    errors = []
    if data.get("jenis") not in JENIS_PEROLEHAN:
        pilihan = ", ".join(JENIS_PEROLEHAN)
        errors.append(f"Jenis perolehan tidak dikenal (pilihan: {pilihan})")
    if not str(data.get("pihak") or "").strip():
        errors.append("Penyedia/pemberi wajib diisi")
    if not str(data.get("nomor_bast") or "").strip():
        errors.append("Nomor BAST wajib diisi (pemicu pencatatan BMN)")
    t = _tgl(data.get("tanggal_bast"))
    hari_ini = _tgl(today_iso)
    if not t:
        errors.append("Tanggal BAST wajib diisi (format YYYY-MM-DD)")
    elif hari_ini and t > hari_ini:
        errors.append("Tanggal BAST tidak boleh di masa depan")
    barang = data.get("barang") or []
    if not barang:
        errors.append("Daftar barang minimal satu baris")
    for i, b in enumerate(barang, start=1):
        if not str(b.get("uraian") or "").strip():
            errors.append(f"Barang #{i}: uraian wajib diisi")
        try:
            jumlah = float(b.get("jumlah") or 0)
        except (TypeError, ValueError):
            jumlah = 0
        if jumlah <= 0:
            errors.append(f"Barang #{i}: jumlah harus lebih dari 0")
        if parse_harga(b.get("harga_satuan")) < 0:
            errors.append(f"Barang #{i}: harga satuan harus angka ≥ 0")
    return errors


def dokumen_kurang_perolehan(p: dict) -> list:
    """Label dokumen sumber yang belum tercentang untuk jenis perolehan."""
    wajib = DOKUMEN_PEROLEHAN.get(p.get("jenis"), ())
    ada = p.get("dokumen") or {}
    return [LABEL_DOKUMEN_SUMBER[k] for k in wajib if not ada.get(k)]


def is_ekstrakomptabel(barang: dict) -> bool:
    """Harga satuan di bawah ambang kapitalisasi PMK 181 untuk kodenya.

    Hanya bermakna bila kode barang terisi dan golongannya berambang
    (3 peralatan-mesin / 4 gedung-bangunan); barang tanpa kode → False
    (tidak dinilai, bukan berarti intrakomptabel).
    """
    kode = str(barang.get("kode") or "").strip()
    if not kode or kode[:1] not in ("3", "4"):
        return False
    return not indikasi_kapitalisasi(barang.get("harga_satuan"), kode)


def nilai_perolehan(p: dict) -> float:
    """Total nilai daftar barang (jumlah × harga satuan)."""
    total = 0.0
    for b in p.get("barang") or []:
        try:
            jumlah = float(b.get("jumlah") or 0)
        except (TypeError, ValueError):
            jumlah = 0
        total += jumlah * parse_harga(b.get("harga_satuan"))
    return total


def rekap_perolehan(items) -> dict:
    """Ringkasan register: jumlah, nilai, kelengkapan, tautan aset."""
    per_jenis = {k: 0 for k in JENIS_PEROLEHAN}
    nilai = 0.0
    lengkap = 0
    barang_total = 0
    belum_tertaut = 0
    ekstra = 0
    for p in items or []:
        j = p.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
        nilai += nilai_perolehan(p)
        if not dokumen_kurang_perolehan(p):
            lengkap += 1
        for b in p.get("barang") or []:
            barang_total += 1
            if not str(b.get("asset_id") or "").strip():
                belum_tertaut += 1
            if is_ekstrakomptabel(b):
                ekstra += 1
    return {"jumlah": len(items or []), "per_jenis": per_jenis,
            "nilai": nilai, "dokumen_lengkap": lengkap,
            "barang_total": barang_total, "belum_tertaut": belum_tertaut,
            "ekstrakomptabel": ekstra}


# ---------------------------------------------------------------------------
# Tautan paket perolehan → usulan Penganggaran (#117 ↔ #115). Snapshot
# identitas usulan agar register perolehan menjejak sumber anggarannya
# (uraian, nomor DIPA, tahun) tanpa join saat baca. Referensi lunak —
# menautkan tidak memvalidasi nilai; kanal resmi tetap SAKTI.
# ---------------------------------------------------------------------------

def snapshot_penganggaran(usulan) -> dict:
    """Ringkas identitas usulan penganggaran untuk disimpan di perolehan.

    usulan None / kosong → snapshot kosong (tautan dilepas).
    """
    if not usulan:
        return {"penganggaran_id": "", "penganggaran_uraian": "",
                "penganggaran_nomor_dipa": "", "penganggaran_tahun": ""}
    return {
        "penganggaran_id": str(usulan.get("id") or "").strip(),
        "penganggaran_uraian": str(usulan.get("uraian") or "").strip(),
        "penganggaran_nomor_dipa": str(usulan.get("nomor_dipa") or "").strip(),
        "penganggaran_tahun": str(usulan.get("tahun_anggaran") or "").strip(),
    }


# ---------------------------------------------------------------------------
# PEJABAT PEMBUAT KOMITMEN (PPK) — snapshot pada dokumen perolehan.
#
# PPK-lah yang MENANDATANGANI kontrak dan MENERIMA hasil pekerjaan dari
# penyedia (Perpres 16/2018 Pasal 11); tanpa namanya, register perolehan
# menyebut "dari siapa" barang datang tetapi bukan "atas komitmen siapa" —
# justru pertanyaan pertama pemeriksa saat menelusuri satu BAST.
#
# DIBEKUKAN, bukan di-join saat baca. Pejabat berganti (mutasi, pensiun,
# Plt/Plh); dokumen yang terbit tahun lalu harus tetap menyebut PPK yang
# menandatanganinya waktu itu. Pola sama dengan snapshot penandatangan BAST.
# ---------------------------------------------------------------------------

def snapshot_ppk(pejabat) -> dict:
    """Ringkas identitas PPK untuk dibekukan di dokumen perolehan.

    `pejabat` None/kosong → snapshot kosong (belum ditetapkan). Field kosong
    disimpan APA ADANYA — bentuk yang stabil membuat pembaca dokumen tak perlu
    membedakan "belum pernah diisi" dari "kunci hilang".
    """
    p = pejabat or {}
    return {
        "ppk_pejabat_id": str(p.get("id") or "").strip(),
        "ppk_nama": str(p.get("nama") or "").strip(),
        "ppk_nip": str(p.get("nip") or "").strip(),
        "ppk_jabatan": str(p.get("jabatan") or "").strip(),
        # Status kepegawaian ikut dibekukan: blok TTD menyembunyikan baris
        # NIP untuk Non-ASN (privasi — lihat baris_identitas_ttd), dan status
        # itu harus dinilai dari keadaan SAAT dokumen terbit.
        "ppk_status_kepegawaian": str(p.get("status_kepegawaian") or "").strip(),
    }


def build_asset_perolehan_projection(perolehan, now_iso) -> dict:
    """Proyeksi BALIK 'dokumen sumber' pada aset (§5A gap #6 — Prinsip 4).

    Tautan perolehan→aset selama ini SATU arah (`perolehan.barang[].asset_id`).
    Saat baris barang ditautkan ke aset master, aset kini menyimpan
    `perolehan_id` + snapshot beku identitas dokumen sumber (BAST/kontrak) →
    bisa ditelusuri DUA arah (aset ⇄ perolehan). `perolehan` None/kosong →
    proyeksi kosong (lepas tautan).

    SENGAJA tak menyentuh field laporan (`purchase_price` dst) & pemanggil TAK
    menaikkan `version` — ini provenance/metadata sumber, bukan keadaan neraca;
    menaikkan version akan memicu OCC 409 palsu pada form edit aset yang terbuka.
    """
    if not perolehan:
        return {"perolehan_id": "", "perolehan": {}}
    return {
        "perolehan_id": str(perolehan.get("id") or "").strip(),
        "perolehan": {
            "jenis": str(perolehan.get("jenis") or "").strip(),
            "pihak": str(perolehan.get("pihak") or "").strip(),
            "nomor_bast": str(perolehan.get("nomor_bast") or "").strip(),
            "tanggal_bast": str(perolehan.get("tanggal_bast") or "").strip()[:10],
            "nomor_kontrak": str(perolehan.get("nomor_kontrak") or "").strip(),
            # PPK ikut turun ke aset: menelusuri "siapa yang berkomitmen atas
            # barang ini" tak boleh menuntut satu kueri balik ke register.
            "ppk_nama": str(perolehan.get("ppk_nama") or "").strip(),
            "ppk_nip": str(perolehan.get("ppk_nip") or "").strip(),
            "ppk_jabatan": str(perolehan.get("ppk_jabatan") or "").strip(),
            "diproyeksikan_pada": now_iso,
        },
    }


def snapshot_perolehan(perolehan) -> dict:
    """Ringkas identitas perolehan Pengadaan untuk disimpan sebagai FK pada
    jurnal transaksi MASUK persediaan (§5A gap #2 — simpul Dokumen Sumber juga
    untuk persediaan, tiru pola `snapshot_penganggaran`). Bentuk RATA agar cocok
    di jurnal `transaksi_persediaan`. perolehan None/kosong → snapshot kosong
    (tautan dilepas).
    """
    if not perolehan:
        return {"perolehan_id": "", "perolehan_nomor_bast": "",
                "perolehan_tanggal_bast": "", "perolehan_jenis": "",
                "perolehan_pihak": "", "perolehan_ppk_nama": "",
                "perolehan_ppk_nip": ""}
    return {
        "perolehan_id": str(perolehan.get("id") or "").strip(),
        "perolehan_nomor_bast": str(perolehan.get("nomor_bast") or "").strip(),
        "perolehan_tanggal_bast": str(perolehan.get("tanggal_bast") or "").strip()[:10],
        "perolehan_jenis": str(perolehan.get("jenis") or "").strip(),
        "perolehan_pihak": str(perolehan.get("pihak") or "").strip(),
        # PPK menyertai jurnal persediaan juga: LPB persediaan pembelian
        # menyebut nama PPK, dan jurnalnya harus bisa membuktikan dari mana
        # nama itu berasal tanpa join ke register perolehan.
        "perolehan_ppk_nama": str(perolehan.get("ppk_nama") or "").strip(),
        "perolehan_ppk_nip": str(perolehan.get("ppk_nip") or "").strip(),
    }


def kunci_ubah_perolehan(p: dict, ada_lpb: bool = False) -> dict:
    """Sejauh mana satu register perolehan masih boleh diubah.

    Register perolehan adalah **jurnal dokumen sumber**, bukan catatan bebas:
    begitu isinya melahirkan sesuatu, mengubahnya diam-diam membuat anak-anak
    itu berbohong. Tiga tingkat, dari longgar ke ketat:

    1. **Belum melahirkan apa pun** — semua boleh diubah. Salah ketik nomor
       BAST atau harga satuan pada menit pertama adalah kejadian yang paling
       sering, dan tanpa jalan perbaikan operator terpaksa menghapus lalu
       mencatat ulang.
    2. **Barangnya sudah tercatat** ke stok persediaan / aset ber-NUP — daftar
       barang dikunci, identitas dokumen masih boleh dirapikan. Mengubah
       jumlah/harga baris yang sudah jadi stok membuat register dan Buku
       Barang berselisih tanpa satu pun jejak yang menjelaskan.
    3. **BAST PPK→KPB sudah terbit, atau ada LPB yang menunjuknya** — hanya
       keterangan. PDF-nya disusun ulang dari data ini setiap kali diunduh,
       jadi mengubah pihak/nomor/tanggal berarti **mengubah isi dokumen resmi
       yang sudah bernomor** — termasuk yang sudah dicetak dan ditandatangani.

    Penjaganya sengaja sejalan dengan penjaga hapus register: yang tak boleh
    dihapus karena sudah "hidup" juga tak boleh diam-diam berganti isi.
    """
    tercatat = [b for b in (p.get("barang") or [])
                if str(b.get("psd_item_id") or "").strip()
                or str(b.get("asset_id") or "").strip()]
    beku = bool(p.get("bast_ppk")) or bool(ada_lpb)
    if beku:
        sebab = ("BAST PPK→KPB sudah diterbitkan"
                 if p.get("bast_ppk") else
                 "ada Laporan Penerimaan Barang (LPB) yang menunjuk register ini")
        alasan = (f"{sebab} — isi dokumen resminya disusun ulang dari data ini "
                  "setiap kali diunduh, jadi hanya keterangan yang dapat diubah.")
    elif tercatat:
        alasan = (f"{len(tercatat)} barang sudah tercatat ke stok/aset — daftar "
                  "barangnya dikunci agar register dan Buku Barang tidak "
                  "berselisih. Batalkan pencatatannya dulu bila memang salah.")
    else:
        alasan = ""
    return {
        "identitas": not beku,
        "barang": not beku and not tercatat,
        "keterangan": True,
        "n_tercatat": len(tercatat),
        "alasan": alasan,
    }
