"""Uji integrasi Redis pada jalur NONAKTIF (bebas jaringan & paket redis).

Di lingkungan test REDIS_URL tak di-set → fitur nonaktif. Semua operasi Redis
harus SHORT-CIRCUIT (None / no-op / False) tanpa menyentuh jaringan atau
meng-import paket `redis`. Cache helper di shared_utils harus jatuh-balik ke
TTLCache lokal per-worker.
"""
import asyncio

import redis_utils as r
import shared_utils as su


# ── Feature flag nonaktif di test ───────────────────────────────────────────
def test_redis_nonaktif_di_test():
    assert r.redis_aktif() is False


def test_operasi_redis_short_circuit():
    run = asyncio.run
    # get → None (miss); set → no-op tanpa error; ping → False; semuanya tanpa
    # menyentuh jaringan / import paket redis.
    assert run(r.redis_get("stats", "k")) is None
    assert run(r.redis_set("stats", "k", {"a": 1}, 60)) is None
    assert run(r.ping()) is False


def test_bump_nonaktif_noop():
    # Nonaktif → no-op; tak melempar & tak butuh event loop berjalan.
    assert r.bump_namespaces(["stats", "filter_opts"]) is None


# ── Cache helper shared_utils: fallback ke TTLCache lokal ────────────────────
def test_cache_set_get_lokal():
    run = asyncio.run
    su._cache_stats.clear()
    # miss awal
    assert run(su.cache_get("stats", "kk")) is None
    # set lalu get (jalur lokal karena Redis nonaktif)
    run(su.cache_set("stats", "kk", {"total_assets": 7}))
    assert run(su.cache_get("stats", "kk")) == {"total_assets": 7}


def test_cache_nilai_kosong_bukan_miss():
    run = asyncio.run
    su._cache_categories.clear()
    # Nilai [] (kategori kosong) valid — HARUS dikembalikan, bukan dianggap miss.
    run(su.cache_set("categories", "all", []))
    assert run(su.cache_get("categories", "all")) == []


def test_invalidate_membersihkan_cache_lokal():
    run = asyncio.run
    run(su.cache_set("stats", "x", {"n": 1}))
    run(su.cache_set("filter_opts", "y", {"locations": []}))
    run(su.cache_set("analytics", "z", {"by_category": []}))
    su.invalidate_asset_cache()
    assert run(su.cache_get("stats", "x")) is None
    assert run(su.cache_get("filter_opts", "y")) is None
    assert run(su.cache_get("analytics", "z")) is None


def test_invalidate_kategori():
    run = asyncio.run
    run(su.cache_set("categories", "all", [{"id": "1"}]))
    su.invalidate_category_cache()
    assert run(su.cache_get("categories", "all")) is None


# ── Registry namespace ↔ TTL konsisten ──────────────────────────────────────
def test_registry_cache():
    assert set(su._CACHE_LOCAL) == set(su._CACHE_TTL)
    for ns in su._CACHE_LOCAL:
        assert su._CACHE_TTL[ns] > 0
    # Namespace yang dipakai endpoint harus terdaftar.
    for ns in ("stats", "filter_opts", "analytics", "categories"):
        assert ns in su._CACHE_LOCAL


# ── Limiter tetap terbangun (mode memory di pytest) ─────────────────────────
def test_limiter_terbangun():
    # _bangun_limiter tak boleh melempar; di pytest → in-memory (tanpa infra).
    assert su.limiter is not None
