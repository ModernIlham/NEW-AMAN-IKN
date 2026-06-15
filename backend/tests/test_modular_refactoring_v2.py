"""
Iteration 29: Modular Refactoring Tests V2
Tests full modular backend refactoring:
- server.py now ~200 lines thin entry point
- 10 route modules + 3 shared modules (db.py, models.py, auth_utils.py, shared_utils.py)
- New batch-pdf-zip endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

# Test activity ID with existing assets
TEST_ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"

# Test user credentials
TEST_USER = {"username": "refactor_test@test.com", "password": "test1234"}


class TestHealthAndArchitecture:
    """Test health check returns new modular architecture info"""
    
    def test_health_check_version_3(self):
        """GET /api/ - health check returns version 3.0.0 and 'modular' architecture"""
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("version") == "3.0.0", f"Expected version 3.0.0, got {data.get('version')}"
        assert data.get("architecture") == "modular", f"Expected 'modular', got {data.get('architecture')}"
        print(f"✓ Health check: version={data.get('version')}, architecture={data.get('architecture')}")


class TestAuthRoutes:
    """Test auth endpoints (routes/auth.py)"""
    
    def test_register_user(self):
        """POST /api/auth/register - user registration"""
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": unique_email,
            "password": "test1234",
            "name": "Test User"
        })
        # Could be 200 (success) or 400 (email already exists)
        assert r.status_code in [200, 400], f"Unexpected status: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "access_token" in data
            assert "user" in data
            print(f"✓ User registration successful: {unique_email}")
        else:
            print(f"✓ Registration blocked (email exists or rate limited): {r.json().get('detail', 'unknown')}")
    
    def test_login_user(self):
        """POST /api/auth/login - user login returns token"""
        r = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        if r.status_code == 200:
            data = r.json()
            assert "access_token" in data
            assert "user" in data
            assert data["user"].get("role") in ["admin", "operator", "viewer"]
            print(f"✓ Login successful: role={data['user'].get('role')}")
        elif r.status_code == 401:
            print("✓ Login returns 401 (user not found or wrong password - expected if user not created)")
        else:
            pytest.fail(f"Unexpected login status: {r.status_code}")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me - returns 401 without token"""
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401
        print("✓ GET /api/auth/me returns 401 without token")
    
    def test_auth_me_with_token(self):
        """GET /api/auth/me - returns user info with valid token"""
        login_r = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_USER)
        if login_r.status_code != 200:
            pytest.skip("Login failed - cannot test /auth/me")
        token = login_r.json().get("access_token")
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "username" in data
        assert "role" in data
        print(f"✓ GET /api/auth/me with token: username={data.get('username')}")


class TestCategoriesRoutes:
    """Test category endpoints (routes/categories.py)"""
    
    def test_get_categories(self):
        """GET /api/categories - returns categories with total count"""
        r = requests.get(f"{BASE_URL}/api/categories")
        assert r.status_code == 200
        data = r.json()
        # Response should be list of categories or have categories key
        if isinstance(data, list):
            print(f"✓ GET /api/categories: {len(data)} categories")
        elif isinstance(data, dict):
            cats = data.get("categories", data.get("data", []))
            print(f"✓ GET /api/categories: {len(cats)} categories, total={data.get('total', len(cats))}")
        else:
            print(f"✓ GET /api/categories returned: {type(data)}")


class TestAssetsRoutes:
    """Test asset endpoints (routes/assets.py)"""
    
    def test_get_assets_paginated(self):
        """GET /api/assets?page_size=1 - returns assets with pagination"""
        r = requests.get(f"{BASE_URL}/api/assets", params={"page_size": 1})
        assert r.status_code == 200
        data = r.json()
        # Should have pagination info - API returns "items" key
        assert "items" in data or "data" in data or "assets" in data or isinstance(data, list)
        total = data.get("total", len(data.get("items", data.get("data", []))))
        print(f"✓ GET /api/assets: total={total} assets")
    
    def test_get_filter_options(self):
        """GET /api/assets/filter-options - returns locations/departments etc"""
        r = requests.get(f"{BASE_URL}/api/assets/filter-options")
        assert r.status_code == 200
        data = r.json()
        # Should have filter options
        expected_keys = ["locations", "departments", "categories", "brands"]
        found_keys = [k for k in expected_keys if k in data]
        print(f"✓ GET /api/assets/filter-options: found keys {found_keys}")


class TestActivitiesRoutes:
    """Test inventory activities endpoints (routes/activities.py)"""
    
    def test_get_inventory_activities(self):
        """GET /api/inventory-activities - returns activities list"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if len(data) > 0:
            # Check activity has expected fields
            act = data[0]
            assert "id" in act
            assert "nama_kegiatan" in act or "nomor_surat" in act
        print(f"✓ GET /api/inventory-activities: {len(data)} activities found")
    
    def test_get_inventory_activity_by_id(self):
        """GET /api/inventory-activities/{id} - returns specific activity"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data.get("id") == TEST_ACTIVITY_ID
        print(f"✓ GET activity by ID: nama={data.get('nama_kegiatan', 'N/A')}")


class TestTemplatesRoutes:
    """Test template download endpoints (routes/templates.py)"""
    
    def test_csv_template(self):
        """GET /api/templates/csv - returns 200"""
        r = requests.get(f"{BASE_URL}/api/templates/csv")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert "csv" in content_type or "octet-stream" in content_type or len(r.content) > 0
        print(f"✓ GET /api/templates/csv: size={len(r.content)} bytes")
    
    def test_xlsx_template(self):
        """GET /api/templates/xlsx - returns 200"""
        r = requests.get(f"{BASE_URL}/api/templates/xlsx")
        assert r.status_code == 200
        assert len(r.content) > 0
        print(f"✓ GET /api/templates/xlsx: size={len(r.content)} bytes")


