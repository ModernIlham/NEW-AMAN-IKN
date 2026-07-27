"""Hierarki Spasial — registry level + pohon `spasial_node` (Fase 2).

Denah kawasan berlapis: Kawasan → Zona(WP) → Distrik(SWP) → Blok → … → Ruangan
(lihat docs/ARSITEKTUR-SPASIAL-IOT.md). Fase ini menyusun POHON-nya; geometri
(gambar poligon, deteksi lokasi otomatis) menyusul di Fase 3.

ISOLASI SATKER (REVIEW-9 R9). Denah itu fisik dan melekat pada satker, jadi ia
BUKAN referensi universal: node baru distempel `kode_satker`, daftar di-scope,
dan baca/ubah/hapus di-guard. `spasial_level` sebaliknya adalah registry
tata kelola GLOBAL (kode_satker "") yang di-seed sekali.

Pola pohon HYBRID: `parent_id` satu-satunya yang boleh diedit pengguna;
`ancestors[]` + `jalur` SELALU diturunkan darinya oleh helper murni di
`spasial_utils`. Memindah sebuah node berarti menulis ulang seluruh keturunannya.
"""
import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     Request, UploadFile)
from pydantic import BaseModel

from auth_utils import require_user, require_user_or_query_token, require_writer
from db import db
from shared_utils import (kode_satker_user, limiter, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)
import spasial_utils as su
import topologi_utils as tu

spasial_router = APIRouter()

_PROJ = {"_id": 0}
_MAKS_NODE = 20000  # plafon per satker; denah kawasan besar pun jauh di bawah ini


# ── Registry level (global, di-seed) ────────────────────────────────────────

def _dok_level_seed() -> list:
    """13 baris registry default (preset ikn_akrab jadi label_ui)."""
    docs = []
    for ordinal, kode, label_akrab, label_baku, containment in su.LEVEL_SPASIAL:
        docs.append({
            "id": f"lvl-{kode.lower()}",
            "kode_satker": "",
            "ordinal_level": ordinal,
            "kode_baku": kode,
            "label_ui": label_akrab,
            "label_baku": label_baku,
            "validasi_containment": containment,
            "punya_ordinal_lantai": kode == "LANTAI",
            "wajib": kode == su.KODE_LEVEL_WAJIB,
            "aktif": True,
        })
    return docs


async def _ambil_level() -> list:
    """Registry level; seed sekali bila kosong (idempoten, aman multi-worker
    lewat indeks unik `id`)."""
    ada = await db.spasial_level.find({}, _PROJ).sort("ordinal_level", 1).to_list(100)
    if ada:
        return ada
    try:
        await db.spasial_level.insert_many(_dok_level_seed(), ordered=False)
    except Exception:
        pass  # balapan seed antar-worker → yang kalah mengabaikan duplikat
    return await db.spasial_level.find({}, _PROJ).sort("ordinal_level", 1).to_list(100)


@spasial_router.get("/spasial/level")
async def daftar_level(preset: str = Query("ikn_akrab"),
                       _user: dict = Depends(require_user)):
    """Registry tingkat spasial (terbesar→terkecil). `preset` memilih label yang
    ditampilkan ke operator; `kode_baku` selalu sama untuk ekspor/dokumen resmi."""
    rows = await _ambil_level()
    pakai_baku = preset == "rdtr_baku"
    for r in rows:
        r["label"] = r.get("label_baku") if pakai_baku else r.get("label_ui")
    return {"items": rows, "jumlah": len(rows), "preset": preset,
            "preset_tersedia": list(su.PRESET_PENAMAAN)}


# ── Node pohon ──────────────────────────────────────────────────────────────

class LantaiIn(BaseModel):
    ordinal: Optional[int] = None
    label: Optional[str] = ""
    label_pendek: Optional[str] = ""
    kategori: Optional[str] = ""


class NodeIn(BaseModel):
    tipe: str                          # kode_baku level, mis. "GEDUNG"
    nama: str
    kode: Optional[str] = ""
    parent_id: Optional[str] = ""
    nama_alias: Optional[list] = None
    lantai: Optional[LantaiIn] = None
    zona_kode: Optional[str] = ""
    subzona_kode: Optional[str] = ""
    fungsi_kawasan: Optional[str] = ""
    properties: Optional[dict] = None
    # None = "tak diubah" pada PUT (dan "aktif" pada POST) — default "aktif"
    # di sini dulunya membuat status yang TAK dikirim klien tak terbedakan
    # dari "aktif" eksplisit, sehingga edit apa pun mengaktifkan draft.
    status: Optional[str] = None
    # Geometri GeoJSON (Fase 3). None = tak diubah pada PUT; {} = dikosongkan.
    geometry: Optional[dict] = None
    prioritas: Optional[int] = None    # kurasi manusia saat area bertumpuk


def _bersih_node(p: NodeIn) -> dict:
    tipe = str(p.tipe or "").strip().upper()
    doc = {
        "tipe": tipe,
        "nama": str(p.nama or "").strip(),
        "kode": str(p.kode or "").strip(),
        "parent_id": str(p.parent_id or "").strip() or None,
        "nama_alias": [str(a).strip() for a in (p.nama_alias or []) if str(a).strip()],
        "zona_kode": str(p.zona_kode or "").strip(),
        "subzona_kode": str(p.subzona_kode or "").strip(),
        "fungsi_kawasan": str(p.fungsi_kawasan or "").strip(),
        # None = "tak diubah" (semantik yang sama dengan geometry) — pemanggil
        # create/update yang memutuskan nilai akhirnya. Dulu None dipetakan ke
        # {}/"aktif" di sini, dan itu dua bug senyap sekaligus: klien yang tak
        # mengirim properties MENGHAPUS jejak impor + overlay denah, dan klien
        # yang tak mengirim status MENGAKTIFKAN draft diam-diam (temuan Fase 7).
        "properties": dict(p.properties) if p.properties is not None else None,
        # Whitelist status — klien TAK boleh menyetel "dihapus" (lihat STATUS_SAH).
        "status": (lambda s: s if s in STATUS_SAH else None)(
            str(p.status or "").strip().lower()),
    }
    # Data lantai hanya bermakna untuk tipe LANTAI.
    if tipe == "LANTAI" and p.lantai is not None:
        lt = p.lantai
        doc["lantai"] = {
            "ordinal": int(lt.ordinal) if lt.ordinal is not None else None,
            "label": str(lt.label or "").strip(),
            "label_pendek": str(lt.label_pendek or "").strip(),
            "kategori": str(lt.kategori or "").strip(),
        }
        doc["lantai_ordinal"] = doc["lantai"]["ordinal"]
    else:
        doc["lantai"] = None
        # Buang turunan basi bila tipe diubah dari LANTAI ke tipe lain.
        doc["lantai_ordinal"] = None
    if p.prioritas is not None:
        doc["prioritas"] = int(p.prioritas)
    return doc


def _terapkan_geometri(doc: dict, geometry) -> None:
    """Sisipkan geometri + field TURUNANNYA (bbox, titik wakil, luas) ke `doc`.

    `geometry` None berarti "tidak diubah" (PUT parsial); dict kosong berarti
    "kosongkan". Geometri divalidasi DULU — geometri rusak yang lolos ke DB
    membuat pembangunan indeks 2dsphere gagal untuk SELURUH koleksi, bukan
    hanya untuk dokumen itu.

    Turunan disimpan karena kueri deteksi sengaja TIDAK memproyeksikan
    `geometry` (demi SLA), sehingga pemeringkatan "area terkecil menang" harus
    memakai `metrik.luas_m2` yang tersimpan.
    """
    if geometry is None:
        return
    if not geometry:                      # {} / falsy → kosongkan
        doc["geometry"] = None
        doc["bbox"] = None
        doc["titik_wakil"] = None
        doc["metrik"] = None
        return
    galat = su.validasi_geometri(geometry)
    if galat:
        raise HTTPException(status_code=400, detail=f"Geometri tidak valid: {galat}")
    # Topologi (Fase 4) — bow-tie, lubang di luar shell, cincin tumpang-tindih.
    # BLOKIR, bukan peringatan: geometri begini merusak pembangunan indeks
    # 2dsphere untuk SELURUH koleksi. Bila shapely absen, cek ini melewati
    # dirinya sendiri dan MongoDB kembali jadi jaring terakhir (perilaku Fase 3).
    galat_topo = tu.validasi_topologi(geometry)   # dijaga plafon MAKS_TITIK_TOPOLOGI
    if galat_topo:
        raise HTTPException(status_code=400,
                            detail=f"Topologi tidak valid: {galat_topo}")
    doc["geometry"] = geometry
    doc["bbox"] = su.hitung_bbox(geometry)
    doc["titik_wakil"] = su.titik_wakil(geometry)
    doc["metrik"] = {"luas_m2": round(su.luas_kasar_m2(geometry), 2),
                     "dihitung_pada": datetime.now(timezone.utc).isoformat()}


# Status yang boleh diset klien. "dihapus" TIDAK termasuk — hapus adalah operasi
# DELETE yang menghapus dokumen, bukan status yang bisa dikirim lewat form (kalau
# tidak, klien bisa menyembunyikan node sambil meyatimkan anaknya — temuan tinjauan).
STATUS_SAH = {"aktif", "draft", "nonaktif"}


async def _peta_parent_satker(_user: dict) -> dict:
    """{id: parent_id} untuk node dalam JANGKAUAN USER — dipakai deteksi siklus &
    penurunan ulang keturunan. DI-SCOPE ke satker user (bukan satker node): tanpa
    ini, mengedit node yatim ber-kode "" akan memuat pohon SEMUA satker dan cascade
    dapat menulis ulang node satker lain (temuan tinjauan). Ringan: dua field."""
    return {n["id"]: n.get("parent_id")
            async for n in db.spasial_node.find(
                scope_query_field_satker(_user), {"_id": 0, "id": 1, "parent_id": 1})}


