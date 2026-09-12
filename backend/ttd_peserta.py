"""Aturan perubahan peserta permintaan E-sign yang belum final, tanpa I/O."""
from ttd_validasi import sudah_membubuhkan, status_permintaan


def urutan_peserta(s):
    try:
        n = int(s.get("urutan"))
        return n if n > 0 else float("inf")
    except (TypeError, ValueError, OverflowError):
        return float("inf")


def ubah_peserta(sr, aksi, *, baru=None, signer_id="", konfirmasi_final=False):
    """Salinan daftar; bukti/urutan peserta lama tidak disentuh."""
    if sr.get("status") in {"selesai", "batal"}:
        raise ValueError("Daftar penanda tangan dokumen final/batal tidak dapat diubah")
    daftar = [dict(s) for s in (sr.get("signers") or [])]
    if aksi == "tambah":
        if len(daftar) >= 64:
            raise ValueError("Maksimal 64 penanda tangan dalam satu permintaan")
        nama = " ".join(str((baru or {}).get("nama") or "").split()).casefold()
        nip = str((baru or {}).get("nip") or "").strip()
        if not nama:
            raise ValueError("Nama penanda tangan wajib diisi")
        if any((nip and nip == str(s.get("nip") or "").strip()) or
               (not nip and not str(s.get("nip") or "").strip() and nama ==
                " ".join(str(s.get("nama") or "").split()).casefold()) for s in daftar):
            raise ValueError("Penanda tangan tersebut sudah ada dalam permintaan")
        target = dict(baru)
        target["urutan"] = max((urutan_peserta(s) for s in daftar
                               if urutan_peserta(s) != float("inf")), default=len(daftar)) + 1
        target["status"] = "aktif" if sr.get("mode") != "berurutan" else "menunggu"
        daftar.append(target)
    elif aksi == "hapus":
        target = next((s for s in daftar if s.get("signer_id") == signer_id), None)
        if not target:
            raise ValueError("Penanda tangan tidak ditemukan; muat ulang permintaan")
        if sudah_membubuhkan(target) or target.get("status") not in {"aktif", "menunggu"}:
            raise ValueError("Penanda tangan yang sudah membubuhkan tidak boleh dihapus")
        if len(daftar) <= 1:
            raise ValueError("Permintaan harus memiliki minimal satu penanda tangan")
        daftar = [s for s in daftar if s.get("signer_id") != signer_id]
    else:
        raise ValueError("Aksi harus tambah atau hapus")
    if sr.get("mode") == "berurutan" and not any(s.get("status") == "aktif" for s in daftar):
        berikut = min((s for s in daftar if s.get("status") == "menunggu"),
                      key=urutan_peserta, default=None)
        if berikut:
            berikut["status"] = "aktif"
    status = status_permintaan(daftar)
    if status == "selesai" and not konfirmasi_final:
        raise ValueError("Penghapusan menyisakan seluruh pembubuhan tervalidasi. "
                         "Periksa dokumen dan konfirmasikan finalisasi terlebih dahulu")
    return daftar, target, status
