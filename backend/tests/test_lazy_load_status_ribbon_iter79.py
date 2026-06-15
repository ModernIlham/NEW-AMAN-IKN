"""Iteration 79 — Backend tests for:
- Activity list endpoint strips heavy fields & exposes photos_count/documents_count
- Activity GET single returns full photos/documents for lazy-load
- PUT with photos=null preserves existing data; photos=[] wipes
- Max limit enforcement (10 photos / 5 documents)
- Completion-status endpoint
- Asset PATCH OCC regression (no version-conflict false positive)
- Backup endpoints regression
"""
import os
import io
import base64
import uuid
import time
import requests
import pytest
from PIL import Image as PILImage

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
USERNAME = "bugfix_admin_test2"
PASSWORD = "BugfixTest123"


def _png_b64():
    img = PILImage.new("RGB", (8, 8), color=(123, 200, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        pytest.skip(f"No token in login response: {r.json()}")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def activity(session):
    """Create an activity with 2 photos + 1 document for tests; cleaned up at the end."""
    nomor = f"TEST-ITER79-{uuid.uuid4().hex[:8]}"
    photo1 = _png_b64()
    photo2 = _png_b64()
    doc1 = {"name": "doc1.pdf", "data": "data:application/pdf;base64,JVBERi0xLjQKJeLjz9MK", "type": "application/pdf"}
    payload = {
        "nomor_surat": nomor,
        "nama_kegiatan": f"TEST Iter79 {nomor}",
        "kode_satker": "TEST79",
        "nama_satker": "TEST Satker 79",
        "tanggal_mulai": "2024-01-01",
        "tanggal_selesai": "2024-12-31",
        "photos": [photo1, photo2],
        "documents": [doc1],
        "asset_ids": [],
    }
    r = session.post(f"{BASE_URL}/api/inventory-activities", json=payload, timeout=60)
    assert r.status_code == 200, f"Create failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    aid = data["id"]
    yield aid
    # Cleanup
    try:
        session.delete(f"{BASE_URL}/api/inventory-activities/{aid}", timeout=30)
    except Exception:
        pass


# ===== List endpoint strips heavy fields =====
class TestListEndpoint:
    def test_list_strips_heavy_includes_counts(self, session, activity):
        r = session.get(f"{BASE_URL}/api/inventory-activities", timeout=60)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        match = next((a for a in items if a.get("id") == activity), None)
        assert match is not None, "Created activity not found in list"
        # Must NOT contain heavy arrays
        assert "photos" not in match, "List endpoint must strip 'photos'"
        assert "photo_thumbnails" not in match, "List endpoint must strip 'photo_thumbnails'"
        assert "documents" not in match, "List endpoint must strip 'documents'"
        # Must contain count fields
        assert match.get("photos_count") == 2, f"Expected photos_count=2, got {match.get('photos_count')}"
        assert match.get("documents_count") == 1, f"Expected documents_count=1, got {match.get('documents_count')}"


# ===== GET single returns full payload =====
class TestGetSingle:
    def test_get_single_returns_full_arrays(self, session, activity):
        r = session.get(f"{BASE_URL}/api/inventory-activities/{activity}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("photos"), list) and len(data["photos"]) == 2
        assert isinstance(data.get("documents"), list) and len(data["documents"]) == 1
        # Each photo should be a non-empty base64 data URL
        assert all(isinstance(p, str) and len(p) > 50 for p in data["photos"])


# ===== PUT preserves on null =====
class TestPutPreserveSemantics:
    def test_put_with_photos_null_preserves_existing(self, session, activity):
        # Get current state first
        before = session.get(f"{BASE_URL}/api/inventory-activities/{activity}").json()
        before_photos_len = len(before["photos"])
        before_docs_len = len(before["documents"])
        assert before_photos_len == 2 and before_docs_len == 1

        # Update only nama, omit photos/documents (so Pydantic gets None)
        payload = {
            "nomor_surat": before["nomor_surat"],
            "nama_kegiatan": before["nama_kegiatan"] + " UPDATED",
            "kode_satker": before["kode_satker"],
            "nama_satker": before["nama_satker"],
            # photos/documents OMITTED → None → preserve
        }
        r = session.put(f"{BASE_URL}/api/inventory-activities/{activity}", json=payload, timeout=30)
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text[:300]}"
        # Verify via GET
        after = session.get(f"{BASE_URL}/api/inventory-activities/{activity}").json()
        assert "UPDATED" in after["nama_kegiatan"]
        assert len(after["photos"]) == before_photos_len, "Photos must be preserved when photos field omitted"
        assert len(after["documents"]) == before_docs_len, "Documents must be preserved when omitted"

    def test_put_with_photos_explicit_empty_wipes(self, session, activity):
        before = session.get(f"{BASE_URL}/api/inventory-activities/{activity}").json()
        payload = {
            "nomor_surat": before["nomor_surat"],
            "nama_kegiatan": before["nama_kegiatan"],
            "kode_satker": before["kode_satker"],
            "nama_satker": before["nama_satker"],
            "photos": [],  # explicit empty → wipe
            # documents omitted → preserve
        }
        r = session.put(f"{BASE_URL}/api/inventory-activities/{activity}", json=payload, timeout=30)
        assert r.status_code == 200
        after = session.get(f"{BASE_URL}/api/inventory-activities/{activity}").json()
        assert after["photos"] == [], "photos=[] should wipe photos"
        assert len(after["documents"]) == 1, "documents must remain when omitted"


# ===== Max limit enforcement =====
class TestMaxLimits:
    def test_post_more_than_10_photos_rejected(self, session):
        photos = [_png_b64() for _ in range(11)]
        payload = {
            "nomor_surat": f"TEST-MAX-{uuid.uuid4().hex[:6]}",
            "nama_kegiatan": "TEST max photos",
            "kode_satker": "TEST79",
            "nama_satker": "TEST Satker 79",
            "photos": photos,
        }
        r = session.post(f"{BASE_URL}/api/inventory-activities", json=payload, timeout=60)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"
        assert "10" in r.text and "foto" in r.text.lower()

    def test_post_more_than_5_documents_rejected(self, session):
        docs = [{"name": f"d{i}.pdf", "data": "data:application/pdf;base64,JVBERi0xLjQK", "type": "application/pdf"} for i in range(6)]
        payload = {
            "nomor_surat": f"TEST-MAXD-{uuid.uuid4().hex[:6]}",
            "nama_kegiatan": "TEST max docs",
            "kode_satker": "TEST79",
            "nama_satker": "TEST Satker 79",
            "documents": docs,
        }
        r = session.post(f"{BASE_URL}/api/inventory-activities", json=payload, timeout=30)
        assert r.status_code == 400
        assert "5" in r.text and "dokumen" in r.text.lower()

    def test_put_more_than_10_photos_rejected(self, session, activity):
        before = session.get(f"{BASE_URL}/api/inventory-activities/{activity}").json()
        photos = [_png_b64() for _ in range(11)]
        payload = {
            "nomor_surat": before["nomor_surat"],
            "nama_kegiatan": before["nama_kegiatan"],
            "kode_satker": before["kode_satker"],
            "nama_satker": before["nama_satker"],
            "photos": photos,
        }
        r = session.put(f"{BASE_URL}/api/inventory-activities/{activity}", json=payload, timeout=60)
        assert r.status_code == 400


# ===== Completion-status endpoint =====
class TestCompletionStatus:
    def test_completion_status_basic(self, session, activity):
        r = session.get(f"{BASE_URL}/api/inventory-activities/{activity}/completion-status", timeout=30)
        assert r.status_code == 200
        data = r.json()
        for key in ["activity_id", "date_phase", "computed_status", "total_assets",
                    "pending_inventory_count", "no_photo_count"]:
            assert key in data, f"Missing key: {key}"
        # No assets linked → all_inventoried=False, computed_status should reflect date phase
        # Activity tanggal_selesai=2024-12-31, today is 2026 → should be selesai_tanggal but with 0 assets → belum_lengkap
        assert data["total_assets"] == 0
        assert data["computed_status"] in ["belum_dimulai", "berlangsung", "belum_lengkap", "selesai_tanggal", "selesai"]

    def test_completion_status_404(self, session):
        r = session.get(f"{BASE_URL}/api/inventory-activities/nonexistent-xyz-123/completion-status", timeout=15)
        assert r.status_code == 404


# ===== Asset PATCH OCC regression =====
class TestAssetPatchOCC:
    def test_patch_asset_with_correct_version(self, session):
        # Pick an existing asset, PATCH it with valid version, expect no OCC conflict
        r = session.get(f"{BASE_URL}/api/assets?limit=1", timeout=30)
        if r.status_code != 200:
            pytest.skip(f"Cannot list assets: {r.status_code}")
        items = r.json().get("items", [])
        if not items:
            pytest.skip("No existing assets to test PATCH")
        a = items[0]
        aid = a["id"]
        version = a.get("version", 0)
        original_notes = a.get("notes", "")
        # PATCH with version → must succeed (no false OCC conflict)
        r = session.patch(
            f"{BASE_URL}/api/assets/{aid}",
            json={"notes": f"OCC-test-{uuid.uuid4().hex[:6]}", "version": version},
            timeout=30,
        )
        assert r.status_code == 200, f"PATCH failed (OCC regression): {r.status_code} {r.text[:300]}"
        # Restore original notes
        r2 = session.get(f"{BASE_URL}/api/assets/{aid}", timeout=15)
        if r2.status_code == 200:
            new_ver = r2.json().get("version", version + 1)
            session.patch(
                f"{BASE_URL}/api/assets/{aid}",
                json={"notes": original_notes, "version": new_ver},
                timeout=15,
            )


# ===== Backup endpoints regression =====
class TestBackupRegression:
    def test_backup_active_endpoint(self, session):
        r = session.get(f"{BASE_URL}/api/backup/active", timeout=30)
        # Either 200 with payload or 200 with null/empty — never 500
        assert r.status_code == 200, f"backup/active broken: {r.status_code} {r.text[:200]}"

    def test_backup_start_endpoint(self, session):
        r = session.post(f"{BASE_URL}/api/backup/start", json={}, timeout=30)
        # Should accept (200/202) or rate-limit/conflict (409). Must not 5xx.
        assert r.status_code < 500, f"backup/start 5xx: {r.status_code} {r.text[:200]}"