async def _susun_derivasi(node_id: str, parent_id, _user: dict) -> dict:
    """Field pohon turunan + validasi induk. Melempar HTTPException(400/403)
    bila induk tak sah."""
    if not parent_id:
        return {"parent_id": None, "ancestors": [], "ancestors_nama": [],
                "jalur": su.bangun_jalur([], node_id), "kedalaman": 0}
    induk = await db.spasial_node.find_one(
        {"id": parent_id, "status": {"$ne": "dihapus"}},
        {"_id": 0, "id": 1, "tipe": 1, "nama": 1, "ancestors": 1,
         "ancestors_nama": 1, "kode_satker": 1})
    if not induk:
        raise HTTPException(status_code=400, detail="Induk tidak ditemukan")
    await pastikan_akses_dok_satker(_user, induk)  # isolasi satker
    anc = [*(induk.get("ancestors") or []), parent_id]
    anc_nama = [*(induk.get("ancestors_nama") or []), induk.get("nama", "")]
    return {"parent_id": parent_id, "ancestors": anc, "ancestors_nama": anc_nama,
            "jalur": su.bangun_jalur(anc, node_id), "kedalaman": len(anc),
            "_tipe_induk": induk.get("tipe")}


def _validasi_level(tipe: str, tipe_induk: Optional[str]):
    lv = su.level_dari_kode(tipe)
    if not lv:
        raise HTTPException(status_code=400,
                            detail=f"Tipe tingkat '{tipe}' tidak dikenal")
    if tipe_induk and not su.parent_level_sah(tipe_induk, tipe):
        raise HTTPException(
            status_code=400,
            detail=f"'{su.level_dari_kode(tipe_induk)['label']}' tidak dapat menjadi "
                   f"induk '{lv['label']}' — induk harus tingkat yang lebih luas.")


async def _cek_kode_unik(kode: str, tipe: str, _user: dict, kecuali_id=None):
    """Keunikan kode DALAM JANGKAUAN USER (scope by user, bukan satker node) —
    supaya cek tak bocor ke satker lain saat menyunting node yatim ber-kode ""."""
    if not kode:
        return
    q = scope_query_field_satker(_user, {"kode": kode, "tipe": tipe,
                                         "status": {"$ne": "dihapus"}})
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    if await db.spasial_node.find_one(q, {"_id": 1}):
        raise HTTPException(status_code=400,
                            detail=f"Kode '{kode}' sudah dipakai node {tipe} lain di satker ini")


@spasial_router.get("/spasial/node")
async def daftar_node(parent_id: str = Query(""), tipe: str = Query(""),
                      q: str = Query(""), _user: dict = Depends(require_user)):
    """Daftar node satker. `parent_id` mengambil anak langsung (untuk pohon
    lazy-expand); `tipe` & `q` menyaring. Tanpa parent_id → seluruh node satker."""
    query = scope_query_field_satker(_user, {"status": {"$ne": "dihapus"}})
    if parent_id:
        query["parent_id"] = parent_id
    if tipe:
        query["tipe"] = tipe.strip().upper()
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"nama": rx}, {"kode": rx}, {"nama_alias": rx}]
    items = await (db.spasial_node.find(query, {**_PROJ, "geometry": 0})
                   .sort([("ordinal_level", 1), ("kode", 1), ("nama", 1)])
                   .to_list(_MAKS_NODE))
    return {"items": items, "jumlah": len(items)}


@spasial_router.get("/spasial/node/{node_id}")
async def detail_node(node_id: str, _user: dict = Depends(require_user)):
    node = await db.spasial_node.find_one({"id": node_id}, _PROJ)
    if not node or node.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    await pastikan_akses_dok_satker(_user, node)  # isolasi satker
    # Gambar denah yang berlaku untuk editor node ini — miliknya sendiri atau
    # warisan moyang terdekat (ruangan memakai denah lantainya). Fase 7.
    node["overlay_efektif"] = await _overlay_efektif(node)
    return node


async def _peringatan_containment(geometry, tipe: str, parent_id, _user: dict):
    """PESAN peringatan bila bentuk keluar dari batas induknya, atau None.

    PERINGATAN — bukan pemblokir (lihat kebijakan di topologi_utils): poligon
    digambar orang berbeda pada waktu berbeda, dan seluruh desain deteksi
    Fase 3 sudah menerima containment yang tak sempurna. Memblokir di sini
    berarti gedung yang benar tak bisa disimpan hanya karena batas kawasan
    digambar kasar. Induk dicari TER-SCOPE satker — menebak parent_id milik
    satker lain sekadar menghasilkan "induk tak ketemu" = tanpa peringatan.
    """
    if not geometry or not isinstance(geometry, dict) or not parent_id:
        return None
    level = su.level_dari_kode(tipe)
    mode = (level or {}).get("containment")
    if mode in tu.MODE_TANPA_CEK:
        return None
    induk = await db.spasial_node.find_one(
        scope_query_field_satker(_user, {"id": parent_id}),
        {"_id": 0, "geometry": 1, "nama": 1})
    if not induk or not induk.get("geometry"):
        return None
    # Operasi GEOS (buffer/covers/difference) di THREAD — handler ini `async`,
    # dan memanggil shapely langsung membekukan event loop worker untuk SEMUA
    # pengguna selama perhitungan berjalan (temuan tinjauan).
    pesan = await asyncio.to_thread(
        tu.validasi_containment, geometry, induk["geometry"], mode)
    if pesan:
        return f"Terhadap induk \"{induk.get('nama') or parent_id}\": {pesan}"
    return None


@spasial_router.post("/spasial/node")
async def buat_node(payload: NodeIn, _user: dict = Depends(require_writer)):
    doc = _bersih_node(payload)
    if not doc["nama"]:
        raise HTTPException(status_code=400, detail="Nama wajib diisi")
    # Node baru: None jatuh ke bawaan; denah_overlay TIDAK boleh disetel dari
    # sini — ia dikelola endpoint overlay (bersama blob GridFS-nya).
    doc["properties"] = doc["properties"] or {}
    doc["properties"].pop("denah_overlay", None)
    doc["status"] = doc["status"] or "aktif"
    kode_satker = kode_satker_user(_user)
    node_id = "sn_" + str(uuid.uuid4())
    deriv = await _susun_derivasi(node_id, doc["parent_id"], _user)
    _validasi_level(doc["tipe"], deriv.pop("_tipe_induk", None))
    await _cek_kode_unik(doc["kode"], doc["tipe"], _user)
    _terapkan_geometri(doc, payload.geometry)
    now = datetime.now(timezone.utc).isoformat()
    doc.update(deriv)
    doc.update({
        "id": node_id, "kode_satker": kode_satker,
        "ordinal_level": su.ordinal_level(doc["tipe"]),
        "versi": 1, "created_at": now, "updated_at": now,
        "created_by": _user.get("username", "system"),
        "updated_by": _user.get("username", "system"),
    })
    await db.spasial_node.insert_one(dict(doc))
    await log_audit("buat_spasial_node", "", node_id,
                    username=_user.get("username", "system"), kode_satker=kode_satker,
                    detail=f"Tambah {doc['tipe']} — {doc['nama']}")
    peringatan = await _peringatan_containment(
        payload.geometry, doc["tipe"], doc["parent_id"], _user)
    return {"ok": True, "id": node_id,
            "peringatan": [peringatan] if peringatan else []}


@spasial_router.put("/spasial/node/{node_id}")
async def ubah_node(node_id: str, payload: NodeIn,
                    _user: dict = Depends(require_writer)):
    lama = await db.spasial_node.find_one({"id": node_id}, _PROJ)
    if not lama or lama.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    await pastikan_akses_dok_satker(_user, lama)  # isolasi satker
    doc = _bersih_node(payload)
    if not doc["nama"]:
        raise HTTPException(status_code=400, detail="Nama wajib diisi")
    # None = tak diubah: klien yang tak mengirim properties/status (form pohon)
    # tak boleh menghapus jejak impor + overlay atau MENGAKTIFKAN draft
    # diam-diam (temuan Fase 7 — dua-duanya sempat terjadi lewat default lama).
    #
    # `properties` TIDAK di-$set utuh melainkan per-kunci (dotted), dan kunci
    # `denah_overlay` TAK PERNAH disentuh PUT ini — menulis balik snapshot
    # `lama` kalah balapan dengan unggah/hapus overlay yang mendarat di
    # sela baca-tulis: node bisa menunjuk blob GridFS yang sudah dihapus
    # (temuan tinjauan). Field itu eksklusif milik endpoint overlay.
    props_klien = doc.pop("properties")
    props_set, props_unset = {}, {}
    if props_klien is not None:
        props_klien.pop("denah_overlay", None)
        for k, v in props_klien.items():
            props_set[f"properties.{k}"] = v
        for k in (lama.get("properties") or {}):
            if k != "denah_overlay" and k not in props_klien:
                props_unset[f"properties.{k}"] = ""
    if doc["status"] is None:
        doc["status"] = lama.get("status") or "aktif"

    parent_baru = doc["parent_id"]
    pindah = parent_baru != lama.get("parent_id")
    nama_berubah = doc["nama"] != lama.get("nama")
    if pindah and parent_baru:
        # Cegah menjadikan diri sendiri / keturunan sebagai induk (subtree hilang).
        peta = await _peta_parent_satker(_user)
        if su.ada_siklus(node_id, parent_baru, peta):
            raise HTTPException(
                status_code=400,
                detail="Node tidak dapat dipindah ke bawah dirinya sendiri.")

    deriv = await _susun_derivasi(node_id, parent_baru, _user)
    _validasi_level(doc["tipe"], deriv.pop("_tipe_induk", None))
    await _cek_kode_unik(doc["kode"], doc["tipe"], _user, kecuali_id=node_id)

    _terapkan_geometri(doc, payload.geometry)
    now = datetime.now(timezone.utc).isoformat()
    doc.update(deriv)
    doc.update({"ordinal_level": su.ordinal_level(doc["tipe"]),
                "updated_at": now, "updated_by": _user.get("username", "system")})
    update = {"$set": {**doc, **props_set}, "$inc": {"versi": 1}}
    if props_unset:
        update["$unset"] = props_unset
    await db.spasial_node.update_one({"id": node_id}, update)

    # Keturunan menyimpan salinan ancestors/jalur/ancestors_nama node ini. Pindah
    # induk mengubah jalur & ancestors mereka; GANTI NAMA saja mengubah
    # ancestors_nama mereka. Keduanya butuh penurunan ulang.
    if pindah or nama_berubah:
        await _turunkan_ulang_keturunan(node_id, deriv["ancestors"],
                                        deriv["ancestors_nama"], doc["nama"], _user)

    await log_audit("ubah_spasial_node", "", node_id,
                    username=_user.get("username", "system"),
                    kode_satker=str(lama.get("kode_satker") or "").strip(),
                    detail=f"Ubah {doc['tipe']} — {doc['nama']}"
                           + (" (pindah induk)" if pindah else ""))
    # Geometri None = tak diubah pada PUT ini → cek containment pada bentuk
    # TERSIMPAN, karena pindah induk pun bisa membuatnya keluar batas.
    geom_cek = payload.geometry if payload.geometry is not None else lama.get("geometry")
    peringatan = await _peringatan_containment(geom_cek, doc["tipe"], parent_baru, _user)
    return {"ok": True, "id": node_id,
            "peringatan": [peringatan] if peringatan else []}


