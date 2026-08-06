"""Util murni Timeline Aset — "data induk = riwayat perlakuan aset".

Prinsip (masterplan Bab 5 + mandat W5): dokumen aset per kegiatan
inventarisasi BUKAN induk data. Aset fisik yang sama dapat tercatat di
BANYAK kegiatan (satu dokumen `assets` per kegiatan). Induk sesungguhnya
adalah IDENTITAS aset — prioritas `kode_register` (ID internal SIMAN),
fallback `asset_code` + `NUP` — dan timeline seluruh perlakuan terhadap
identitas itu lintas modul (inventarisasi, penggunaan, pemeliharaan,
pengamanan, penilaian, penghapusan, pemindahtanganan, pemusnahan, wasdal,
BAST, pembukuan, SIMAN V2).

Semua fungsi di file ini murni (tanpa Mongo) agar teruji unit.
Bentuk baku satu event timeline:
    {"tanggal": str ISO ("" bila tak diketahui), "modul": str,
     "jenis": str, "judul": str, "detail": str, "ref_id": str,
     "status": str}
Catatan casing: koleksi `assets` memakai `NUP` (kapital); `mutasi_bmn`,
`audit_logs`, dan SIMAN memakai `nup` — normalisasi di `identitas_aset`.
"""

# Label modul baku untuk badge di UI — kunci = nilai field `modul` event.
MODUL_LABEL = {
    "inventarisasi": "Inventarisasi",
    "penggunaan": "Penggunaan",
    "pemanfaatan": "Pemanfaatan",
    "pemeliharaan": "Pemeliharaan",
    "pengamanan": "Pengamanan",
    "penilaian": "Penilaian",
    "penghapusan": "Penghapusan",
    "pemindahtanganan": "Pemindahtanganan",
    "pemusnahan": "Pemusnahan",
    "wasdal": "Wasdal",
    "bast": "BAST",
    "pembukuan": "Pembukuan",
    "siman": "SIMAN V2",
    "lokasi": "Lokasi & Opname",
    "aset": "Master Aset",
}

# Status rekonsiliasi satu scan opname (lihat `opname_utils.klasifikasi_scan`)
# → kalimat yang dibaca operator di timeline.
LABEL_STATUS_SCAN = {
    "baru": "penempatan pertama",
    "sesuai": "cocok dengan catatan",
    "pindah": "BEDA dari catatan",
    "tanpa_lokasi": "di luar kawasan terpetakan",
}

# Label badge status event timeline. SENGAJA KURATIF, bukan menyapu semua nilai
# yang mungkin muncul: `status` event diisi dari bermacam sumber, termasuk
# `kode_transaksi` Buku Barang ("100", "101", …). Menampilkan nilai mentah apa
# adanya akan memunculkan badge "100" yang tak berarti — dan bila dipetakan
# lewat KODE_TRANSAKSI_LABEL justru mengulang judulnya persis.
#
# Karena itu UI hanya menampilkan badge untuk status yang ADA di peta ini;
# selebihnya dibiarkan tersampaikan lewat judul/detail. Status baru yang layak
# tampil cukup didaftarkan di sini.
LABEL_STATUS = {
    # Register siklus (usulan, pemindahtanganan, pemusnahan, penertiban, …)
    "draft": "Draf",
    "diusulkan": "Diusulkan",
    "diproses": "Diproses",
    "menunggu_persetujuan": "Menunggu persetujuan",
    "disetujui": "Disetujui",
    "ditolak": "Ditolak",
    "selesai": "Selesai",
    "dibatalkan": "Dibatalkan",
    "aktif": "Aktif",
    "berakhir": "Berakhir",
    # Status inventarisasi aset
    "ditemukan": "Ditemukan",
    "tidak_ditemukan": "Tidak ditemukan",
    "belum_diinventarisasi": "Belum diinventarisasi",
    "berlebih": "Berlebih",
    # Opname (dari LABEL_STATUS_SCAN, dikapitalkan agar seragam sebagai badge)
    "baru": "Penempatan pertama",
    "sesuai": "Cocok dengan catatan",
    "pindah": "BEDA dari catatan",
    "tanpa_lokasi": "Di luar kawasan terpetakan",
}

# Uraian kode transaksi Buku Barang (mutasi_bmn) yang umum dipakai.
KODE_TRANSAKSI_LABEL = {
    "100": "Saldo awal / perolehan",
    "101": "Pembelian",
    "102": "Transfer masuk",
    "107": "Reklasifikasi masuk",
    "204": "Koreksi nilai (revaluasi)",
    "205": "Koreksi nilai berkurang (revaluasi)",
    "301": "Penghapusan",
    "302": "Transfer keluar",
    "304": "Reklasifikasi keluar",
}


