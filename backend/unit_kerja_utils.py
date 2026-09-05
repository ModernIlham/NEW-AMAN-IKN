"""Master Unit Kerja berjenjang (Eselon I–V) — LOGIKA MURNI (teruji unit).

Adopsi pola KERJA-BARENG `UnitKerjaManager`: unit disimpan hierarkis
{nama_unit, eselon "1".."5", parent_id} sehingga form pegawai dapat memakai
pilihan BERTINGKAT (opsi Eselon N mengikuti induk Eselon N-1 yang dipilih)
dan laporan BMN dapat direkap per unit organisasi resmi.

Modul ini mengurus PEMETAAN antara pohon dan kolom teks eselon1–5 milik
pegawai. Aturan tentang apa yang sah pada pohonnya sendiri — tingkat, induk,
pemindahan, penghapusan — ada di `organisasi_utils`, dan hanya di sana.
`validate_unit` di sini pernah menjadi salinan keduanya; salinan itu sudah
menyimpang dari rutenya (satu menolak, satu meloloskan) sebelum sempat
dipakai bersama, dan kini dihapus.
"""
import organisasi_utils as org

#: Tetap di sini sebagai bentuk STRING karena kolom `eselon` pegawai dan
#: unit_kerja memang string; sumber angkanya satu, di `organisasi_utils`.
ESELON_SAH = tuple(str(b["level"]) for b in org.daftar_level())


def opsi_bertingkat(units, pilihan):
    """Opsi nama unit per level MENGIKUTI induk terpilih. MURNI.

    `units` = daftar master; `pilihan` = {eselon1..eselon5: nama terpilih}.
    Kembalikan {eselon1: [nama...], ..., eselon5: [...]} — level 1 semua unit
    eselon 1; level N hanya anak dari unit induk terpilih (dicocokkan via
    nama, krn data pegawai menyimpan NAMA unit). Induk tak dipilih/tak
    dikenal → daftar level itu berisi SEMUA unit eselon N (tetap membantu).
    """
    per_es = {es: [u for u in (units or []) if str(u.get("eselon")) == es]
              for es in ESELON_SAH}
    by_id = {u.get("id"): u for u in (units or [])}
    hasil = {}
    hasil["eselon1"] = [u["nama_unit"] for u in per_es["1"]]
    for n in range(2, 6):
        es = str(n)
        induk_nama = str((pilihan or {}).get(f"eselon{n - 1}") or "").strip()
        induk = next((u for u in per_es[str(n - 1)]
                      if u.get("nama_unit") == induk_nama), None)
        if induk:
            anak = [u["nama_unit"] for u in per_es[es]
                    if u.get("parent_id") == induk.get("id")]
        else:
            anak = [u["nama_unit"] for u in per_es[es]]
        hasil[f"eselon{n}"] = anak
    # rujukan silang id→unit tak dipakai keluar, tapi cegah lint unused
    _ = by_id
    return hasil


def unit_dari_pegawai(pegawai_list):
    """Derivasi master unit hierarkis dari data pegawai (eselon1..5). MURNI.

    Tiap pegawai menyumbang jalur unitnya: eselon1 "A" → eselon2 "B" (induk
    A) → dst. Kembalikan daftar {nama_unit, eselon, induk_nama} UNIK per
    (eselon, nama, induk) — bahan upsert massal (bangun master 1-klik dari
    data impor).
    """
    seen = set()
    hasil = []
    for p in (pegawai_list or []):
        induk = ""
        for n in range(1, 6):
            nama = str((p or {}).get(f"eselon{n}") or "").strip()
            if not nama:
                break  # jalur putus — level di bawahnya tak sah tanpa induk
            kunci = (str(n), nama, induk)
            if kunci not in seen:
                seen.add(kunci)
                hasil.append({"nama_unit": nama, "eselon": str(n),
                              "induk_nama": induk})
            induk = nama
    return hasil