async def _turunkan_ulang_keturunan(node_id: str, anc_baru: list,
                                    anc_nama_baru: list, nama_node: str,
                                    _user: dict):
    """Tulis ulang ancestors/jalur/ancestors_nama SELURUH keturunan setelah node
    dipindah dan/atau diganti nama.

    Dikerjakan di memori lalu satu bulk_write agar tak menembak DB per keturunan.
    Penyaring: keturunan yang jalurnya MEMUAT `,node_id,`. DI-SCOPE ke satker USER
    (bukan node) — mencegah menulis ulang keturunan milik satker lain saat node
    yatim disunting (temuan tinjauan). Derivasi per-keturunan memakai helper murni
    `susun_ulang_keturunan` (teruji) — bug lama menggandakan node_id di ancestors.
    """
    from pymongo import UpdateOne
    ops = []
    cursor = db.spasial_node.find(
        scope_query_field_satker(_user,
                                 {"jalur": {"$regex": f",{re.escape(node_id)},"},
                                  "id": {"$ne": node_id}}),
        {"_id": 0, "id": 1, "ancestors": 1, "ancestors_nama": 1})
    async for k in cursor:
        d = su.susun_ulang_keturunan(
            k.get("ancestors") or [], k.get("ancestors_nama") or [],
            node_id, anc_baru, anc_nama_baru, nama_node, k["id"])
        ops.append(UpdateOne({"id": k["id"]}, {"$set": d}))
    if ops:
        await db.spasial_node.bulk_write(ops, ordered=False)


@spasial_router.delete("/spasial/node/{node_id}")
async def hapus_node(node_id: str, _user: dict = Depends(require_writer)):
    node = await db.spasial_node.find_one(
        {"id": node_id}, {"_id": 0, "id": 1, "nama": 1, "tipe": 1,
                          "kode_satker": 1, "properties.denah_overlay": 1})
    if not node:
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    await pastikan_akses_dok_satker(_user, node)  # isolasi satker
    # Tolak bila punya anak — menghapus induk membuat sub-pohon YATIM yang tak
    # bisa dipastikan kepemilikannya lagi (konsisten dengan fail-closed
    # pastikan_akses_kegiatan_id). Pengguna hapus dari daun ke atas.
    anak = await db.spasial_node.find_one(
        scope_query_field_satker(_user,
                                 {"parent_id": node_id, "status": {"$ne": "dihapus"}}),
        {"_id": 1})
    if anak:
        raise HTTPException(
            status_code=409,
            detail="Node ini masih memiliki anak — hapus atau pindahkan isinya dulu.")
    await db.spasial_node.delete_one({"id": node_id})
    # Node dihapus KERAS — blob overlay di GridFS ikut dibuang, atau ia yatim
    # selamanya (tak ada penyapu untuk metadata.overlay_node). Fase 7.
    ov = (node.get("properties") or {}).get("denah_overlay") or {}
    if ov.get("file_id"):
        try:
            from bson import ObjectId
            from shared_utils import fs_bucket
            await fs_bucket.delete(ObjectId(ov["file_id"]))
        except Exception:
            pass
    await log_audit("hapus_spasial_node", "", node_id,
                    username=_user.get("username", "system"),
                    kode_satker=str(node.get("kode_satker") or "").strip(),
                    detail=f"Hapus {node.get('tipe')} — {node.get('nama')}")
    return {"ok": True, "id": node_id}


# ═══════════════════════════════════════════════════════════════════════════
# DETEKSI LOKASI OTOMATIS (Fase 3) — inti permintaan pemilik
# ═══════════════════════════════════════════════════════════════════════════

# Ordinal GEDUNG. Deteksi dari titik berhenti di sini: lantai & ruangan tak bisa
# dipilih dari koordinat 2D (semua lantai bertumpuk di footprint yang sama),
# jadi pengguna memilih lantai lalu ruangan dideteksi di dalamnya.
ORDINAL_GEDUNG = 80

# Radius pencarian "terdekat" saat titik jatuh di luar SEMUA poligon. Aset di
# lapangan terbuka (tiang, gardu, taman) itu nyata — jangan diblokir, cukup
# tawarkan yang terdekat.
RADIUS_TERDEKAT_M = 500

# Plafon kandidat untuk satu titik. Rantai terdalam yang wajar hanya ~10 tingkat;
# sisanya adalah poligon bertumpuk. Nilainya longgar agar tak pernah memotong
# kasus nyata, tapi tetap ada sebagai pembendung data patologis. Kueri diurutkan
# MENURUN sehingga kalau plafon ini kena, yang terbuang adalah tingkat terluas
# (yang bisa disusun ulang dari `ancestors`), bukan gedung yang dicari.
MAKS_KANDIDAT_TITIK = 200

_PROJ_RANTAI = {"_id": 0, "id": 1, "tipe": 1, "ordinal_level": 1, "nama": 1,
                "kode": 1, "parent_id": 1, "ancestors": 1, "ancestors_nama": 1,
                "prioritas": 1, "metrik": 1}


class TitikIn(BaseModel):
    lon: float
    lat: float
    akurasi_m: Optional[float] = None


class GeometriPratinjauIn(BaseModel):
    geometry: dict
    tipe: Optional[str] = ""
    parent_id: Optional[str] = ""


@spasial_router.post("/spasial/validasi-geometri")
@limiter.limit("60/minute")
async def validasi_geometri_pratinjau(request: Request,
                                      payload: GeometriPratinjauIn,
                                      _user: dict = Depends(require_user)):
    """Periksa geometri TANPA menyimpan — dipanggil editor sebelum "Simpan".

    Mengembalikan galat struktur/topologi (pemblokir), peringatan containment
    (bukan pemblokir), luas kasar, dan — bila topologi rusak — usulan hasil
    `make_valid` sebagai PRATINJAU. Perbaikan otomatis tak pernah diterapkan
    diam-diam saat menyimpan: make_valid bisa memecah poligon atau menggeser
    bentuk, jadi keputusannya harus di tangan operator.

    `require_user` (bukan writer): ini operasi baca murni, dan viewer yang
    membuka editor mode lihat tetap berhak melihat status bentuknya. Karena
    itu pula endpoint ini DIBATASI kecepatannya dan seluruh kerja GEOS-nya
    dijalankan di THREAD — tanpa keduanya, satu akun ber-hak-rendah bisa
    membekukan event loop worker untuk semua orang (temuan tinjauan).
    """
    geom = payload.geometry
    galat = su.validasi_geometri(geom)
    if galat:
        return {"valid": False, "galat": f"Geometri tidak valid: {galat}",
                "peringatan": [], "luas_m2": None, "perbaikan": None,
                "topologi_aktif": tu.topologi_aktif()}
    galat_topo = await asyncio.to_thread(tu.validasi_topologi, geom)
    if galat_topo:
        # `perbaiki_topologi` menjaga plafon ukurannya sendiri, tetapi bentuk
        # yang ditolak KARENA terlalu besar jelas tak perlu dicoba diperbaiki.
        usul = None
        if "terlalu besar" not in galat_topo:
            usul = await asyncio.to_thread(tu.perbaiki_topologi, geom)
            # Usulan hanya dikirim bila BENAR-BENAR lolos seluruh validasi —
            # menawarkan perbaikan yang akan ditolak saat disimpan itu menyesatkan.
            if usul is not None:
                tolak = su.validasi_geometri(usul) or await asyncio.to_thread(
                    tu.validasi_topologi, usul)
                if tolak:
                    usul = None
        return {"valid": False, "galat": f"Topologi tidak valid: {galat_topo}",
                "peringatan": [], "luas_m2": None, "perbaikan": usul,
                "topologi_aktif": tu.topologi_aktif()}
    peringatan = await _peringatan_containment(
        geom, str(payload.tipe or "").strip().upper(),
        str(payload.parent_id or "").strip() or None, _user)
    return {"valid": True, "galat": None,
            "peringatan": [peringatan] if peringatan else [],
            "luas_m2": round(su.luas_kasar_m2(geom), 2),
            "perbaikan": None, "topologi_aktif": tu.topologi_aktif()}


