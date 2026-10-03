"""Gerbang bukti BAST untuk proyeksi BMN Saya; tidak menulis master/jurnal.

Manifest PDF dibekukan sekali di jalur BAST, bukan dibentuk dari daftar peserta
yang mungkin telah dikurangi. Pemeriksaan akses berikutnya memakai referensi
dan hash beku sehingga tidak membaca ulang seluruh PDF per aset.
"""
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from ttd_kelengkapan import jumlah_pembubuhan
from ttd_validasi import sudah_terverifikasi


_ISI_BAST = (
    "id", "kode_satker", "jenis", "judul_lainnya", "nomor", "surat_id", "tanggal",
    "pihak_pertama", "pihak_kedua", "asset_ids", "aset", "jangka_dari", "jangka_sampai",
    "penanggung_jawab_tambahan", "surat_pernyataan", "almarhum", "saksi", "tembusan",
    "penyerah_atas_nama_kpb", "sertakan_foto", "tampilkan_nilai", "terapkan_ke_aset",
    "keterangan", "revisi_dari", "revisi_dari_nomor", "revisi_ke", "revisi_mode", "revisi_alasan",
)
_ITEM_OTOMASI = ("asset_id", "aksi", "penerima", "ikatan_awal", "alias",
                 "identitas_pegawai", "alasan_awal")
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _teks(value):
    return str(value or "").strip()


