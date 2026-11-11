"""Direktori gabungan: mengenali seseorang lewat nomornya di Master Pegawai
internal DAN di direktori orang luar.

Rencana: `docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md` (PGW-06; kontrak 6.5).

Aturan yang dipegang modul ini:
- **Internal menang.** Nomor yang ada di kedua koleksi dikenali sebagai
  internal (invarian 4 sebenarnya mencegah kembaran baru; ini menjaga data
  lama).
- **Scope hanya untuk internal.** `scope_internal` diserahkan pemanggil —
  biasanya `partial(scope_query_field_satker, user)` — dan hanya dikenakan
  pada `pegawai`. `pegawai_luar` adalah direktori bersama tanpa scope.
- **Hanya baca.** Tidak ada penulisan ke koleksi mana pun.
"""
from organisasi_luar_utils import kunci_ikon as _kunci_ikon_kelompok

PROYEKSI_RINGKAS = {
    "_id": 0, "id": 1, "nama": 1, "nip": 1, "jabatan": 1, "unit_kerja": 1,
    "email": 1, "alamat": 1, "status": 1, "status_kepegawaian": 1,
    "foto_file_id": 1, "eselon1": 1, "eselon2": 1, "eselon3": 1, "eselon4": 1,
    "eselon5": 1,
}
PROYEKSI_RINGKAS_LUAR = {
    **PROYEKSI_RINGKAS, "kelompok": 1, "tataran": 1, "jenis_instansi": 1,
    "instansi_id": 1, "instansi_nama": 1, "provinsi_nama": 1,
    "satker_luar_id": 1, "satker_luar_nama": 1, "kapasitas_bertindak": 1,
}
STATUS_AKTIF_LUAR = ["aktif", "", None]
BATAS_NOMOR = 500


def _db(database):
    if database is not None:
        return database
    from db import db
    return db


def tandai_internal(doc: dict) -> dict:
    d = dict(doc or {})
    d.update({"ranah": "internal", "kelompok": "internal", "tataran": "",
              "kunci_ikon": "internal"})
    return d


def tandai_luar(doc: dict) -> dict:
    d = dict(doc or {})
    d["ranah"] = "luar"
    d["kunci_ikon"] = _kunci_ikon_kelompok(d.get("kelompok"), d.get("tataran"))
    return d


def _bersihkan_nomor(nips) -> list:
    out, lihat = [], set()
    for n in nips or []:
        s = str(n or "").strip()
        if s and not set(s) <= set(".-_ ") and s not in lihat:
            lihat.add(s)
            out.append(s)
    return out


async def cari_orang(scope_internal, nip, proyeksi=None, database=None,
                     hanya_aktif_luar=False):
    """Satu orang lewat nomornya — internal dulu, lalu luar. None bila tak ada.

    Hasil membawa `ranah`, `kelompok`, dan `kunci_ikon`."""
    d = _db(database)
    n = str(nip or "").strip()
    if not n or set(n) <= set(".-_ "):
        return None
    proj = proyeksi or PROYEKSI_RINGKAS
    q = {"nip": n}
    internal = await d.pegawai.find_one(scope_internal(dict(q)) if scope_internal else q, proj)
    if internal:
        return tandai_internal(internal)
    q_luar = {"nip": n}
    if hanya_aktif_luar:
        q_luar["status"] = {"$in": STATUS_AKTIF_LUAR}
    luar = await d.pegawai_luar.find_one(q_luar, {**proj, **{
        k: 1 for k in PROYEKSI_RINGKAS_LUAR if k != "_id"}})
    return tandai_luar(luar) if luar else None


async def cari_orang_banyak(scope_internal, nips, proyeksi=None, database=None,
                            hanya_aktif_luar=False) -> dict:
    """{nip: dok} untuk sekumpulan nomor — dua kueri `$in`, internal menang.
    Tidak pernah mengembalikan nomor yang tidak ditanyakan."""
    d = _db(database)
    nomor = _bersihkan_nomor(nips)
    if not nomor:
        return {}
    proj = proyeksi or PROYEKSI_RINGKAS
    q = {"nip": {"$in": nomor}}
    hasil = {}
    async for p in d.pegawai.find(scope_internal(dict(q)) if scope_internal else q, proj):
        n = str(p.get("nip") or "").strip()
        if n in nomor and n not in hasil:
            hasil[n] = tandai_internal(p)
    sisa = [n for n in nomor if n not in hasil]
    if sisa:
        q_luar = {"nip": {"$in": sisa}}
        if hanya_aktif_luar:
            q_luar["status"] = {"$in": STATUS_AKTIF_LUAR}
        proj_luar = {**proj, **{k: 1 for k in PROYEKSI_RINGKAS_LUAR if k != "_id"}}
        async for p in d.pegawai_luar.find(q_luar, proj_luar):
            n = str(p.get("nip") or "").strip()
            if n in sisa and n not in hasil:
                hasil[n] = tandai_luar(p)
    return hasil


async def kelompok_nomor(scope_internal, nips, database=None) -> dict:
    """{nip: kunci_ikon} — bahan ikon kelompok. Cakupannya sama dengan
    direktori: internal ter-scope satker pemanggil, luar yang aktif saja."""
    peta = await cari_orang_banyak(
        scope_internal, nips, proyeksi={"_id": 0, "nip": 1}, database=database,
        hanya_aktif_luar=True)
    return {n: d["kunci_ikon"] for n, d in peta.items()}


async def orang_luar_per_nip(nips, proyeksi=None, database=None) -> dict:
    """{nip: dok} dari `pegawai_luar` saja (tanpa scope) — untuk pembaca yang
    sudah memeriksa Master Pegawai internal dengan caranya sendiri dan hanya
    perlu melengkapinya dengan orang luar."""
    d = _db(database)
    nomor = _bersihkan_nomor(nips)
    if not nomor:
        return {}
    hasil = {}
    async for p in d.pegawai_luar.find(
            {"nip": {"$in": nomor}},
            proyeksi or {**PROYEKSI_RINGKAS_LUAR}):
        n = str(p.get("nip") or "").strip()
        if n in nomor and n not in hasil:
            hasil[n] = tandai_luar(p)
    return hasil
