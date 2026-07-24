"""Administrasi mesin pencari Meilisearch (opsional).

- GET  /api/search/status  → status flag + jumlah dokumen per indeks (admin).
- POST /api/search/reindex → bangun ulang indeks dari Mongo (super-admin).

Reindex menyentuh SELURUH satker (indeks global; isolasi ditegakkan saat
pencarian), maka dibatasi super-admin lintas-satker. Bila Meilisearch nonaktif,
endpoint tetap membalas rapi (aktif=false) tanpa error.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from auth_utils import require_admin, require_super_admin
from meili_utils import (INDEKS, meili_aktif, reindex_koleksi, reindex_semua,
                         status_indeks)

logger = logging.getLogger(__name__)
search_router = APIRouter()


@search_router.get("/search/status")
async def status_pencarian(_admin: dict = Depends(require_admin)):
    """Status integrasi Meilisearch (aktif? + statistik indeks)."""
    return await status_indeks()


@search_router.post("/search/reindex")
async def reindex_pencarian(
    koleksi: str = Query("all", pattern="^(all|assets|surat|persediaan)$"),
    _admin: dict = Depends(require_super_admin),
):
    """Bangun ulang indeks Meilisearch dari data Mongo (super-admin).

    `koleksi=all` (bawaan) me-reindex ketiganya; atau pilih satu koleksi.
    Nonaktif → 409 dengan pesan cara mengaktifkan.
    """
    if not meili_aktif():
        raise HTTPException(
            status_code=409,
            detail=("Meilisearch belum aktif. Set MEILI_URL & MEILI_MASTER_KEY "
                    "di backend/.env lalu restart backend (lihat docs/MEILISEARCH.md)."))
    if koleksi == "all":
        hasil = await reindex_semua()
    else:
        hasil = await reindex_koleksi(koleksi)
    logger.info("Meili: reindex manual (%s) oleh %s", koleksi,
                _admin.get("username", "?"))
    return {"ok": True, "hasil": hasil}
