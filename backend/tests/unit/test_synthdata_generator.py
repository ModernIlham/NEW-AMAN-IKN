"""Test generator data sintetis (scripts.synthdata).

Menjaga empat jaminan yang membuat data uji tetap berguna:
  1. ADAPTIF (anti-drift): tiap field di registry punya strategi & sebaliknya —
     menambah field aset TANPA menambah strateginya menggagalkan test ini,
     sehingga data uji selalu selaras dengan fitur aplikasi terkini.
  2. VALID SKEMA: setiap record (semua profil) lolos model ``AssetCreate``.
  3. DETERMINISTIK: seed sama → keluaran identik (repro di CI).
  4. ANOMALI: profil ``edge`` benar-benar menyuntikkan kasus tepi.
"""
import json

import pytest


def test_registry_drift_guard_setiap_field_punya_strategi():
    # Anti-drift: himpunan strategi HARUS sama persis dengan field registry.
    from asset_fields import SCALAR_FIELD_NAMES
    from scripts.synthdata.generator import FIELD_STRATEGIES

    field_registry = set(SCALAR_FIELD_NAMES)
    field_strategi = set(FIELD_STRATEGIES)
    kurang = field_registry - field_strategi
    lebih = field_strategi - field_registry
    assert not kurang, (
        f"Field registry tanpa strategi generator: {sorted(kurang)}. "
        f"Tambahkan strateginya di scripts/synthdata/generator.py.")
    assert not lebih, (
        f"Strategi menyebut field yang tak ada di registry: {sorted(lebih)}.")


@pytest.mark.parametrize("profile", ["normal", "mixed", "edge"])
def test_setiap_record_lolos_AssetCreate(profile):
    # Semua profil menghasilkan record yang valid terhadap skema Pydantic
    # (anomali tetap berupa string → tak melanggar tipe).
    from models import AssetCreate
    from scripts.synthdata import generate_assets

    for rec in generate_assets(60, seed=3, profile=profile):
        AssetCreate(**rec)  # ValidationError bila ada yang salah


def test_field_wajib_selalu_terisi_pada_profil_normal():
    from scripts.synthdata import generate_assets
    for rec in generate_assets(100, seed=11, profile="normal"):
        # Profil normal (tanpa anomali) → inti aset koheren & tak kosong.
        assert rec["asset_code"] and rec["asset_name"] and rec["category"]
        assert "." in rec["asset_code"]  # pola kodefikasi BMN


def test_pilihan_dari_daftar_sah_pada_profil_normal():
    from scripts.synthdata import generate_assets
    from scripts.synthdata import valuebanks as vb
    import shared_utils as su

    for rec in generate_assets(120, seed=5, profile="normal"):
        assert rec["condition"] in su.VALID_CONDITIONS
        assert rec["status"] in su.VALID_STATUSES
        assert rec["inventory_status"] in su.VALID_INVENTORY_STATUSES
        assert rec["stiker_status"] in su.VALID_STIKER_STATUSES
        assert rec["category"] in vb.KATEGORI


def test_koherensi_status_inventarisasi():
    # Field turunan hanya terisi saat status inventarisasi cocok (profil normal).
    from scripts.synthdata import generate_assets
    for rec in generate_assets(300, seed=9, profile="normal"):
        if rec["inventory_status"] != "Tidak Ditemukan":
            assert rec["klasifikasi_tidak_ditemukan"] == ""
            assert rec["sub_klasifikasi"] == ""
        if rec["inventory_status"] == "Sengketa":
            assert rec["pihak_bersengketa"] != ""
        if rec["inventory_status"] == "Belum Diinventarisasi":
            # Belum diinventarisasi → belum ada titik koordinat.
            assert rec["koordinat_latitude"] == ""


def test_determinisme_seed_sama_keluaran_sama():
    from scripts.synthdata import generate_assets
    a = generate_assets(80, seed=123, profile="mixed")
    b = generate_assets(80, seed=123, profile="mixed")
    assert a == b
    c = generate_assets(80, seed=124, profile="mixed")
    assert a != c  # seed beda → keluaran beda


def test_profil_edge_menyuntikkan_anomali():
    from scripts.synthdata import generate_assets
    from scripts.synthdata.profiles import (
        EDGE_ANGKA, EDGE_KOORDINAT, EDGE_TANGGAL, EDGE_TEKS,
    )
    semua_anomali = set(EDGE_TANGGAL) | set(EDGE_ANGKA) | set(EDGE_KOORDINAT) | set(EDGE_TEKS)
    nilai_muncul = set()
    for rec in generate_assets(200, seed=7, profile="edge"):
        nilai_muncul.update(str(v) for v in rec.values())
    assert nilai_muncul & semua_anomali, "profil edge tidak menyuntik anomali apa pun"


def test_profil_normal_tanpa_anomali():
    from scripts.synthdata import generate_assets
    from scripts.synthdata.profiles import EDGE_TEKS
    penanda = {"'; DROP TABLE assets;--", "A" * 4000, "<script>alert('xss')</script>"}
    for rec in generate_assets(150, seed=2, profile="normal"):
        assert not (set(str(v) for v in rec.values()) & penanda)
    assert penanda & set(EDGE_TEKS)  # penanda memang bagian bank anomali


def test_profil_tak_dikenal_ditolak():
    from scripts.synthdata import generate_assets
    with pytest.raises(ValueError):
        generate_assets(5, profile="tidak-ada")


def test_activity_id_diteruskan():
    from scripts.synthdata import generate_assets
    for rec in generate_assets(10, seed=1, profile="normal", activity_id="keg-9"):
        assert rec["activity_id"] == "keg-9"


def test_generator_pegawai_satker_kegiatan():
    from scripts.synthdata import (
        generate_activity, generate_pegawai, generate_satker,
    )
    peg = generate_pegawai(20, seed=4)
    assert len(peg) == 20 and all(p["nip"].isdigit() and len(p["nip"]) == 18 for p in peg)
    sat = generate_satker(seed=4)
    assert sat and all(len(s["kode_satker_lengkap"]) == 20 for s in sat)
    keg = generate_activity(15, seed=4)
    assert len(keg) == 15 and all(k["name"] and 2023 <= k["tahun"] <= 2025 for k in keg)


def test_cli_main_menulis_ndjson(tmp_path):
    from scripts.synthdata.__main__ import main
    out = tmp_path / "aset.ndjson"
    rc = main(["-n", "8", "-p", "normal", "--format", "ndjson", "-o", str(out)])
    assert rc == 0
    baris = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(baris) == 8
    for b in baris:
        rec = json.loads(b)  # tiap baris JSON valid
        assert rec["asset_code"] and rec["asset_name"]
