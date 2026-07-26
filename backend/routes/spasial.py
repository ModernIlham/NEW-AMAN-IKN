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
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth_utils import require_user, require_writer
from db import db
from shared_utils import (kode_satker_user, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)
import spasial_utils as su

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
    status: Optional[str] = "aktif"


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
        "properties": dict(p.properties or {}),
        # Whitelist status — klien TAK boleh menyetel "dihapus" (lihat STATUS_SAH).
        "status": (lambda s: s if s in STATUS_SAH else "aktif")(
            str(p.status or "aktif").strip().lower()),
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
    return doc


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
    return node


@spasial_router.post("/spasial/node")
async def buat_node(payload: NodeIn, _user: dict = Depends(require_writer)):
    doc = _bersih_node(payload)
    if not doc["nama"]:
        raise HTTPException(status_code=400, detail="Nama wajib diisi")
    kode_satker = kode_satker_user(_user)
    node_id = "sn_" + str(uuid.uuid4())
    deriv = await _susun_derivasi(node_id, doc["parent_id"], _user)
    _validasi_level(doc["tipe"], deriv.pop("_tipe_induk", None))
    await _cek_kode_unik(doc["kode"], doc["tipe"], _user)
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
    return {"ok": True, "id": node_id}


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

    now = datetime.now(timezone.utc).isoformat()
    doc.update(deriv)
    doc.update({"ordinal_level": su.ordinal_level(doc["tipe"]),
                "updated_at": now, "updated_by": _user.get("username", "system")})
    await db.spasial_node.update_one(
        {"id": node_id}, {"$set": doc, "$inc": {"versi": 1}})

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
    return {"ok": True, "id": node_id}


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
        {"id": node_id}, {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "kode_satker": 1})
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
    await log_audit("hapus_spasial_node", "", node_id,
                    username=_user.get("username", "system"),
                    kode_satker=str(node.get("kode_satker") or "").strip(),
                    detail=f"Hapus {node.get('tipe')} — {node.get('nama')}")
    return {"ok": True, "id": node_id}