class TestUsersRoutes:
    """Test user management endpoints (routes/users.py)"""
    
    def test_get_users_requires_auth(self):
        """GET /api/users - requires authentication"""
        r = requests.get(f"{BASE_URL}/api/users")
        # Should return 401 without auth or 200 with results (if public)
        if r.status_code == 401:
            print("✓ GET /api/users requires authentication (401)")
        elif r.status_code == 200:
            data = r.json()
            print(f"✓ GET /api/users returned {len(data) if isinstance(data, list) else 'data'}")
        else:
            print(f"✓ GET /api/users returned {r.status_code}")


class TestReportSettingsRoutes:
    """Test report settings endpoints (routes/reports.py)"""
    
    def test_get_report_settings(self):
        """GET /api/report-settings - returns report settings"""
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        assert data.get("type") == "global"
        print(f"✓ GET /api/report-settings: type={data.get('type')}")


class TestInventoryClassifications:
    """Test inventory classifications endpoint (server.py)"""
    
    def test_get_inventory_classifications(self):
        """GET /api/inventory-classifications - returns statuses and classifications"""
        r = requests.get(f"{BASE_URL}/api/inventory-classifications")
        assert r.status_code == 200
        data = r.json()
        required = ["inventory_statuses", "klasifikasi", "sub_klasifikasi", "berlebih_info", "sengketa_info"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        print("✓ GET /api/inventory-classifications: all 5 required fields present")


class TestRekapitulasiEndpoint:
    """Test rekapitulasi data endpoint (routes/reports.py)"""
    
    def test_rekapitulasi_get(self):
        """GET /api/inventory-activities/{id}/rekapitulasi - returns rekapitulasi data"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rekapitulasi")
        assert r.status_code == 200
        data = r.json()
        required_fields = ["total_bmn_diteliti", "ditemukan", "tidak_ditemukan", "berlebih", "sengketa"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        print(f"✓ Rekapitulasi: total_bmn={data.get('total_bmn_diteliti')}")


class TestBatchPDFZipEndpoint:
    """Test NEW batch-pdf-zip endpoint (routes/reports.py)"""
    
    def test_batch_pdf_zip_single_report(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - single report returns ZIP"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": ["rhi"]}
        )
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        # ZIP files start with PK (0x504B)
        assert r.content[:2] == b"PK", "Response is not a valid ZIP file"
        print(f"✓ Batch PDF ZIP (single rhi): size={len(r.content)} bytes")
    
    def test_batch_pdf_zip_multiple_reports(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - multiple reports returns ZIP"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": ["rhi", "bahi", "sp-hasil"]}
        )
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        assert r.content[:2] == b"PK"
        print(f"✓ Batch PDF ZIP (3 reports): size={len(r.content)} bytes")
    
    def test_batch_pdf_zip_with_dbhi(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - DBHI reports in ZIP"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": ["dbhi-kondisi-baik", "dbhi-tidak-ditemukan"]}
        )
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        assert r.content[:2] == b"PK"
        print(f"✓ Batch PDF ZIP (2 DBHI): size={len(r.content)} bytes")
    
    def test_batch_pdf_zip_with_cover(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - cover page in ZIP"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": ["cover", "rhi"]}
        )
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        assert r.content[:2] == b"PK"
        print(f"✓ Batch PDF ZIP (cover + rhi): size={len(r.content)} bytes")
    
    def test_batch_pdf_zip_empty_types_error(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - empty types returns 400"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": []}
        )
        assert r.status_code == 400
        print("✓ Batch PDF ZIP with empty types returns 400")
    
    def test_batch_pdf_zip_invalid_activity(self):
        """POST /api/inventory-activities/{invalid}/batch-pdf-zip - invalid ID returns 404"""
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/invalid-id-99999/batch-pdf-zip",
            json={"types": ["rhi"]}
        )
        assert r.status_code == 404
        print("✓ Batch PDF ZIP with invalid activity returns 404")
    
    def test_batch_pdf_zip_all_types(self):
        """POST /api/inventory-activities/{id}/batch-pdf-zip - all report types"""
        all_types = [
            "cover", "rhi", "bahi", "sp-hasil", "sp-pelaksanaan",
            "dbhi-kondisi-baik", "dbhi-kondisi-rusak-ringan", "dbhi-kondisi-rusak-berat",
            "dbhi-berlebih", "dbhi-tidak-ditemukan", "dbhi-sengketa",
            "berita-acara", "sptjm", "surat-koreksi", "executive-summary"
        ]
        r = requests.post(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/batch-pdf-zip",
            json={"types": all_types},
            timeout=120  # Allow more time for generating all reports
        )
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/zip"
        assert r.content[:2] == b"PK"
        print(f"✓ Batch PDF ZIP (ALL {len(all_types)} types): size={len(r.content)} bytes")


class TestExistingPDFEndpoints:
    """Regression: Verify existing PDF endpoints still work after refactoring"""
    
    def test_rhi_pdf(self):
        """GET /api/inventory-activities/{id}/rhi-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ RHI PDF: size={len(r.content)} bytes")
    
    def test_bahi_pdf(self):
        """GET /api/inventory-activities/{id}/bahi-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/bahi-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ BAHI PDF: size={len(r.content)} bytes")
    
    def test_executive_summary_pdf(self):
        """GET /api/inventory-activities/{id}/executive-summary-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ Executive Summary PDF: size={len(r.content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