def _ringkas(n: dict) -> dict:
    return {"id": n.get("id"), "tipe": n.get("tipe"), "nama": n.get("nama"),
            "kode": n.get("kode"), "ordinal_level": n.get("ordinal_level")}


@spasial_router.post("/spasial/lokasi-di-titik")
async def lokasi_di_titik(payload: TitikIn, _user: dict = Depends(require_user)):
    """Tancapkan titik → rantai wilayah terdeteksi otomatis.

    SATU kueri `$geoIntersects` mengembalikan SELURUH tingkat yang memuat titik
    sekaligus — inilah alasan pohon disimpan dalam satu koleksi polimorfik.
    `geometry` sengaja TIDAK diproyeksikan (poligon bisa ribuan verteks; SLA
    bergantung pada ini).

    Berhenti di GEDUNG: lantai tak dapat ditentukan dari koordinat 2D. Bila
    gedung hanya punya SATU lantai, lantai itu langsung dikembalikan agar
    operator tak perlu memilih.
    """
    lat = su.parse_lintang(payload.lat)
    lon = su.parse_bujur(payload.lon)
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Koordinat tidak valid")
    titik = {"type": "Point", "coordinates": [lon, lat]}

    # Urut MENURUN (terdalam dulu). Plafon to_list ada untuk membendung data
    # patologis, dan kalau plafon itu kena, yang HARUS selamat adalah tingkat
    # TERDALAM — itulah jawaban yang dicari. Tingkat di atasnya toh disusun ulang
    # dari `ancestors` (lihat su.pilih_rantai), jadi kehilangannya tak berakibat.
    # Dengan urutan MENAIK, pemotongan justru membuang gedung dan menyisakan
    # kawasan — persis kebalikan dari yang dibutuhkan (temuan tinjauan).
    kandidat = await db.spasial_node.find(
        scope_query_field_satker(_user, {
            "status": "aktif",
            "ordinal_level": {"$lte": ORDINAL_GEDUNG},
            "geometry": {"$geoIntersects": {"$geometry": titik}},
        }), _PROJ_RANTAI).sort("ordinal_level", -1).to_list(MAKS_KANDIDAT_TITIK)

    pilih = su.pilih_rantai(kandidat)
    terdalam = pilih["terdalam"]

    if not terdalam:
        # Di luar semua poligon — BUKAN galat. Tawarkan yang terdekat.
        terdekat = await db.spasial_node.find_one(
            scope_query_field_satker(_user, {
                "status": "aktif",
                "ordinal_level": {"$lte": ORDINAL_GEDUNG},
                "geometry": {"$near": {"$geometry": titik,
                                       "$maxDistance": RADIUS_TERDEKAT_M}},
            }), _PROJ_RANTAI)
        return {"ditemukan": False, "rantai": [], "terdekat": _ringkas(terdekat) if terdekat else None,
                "radius_cari_m": RADIUS_TERDEKAT_M,
                "pesan": ("Di luar kawasan terpetakan."
                          + (f" Terdekat: {terdekat.get('nama')}." if terdekat else ""))}

    # Rantai SELALU mengikuti pohon (ancestors), bukan gabungan hasil geo —
    # lihat su.pilih_rantai. Ambil nama leluhur dari snapshot bila ada.
    nama_leluhur = terdalam.get("ancestors_nama") or []
    rantai = [{"id": aid, "nama": (nama_leluhur[i] if i < len(nama_leluhur) else "")}
              for i, aid in enumerate(pilih["ancestors"])]
    rantai.append(_ringkas(terdalam))

    lantai = []
    if int(terdalam.get("ordinal_level") or 0) == ORDINAL_GEDUNG:
        lantai = await db.spasial_node.find(
            scope_query_field_satker(_user, {"parent_id": terdalam["id"], "tipe": "LANTAI",
                                             "status": {"$ne": "dihapus"}}),
            {"_id": 0, "id": 1, "nama": 1, "lantai": 1, "status": 1}
        ).sort("lantai.ordinal", 1).to_list(100)

    # Auto-pilih HANYA boleh dari lantai berstatus aktif. Lantai draft (masih
    # digambar) atau nonaktif (sedang direnovasi) tetap DITAMPILKAN agar operator
    # sadar keberadaannya, tetapi tak boleh ditetapkan diam-diam — gedung dengan
    # satu lantai draft sebelumnya langsung terpilih (temuan tinjauan).
    lantai_aktif = [l for l in lantai if l.get("status") == "aktif"]

    return {
        "ditemukan": True,
        "rantai": rantai,
        "terdalam": _ringkas(terdalam),
        "alternatif": [_ringkas(a) for a in pilih["alternatif"]],
        "lantai": lantai,
        # Gedung 1 lantai AKTIF → langsung terpilih, operator tak perlu memilih.
        "lantai_terpilih": lantai_aktif[0]["id"] if len(lantai_aktif) == 1 else None,
        "perlu_pilih_lantai": len(lantai_aktif) != 1,
        "boleh_auto_ruangan": su.boleh_auto_ruangan(payload.akurasi_m),
        "akurasi_m": payload.akurasi_m,
        "konsisten": pilih["konsisten"],
        "catatan": pilih["catatan"],
    }


@spasial_router.get("/spasial/ruangan-di-titik")
async def ruangan_di_titik(lon: float, lat: float, lantai_id: str,
                           _user: dict = Depends(require_user)):
    """Ruangan yang memuat titik DI DALAM sebuah lantai.

    Nol hasil BUKAN galat: titik bisa berada di koridor/area sirkulasi. Dalam
    kasus itu daftar ruangan lantai tersebut dikembalikan agar operator memilih.
    """
    la = su.parse_lintang(lat)
    lo = su.parse_bujur(lon)
    if la is None or lo is None:
        raise HTTPException(status_code=400, detail="Koordinat tidak valid")
    lantai = await db.spasial_node.find_one(
        {"id": lantai_id}, {"_id": 0, "id": 1, "kode_satker": 1, "nama": 1})
    if not lantai:
        raise HTTPException(status_code=404, detail="Lantai tidak ditemukan")
    await pastikan_akses_dok_satker(_user, lantai)   # isolasi satker

    titik = {"type": "Point", "coordinates": [lo, la]}
    cocok = await db.spasial_node.find(
        scope_query_field_satker(_user, {
            "parent_id": lantai_id, "tipe": "RUANGAN", "status": "aktif",
            "geometry": {"$geoIntersects": {"$geometry": titik}},
        }), _PROJ_RANTAI).to_list(20)
    urut = su.peringkat_kandidat(cocok)
    if urut:
        return {"ditemukan": True, "ruangan": _ringkas(urut[0]),
                "alternatif": [_ringkas(r) for r in urut[1:]]}
    semua = await db.spasial_node.find(
        scope_query_field_satker(_user, {"parent_id": lantai_id, "tipe": "RUANGAN",
                                         "status": {"$ne": "dihapus"}}),
        {"_id": 0, "id": 1, "nama": 1, "kode": 1}).sort("nama", 1).to_list(500)
    return {"ditemukan": False, "ruangan": None, "daftar_ruangan": semua,
            "pesan": f"Titik berada di area sirkulasi {lantai.get('nama') or 'lantai ini'}."}


@spasial_router.get("/spasial/lantai/{gedung_id}")
async def lantai_gedung(gedung_id: str, _user: dict = Depends(require_user)):
    """Lantai sebuah gedung, terurut ordinal (basement → rooftop) untuk switcher."""
    # Proyeksi mencakup semua field yang dibaca `_ringkas` — tanpa `tipe`,
    # `kode`, dan `ordinal_level` respons memang terbentuk, tapi separuh isinya
    # None sehingga klien tak bisa membedakan "tak punya kode" dari "tak dikirim".
    gedung = await db.spasial_node.find_one(
        {"id": gedung_id},
        {"_id": 0, "id": 1, "nama": 1, "kode": 1, "tipe": 1,
         "ordinal_level": 1, "kode_satker": 1, "status": 1})
    if not gedung or gedung.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Gedung tidak ditemukan")
    await pastikan_akses_dok_satker(_user, gedung)   # isolasi satker
    items = await db.spasial_node.find(
        scope_query_field_satker(_user, {"parent_id": gedung_id, "tipe": "LANTAI",
                                         "status": {"$ne": "dihapus"}}),
        {"_id": 0, "id": 1, "nama": 1, "kode": 1, "lantai": 1}
    ).sort("lantai.ordinal", 1).to_list(200)
    return {"items": items, "jumlah": len(items), "gedung": _ringkas(gedung)}


# Plafon fitur per permintaan peta. Di atas ini klien menerima penanda
# `terpotong` + hanya bbox/titik wakil — merender puluhan ribu poligon
# membekukan peramban, dan pengguna toh tak bisa membedakannya di zoom itu.
BATAS_FITUR_PETA = 3000


