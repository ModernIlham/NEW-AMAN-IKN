
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Iteration 63: Complete Refactoring Verification Test Suite
Tests both backend (modular routes) and frontend (custom hooks) after full refactoring.

Backend: assets.py (1312 lines) -> 5 modular files:
  - routes/assets.py (572L) - CRUD, filter-options, stats, analytics
  - routes/batch.py (399L) - lock/unlock/heartbeat, batch-update, groups, all-ids
  - routes/exports.py (815L) - CSV/XLSX export, doc-file serving, bulk delete
  - routes/media.py (149L) - image compression
  - routes/audit.py (33L) - audit logs

Frontend: DashboardPage.jsx (1312 -> 663 lines) with 4 custom hooks:
  - useRowLocking.js (86L)
  - useAssetFilters.js (104L)
  - usePullToRefresh.js (65L)
  - useDragDropImport.js (58L)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"  # Has 451 assets


class TestAuth:
    """Authentication endpoint tests - routes/auth.py"""
    
    def test_login_success(self):
        """POST /api/auth/login - valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        print("✓ Login success - admin user authenticated")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Login invalid - correctly returns 401")


class TestAssetsCRUD:
    """Asset CRUD endpoints - routes/assets.py"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_assets_paginated(self):
        """GET /api/assets - paginated list with activity filter"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert len(data["items"]) <= 50
        print(f"✓ Assets list - {len(data['items'])} items, total: {data['total']}")
    
    def test_get_filter_options(self):
        """GET /api/assets/filter-options - dropdown values"""
        response = requests.get(f"{BASE_URL}/api/assets/filter-options", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        assert "conditions" in data
        assert "statuses" in data
        print(f"✓ Filter options - {len(data.get('locations', []))} locations")
    
    def test_get_stats(self):
        """GET /api/assets/stats - aggregate statistics"""
        response = requests.get(f"{BASE_URL}/api/assets/stats", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert "total_assets" in data
        assert "total_value" in data
        print(f"✓ Stats - {data['total_assets']} assets, value: {data['total_value']}")
    
    def test_get_analytics(self):
        """GET /api/assets/analytics - chart data"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert "by_category" in data
        assert "by_condition" in data
        print(f"✓ Analytics - {len(data.get('by_category', []))} categories")
    
    def test_create_update_delete_asset(self, auth_token):
        """Full CRUD cycle - create, get, update, delete"""
        headers = {"Authorization": f"Bearer {auth_token}", "X-Audit-User": "test_agent"}
        
        # CREATE
        test_code = f"TEST_{uuid.uuid4().hex[:8].upper()}"
        create_payload = {
            "asset_code": test_code,
            "NUP": "001",
            "asset_name": "Test Asset Iteration 63",
            "category": "Test Category",
            "activity_id": ACTIVITY_ID
        }
        r_create = requests.post(f"{BASE_URL}/api/assets", json=create_payload, headers=headers)
        assert r_create.status_code == 200, f"Create failed: {r_create.text}"
        created = r_create.json()
        asset_id = created["id"]
        print(f"✓ Create asset - ID: {asset_id}")
        
        # GET single
        r_get = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert r_get.status_code == 200
        assert r_get.json()["asset_code"] == test_code
        print(f"✓ Get asset - verified code: {test_code}")
        
        # UPDATE
        update_payload = {**create_payload, "asset_name": "Updated Test Asset"}
        r_update = requests.put(f"{BASE_URL}/api/assets/{asset_id}", json=update_payload, headers=headers)
        assert r_update.status_code == 200
        assert r_update.json()["asset_name"] == "Updated Test Asset"
        print("✓ Update asset - name changed")
        
        # DELETE
        r_delete = requests.delete(f"{BASE_URL}/api/assets/{asset_id}", headers=headers)
        assert r_delete.status_code == 200
        print("✓ Delete asset - removed")
        
        # Verify deletion
        r_verify = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert r_verify.status_code == 404
        print("✓ Delete verified - 404 returned")
    
    def test_get_nonexistent_asset(self):
        """GET /api/assets/{id} - nonexistent returns 404"""
        response = requests.get(f"{BASE_URL}/api/assets/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ Nonexistent asset - correctly returns 404")


