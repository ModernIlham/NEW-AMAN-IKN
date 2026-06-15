
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Backend Tests for Iteration 62 - Backend Refactoring Verification
Tests for the modular refactoring: assets.py split into assets, batch, exports, media, audit modules.
API paths remain unchanged - this verifies all existing functionality still works.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"  # Activity with 451 assets

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = TEST_ADMIN_PASSWORD


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test session"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestAuthRoutes:
    """Test authentication routes (routes/auth.py)"""
    
    def test_login_success(self):
        """POST /api/auth/login - successful login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == TEST_USERNAME
        assert data["user"]["role"] == "admin"
        print("✓ POST /api/auth/login - PASS")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "invalid",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ POST /api/auth/login (invalid) - PASS")


class TestAssetsRoutes:
    """Test asset CRUD routes (routes/assets.py) - 572 lines"""
    
    def test_get_assets_list(self, auth_headers):
        """GET /api/assets - paginated asset list with activity_id"""
        response = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": ACTIVITY_ID, "page": 1, "page_size": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert data["total"] > 0, "Activity should have assets"
        print(f"✓ GET /api/assets - PASS (total: {data['total']} assets)")
    
    def test_get_filter_options(self, auth_headers):
        """GET /api/assets/filter-options - dropdown filter values"""
        response = requests.get(
            f"{BASE_URL}/api/assets/filter-options",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        assert "eselon1s" in data
        assert "eselon2s" in data
        assert "conditions" in data
        assert "statuses" in data
        print("✓ GET /api/assets/filter-options - PASS")
    
    def test_get_assets_stats(self, auth_headers):
        """GET /api/assets/stats - aggregate statistics"""
        response = requests.get(
            f"{BASE_URL}/api/assets/stats",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_assets" in data
        assert "total_value" in data
        assert data["total_assets"] > 0
        print(f"✓ GET /api/assets/stats - PASS (total: {data['total_assets']}, value: {data['total_value']})")
    
    def test_create_get_update_delete_asset(self, auth_headers):
        """Full CRUD cycle: POST -> GET -> PUT -> DELETE"""
        # CREATE
        unique_code = f"TEST_ITER62_{uuid.uuid4().hex[:8].upper()}"
        create_payload = {
            "asset_code": unique_code,
            "NUP": "001",
            "asset_name": "Test Asset Iteration 62",
            "category": "Testing Category",
            "brand": "TestBrand",
            "model": "TestModel",
            "location": "Test Location",
            "condition": "Baik",
            "status": "Aktif",
            "activity_id": ACTIVITY_ID
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/assets",
            json=create_payload,
            headers=auth_headers
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created_asset = create_response.json()
        assert created_asset["asset_code"] == unique_code
        asset_id = created_asset["id"]
        print(f"✓ POST /api/assets - PASS (created: {asset_id})")
        
        # GET single
        get_response = requests.get(
            f"{BASE_URL}/api/assets/{asset_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["id"] == asset_id
        assert fetched["asset_name"] == "Test Asset Iteration 62"
        print(f"✓ GET /api/assets/{asset_id} - PASS")
        
        # UPDATE
        update_payload = {**create_payload, "asset_name": "Updated Test Asset", "condition": "Rusak Ringan"}
        update_response = requests.put(
            f"{BASE_URL}/api/assets/{asset_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["asset_name"] == "Updated Test Asset"
        assert updated["condition"] == "Rusak Ringan"
        print(f"✓ PUT /api/assets/{asset_id} - PASS")
        
        # DELETE
        delete_response = requests.delete(
            f"{BASE_URL}/api/assets/{asset_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ DELETE /api/assets/{asset_id} - PASS")
        
        # Verify deleted
        verify_response = requests.get(
            f"{BASE_URL}/api/assets/{asset_id}",
            headers=auth_headers
        )
        assert verify_response.status_code == 404
        print("✓ Asset deletion verified - PASS")
    
    def test_get_nonexistent_asset_returns_404(self, auth_headers):
        """GET /api/assets/{id} - nonexistent asset returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/assets/nonexistent-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ GET /api/assets/{nonexistent} - PASS (404)")