@spasial_router.get("/spasial/geojson")
async def geojson_viewport(bbox: str = Query("", description="lon_min,lat_min,lon_maks,lat_maks"),
                           level_maks: int = Query(100),
                           induk: str = Query("", description="hanya anak LANGSUNG node ini"),
                           dalam: str = Query("", description="seluruh keturunan node ini"),
                           _user: dict = Depends(require_user)):
    """FeatureCollection untuk render peta, dibatasi viewport & tingkat.

    Dimuat per-viewport (bukan sekali seluruh satker) supaya memori peramban
    tetap wajar saat denah kawasan lengkap. `level_maks` memungkinkan klien
    meminta hanya tingkat besar saat zoom jauh.

    `induk` menyaring ke anak LANGSUNG satu node; `dalam` ke SELURUH keturunannya
    (lewat indeks multikey `ancestors`). Peta memakai `dalam` untuk memuat ruangan
    satu lantai: tanpa penyaringan itu semua lantai gedung bertumpuk di tempat
    yang sama (mereka memang berbagi jejak 2D yang sama), dan dengan `induk` saja
    ruangan yang bersarang di bawah SAYAP — Lantai → Sayap → Ruangan, jalur yang
    sah menurut registry — tak akan pernah ikut terambil.

    Isolasi satker tetap dari `scope_query_field_satker`, jadi menebak id lantai
    milik satker lain hanya menghasilkan koleksi kosong.
    """
    # level_maks dijepit ke rentang registry: nilai liar (mis. 10**9) tak boleh
    # jadi jalan pintas menarik seluruh denah satker dalam satu GET.
    lv = max(0, min(int(level_maks), su.LEVEL_SPASIAL[-1][0]))
    q = {"status": "aktif", "geometry": {"$ne": None},
         "ordinal_level": {"$lte": lv}}
    if induk:
        q["parent_id"] = induk
    if dalam:
        q["ancestors"] = dalam          # indeks multikey spasial_node_ancestors
    if bbox:
        # Tiga hasil; lihat su.kotak_dari_bbox. `kotak` None TANPA galat berarti
        # bbox sah tapi terlalu lebar untuk disaring (jebakan komplemen MongoDB)
        # — sengaja tidak menyaring, biar LOD + plafon fitur yang membatasi.
        kotak, galat = su.kotak_dari_bbox(bbox)
        if galat:
            raise HTTPException(status_code=400, detail=galat)
        if kotak:
            q["geometry"] = {"$geoIntersects": {"$geometry": kotak}}

    query = scope_query_field_satker(_user, q)
    jumlah = await db.spasial_node.count_documents(query)
    terpotong = jumlah > BATAS_FITUR_PETA
    proyeksi = ({"_id": 0, "id": 1, "tipe": 1, "nama": 1, "kode": 1,
                 "ordinal_level": 1, "titik_wakil": 1, "bbox": 1}
                if terpotong else
                {"_id": 0, "id": 1, "tipe": 1, "nama": 1, "kode": 1,
                 "ordinal_level": 1, "geometry": 1, "bbox": 1, "parent_id": 1})
    rows = await db.spasial_node.find(query, proyeksi).sort(
        "ordinal_level", 1).to_list(BATAS_FITUR_PETA)

    fitur = []
    for r in rows:
        geom = r.get("geometry") or r.get("titik_wakil")
        if not geom:
            continue
        fitur.append({"type": "Feature", "geometry": geom, "properties": {
            "id": r.get("id"), "tipe": r.get("tipe"), "nama": r.get("nama"),
            "kode": r.get("kode"), "ordinal_level": r.get("ordinal_level"),
            "parent_id": r.get("parent_id")}})
    return {"type": "FeatureCollection", "features": fitur,
            "jumlah": len(fitur), "jumlah_total": jumlah,
            "terpotong": terpotong, "batas": BATAS_FITUR_PETA}


# ═══════════════════════════════════════════════════════════════════════════
# IMPOR SHP / KML / KMZ / GeoJSON (Fase 5)
#
# Alur: pratinjau SINKRON (parse header + cacah, tanpa menulis apa pun) →
# operator memilih tingkat/induk/field nama → job LATAR mem-parse penuh,
# membersihkan tiap fitur (struktur → topologi → make_valid ber-pagar-luas),
# lalu menulis node ber-status **DRAFT** di bawah induk pilihan. Draft sengaja
# TIDAK ikut deteksi lokasi maupun lapisan denah (keduanya menyaring "aktif")
# — hasil impor harus DIPERIKSA manusia dulu, baru diaktifkan lewat form ubah.
#
# File TIDAK disimpan di GridFS: byte-nya dipegang closure task (≤ plafon
# ukuran). Server restart di tengah job → bersihkan_job_basi menandai failed.
# ═══════════════════════════════════════════════════════════════════════════

MAKS_UKURAN_IMPOR = 20 * 1024 * 1024      # 20 MB — kecamatan penuh pun cukup
_IMPOR_TASKS = set()                      # pegang referensi task agar tak di-GC
# Satu impor pada satu waktu per proses: parsing+shapely CPU-berat di VPS kecil,
# dan dua impor paralel ke pohon yang sama hanya mengundang kekacauan urutan.
_IMPOR_SEM = asyncio.Semaphore(1)


async def _baca_terbatas(file: "UploadFile", maks: int = None) -> bytes:
    """Baca UploadFile BERTAHAP dan berhenti begitu melewati plafon — sehingga
    file 200 MB tak lebih dulu ditahan penuh di memori sebelum ditolak (temuan
    tinjauan). `file.read()` polos memuat seluruh body dulu, baru mengecek."""
    maks = maks or MAKS_UKURAN_IMPOR
    potong, total = [], 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > maks:
            raise HTTPException(
                status_code=400,
                detail=f"File melebihi {maks // (1024*1024)} MB")
        potong.append(chunk)
    return b"".join(potong)


def _potong_teks(nilai, batas=120) -> str:
    return str(nilai or "").strip()[:batas]


def _potong_atribut(atribut: dict) -> dict:
    """Batasi jumlah kunci & panjang nilai atribut impor agar dokumen node tak
    membengkak melewati batas 16 MB Mongo (temuan tinjauan). 60 kolom × 500 char
    jauh cukup untuk atribut denah wajar, dan node ditolak DB bila melampaui.

    Kunci yang dipotong 40 karakter bisa BERTABRAKAN: nama properti KML/GeoJSON
    panjangnya bebas, jadi dua field ber-awalan 40 karakter sama akan saling
    menimpa dan satu nilai hilang diam-diam — persis kelas bug yang sama dengan
    pemotongan 10 karakter DBF. Yang bertabrakan diberi akhiran urut."""
    hasil = {}
    for k, v in list(atribut.items())[:60]:
        kunci = str(k)[:40]
        if kunci in hasil:
            n = 2
            while f"{kunci}__{n}" in hasil:
                n += 1
            kunci = f"{kunci}__{n}"
        hasil[kunci] = str(v)[:500]
    return hasil