def _s(v) -> str:
    return str(v or "").strip()


def identitas_aset(doc) -> dict:
    """Identitas lintas kegiatan sebuah dokumen aset/mutasi/riwayat.

    Menerima dokumen dengan casing campuran (NUP atau nup, asset_code atau
    kode_barang) dan mengembalikan bentuk baku."""
    d = doc or {}
    return {
        "kode_register": _s(d.get("kode_register")),
        "asset_code": _s(d.get("asset_code") or d.get("kode_barang")),
        "nup": _s(d.get("NUP") if d.get("NUP") is not None else d.get("nup")),
    }


def query_identitas(identitas) -> dict:
    """Query Mongo koleksi `assets` untuk menemukan SEMUA dokumen aset dengan
    identitas fisik yang sama (lintas kegiatan). Prioritas kode_register;
    fallback asset_code + NUP. {} bila identitas tak memadai (jangan query)."""
    i = identitas or {}
    reg = _s(i.get("kode_register"))
    kode = _s(i.get("asset_code"))
    nup = _s(i.get("nup"))
    if reg:
        # Aset lama mungkin belum menyimpan kode_register — sertakan juga
        # kecocokan kode+NUP agar saudara pra-SIMAN tetap terjaring.
        if kode:
            q_nup = {"asset_code": kode}
            if nup:
                q_nup["NUP"] = nup
            return {"$or": [{"kode_register": reg}, q_nup]}
        return {"kode_register": reg}
    if kode:
        q = {"asset_code": kode}
        if nup:
            q["NUP"] = nup
        return q
    return {}


def buat_event(modul, jenis, judul, tanggal="", detail="", ref_id="",
               status="", urut="") -> dict:
    """Bentuk baku satu event timeline.

    `urut` adalah PEMECAH SERI: dipakai HANYA ketika dua event punya `tanggal`
    yang sama persis. Isi dengan cap waktu terlengkap yang dimiliki dokumen
    sumber (umumnya `created_at`). Boleh kosong — event tanpa pemecah seri
    tetap tersusun, hanya tak punya urutan bermakna di dalam harinya.
    """
    return {
        "tanggal": _s(tanggal), "modul": _s(modul) or "aset",
        "jenis": _s(jenis), "judul": _s(judul), "detail": _s(detail),
        "ref_id": _s(ref_id), "status": _s(status), "urut": _s(urut),
    }


def urut_events(events) -> list:
    """Urutkan event terbaru dulu. `tanggal` string ISO (tanggal saja atau
    timestamp) — perbandingan leksikal cukup; tanggal kosong di paling akhir.

    PEMECAH SERI (`urut`) wajib ada di kunci, bukan sekadar mengandalkan
    kestabilan `sort`. Banyak event bertanggal HARI saja ("2026-08-04"), dan
    beberapa modul menerbitkan puluhan dokumen dalam satu hari — BAST serah
    terima B-017 s.d. B-023, misalnya. Pada seri, `list.sort` yang stabil
    mempertahankan urutan MASUK, dan urutan masuk itu menaik; hasilnya yang
    TERBARU justru mendarat di paling bawah, persis kebalikan dari yang
    dijanjikan judul kolomnya.
    """
    ada, kosong = [], []
    for e in events or []:
        (ada if _s(e.get("tanggal")) else kosong).append(e)
    ada.sort(key=lambda e: (e["tanggal"], _s(e.get("urut"))), reverse=True)
    return ada + kosong


def ringkas_per_modul(events) -> dict:
    """{modul: jumlah event} — bahan chip filter di UI."""
    n = {}
    for e in events or []:
        m = _s(e.get("modul")) or "aset"
        n[m] = n.get(m, 0) + 1
    return n


def info_psp_siman(siman_sub) -> dict:
    """Ekstrak info penetapan status penggunaan (PSP) & status resmi dari
    subdoc `assets.siman.referensi` hasil impor SIMAN V2 — data otoritatif
    yang selama ini tersimpan tapi belum dipakai modul lain.

    Kembalian {} bila tidak ada satu pun info bermakna."""
    # norm_no_psp: placeholder "belum PSP" ("-", "Tidak Ada Inputan" dsb.)
    # dari referensi lama di DB tidak boleh dianggap nomor PSP — tanpa ini
    # aset belum ter-PSP mendapat event "PSP menurut SIMAN" palsu.
    from siman_utils import norm_no_psp
    ref = ((siman_sub or {}).get("referensi") or {})
    info = {
        "no_psp": norm_no_psp(ref.get("no_psp")),
        "tanggal_psp": _s(ref.get("tanggal_psp")),
        "status_penggunaan": _s(ref.get("status_penggunaan")),
        "status_bmn": _s(ref.get("status_bmn")),
        "status_idle": _s(ref.get("status_idle")),
        "henti_guna": _s(ref.get("henti_guna")),
        "intra_ekstra": _s(ref.get("intra_ekstra")),
    }
    return info if any(info.values()) else {}


