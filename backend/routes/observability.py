"""Snapshot operasional lintas-satker hanya untuk super-admin pusat."""
from fastapi import APIRouter,Depends
from auth_utils import require_super_admin
from runtime_observability import OBS

observability_router=APIRouter()


@observability_router.get("/system/observability")
async def observability_snapshot(_admin:dict=Depends(require_super_admin)):
    return OBS.snapshot()