@spasial_router.post("/spasial/impor/pratinjau")
@limiter.limit("12/minute")
async def impor_pratinjau(request: Request, file: UploadFile = File(...),
                          _user: dict = Depends(require_writer)):
    """Baca file TANPA menyimpan apa pun: format, cacah fitur, daftar field
    atribut, CRS terdeteksi, sampel nama, dan peringatan (mojibake/CRS tebakan).
    Dipakai dialog impor untuk mengisi dropdown "field nama" sebelum mulai."""
    import impor_geo_utils as ig
    data = await _baca_terbatas(file)
    try:
        hasil = await asyncio.to_thread(ig.parse_file, file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fitur = hasil["fitur"]
    peringatan = list(hasil.get("peringatan") or [])
    if len(fitur) > ig.MAKS_FITUR_IMPOR:
        peringatan.append(
            f"File berisi {len(fitur)} fitur — hanya {ig.MAKS_FITUR_IMPOR} "
            "pertama yang akan diimpor; pecah filenya bila perlu semua")
    # Sampel nama per field agar operator bisa memilih field yang benar —
    # sekaligus memunculkan mojibake SEBELUM tersimpan (jebakan #3 riset).
    sampel = {}
    for f in fitur[:8]:
        if f.get("nama"):
            sampel.setdefault("(nama bawaan)", []).append(f["nama"])
        for k, v in (f.get("atribut") or {}).items():
            if v:
                sampel.setdefault(k, []).append(v)
    sampel = {k: v[:5] for k, v in sampel.items()}
    if any(ig.deteksi_mojibake(v) for vs in sampel.values() for v in vs):
        peringatan.append("Sebagian nama tampak RUSAK encoding (mojibake) — "
                          "periksa sampel; sertakan file .cpg pada shapefile")
    return {"format": hasil["format"], "jumlah_fitur": len(fitur),
            "fields": hasil["fields"], "crs": hasil["crs"],
            "sampel": sampel, "peringatan": peringatan,
            "maks_fitur": ig.MAKS_FITUR_IMPOR}


@spasial_router.post("/spasial/impor")
@limiter.limit("6/minute")
async def impor_mulai(request: Request,
                      file: UploadFile = File(...),
                      tipe: str = Form(...),
                      parent_id: str = Form(""),
                      field_nama: str = Form(""),
                      field_kode: str = Form(""),
                      perbaiki: bool = Form(False),
                      _user: dict = Depends(require_writer)):
    """Mulai job impor. Validasi tingkat+induk terjadi DI SINI (sinkron, dengan
    konteks user penuh) supaya galat izin/hierarki muncul seketika — worker
    hanya mengerjakan yang sudah pasti boleh."""
    from jobs import buat_job

    data = await _baca_terbatas(file)
    tipe = str(tipe or "").strip().upper()
    parent_id = str(parent_id or "").strip()
    deriv = await _susun_derivasi("__impor__", parent_id or None, _user)
    _validasi_level(tipe, deriv.pop("_tipe_induk", None))
    deriv.pop("jalur", None)                  # jalur per-node, disusun worker

    job_id = await buat_job(
        "impor_spasial", _user.get("username", ""),
        kode_satker=kode_satker_user(_user),
        status="queued", progress=0, done=False,
        nama_file=_potong_teks(file.filename), tipe=tipe)
    t = asyncio.create_task(_jalankan_impor(
        job_id, data, _potong_teks(file.filename), tipe, deriv,
        _potong_teks(field_nama, 40), _potong_teks(field_kode, 40),
        bool(perbaiki), kode_satker_user(_user), _user.get("username", "")))
    _IMPOR_TASKS.add(t)
    t.add_done_callback(_IMPOR_TASKS.discard)
    await log_audit("impor_spasial_mulai", "", job_id,
                    username=_user.get("username", "system"),
                    kode_satker=kode_satker_user(_user),
                    detail=f"Impor {file.filename} → {tipe}")
    return {"job_id": job_id}


async def _sisip_batch(dok_batch: list) -> int:
    """insert_many yang mengembalikan JUMLAH NYATA tertulis, tak melempar bila
    sebagian gagal. `ordered=False` melanjutkan sisa dokumen saat satu ditolak
    (mis. dokumen kelewat besar); tanpa penanganan ini satu fitur cacat membuat
    seluruh impor 'failed' padahal ratusan node draft yang sah SUDAH tertulis —
    yatim tanpa laporan (temuan tinjauan)."""
    from pymongo.errors import BulkWriteError
    try:
        r = await db.spasial_node.insert_many(dok_batch, ordered=False)
        return len(r.inserted_ids)
    except BulkWriteError as e:
        return int((e.details or {}).get("nInserted", 0))


async def _jalankan_impor(job_id, data, nama_file, tipe, deriv,
                          field_nama, field_kode, perbaiki,
                          kode_satker, username):
    """Worker job impor: parse → bersihkan per fitur → tulis node DRAFT.

    Kerja CPU (parse + shapely) di thread; penulisan batch insert_many.
    Laporan disimpan langsung di dokumen job (kecil), bukan artifact.
    """
    from jobs import update_job
    from log_setup import set_job_id
    import impor_geo_utils as ig
    set_job_id(job_id)
    try:
        async with _IMPOR_SEM:
            await update_job(job_id, status="running", progress=5,
                             message="Membaca file…")
            hasil = await asyncio.to_thread(ig.parse_file, nama_file, data)
            fitur = hasil["fitur"][:ig.MAKS_FITUR_IMPOR]
            peringatan = list(hasil.get("peringatan") or [])
            if len(hasil["fitur"]) > ig.MAKS_FITUR_IMPOR:
                peringatan.append(
                    f"{len(hasil['fitur']) - ig.MAKS_FITUR_IMPOR} fitur di atas "
                    "plafon TIDAK diimpor")
            total = len(fitur)
            if total == 0:
                await update_job(job_id, status="done", done=True, progress=100,
                                 dibuat=0, dilewati=[], peringatan=peringatan,
                                 message="Tidak ada fitur poligon di file ini")
                return

            # Keunikan kode: satu fetch untuk seluruh batch (bukan N kueri).
            kode_terpakai = set()
            if field_kode:
                async for d in db.spasial_node.find(
                        {"kode_satker": kode_satker, "tipe": tipe,
                         "kode": {"$ne": ""}, "status": {"$ne": "dihapus"}},
                        {"_id": 0, "kode": 1}):
                    kode_terpakai.add(d.get("kode"))

            now = datetime.now(timezone.utc).isoformat()
            anc = deriv.get("ancestors") or []
            dibuat, dilewati, dok_batch = 0, [], []
            for i, f in enumerate(fitur):
                nama = (_potong_teks(f["atribut"].get(field_nama))
                        if field_nama else "") or _potong_teks(f.get("nama")) \
                    or f"{tipe.title()} impor {i + 1}"
                geom, alasan = await asyncio.to_thread(
                    ig.bersihkan_fitur, f["geometry"], perbaiki)
                if geom is None:
                    dilewati.append({"nama": nama, "alasan": alasan})
                    continue
                kode = _potong_teks(f["atribut"].get(field_kode), 40) \
                    if field_kode else ""
                if kode and kode in kode_terpakai:
                    peringatan.append(f"Kode '{kode}' ganda — dikosongkan "
                                      f"pada '{nama}'")
                    kode = ""
                if kode:
                    kode_terpakai.add(kode)
                node_id = "sn_" + str(uuid.uuid4())
                dok_batch.append({
                    "id": node_id, "kode_satker": kode_satker,
                    "tipe": tipe, "nama": nama, "kode": kode,
                    "parent_id": deriv.get("parent_id"),
                    "ancestors": list(anc),
                    "ancestors_nama": list(deriv.get("ancestors_nama") or []),
                    "jalur": su.bangun_jalur(anc, node_id),
                    "kedalaman": deriv.get("kedalaman", 0),
                    "ordinal_level": su.ordinal_level(tipe),
                    "nama_alias": [], "zona_kode": "", "subzona_kode": "",
                    "fungsi_kawasan": "",
                    # Atribut sumber tersimpan sebagai jejak audit, TAPI dipotong:
                    # DBF/KML bisa punya field teks raksasa dan dokumen node yang
                    # membengkak > 16 MB akan DITOLAK Mongo saat insert (temuan
                    # tinjauan). Batasi jumlah kunci & panjang nilai.
                    "properties": {"impor": {"file": nama_file,
                                             "atribut": _potong_atribut(f["atribut"])}},
                    "status": "draft",
                    "geometry": geom,
                    "bbox": su.hitung_bbox(geom),
                    "titik_wakil": su.titik_wakil(geom),
                    "metrik": {"luas_m2": round(su.luas_kasar_m2(geom), 2),
                               "dihitung_pada": now},
                    "lantai": None, "lantai_ordinal": None,
                    "versi": 1, "created_at": now, "updated_at": now,
                    "created_by": username, "updated_by": username,
                })
                if len(dok_batch) >= 100:
                    dibuat += await _sisip_batch(dok_batch)
                    dok_batch = []
                # `total` bisa < 25; perbarui progres di kelipatan 25 ATAU pada
                # fitur terakhir supaya file kecil pun bergerak dari 5%.
                if (i + 1) % 25 == 0 or (i + 1) == total:
                    await update_job(
                        job_id, progress=5 + int(90 * (i + 1) / total),
                        message=f"Memproses fitur {i + 1}/{total}…")
            if dok_batch:
                dibuat += await _sisip_batch(dok_batch)

            await update_job(
                job_id, status="done", done=True, progress=100,
                dibuat=dibuat, total=total,
                dilewati=dilewati[:50],       # plafon laporan; jumlah tetap utuh
                jumlah_dilewati=len(dilewati),
                peringatan=peringatan[:20],
                message=(f"Selesai: {dibuat} node draft dibuat"
                         + (f", {len(dilewati)} dilewati" if dilewati else "")))
            await log_audit("impor_spasial_selesai", "", job_id,
                            username=username, kode_satker=kode_satker,
                            detail=f"{nama_file}: {dibuat} dibuat, "
                                   f"{len(dilewati)} dilewati")
    except ValueError as e:
        await update_job(job_id, status="failed", done=True, error=str(e),
                         message=f"Impor gagal: {e}")
    except Exception as e:                    # jangan biarkan task mati senyap
        await update_job(job_id, status="failed", done=True, error=str(e),
                         message="Impor gagal karena kesalahan tak terduga")


# ── Ekspor denah (Fase 6) — GeoJSON / KML / KMZ / Shapefile + template ──────
#
# Sinkron (bukan job): ekspor = baca + serialisasi, dibatasi _MAKS_NODE dan
# ukuran geometri denah yang wajar — berbeda dari impor yang berat di parsing
# + shapely + tulis massal. Serialisasi tetap di thread supaya event loop tak
# tersandera, dan rate-limit menjaga dari pengunduhan beruntun.

_FORMAT_EKSPOR = {
    "geojson": ("application/geo+json", "geojson"),
    "kml": ("application/vnd.google-earth.kml+xml", "kml"),
    "kmz": ("application/vnd.google-earth.kmz", "kmz"),
    "shp": ("application/zip", "zip"),
}


def _bangun_ekspor(fmt: str, rows: list, label_level: dict) -> bytes:
    """Dipanggil di thread — murni CPU, tanpa await."""
    import ekspor_geo_utils as eg
    if fmt == "geojson":
        return eg.ke_geojson(rows)
    if fmt == "kml":
        return eg.ke_kml(rows, label_level)
    if fmt == "kmz":
        return eg.ke_kmz(eg.ke_kml(rows, label_level))
    return eg.ke_shp_zip(rows)


@spasial_router.get("/spasial/ekspor")
@limiter.limit("10/minute")
async def ekspor_denah(request: Request,
                       format: str = Query("geojson"),
                       dalam: str = Query("", description="subtree node ini (node + seluruh keturunan)"),
                       sertakan_draft: bool = Query(True),
                       _user: dict = Depends(require_user)):
    """Unduh denah satker sebagai file GIS — kebalikan endpoint impor Fase 5.

    Operasi BACA murni (viewer boleh — mereka sudah bisa membaca node yang
    sama lewat /spasial/node), ter-scope satker seperti seluruh kueri denah.
    `dalam` membatasi ke satu subtree via indeks multikey `ancestors` — node
    akarnya sendiri ikut. Node tanpa geometri tak diekspor KECUALI di KML,
    tempat moyang tanpa geometri tetap dibutuhkan sebagai Folder hierarki.
    """
    from fastapi.responses import Response

    fmt = str(format or "").strip().lower()
    if fmt not in _FORMAT_EKSPOR:
        raise HTTPException(status_code=400,
                            detail=f"Format '{format}' tak dikenal — pilih "
                                   f"{', '.join(sorted(_FORMAT_EKSPOR))}")
    q = {"status": {"$ne": "dihapus"}}
    if not sertakan_draft:
        q["status"] = {"$nin": ["dihapus", "draft"]}
    if dalam:
        q["$or"] = [{"id": dalam}, {"ancestors": dalam}]
    rows = await (db.spasial_node.find(scope_query_field_satker(_user, q), _PROJ)
                  .sort([("ordinal_level", 1), ("kode", 1), ("nama", 1)])
                  .to_list(_MAKS_NODE))
    # KML memakai node tanpa geometri sebagai Folder; format lain hanya fitur.
    if fmt not in ("kml", "kmz"):
        rows = [r for r in rows if r.get("geometry")]
    if not any(r.get("geometry") for r in rows):
        raise HTTPException(status_code=400,
                            detail="Tidak ada node bergeometri pada cakupan ini "
                                   "— gambar atau impor denah dulu")

    label_level = {l["kode_baku"]: l["label"] for l in su.daftar_level()}
    try:
        data = await asyncio.to_thread(_bangun_ekspor, fmt, rows, label_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    media, ext = _FORMAT_EKSPOR[fmt]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    # kode_satker dikutip di header Content-Disposition — saring ke aman-header
    # (nilai wajarnya 6 digit, tapi header rusak bukan cara menemukan itu).
    satker = re.sub(r"[^A-Za-z0-9_-]", "", kode_satker_user(_user)) or "aman"
    nama_file = f"denah-{satker}-{stamp}.{ext}"
    await log_audit("ekspor_spasial", "", nama_file,
                    username=_user.get("username", "system"),
                    kode_satker=kode_satker_user(_user),
                    detail=f"Ekspor {fmt} ({len(rows)} node)")
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{nama_file}"'})


@spasial_router.get("/spasial/ekspor/template")
@limiter.limit("10/minute")
async def ekspor_template(request: Request, format: str = Query("shp"),
                          _user: dict = Depends(require_user)):
    """Template gambar kosong ber-skema: `shp` untuk QGIS/ArcGIS, `kml` untuk
    Google Earth. Isinya satu fitur contoh + petunjuk alur bolak-balik; tanpa
    data satker sedikit pun, jadi tak perlu scoping."""
    from fastapi.responses import Response
    import ekspor_geo_utils as eg

    fmt = str(format or "").strip().lower()
    if fmt == "shp":
        data = await asyncio.to_thread(eg.template_shp_zip)
        return Response(content=data, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="template-denah-qgis.zip"'})
    if fmt == "kml":
        data = await asyncio.to_thread(eg.template_kml)
        return Response(content=data,
                        media_type="application/vnd.google-earth.kml+xml",
                        headers={"Content-Disposition":
                                 'attachment; filename="template-denah-google-earth.kml"'})
    raise HTTPException(status_code=400,
                        detail=f"Format template '{format}' tak dikenal — pilih shp / kml")


# ── Overlay gambar denah dalam-gedung (Fase 7) ──────────────────────────────
#
# Masalah yang diselesaikan: interior gedung TIDAK terlihat di citra satelit,
# jadi menggambar ruangan akurat (Fase 4) butuh alas — gambar denah lantai
# hasil ekspor CAD/PDF. Gambar disimpan di GridFS, penempatannya (3 sudut
# lon/lat: tl/tr/bl = transformasi affine penuh) di properties.denah_overlay
# node, dan DIWARISKAN: editor ruangan menampilkan overlay milik lantai/gedung
# moyang terdekat (lihat `_overlay_efektif` yang disisipkan ke detail node).

MAKS_GAMBAR_OVERLAY = 10 * 1024 * 1024


async def _node_untuk_overlay(node_id: str, _user: dict) -> dict:
    node = await db.spasial_node.find_one({"id": node_id}, _PROJ)
    if not node or node.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    await pastikan_akses_dok_satker(_user, node)
    return node


async def _sudut_bawaan_node(node: dict) -> dict:
    """Penempatan awal: bbox node → bbox moyang bergeometri TERDEKAT → kotak
    kecil di sekitar titik_wakil → kotak KIPP IKN. Selalu menghasilkan sudut
    sah — operator tinggal menggeser, bukan mencari gambarnya dulu di (0,0)."""
    bb = node.get("bbox")
    if not bb:
        for aid in reversed(node.get("ancestors") or []):
            d = await db.spasial_node.find_one({"id": aid}, {"_id": 0, "bbox": 1})
            if d and d.get("bbox"):
                bb = d["bbox"]
                break
    if not bb and (node.get("titik_wakil") or {}).get("coordinates"):
        lon, lat = node["titik_wakil"]["coordinates"][:2]
        bb = [lon - 0.0008, lat - 0.0006, lon + 0.0008, lat + 0.0006]
    sudut = su.sudut_overlay_bawaan(bb)
    return sudut or su.sudut_overlay_bawaan([116.700, -1.410, 116.720, -1.395])


async def _overlay_efektif(node: dict):
    """Overlay node ini, atau milik moyang TERDEKAT yang punya — plus asal-nya
    (`dari_node`) supaya klien tahu penempatan boleh diubah dari editor mana.

    Moyang disaring ke SATKER node sendiri dan status hidup: id di `ancestors`
    adalah data (bisa korup/warisan lama menunjuk lintas-satker), dan tanpa
    saringan itu metadata overlay satker lain — koordinat denah interior,
    nama file, username — bocor lewat pewarisan (temuan tinjauan)."""
    ov = (node.get("properties") or {}).get("denah_overlay")
    if ov:
        return {**ov, "dari_node": node.get("id"), "dari_nama": node.get("nama")}
    anc = [a for a in (node.get("ancestors") or []) if a]
    if not anc:
        return None
    satker = str(node.get("kode_satker") or "").strip()
    docs = await db.spasial_node.find(
        {"id": {"$in": anc}, "properties.denah_overlay": {"$exists": True},
         "kode_satker": {"$in": [satker, "", None]},
         "status": {"$ne": "dihapus"}},
        {"_id": 0, "id": 1, "nama": 1, "properties.denah_overlay": 1}).to_list(64)
    peta = {d["id"]: d for d in docs}
    for aid in reversed(anc):                     # ancestors akar→daun; terdekat = belakang
        d = peta.get(aid)
        if d:
            return {**d["properties"]["denah_overlay"],
                    "dari_node": aid, "dari_nama": d.get("nama")}
    return None


@spasial_router.post("/spasial/node/{node_id}/overlay")
@limiter.limit("10/minute")
async def unggah_overlay(request: Request, node_id: str,
                         file: UploadFile = File(...),
                         _user: dict = Depends(require_writer)):
    """Unggah/ganti gambar denah node. Saat MENGGANTI, penempatan lama
    dipertahankan (operator mengganti hasil ekspor CAD revisi — posisinya
    sudah benar); sudut bawaan hanya untuk unggahan pertama."""
    from bson import ObjectId
    from shared_utils import fs_bucket

    node = await _node_untuk_overlay(node_id, _user)
    data = await _baca_terbatas(file, MAKS_GAMBAR_OVERLAY)
    try:
        fmt, lebar, tinggi = su.periksa_gambar_overlay(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lama = (node.get("properties") or {}).get("denah_overlay") or {}
    sudut = lama.get("sudut") if not su.validasi_sudut_overlay(lama.get("sudut")) \
        else await _sudut_bawaan_node(node)
    opasitas = su.opasitas_overlay_sah(lama.get("opasitas",
                                                su.OPASITAS_OVERLAY_BAWAAN))

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=_potong_teks(file.filename) or "denah.png",
        metadata={"content_type": su.FORMAT_OVERLAY[fmt], "size": len(data),
                  "overlay_node": node_id})
    await grid_in.write(data)
    await grid_in.close()

    now = datetime.now(timezone.utc).isoformat()
    overlay = {"file_id": str(file_id),
               "nama_file": _potong_teks(file.filename) or "denah.png",
               "format": fmt, "lebar": lebar, "tinggi": tinggi,
               "sudut": su.rapikan_sudut_overlay(sudut), "opasitas": opasitas,
               "updated_at": now, "updated_by": _user.get("username", "")}
    await db.spasial_node.update_one(
        {"id": node_id},
        {"$set": {"properties.denah_overlay": overlay,
                  "updated_at": now, "updated_by": _user.get("username", "")}})
    # Blob lama dihapus SETELAH metadata menunjuk blob baru — gagal di sini
    # hanya menyisakan file yatim (disapu bersihkan_artifact_yatim? tidak —
    # metadata.overlay_node bukan job; yatim langka dan kecil, diterima).
    if lama.get("file_id"):
        try:
            await fs_bucket.delete(ObjectId(lama["file_id"]))
        except Exception:
            pass
    await log_audit("overlay_spasial_unggah", "", node_id,
                    username=_user.get("username", "system"),
                    kode_satker=kode_satker_user(_user),
                    detail=f"{node.get('nama')}: {file.filename} "
                           f"({lebar}x{tinggi} {fmt})")
    return {**overlay, "dari_node": node_id, "dari_nama": node.get("nama")}


class OverlayPosisiIn(BaseModel):
    sudut: dict
    opasitas: float = su.OPASITAS_OVERLAY_BAWAAN


@spasial_router.put("/spasial/node/{node_id}/overlay")
async def atur_overlay(node_id: str, payload: OverlayPosisiIn,
                       _user: dict = Depends(require_writer)):
    """Simpan penempatan (3 sudut) + opasitas — dipanggil saat operator selesai
    menggeser marker sudut di editor."""
    node = await _node_untuk_overlay(node_id, _user)
    if not (node.get("properties") or {}).get("denah_overlay"):
        raise HTTPException(status_code=404,
                            detail="Node ini belum punya gambar denah — unggah dulu")
    galat = su.validasi_sudut_overlay(payload.sudut)
    if galat:
        raise HTTPException(status_code=400, detail=galat)
    now = datetime.now(timezone.utc).isoformat()
    # Filter menyertakan file_id ($exists) — tanpa itu, DELETE overlay yang
    # mendarat di sela cek-atas dan $set dotted ini MENCIPTAKAN ULANG
    # denah_overlay parsial tanpa file_id: "overlay hantu" yang memblokir
    # pewarisan dan tampil kosong diam-diam (temuan tinjauan).
    r = await db.spasial_node.update_one(
        {"id": node_id, "properties.denah_overlay.file_id": {"$exists": True}},
        {"$set": {"properties.denah_overlay.sudut":
                      su.rapikan_sudut_overlay(payload.sudut),
                  "properties.denah_overlay.opasitas":
                      su.opasitas_overlay_sah(payload.opasitas),
                  "properties.denah_overlay.updated_at": now,
                  "properties.denah_overlay.updated_by":
                      _user.get("username", ""),
                  "updated_at": now}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404,
                            detail="Gambar denah sudah dihapus — muat ulang editor")
    return {"ok": True}


@spasial_router.delete("/spasial/node/{node_id}/overlay")
async def hapus_overlay(node_id: str, _user: dict = Depends(require_writer)):
    from bson import ObjectId
    from shared_utils import fs_bucket
    node = await _node_untuk_overlay(node_id, _user)
    ov = (node.get("properties") or {}).get("denah_overlay")
    if not ov:
        raise HTTPException(status_code=404, detail="Node ini tak punya gambar denah")
    await db.spasial_node.update_one(
        {"id": node_id}, {"$unset": {"properties.denah_overlay": ""},
                          "$set": {"updated_at":
                                   datetime.now(timezone.utc).isoformat()}})
    if ov.get("file_id"):
        try:
            await fs_bucket.delete(ObjectId(ov["file_id"]))
        except Exception:
            pass
    await log_audit("overlay_spasial_hapus", "", node_id,
                    username=_user.get("username", "system"),
                    kode_satker=kode_satker_user(_user),
                    detail=str(node.get("nama") or node_id))
    return {"ok": True}


@spasial_router.get("/spasial/overlay/{file_id}")
async def gambar_overlay(file_id: str, request: Request,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream gambar overlay untuk <img>/Leaflet (token boleh di query —
    pola media yang sama dengan foto aset). Isolasi satker lewat NODE
    pemiliknya, bukan sekadar ke-takterkaan ObjectId; koleksi spasial_node
    kecil (ribuan) sehingga pencarian tanpa indeks di sini murah, dan hasilnya
    di-cache lama oleh peramban karena file_id baru terbit di tiap unggahan."""
    from shared_utils import get_document_from_gridfs
    node = await db.spasial_node.find_one(
        {"properties.denah_overlay.file_id": str(file_id)},
        {"_id": 0, "kode_satker": 1, "properties.denah_overlay": 1})
    if not node:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
    await pastikan_akses_dok_satker(_user, node)
    data = await get_document_from_gridfs(str(file_id))
    if data is None:
        raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
    from fastapi.responses import Response
    ov = node["properties"]["denah_overlay"]
    etag = f'"ov-{file_id}"'
    if request.headers.get("if-none-match", "").strip() == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=data,
        media_type=su.FORMAT_OVERLAY.get(ov.get("format"),
                                         "application/octet-stream"),
        headers={"Cache-Control": "private, max-age=604800", "ETag": etag,
                 "X-Content-Type-Options": "nosniff"})


# ── Custody berlokasi: aset menempati node denah (Fase 9) ───────────────────
#
# Aset bergerak (laptop, meja, kendaraan) MENEMPATI node denah — biasanya
# Ruangan. Snapshot lokasi disimpan DI DOKUMEN ASET (`lokasi_spasial`, format
# sama dengan tiket wasdal Fase 8) supaya daftar/ekspor aset tak perlu join,
# sedangkan RIWAYAT perpindahan masuk koleksi terpisah `riwayat_lokasi_aset`:
# menaruhnya sebagai array di dokumen aset akan tumbuh tanpa batas seumur
# pakai barang dan menyeret setiap pembacaan aset.

_MAKS_ISI_NODE = 500


class LokasiAsetIn(BaseModel):
    lat: object = None
    lon: object = None
    node_id: str = ""
    hapus: bool = False


@spasial_router.put("/assets/{asset_id}/lokasi-spasial")
async def set_lokasi_aset(asset_id: str, payload: LokasiAsetIn,
                          _user: dict = Depends(require_writer)):
    """Tempatkan aset pada node denah (atau cabut penempatannya).

    Guard aset memakai jalur BAKU modul aset — lewat kegiatan induknya
    (`pastikan_akses_aset`), bukan kode_satker di dokumen aset, supaya aturan
    akses tetap satu sumber. Node divalidasi terpisah dengan scope satker
    user: menempatkan aset ke ruangan milik satker lain harus mustahil.
    """
    from shared_utils import pastikan_akses_aset

    aset = await db.assets.find_one(
        {"id": asset_id},
        {"_id": 0, "id": 1, "activity_id": 1, "asset_name": 1,
         "asset_code": 1, "NUP": 1, "lokasi_spasial": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, aset)

    now = datetime.now(timezone.utc).isoformat()
    lokasi_lama = aset.get("lokasi_spasial")
    username = _user.get("username", "")

    if payload.hapus:
        if lokasi_lama:
            await db.riwayat_lokasi_aset.insert_one(
                su.entri_riwayat_lokasi(asset_id, lokasi_lama, None,
                                        username, now))
        await db.assets.update_one({"id": asset_id},
                                   {"$unset": {"lokasi_spasial": ""},
                                    "$set": {"updated_at": now}})
        await log_audit("aset_lokasi_hapus", aset.get("activity_id") or "",
                        asset_id, asset_code=aset.get("asset_code") or "",
                        asset_name=aset.get("asset_name") or "",
                        username=username or "system",
                        kode_satker=kode_satker_user(_user),
                        detail="Penempatan denah dicabut")
        return {"ok": True, "lokasi_spasial": None}

    lat = su.parse_lintang(payload.lat)
    lon = su.parse_bujur(payload.lon)
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Koordinat tidak valid")
    node = None
    nid = str(payload.node_id or "").strip()
    if nid:
        node = await db.spasial_node.find_one(
            scope_query_field_satker(_user, {"id": nid,
                                             "status": {"$ne": "dihapus"}}),
            {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "ancestors_nama": 1})
        if not node:
            raise HTTPException(status_code=404,
                                detail="Node denah tidak ditemukan")
    lokasi = su.snapshot_lokasi_temuan(node, lon, lat)
    lokasi.update({"ditandai_oleh": username, "ditandai_pada": now})

    # Riwayat HANYA saat benar-benar berpindah — menyimpan ulang lokasi yang
    # sama tak boleh menggelembungkan jejak custody (lihat helper).
    if su.pindah_lokasi_berarti(lokasi_lama, lokasi):
        await db.riwayat_lokasi_aset.insert_one(
            su.entri_riwayat_lokasi(asset_id, lokasi_lama, lokasi,
                                    username, now))
    await db.assets.update_one({"id": asset_id},
                               {"$set": {"lokasi_spasial": lokasi,
                                         "updated_at": now}})
    await log_audit("aset_lokasi_tandai", aset.get("activity_id") or "",
                    asset_id, asset_code=aset.get("asset_code") or "",
                    asset_name=aset.get("asset_name") or "",
                    username=username or "system",
                    kode_satker=kode_satker_user(_user),
                    detail=(lokasi.get("jalur_nama")
                            or f"{lat:.6f}, {lon:.6f}")[:120])
    return {"ok": True, "lokasi_spasial": lokasi}


@spasial_router.get("/assets/{asset_id}/riwayat-lokasi")
async def riwayat_lokasi_aset(asset_id: str,
                              _user: dict = Depends(require_user)):
    """Jejak perpindahan aset antar node denah (terbaru dulu)."""
    from shared_utils import pastikan_akses_aset

    aset = await db.assets.find_one({"id": asset_id},
                                    {"_id": 0, "id": 1, "activity_id": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, aset)
    items = await (db.riwayat_lokasi_aset.find({"asset_id": asset_id},
                                               {"_id": 0})
                   .sort("pada", -1).to_list(200))
    return {"items": items, "jumlah": len(items)}


@spasial_router.get("/spasial/node/{node_id}/isi")
async def isi_node(node_id: str, dalam: bool = Query(True),
                   _user: dict = Depends(require_user)):
    """Aset yang menempati node ini — `dalam=true` (bawaan) termasuk SELURUH
    keturunannya, sehingga membuka Gedung memperlihatkan isi tiap ruangannya.

    Node divalidasi ter-scope satker lebih dulu; daftar aset lalu disaring
    lewat `lokasi_spasial.node_id`. Ini kebalikan Fase 3 (titik → wilayah):
    di sini wilayah → daftar barang, yaitu bentuk yang dibutuhkan opname.
    """
    node = await db.spasial_node.find_one(
        scope_query_field_satker(_user, {"id": node_id}),
        {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "ordinal_level": 1,
         "kode": 1, "status": 1})
    if not node or node.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")

    ids = [node_id]
    if dalam:
        # Keturunan lewat indeks multikey `ancestors` (satu kueri, bukan
        # rekursi per tingkat).
        anak = await db.spasial_node.find(
            scope_query_field_satker(_user, {"ancestors": node_id,
                                             "status": {"$ne": "dihapus"}}),
            {"_id": 0, "id": 1}).to_list(_MAKS_NODE)
        ids.extend(d["id"] for d in anak)

    rows = await (db.assets.find(
        {"lokasi_spasial.node_id": {"$in": ids}},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "category": 1, "condition": 1, "user": 1, "status": 1,
         "lokasi_spasial": 1, "activity_id": 1})
        .sort("asset_name", 1).to_list(_MAKS_ISI_NODE))

    # Isolasi satker aset mengikuti KEGIATAN induknya (aturan baku modul aset),
    # jadi hasil disaring dengan guard yang sama — bukan sekadar percaya bahwa
    # node ter-scope sudah cukup (aset satker lain bisa saja menunjuk node
    # era-lama tanpa stempel satker).
    from shared_utils import pastikan_akses_aset
    hasil = []
    for r in rows:
        try:
            await pastikan_akses_aset(_user, r)
        except HTTPException:
            continue
        hasil.append(r)
    return {"node": _ringkas(node), "items": hasil, "jumlah": len(hasil),
            "termasuk_keturunan": bool(dalam),
            "terpotong": len(rows) >= _MAKS_ISI_NODE}