def event_psp_siman(siman_sub) -> list:
    """Event timeline dari PSP menurut SIMAN V2 (bila nomornya ada)."""
    info = info_psp_siman(siman_sub)
    if not info.get("no_psp"):
        return []
    detail = "; ".join(x for x in (
        f"Status penggunaan: {info['status_penggunaan']}" if info.get("status_penggunaan") else "",
        f"Status BMN: {info['status_bmn']}" if info.get("status_bmn") else "",
    ) if x)
    return [buat_event(
        "siman", "psp", f"PSP menurut SIMAN V2 — No. {info['no_psp']}",
        tanggal=info.get("tanggal_psp", ""), detail=detail,
        status=info.get("status_penggunaan", ""))]


def event_dari_riwayat(doc, modul, judul, ref_id="", kunci_waktu=("tanggal", "waktu")) -> list:
    """Event dari array `riwayat[]` sebuah dokumen modul (pola umum:
    {status, tanggal|waktu, oleh, catatan}). Judul dipakai sebagai konteks."""
    hasil = []
    for i, r in enumerate((doc or {}).get("riwayat", []) or []):
        if not isinstance(r, dict):
            continue
        tanggal = ""
        for k in kunci_waktu:
            if _s(r.get(k)):
                tanggal = _s(r.get(k))
                break
        st = _s(r.get("status"))
        catatan = _s(r.get("catatan") or r.get("keterangan"))
        hasil.append(buat_event(
            modul, "riwayat_status",
            f"{judul}: {st}" if st else judul,
            tanggal=tanggal, detail=catatan, ref_id=ref_id, status=st,
            # Pemecah seri = POSISI dalam array. `riwayat[]` selalu ditambah di
            # belakang, jadi indeks menaik = kronologis; dibandingkan menurun ia
            # menaruh langkah terakhir di atas. Nol di depan wajib — tanpa itu
            # "10" bandingkan sebagai lebih kecil dari "9" secara leksikal.
            urut=f"{i:06d}"))
    return hasil


def label_transaksi_buku(kode) -> str:
    k = _s(kode)
    return KODE_TRANSAKSI_LABEL.get(k, f"Transaksi {k}" if k else "Transaksi")


def _nama_lokasi(sisi) -> str:
    """Nama lokasi terbaca dari satu sisi entri riwayat: jalur lengkap bila
    ada (lebih informatif), jatuh ke nama node, lalu "" bila memang lepas."""
    s = sisi or {}
    return _s(s.get("jalur")) or _s(s.get("nama")) or _s(s.get("node_nama"))


def event_scan_opname(scan) -> dict:
    """Satu scan stiker QR (`opname_scan`) → event timeline.

    Selama ini scan HANYA muncul lewat audit log dengan judul "Perubahan data
    aset (opname_scan)" — menyesatkan (scan tak mengubah data apa pun) dan
    tanpa satu pun isi yang berguna: node mana, cocok atau tidak, sudah
    diterapkan atau belum. Padahal inilah satu-satunya bukti bahwa seseorang
    benar-benar MELIHAT barangnya di lapangan.
    """
    s = scan or {}
    status = _s(s.get("status_rekonsiliasi"))
    lokasi = _s((s.get("lokasi_spasial") or {}).get("jalur_nama")) \
        or _s((s.get("lokasi_spasial") or {}).get("node_nama"))
    judul = f"Dipindai di {lokasi}" if lokasi else "Dipindai (tanpa lokasi denah)"

    # Hasil rekonsiliasi TIDAK diulang di detail — ia sudah jadi badge status
    # di UI (lihat LABEL_STATUS). Menulisnya di dua tempat membuat tiap baris
    # scan berbunyi dua kali.
    bagian = []
    if status == "pindah":
        # Titik paling berharga bagi penelusur: dari mana ia berpindah.
        asal = _nama_lokasi(s.get("lokasi_sebelum"))
        if asal:
            bagian.append(f"Tercatat sebelumnya di {asal}")
        bagian.append("Sudah diterapkan" if s.get("diterapkan")
                      else "BELUM diterapkan ke catatan")
    if _s(s.get("catatan")):
        bagian.append(_s(s.get("catatan")))
    if _s(s.get("oleh")):
        bagian.append(f"Oleh: {_s(s.get('oleh'))}")

    return buat_event("lokasi", "opname_scan", judul,
                      tanggal=_s(s.get("pada")) or _s(s.get("diterima_pada")),
                      detail="; ".join(bagian), ref_id=_s(s.get("id")),
                      status=status)


