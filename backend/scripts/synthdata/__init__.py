"""Generator data sintetis AMAN — realistis, adaptif, & beranomali.

Perkakas pengembangan/pengujian (BUKAN runtime aplikasi). Menghasilkan data
BMN sintetis berkonteks OIKN/IKN untuk: memuat basis data uji, load/stress
testing (lihat ``scripts/loadtest``), dan menambah cakupan kasus tepi.

Pemakaian program:
    from scripts.synthdata import generate_assets
    aset = generate_assets(500, seed=42, profile="mixed")

Pemakaian CLI (dari direktori ``backend``):
    python -m scripts.synthdata --count 500 --profile mixed --seed 42 \
        --out /tmp/aset.json
"""
from .generator import (
    FIELD_STRATEGIES,
    PROFIL_TERSEDIA,
    generate_activity,
    generate_asset,
    generate_assets,
    generate_pegawai,
    generate_satker,
)

__all__ = [
    "generate_assets",
    "generate_asset",
    "generate_pegawai",
    "generate_satker",
    "generate_activity",
    "FIELD_STRATEGIES",
    "PROFIL_TERSEDIA",
]
