"""Daftar periksa dokumen usulan BMN — rute referensi lintas modul.

Sengaja berdiri sendiri, bukan menempel di `routes/penggunaan.py`: daftar
periksa yang sama dipakai pemindahtanganan (hibah/penjualan/tukar menukar),
penghapusan, pemusnahan, dan pemanfaatan. Menaruhnya di satu modul rezim
akan membuat modul lain mengimpor lintas-rezim atau, lebih buruk, menyalin
daftarnya.

Rute ini murni MEMBACA tabel — tidak menyentuh basis data sama sekali.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth_utils import require_user
from syarat_dokumen_utils import (
    JENIS_OBJEK, REZIM, jenis_pilihan, kelengkapan_dokumen,
)

syarat_dokumen_router = APIRouter()


def _konteks(jenis_objek, punya_dokumen_kepemilikan, ada_fotokopi,
             unggah_pindaian, dokumen_tidak_ada, dokumen_hilang,
             penandatangan_didelegasikan, untuk_pmpp, fisik_tak_dikuasai,
             ada_pungutan_masyarakat, kspi, penerima_lembaga_nonpemerintah):
    return {
        "jenis_objek": jenis_objek,
        "punya_dokumen_kepemilikan": punya_dokumen_kepemilikan,
        "ada_fotokopi": ada_fotokopi,
        "unggah_pindaian": unggah_pindaian,
        "dokumen_tidak_ada": dokumen_tidak_ada,
        "dokumen_hilang": dokumen_hilang,
        "penandatangan_didelegasikan": penandatangan_didelegasikan,
        "untuk_pmpp": untuk_pmpp,
        "fisik_tak_dikuasai": fisik_tak_dikuasai,
        "ada_pungutan_masyarakat": ada_pungutan_masyarakat,
        "kspi": kspi,
        "penerima_lembaga_nonpemerintah": penerima_lembaga_nonpemerintah,
    }


@syarat_dokumen_router.get("/syarat-dokumen/rezim")
async def daftar_rezim(_user: dict = Depends(require_user)):
    """Rezim usulan yang dikenal + jenis objek, untuk mengisi pilihan."""
    return {
        "rezim": [{"kode": k, "nama": v} for k, v in REZIM.items()],
        "jenis_objek": [{"kode": k, "nama": v} for k, v in JENIS_OBJEK.items()],
    }


@syarat_dokumen_router.get("/syarat-dokumen")
async def daftar_syarat(
    rezim: str,
    jenis_objek: str = "",
    punya_dokumen_kepemilikan: bool = False,
    # Bawaan True untuk dua butir berikut: berkas usulan BMN nyaris selalu
    # memuat fotokopi, dan seluruh alur SIMAN V2 adalah unggahan arsip
    # digital. Bawaan False akan menyembunyikan dua surat keterangan yang
    # justru paling sering terlupa.
    ada_fotokopi: bool = True,
    unggah_pindaian: bool = True,
    dokumen_tidak_ada: bool = False,
    dokumen_hilang: bool = False,
    penandatangan_didelegasikan: bool = False,
    untuk_pmpp: bool = False,
    fisik_tak_dikuasai: bool = False,
    ada_pungutan_masyarakat: bool = False,
    kspi: bool = False,
    penerima_lembaga_nonpemerintah: bool = False,
    # Bawaan `str = ""` polos, BUKAN `Query("")`: seluruh uji unit repo ini
    # memanggil fungsi rutenya langsung tanpa FastAPI, dan objek `Query`
    # akan sampai apa adanya ke `.split()`.
    terunggah: str = "",
    _user: dict = Depends(require_user),
):
    """Daftar periksa dokumen + ringkas kelengkapannya untuk satu keadaan.

    `terunggah` = kode jenis dokumen yang sudah ada berkasnya, dipisah koma.
    """
    if rezim not in REZIM:
        raise HTTPException(
            status_code=400,
            detail=f"Rezim tidak dikenal (pilihan: {', '.join(REZIM)})")
    if jenis_objek and jenis_objek not in JENIS_OBJEK:
        raise HTTPException(
            status_code=400,
            detail=f"Jenis objek tidak dikenal (pilihan: {', '.join(JENIS_OBJEK)})")
    konteks = _konteks(
        jenis_objek, punya_dokumen_kepemilikan, ada_fotokopi, unggah_pindaian,
        dokumen_tidak_ada, dokumen_hilang, penandatangan_didelegasikan,
        untuk_pmpp, fisik_tak_dikuasai, ada_pungutan_masyarakat, kspi,
        penerima_lembaga_nonpemerintah)
    punya = [t.strip() for t in (terunggah or "").split(",") if t.strip()]
    hasil = kelengkapan_dokumen(rezim, punya, konteks)
    hasil["pilihan"] = jenis_pilihan(rezim, konteks)
    return hasil