def event_pindah_lokasi(baris) -> dict:
    """Satu baris `riwayat_lokasi_aset` → event timeline.

    Koleksi ini menyimpan snapshot NAMA kedua sisi justru agar riwayat custody
    tetap terbaca bertahun kemudian; sampai kini tak ada satu pun layar yang
    membacanya. Tiga bentuk perpindahan dibedakan supaya kalimatnya jujur:
    penempatan pertama, pencabutan, dan perpindahan antar-lokasi.
    """
    b = baris or {}
    dari = _nama_lokasi(b.get("dari"))
    ke = _nama_lokasi(b.get("ke"))
    if dari and ke:
        judul, jenis = f"Dipindahkan: {dari} → {ke}", "pindah"
    elif ke:
        judul, jenis = f"Ditempatkan di {ke}", "penempatan"
    elif dari:
        judul, jenis = f"Penempatan dicabut (sebelumnya {dari})", "pencabutan"
    else:
        # Kedua sisi kosong: baris tanpa makna (data lama/cacat). Tetap
        # ditampilkan sebagai jejak, bukan dibuang senyap.
        judul, jenis = "Perubahan penempatan denah", "pindah"
    oleh = _s(b.get("oleh"))
    return buat_event("lokasi", jenis, judul, tanggal=_s(b.get("pada")),
                      detail=f"Oleh: {oleh}" if oleh else "",
                      ref_id=_s(b.get("asset_id")))


def ringkas_perubahan_audit(changes, batas=4) -> str:
    """Ringkas array `changes` audit_logs ({field, from, to}) jadi 1 baris."""
    items = [c for c in (changes or []) if isinstance(c, dict) and _s(c.get("field"))]
    if not items:
        return ""
    nama = [_s(c["field"]) for c in items[:batas]]
    sisa = len(items) - len(nama)
    teks = ", ".join(nama)
    if sisa > 0:
        teks += f" +{sisa} lainnya"
    return f"Field berubah: {teks}"


def susun_kelompok_lintas_kegiatan(groups, kegiatan_info=None) -> list:
    """Susun hasil agregasi aset ber-identitas sama LINTAS kegiatan (W5).

    Jawaban atas "sistem belum mengenali barang yang sama di berbagai
    kegiatan inventarisasi": kelompok = kode barang + NUP; hanya kelompok
    yang tercatat di LEBIH dari satu kegiatan yang dikembalikan.

    - groups: dokumen hasil $group Mongo:
      {_id: {kode, nup}, n, kegiatan: [activity_id...],
       docs: [{id, activity_id, asset_name, kode_register,
               inventory_status, condition, updated_at}...]}
    - kegiatan_info: {activity_id: {ticket_number, name, status_pengesahan}}

    Kembalian per kelompok: {asset_code, nup, asset_name, kode_register,
    jumlah_dokumen, jumlah_kegiatan, kegiatan: [{asset_id, activity_id,
    ticket_number, nama_kegiatan, status_pengesahan, inventory_status,
    condition, updated_at}] terbaru dulu}. MURNI.
    """
    info = kegiatan_info or {}
    hasil = []
    for g in groups or []:
        gid = g.get("_id") or {}
        keg_ids = {k for k in (g.get("kegiatan") or []) if k}
        if len(keg_ids) < 2:
            continue
        docs = [d for d in (g.get("docs") or []) if isinstance(d, dict)]
        docs.sort(key=lambda d: str(d.get("updated_at") or ""), reverse=True)
        nama = next((str(d.get("asset_name") or "").strip()
                     for d in docs if str(d.get("asset_name") or "").strip()), "")
        reg = next((str(d.get("kode_register") or "").strip()
                    for d in docs if str(d.get("kode_register") or "").strip()), "")
        hasil.append({
            "asset_code": _s(gid.get("kode")),
            "nup": _s(gid.get("nup")),
            "asset_name": nama,
            "kode_register": reg,
            "jumlah_dokumen": int(g.get("n") or len(docs)),
            "jumlah_kegiatan": len(keg_ids),
            "kegiatan": [{
                "asset_id": _s(d.get("id")),
                "activity_id": _s(d.get("activity_id")),
                "ticket_number": _s((info.get(d.get("activity_id")) or {})
                                    .get("ticket_number")),
                "nama_kegiatan": _s((info.get(d.get("activity_id")) or {})
                                    .get("name")),
                "status_pengesahan": _s((info.get(d.get("activity_id")) or {})
                                        .get("status_pengesahan")),
                "inventory_status": _s(d.get("inventory_status")),
                "condition": _s(d.get("condition")),
                "updated_at": _s(d.get("updated_at")),
            } for d in docs],
        })
    hasil.sort(key=lambda k: (-k["jumlah_kegiatan"], k["asset_code"],
                              k["nup"]))
    return hasil