class TestBatchRoutes:
    """Test batch operations routes (routes/batch.py) - 399 lines"""
    
    def test_lock_unlock_asset(self, auth_headers):
        """POST /api/assets/lock and /api/assets/unlock"""
        # Get first asset
        assets_response = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": ACTIVITY_ID, "page": 1, "page_size": 1},
            headers=auth_headers
        )
        assert assets_response.status_code == 200
        asset_id = assets_response.json()["items"][0]["id"]
        
        # Lock
        lock_headers = {**auth_headers, "X-User-Id": "test-user", "X-User-Name": "Test User", "X-Session-Id": "test-session-123"}
        lock_response = requests.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": asset_id},
            headers=lock_headers
        )
        assert lock_response.status_code == 200
        lock_data = lock_response.json()
        assert lock_data.get("locked") == True or lock_data.get("locked_by") is not None
        print(f"✓ POST /api/assets/lock - PASS (asset: {asset_id})")
        
        # Unlock
        unlock_response = requests.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": asset_id},
            headers=lock_headers
        )
        assert unlock_response.status_code == 200
        print("✓ POST /api/assets/unlock - PASS")
    
    def test_heartbeat_lock(self, auth_headers):
        """POST /api/assets/heartbeat - renew lock TTL"""
        # Get first asset
        assets_response = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": ACTIVITY_ID, "page": 1, "page_size": 1},
            headers=auth_headers
        )
        asset_id = assets_response.json()["items"][0]["id"]
        
        lock_headers = {**auth_headers, "X-User-Id": "test-user", "X-User-Name": "Test User", "X-Session-Id": "test-hb-session"}
        
        # Lock first
        requests.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": asset_id}, headers=lock_headers)
        
        # Heartbeat
        hb_response = requests.post(
            f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": asset_id},
            headers=lock_headers
        )
        assert hb_response.status_code == 200
        print("✓ POST /api/assets/heartbeat - PASS")
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": asset_id}, headers=lock_headers)
    
    def test_get_all_locks(self, auth_headers):
        """GET /api/assets/locks - list all locked assets"""
        response = requests.get(
            f"{BASE_URL}/api/assets/locks",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "locks" in data
        print(f"✓ GET /api/assets/locks - PASS (count: {len(data['locks'])})")
    
    def test_batch_update_with_clear(self, auth_headers):
        """PUT /api/assets/batch-update - batch update with __clear__ sentinel"""
        # Create test assets
        test_assets = []
        for i in range(2):
            unique_code = f"TEST_BATCH62_{uuid.uuid4().hex[:6].upper()}"
            create_response = requests.post(
                f"{BASE_URL}/api/assets",
                json={
                    "asset_code": unique_code,
                    "NUP": f"00{i+1}",
                    "asset_name": f"Batch Test Asset {i}",
                    "category": "Batch Test",
                    "location": "Original Location",
                    "brand": "OriginalBrand",
                    "activity_id": ACTIVITY_ID
                },
                headers=auth_headers
            )
            if create_response.status_code == 200:
                test_assets.append(create_response.json()["id"])
        
        assert len(test_assets) >= 2, "Need at least 2 test assets"
        
        # Batch update - set location and clear brand
        batch_headers = {**auth_headers, "X-User-Id": "test-user", "X-User-Name": "Test User", "X-Session-Id": "batch-test-session"}
        batch_response = requests.put(
            f"{BASE_URL}/api/assets/batch-update",
            json={
                "asset_ids": test_assets,
                "updates": {
                    "location": "Batch Updated Location",
                    "brand": "__clear__"
                }
            },
            headers=batch_headers
        )
        assert batch_response.status_code == 200
        batch_data = batch_response.json()
        assert batch_data["updated"] == len(test_assets)
        print(f"✓ PUT /api/assets/batch-update - PASS (updated: {batch_data['updated']})")
        
        # Verify updates
        for asset_id in test_assets:
            verify_response = requests.get(f"{BASE_URL}/api/assets/{asset_id}", headers=auth_headers)
            if verify_response.status_code == 200:
                asset = verify_response.json()
                assert asset["location"] == "Batch Updated Location", "Location should be updated"
                assert asset["brand"] == "", "Brand should be cleared (empty string)"
        print("✓ Batch update verification - PASS")
        
        # Cleanup
        for asset_id in test_assets:
            requests.delete(f"{BASE_URL}/api/assets/{asset_id}", headers=auth_headers)
    
    def test_get_all_asset_ids(self, auth_headers):
        """GET /api/assets/all-ids - get all IDs matching filters"""
        response = requests.get(
            f"{BASE_URL}/api/assets/all-ids",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "ids" in data
        assert "total" in data
        assert data["total"] > 0
        print(f"✓ GET /api/assets/all-ids - PASS (total: {data['total']})")
    
    def test_get_asset_groups(self, auth_headers):
        """GET /api/assets/groups - grouping by asset_code/name"""
        response = requests.get(
            f"{BASE_URL}/api/assets/groups",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert "total_groups" in data
        print(f"✓ GET /api/assets/groups - PASS (groups: {data['total_groups']})")


class TestExportRoutes:
    """Test export routes (routes/exports.py) - 815 lines"""
    
    def test_export_csv(self, auth_headers):
        """GET /api/export/csv - CSV export"""
        response = requests.get(
            f"{BASE_URL}/api/export/csv",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        # Check CSV headers
        content = response.text[:500]
        assert "asset_code" in content or "#" in content  # Has header row or activity info
        print("✓ GET /api/export/csv - PASS")
    
    def test_export_xlsx(self, auth_headers):
        """GET /api/export/xlsx - Excel export"""
        response = requests.get(
            f"{BASE_URL}/api/export/xlsx",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "spreadsheetml" in content_type or "octet-stream" in content_type
        print("✓ GET /api/export/xlsx - PASS")


class TestAuditRoutes:
    """Test audit log routes (routes/audit.py) - 33 lines"""
    
    def test_get_audit_logs(self, auth_headers):
        """GET /api/audit-logs - audit log retrieval"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": ACTIVITY_ID, "page": 1, "page_size": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        print(f"✓ GET /api/audit-logs - PASS (total: {data['total']})")


class TestMediaRoutes:
    """Test image compression routes (routes/media.py) - 149 lines"""
    
    def test_get_compression_stats(self, auth_headers):
        """GET /api/compression-stats - Tinify usage stats"""
        response = requests.get(
            f"{BASE_URL}/api/compression-stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "tinify_available" in data
        assert "monthly_limit" in data
        print(f"✓ GET /api/compression-stats - PASS (tinify available: {data['tinify_available']})")


class TestRouterOrdering:
    """Test that route ordering is correct (batch_router before assets_router)"""
    
    def test_all_ids_route_accessible(self, auth_headers):
        """Verify /api/assets/all-ids is accessible (not caught by {asset_id})"""
        response = requests.get(
            f"{BASE_URL}/api/assets/all-ids",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        # Should return 200, not 404 (which would happen if caught by {asset_id})
        assert response.status_code == 200
        data = response.json()
        assert "ids" in data, "Response should have 'ids' key, not asset error"
        print("✓ Route ordering: /api/assets/all-ids accessible - PASS")
    
    def test_groups_route_accessible(self, auth_headers):
        """Verify /api/assets/groups is accessible (not caught by {asset_id})"""
        response = requests.get(
            f"{BASE_URL}/api/assets/groups",
            params={"activity_id": ACTIVITY_ID},
            headers=auth_headers
        )
        # Should return 200, not 404
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data, "Response should have 'groups' key"
        print("✓ Route ordering: /api/assets/groups accessible - PASS")
    
    def test_locks_route_accessible(self, auth_headers):
        """Verify /api/assets/locks is accessible"""
        response = requests.get(
            f"{BASE_URL}/api/assets/locks",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "locks" in data
        print("✓ Route ordering: /api/assets/locks accessible - PASS")


class TestHealthCheck:
    """Test health check endpoints"""
    
    def test_root_health(self):
        """GET /health - Kubernetes health probe"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ GET /health - PASS")
    
    def test_api_health(self):
        """GET /api/ - API health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert "version" in data
        print(f"✓ GET /api/ - PASS (version: {data.get('version')})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