class TestBatchOperations:
    """Batch operations & row locking - routes/batch.py (CRITICAL: must be before assets_router)"""
    
    @pytest.fixture
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        user = response.json()["user"]
        return {
            "Authorization": f"Bearer {token}",
            "x-user-id": user["id"],
            "x-user-name": user["name"],
            "x-session-id": f"test_session_{uuid.uuid4().hex[:8]}"
        }
    
    def test_get_all_ids_route_ordering(self):
        """GET /api/assets/all-ids - route ordering test (must not be caught by /{asset_id})"""
        response = requests.get(f"{BASE_URL}/api/assets/all-ids", params={
            "activity_id": ACTIVITY_ID
        })
        # If route ordering is wrong, this would 404 or fail
        assert response.status_code == 200, f"Route ordering issue: {response.status_code} {response.text}"
        data = response.json()
        assert "ids" in data
        assert "total" in data
        print(f"✓ All IDs route - {data['total']} asset IDs (route ordering correct)")
    
    def test_asset_groups(self):
        """GET /api/assets/groups - grouping by same asset_code"""
        response = requests.get(f"{BASE_URL}/api/assets/groups", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        print(f"✓ Asset groups - {data.get('total_groups', 0)} groups found")
    
    def test_lock_unlock_heartbeat(self, auth_headers):
        """POST /api/assets/lock, /unlock, /heartbeat - row locking flow"""
        # First get a real asset ID
        r_list = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID, "page_size": 1
        })
        assets = r_list.json().get("items", [])
        if not assets:
            pytest.skip("No assets to test locking")
        
        asset_id = assets[0]["id"]
        
        # LOCK
        r_lock = requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": asset_id}, headers=auth_headers)
        assert r_lock.status_code == 200
        assert r_lock.json().get("locked") == True
        print("✓ Lock asset - locked successfully")
        
        # HEARTBEAT
        r_heartbeat = requests.post(f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": asset_id}, headers=auth_headers)
        assert r_heartbeat.status_code == 200
        print("✓ Heartbeat - lock renewed")
        
        # UNLOCK
        r_unlock = requests.post(f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": asset_id}, headers=auth_headers)
        assert r_unlock.status_code == 200
        assert r_unlock.json().get("unlocked") == True
        print("✓ Unlock asset - unlocked successfully")
    
    def test_get_locks(self):
        """GET /api/assets/locks - get all active locks"""
        response = requests.get(f"{BASE_URL}/api/assets/locks")
        assert response.status_code == 200
        data = response.json()
        assert "locks" in data
        print(f"✓ Get locks - {len(data['locks'])} active locks")
    
    def test_batch_update_with_clear_sentinel(self, auth_headers):
        """PUT /api/assets/batch-update - with __clear__ sentinel value"""
        # Create test asset first
        test_code = f"TEST_BATCH_{uuid.uuid4().hex[:8].upper()}"
        r_create = requests.post(f"{BASE_URL}/api/assets", json={
            "asset_code": test_code,
            "NUP": "001",
            "asset_name": "Batch Test Asset",
            "category": "Test",
            "location": "Initial Location",
            "activity_id": ACTIVITY_ID
        }, headers=auth_headers)
        assert r_create.status_code == 200
        asset_id = r_create.json()["id"]
        
        try:
            # Batch update with __clear__ to clear location
            r_batch = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
                "asset_ids": [asset_id],
                "updates": {"location": "__clear__"}
            }, headers=auth_headers, timeout=60)
            assert r_batch.status_code == 200, f"Batch update failed: {r_batch.text}"
            assert r_batch.json().get("updated", 0) > 0
            print("✓ Batch update with __clear__ - location cleared")
            
            # Verify location is cleared
            r_verify = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
            assert r_verify.status_code == 200
            assert r_verify.json().get("location") == ""
            print("✓ Verified - location is now empty string")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/assets/{asset_id}", headers=auth_headers)
    
    def test_batch_update_clear_photos(self, auth_headers):
        """PUT /api/assets/batch-update - with clear_photos=true"""
        # Create test asset with photo placeholder
        test_code = f"TEST_PHOTO_{uuid.uuid4().hex[:8].upper()}"
        r_create = requests.post(f"{BASE_URL}/api/assets", json={
            "asset_code": test_code,
            "NUP": "001",
            "asset_name": "Photo Clear Test",
            "category": "Test",
            "activity_id": ACTIVITY_ID
        }, headers=auth_headers)
        assert r_create.status_code == 200
        asset_id = r_create.json()["id"]
        
        try:
            # Batch update with clear_photos
            r_batch = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
                "asset_ids": [asset_id],
                "updates": {"clear_photos": True}
            }, headers=auth_headers, timeout=60)
            assert r_batch.status_code == 200
            print("✓ Batch update clear_photos - executed")
        finally:
            requests.delete(f"{BASE_URL}/api/assets/{asset_id}", headers=auth_headers)


class TestExports:
    """Export endpoints - routes/exports.py (CRITICAL: must be before assets_router)"""
    
    def test_csv_export(self):
        """GET /api/export/csv - CSV export streaming"""
        response = requests.get(f"{BASE_URL}/api/export/csv", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        # Check we get some data
        content = response.text
        assert len(content) > 100
        assert "asset_code" in content.lower() or "kode" in content.lower()
        print(f"✓ CSV export - {len(content)} bytes received")
    
    def test_xlsx_export(self):
        """GET /api/export/xlsx - Excel export"""
        response = requests.get(f"{BASE_URL}/api/export/xlsx", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        assert "spreadsheet" in response.headers.get("Content-Type", "")
        # Excel files start with PK (zip signature)
        assert response.content[:2] == b'PK', "Not a valid Excel file"
        print(f"✓ XLSX export - {len(response.content)} bytes, valid Excel")


class TestAuditLogs:
    """Audit log endpoints - routes/audit.py"""
    
    def test_get_audit_logs(self):
        """GET /api/audit-logs - retrieve audit trail"""
        response = requests.get(f"{BASE_URL}/api/audit-logs", params={
            "activity_id": ACTIVITY_ID,
            "page": 1,
            "page_size": 20
        })
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        print(f"✓ Audit logs - {len(data['logs'])} logs, total: {data['total']}")


class TestMediaCompression:
    """Image compression endpoints - routes/media.py"""
    
    def test_compression_stats(self):
        """GET /api/compression-stats - Tinify usage stats"""
        response = requests.get(f"{BASE_URL}/api/compression-stats")
        assert response.status_code == 200
        data = response.json()
        assert "tinify_available" in data
        assert "monthly_limit" in data
        print(f"✓ Compression stats - Tinify available: {data['tinify_available']}, remaining: {data.get('remaining', 'N/A')}")


class TestAPIHealth:
    """API health check"""
    
    def test_api_health(self):
        """GET /api/ - API running check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ API health - status OK, version: {data.get('version', 'unknown')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