def _sidik(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def sidik_isi_bast(bast) -> str:
    """Identitas/isi dokumen dan tujuan per aset; abaikan status proyeksi runtime."""
    b = bast or {}
    isi = {k: b.get(k) for k in _ISI_BAST}
    isi["portal_items"] = [{k: item.get(k) for k in _ITEM_OTOMASI}
                            for item in (b.get("portal_otomasi") or {}).get("items", [])]
    # Foto dapat ditambah untuk dokumentasi tanpa mengubah naskah yang tidak
    # mencetak foto. Jika dicetak, perubahan referensinya mengubah isi naskah.
    if b.get("sertakan_foto"):
        isi.update({k: b.get(k) for k in ("foto_serah_terima", "foto_serah_terima_bersama")})
    return _sidik(isi)


def _jumlah_wajib(signer):
    try:
        jumlah = int(signer.get("jumlah_ttd", 1))
        return jumlah if 1 <= jumlah <= 20 else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def _identitas_signer(signer):
    return {k: _teks(signer.get(k)) for k in ("signer_id", "nama", "nip", "jabatan")}


async def bekukan_manifest_bast(db, bast, sr_id):
    """Sesudah PDF terlampir dan sebelum pembubuhan: hash byte GridFS aktual.

    Replay tidak pernah membekukan ulang daftar wajib. Perubahan isi/berkas
    sesudah pembekuan memerlukan permintaan baru, bukan pembenaran manifest.
    """
    from shared_utils import get_document_from_gridfs

    b = await db.bast_serah_terima.find_one({"id": (bast or {}).get("id")})
    sr = await db.signature_requests.find_one({"id": sr_id})
    kode = _teks((b or {}).get("kode_satker"))
    if (not b or not sr or not kode or kode != _teks(sr.get("kode_satker"))
            or sr.get("doc_type") != "bast" or sr.get("doc_ref") != b.get("id")
            or b.get("signature_request_id") != sr_id or sr.get("status") == "batal"
            or b.get("direvisi_oleh")):
        raise HTTPException(409, "BAST atau permintaan TTD bukan sumber aktif yang sama")
    sidik = sidik_isi_bast(b)
    if sidik != sidik_isi_bast(bast):
        raise HTTPException(409, "Isi BAST berubah ketika PDF disiapkan; kirim ulang dokumen")
    fid = _teks(sr.get("dok_file_id"))
    lama = sr.get("bast_otomasi_manifest")
    if lama:
        if lama.get("bast_sidik") == sidik and lama.get("dok_file_id") == fid:
            return lama
        raise HTTPException(409, "Manifest BAST telah dibekukan untuk isi atau berkas berbeda")
    signers = sr.get("signers") or []
    if (not fid or not signers or len({s.get("signer_id") for s in signers}) != len(signers)
            or any(not _teks(s.get("signer_id")) or not _teks(s.get("nama"))
                   or not _jumlah_wajib(s) or s.get("signature_file_id")
                   or s.get("status") not in {"aktif", "menunggu"} for s in signers)):
        raise HTTPException(409, "PDF dan peserta wajib harus lengkap sebelum pembubuhan dimulai")
    data = await get_document_from_gridfs(fid)
    if not data or not data.lstrip().startswith(b"%PDF-"):
        raise HTTPException(409, "PDF sumber BAST tidak dapat dibaca untuk pembekuan bukti")
    manifest = {"schema": 1, "bast_sidik": sidik, "dok_file_id": fid,
                "dok_sha256": hashlib.sha256(data).hexdigest(),
                "wajib": [{**_identitas_signer(s), "jumlah_ttd": _jumlah_wajib(s)} for s in signers],
                "dibekukan_pada": datetime.now(timezone.utc).isoformat()}
    res = await db.signature_requests.update_one(
        {"id": sr_id, "dok_file_id": fid, "signers": signers,
         "status": sr.get("status"), "bast_otomasi_manifest": {"$exists": False}},
        {"$set": {"bast_otomasi_manifest": manifest}})
    if not res.modified_count:
        terkini = await db.signature_requests.find_one({"id": sr_id}) or {}
        stored = terkini.get("bast_otomasi_manifest") or {}
        if all(stored.get(k) == manifest[k] for k in
               ("schema", "bast_sidik", "dok_file_id", "dok_sha256", "wajib")):
            return stored
        raise HTTPException(409, "Permintaan TTD berubah ketika manifest dibekukan")
    return manifest


def _waktu(value):
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(_teks(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _hasil(sah=False, alasan="", *, jenis="", file_id="", oleh="", bukti=None):
    return {"sah": sah, "alasan": alasan, "jenis": jenis, "file_id": file_id,
            "oleh": oleh, "kunci_bukti": f"{jenis}:{_sidik(bukti)}" if sah else ""}


def _hari_wita():
    return datetime.now(timezone(timedelta(hours=8))).date()


async def _alasan_agenda(db, bast):
    surat_id = _teks(bast.get("surat_id"))
    if not surat_id:
        return ""
    kode = _teks(bast.get("kode_satker"))
    surat = await db.surat.find_one({"id": surat_id})
    if not surat or _teks(surat.get("kode_satker")) != kode:
        return "Nomor agenda BAST tidak tersedia dalam satker yang sama"
    if surat.get("dihapus") or surat.get("status") == "dibatalkan":
        return "Nomor agenda BAST telah dihapus atau dibatalkan"
    # Booking sendiri boleh: gateway mengesahkan agenda setelah proyeksi
    # lengkap. Panah dari naskah lain yang masih booking belum berlaku.
    relasi = await db.surat_relasi.find({"ke_id": surat_id, "jenis": {"$in": [
        "mencabut", "membatalkan", "mengubah", "mencabut_sebagian"]}}).to_list(None)
    if not relasi:
        return ""
    sumber = {s["id"]: s async for s in db.surat.find(
        {"id": {"$in": list({r.get("dari_id") for r in relasi})}})}
    for rel in relasi:
        doc = sumber.get(rel.get("dari_id"))
        if (not doc or _teks(doc.get("kode_satker")) != kode
                or _teks(rel.get("kode_satker")) != kode):
            return "Relasi perubahan BAST perlu ditinjau karena sumbernya tidak cocok"
        if not doc.get("dihapus") and doc.get("status") not in {"dibooking", "dibatalkan"}:
            return "Nomor agenda BAST dicabut atau diubah; perlu tinjauan dasar amanah"
    return ""


async def evaluasi_bast_sah(db, bast) -> dict:
    """Satu keputusan untuk sinkronisasi DAN guard per-request portal.

    `sah` berarti memenuhi gerbang bukti aplikasi, bukan penilaian hukum atau
    izin mengubah jurnal akuntansi. Pemegang/aset terkini diperiksa pemanggil.
    """
    b = bast or {}
    kode = _teks(b.get("kode_satker"))
    if not b.get("id") or not kode:
        return _hasil(alasan="Identitas BAST dan satker wajib lengkap")
    if b.get("direvisi_oleh"):
        return _hasil(alasan="BAST telah digantikan atau dicabut oleh dokumen lain")
    if b.get("jenis") == "penggunaan_sementara" and _teks(b.get("jangka_dari")):
        try:
            mulai = date.fromisoformat(_teks(b["jangka_dari"]))
        except (ValueError, TypeError, OverflowError):
            return _hasil(alasan="Tanggal mulai penggunaan sementara perlu diperbaiki")
        if mulai > _hari_wita():
            return _hasil(alasan=f"Penggunaan sementara belum dimulai; sinkronkan kembali pada {mulai.isoformat()}")
    # Jangka selesai bukan bukti barang sudah dikembalikan: akses pelaporan
    # tetap hidup sampai pengembalian/pencabutan sah, tanpa cron tersembunyi.
    alasan_agenda = await _alasan_agenda(db, b)
    if alasan_agenda:
        return _hasil(alasan=alasan_agenda)
    sidik = sidik_isi_bast(b)
    sr_id = _teks(b.get("signature_request_id"))
    sr = await db.signature_requests.find_one({"id": sr_id}) if sr_id else None

    # Scan sesudah pembatalan elektronik dapat menjadi bukti baru, tetapi
    # scan yang diverifikasi SEBELUM pembatalan tidak boleh membangkitkannya.
    bukti = b.get("bukti") or {}
    waktu_basah = _waktu(bukti.get("diverifikasi_pada"))
    waktu_batal = _waktu((sr or {}).get("batal_pada"))
    basah_setelah_batal = (not sr or sr.get("status") != "batal"
                          or bool(waktu_basah and waktu_batal and waktu_basah > waktu_batal))
    if (bukti.get("verifikasi_lengkap") is True and _teks(bukti.get("diverifikasi_oleh"))
            and waktu_basah and bukti.get("bast_sidik") == sidik
            and _teks(bukti.get("file_id")) and _HASH.fullmatch(_teks(bukti.get("sha256")))
            and basah_setelah_batal):
        kunci = {k: bukti.get(k) for k in ("bast_sidik", "file_id", "sha256", "diverifikasi_oleh", "diverifikasi_pada")}
        return _hasil(True, "Bukti tanda tangan basah telah diperiksa lengkap", jenis="basah",
                      file_id=bukti["file_id"], oleh=bukti["diverifikasi_oleh"], bukti=kunci)
    if not sr:
        return _hasil(alasan="Bukti lengkap belum diverifikasi")
    if sr.get("doc_type") != "bast" or sr.get("doc_ref") != b["id"] or _teks(sr.get("kode_satker")) != kode:
        return _hasil(alasan="Permintaan TTD tidak cocok dengan BAST dan satker")
    if sr.get("status") != "selesai":
        return _hasil(alasan="Permintaan TTD dibatalkan atau belum selesai divalidasi")
    manifest = sr.get("bast_otomasi_manifest") or {}
    fid = _teks(sr.get("dok_file_id"))
    if (manifest.get("schema") != 1 or manifest.get("bast_sidik") != sidik
            or not fid or manifest.get("dok_file_id") != fid
            or not _HASH.fullmatch(_teks(manifest.get("dok_sha256")))):
        return _hasil(alasan="Manifest PDF tidak tersedia atau isi BAST berubah")
    if not isinstance(sr.get("posisi_qr"), dict) or not sr["posisi_qr"]:
        return _hasil(alasan="QR dokumen final belum ditempatkan")
    signers = sr.get("signers") or []
    if (not signers or len({s.get("signer_id") for s in signers}) != len(signers)
            or any(not sudah_terverifikasi(s) or not _teks(s.get("signature_file_id"))
                   or not _teks(s.get("hash")) for s in signers)):
        return _hasil(alasan="Seluruh peserta dan bukti pembubuhan belum tervalidasi")
    wajib = manifest.get("wajib") or []
    if not wajib:
        return _hasil(alasan="Manifest peserta wajib BAST kosong")
    by_id = {s.get("signer_id"): s for s in signers}
    for item in wajib:
        signer = by_id.get(item.get("signer_id"))
        if not signer or _identitas_signer(signer) != _identitas_signer(item):
            return _hasil(alasan="Peserta wajib BAST telah dihapus atau identitasnya berubah")
        jumlah = jumlah_pembubuhan(signer.get("posisi_ttd"), signer.get("posisi_ttd_lain"))
        minimum = _jumlah_wajib(item)
        deklarasi = (signer.get("deklarasi_tanpa_area") is True and jumlah >= 1
                      and _teks(signer.get("validation_note")) and _teks(signer.get("validated_by")))
        if not minimum or (jumlah < minimum and not deklarasi):
            return _hasil(alasan="Area pembubuhan peserta wajib belum lengkap atau belum diperiksa")
    kunci = {"sr_id": sr_id, "bast_sidik": sidik, "dok_file_id": fid,
             "dok_sha256": manifest["dok_sha256"], "posisi_qr": sr["posisi_qr"],
             "bukti_signers": [{k: s.get(k) for k in ("signer_id", "signature_file_id", "hash",
                                   "posisi_ttd", "posisi_ttd_lain", "validated_at", "validated_by")}
                                for s in signers]}
    return _hasil(True, "Dokumen elektronik lengkap dan tervalidasi", jenis="esign", file_id=fid,
                  oleh=_teks(sr.get("finalized_by")) or _teks(sr.get("created_by")), bukti=kunci)
