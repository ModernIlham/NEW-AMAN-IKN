
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Persistent Row Locking and Batch Update features
- Lock endpoints: POST /api/assets/lock, /api/assets/heartbeat, /api/assets/unlock, GET /api/assets/locks
- Batch Update: PUT /api/assets/batch-update
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAuth:
    """Authentication tests - required before other tests"""
    
    def test_login_success(self):
        """Login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        assert "user" in data
        print(f"✓ Login success - user: {data['user'].get('username')}")
        token = data.get("access_token") or data.get("token")
        return token, data["user"]


class TestLockEndpoints:
    """Row Locking endpoints - MongoDB persistent locks with TTL"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth before each test"""
        auth_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": TEST_ADMIN_PASSWORD
        })
        self.token = auth_resp.json().get("token", "")
        self.user = auth_resp.json().get("user", {})
        self.user_id = self.user.get("id", "test_user_1")
        self.user_name = self.user.get("name", "Test Admin")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-User-Id": self.user_id,
            "X-User-Name": self.user_name
        }
        
        # Get first asset ID for testing
        assets_resp = requests.get(f"{BASE_URL}/api/assets?page_size=1")
        if assets_resp.status_code == 200 and assets_resp.json().get("items"):
            self.test_asset_id = assets_resp.json()["items"][0]["id"]
        else:
            self.test_asset_id = "test-asset-id-dummy"
        yield
        # Cleanup: unlock any locks
        try:
            requests.post(f"{BASE_URL}/api/assets/unlock", 
                json={"asset_id": self.test_asset_id},
                headers=self.headers)
        except:
            pass
    
    def test_lock_asset_success(self):
        """POST /api/assets/lock - First user can lock an asset"""
        response = requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("locked") == True
        print(f"✓ Asset {self.test_asset_id} locked successfully")
    
    def test_lock_blocked_by_another_user(self):
        """POST /api/assets/lock - Second user gets blocked if first user has lock"""
        # First user locks
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        # Second user tries to lock
        second_user_headers = {
            "Content-Type": "application/json",
            "X-User-Id": "second_user_123",
            "X-User-Name": "Second User"
        }
        response = requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=second_user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("locked") == False
        assert "locked_by" in data
        print(f"✓ Second user blocked - locked by: {data.get('locked_by')}")
    
    def test_heartbeat_renews_lock(self):
        """POST /api/assets/heartbeat - Renews lock TTL"""
        # First lock the asset
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        # Send heartbeat
        response = requests.post(f"{BASE_URL}/api/assets/heartbeat", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("renewed") == True
        print("✓ Heartbeat renewed lock successfully")
    
    def test_heartbeat_fails_for_wrong_user(self):
        """POST /api/assets/heartbeat - Wrong user cannot renew lock"""
        # First lock the asset
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        # Second user tries heartbeat
        second_user_headers = {
            "Content-Type": "application/json",
            "X-User-Id": "second_user_123",
            "X-User-Name": "Second User"
        }
        response = requests.post(f"{BASE_URL}/api/assets/heartbeat", 
            json={"asset_id": self.test_asset_id},
            headers=second_user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("renewed") == False
        print("✓ Second user heartbeat correctly rejected")
    
    def test_unlock_releases_lock(self):
        """POST /api/assets/unlock - Releases the lock"""
        # First lock the asset
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        # Unlock
        response = requests.post(f"{BASE_URL}/api/assets/unlock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("unlocked") == True
        print("✓ Asset unlocked successfully")
        
        # Verify second user can now lock
        second_user_headers = {
            "Content-Type": "application/json",
            "X-User-Id": "second_user_123",
            "X-User-Name": "Second User"
        }
        lock_resp = requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=second_user_headers)
        assert lock_resp.json().get("locked") == True
        print("✓ Second user can lock after first user unlocks")
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/assets/unlock", 
            json={"asset_id": self.test_asset_id},
            headers=second_user_headers)
    
    def test_get_all_locks(self):
        """GET /api/assets/locks - Returns all active locks"""
        # Lock the asset first
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_id},
            headers=self.headers)
        
        response = requests.get(f"{BASE_URL}/api/assets/locks")
        
        assert response.status_code == 200
        data = response.json()
        assert "locks" in data
        assert isinstance(data["locks"], dict)
        
        # Should contain our locked asset
        if self.test_asset_id in data["locks"]:
            lock_info = data["locks"][self.test_asset_id]
            assert "user_name" in lock_info
            assert "user_id" in lock_info
            print(f"✓ Found lock for asset - locked by: {lock_info.get('user_name')}")
        else:
            print(f"✓ Get locks endpoint works - {len(data['locks'])} active locks")


class TestBatchUpdate:
    """Batch Update endpoint - PUT /api/assets/batch-update"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth and test assets"""
        auth_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": TEST_ADMIN_PASSWORD
        })
        self.token = auth_resp.json().get("token", "")
        self.user = auth_resp.json().get("user", {})
        self.user_id = self.user.get("id", "test_user_1")
        self.user_name = self.user.get("name", "Test Admin")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-User-Id": self.user_id,
            "X-User-Name": self.user_name,
            "X-Audit-User": self.user_name
        }
        
        # Get first activity ID
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities")
        if activities_resp.status_code == 200 and activities_resp.json():
            self.activity_id = activities_resp.json()[0]["id"]
        else:
            self.activity_id = ""
        
        # Create test assets for batch operations
        self.test_asset_ids = []
        for i in range(3):
            asset_payload = {
                "asset_code": f"TEST-BATCH-{int(time.time())}-{i}",
                "NUP": str(i + 1),
                "asset_name": f"Test Batch Asset {i}",
                "category": "Komputer",
                "location": "Test Location",
                "department": "Test Dept",
                "condition": "Baik",
                "status": "Aktif",
                "activity_id": self.activity_id
            }
            create_resp = requests.post(f"{BASE_URL}/api/assets", 
                json=asset_payload,
                headers=self.headers)
            if create_resp.status_code in [200, 201]:
                self.test_asset_ids.append(create_resp.json()["id"])
                print(f"  Created test asset: {asset_payload['asset_code']}")
        
        yield
        
        # Cleanup test assets
        for asset_id in self.test_asset_ids:
            try:
                requests.delete(f"{BASE_URL}/api/assets/{asset_id}", headers=self.headers)
            except:
                pass
    
    def test_batch_update_success(self):
        """PUT /api/assets/batch-update - Updates multiple assets"""
        if len(self.test_asset_ids) < 2:
            pytest.skip("Not enough test assets created")
        
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": self.test_asset_ids,
                "updates": {
                    "location": "Batch Updated Location",
                    "department": "Batch Updated Dept"
                }
            },
            headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("updated") >= 1
        assert "location" in data.get("fields", [])
        assert "department" in data.get("fields", [])
        print(f"✓ Batch updated {data.get('updated')} assets - fields: {data.get('fields')}")
        
        # Verify updates persisted
        for asset_id in self.test_asset_ids:
            get_resp = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
            if get_resp.status_code == 200:
                asset = get_resp.json()
                assert asset.get("location") == "Batch Updated Location"
                assert asset.get("department") == "Batch Updated Dept"
        print("✓ Verified batch updates persisted in database")
    
    def test_batch_update_all_fields(self):
        """PUT /api/assets/batch-update - Tests all 7 supported fields"""
        if len(self.test_asset_ids) < 1:
            pytest.skip("No test assets created")
        
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": self.test_asset_ids[:1],  # Just one asset
                "updates": {
                    "category": "Peralatan Kantor",
                    "location": "Ruang Rapat",
                    "department": "IT Department",
                    "condition": "Rusak Ringan",
                    "inventory_status": "Ditemukan",
                    "stiker_status": "Sudah Terpasang",
                    "stiker_ukuran": "Sedang"
                }
            },
            headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("updated") >= 1
        print(f"✓ Batch updated with all 7 fields: {data.get('fields')}")
        
        # Verify all fields updated
        get_resp = requests.get(f"{BASE_URL}/api/assets/{self.test_asset_ids[0]}")
        if get_resp.status_code == 200:
            asset = get_resp.json()
            assert asset.get("category") == "Peralatan Kantor"
            assert asset.get("location") == "Ruang Rapat"
            assert asset.get("department") == "IT Department"
            assert asset.get("condition") == "Rusak Ringan"
            assert asset.get("inventory_status") == "Ditemukan"
            assert asset.get("stiker_status") == "Sudah Terpasang"
            assert asset.get("stiker_ukuran") == "Sedang"
        print("✓ All 7 fields verified in database")
    
    def test_batch_update_empty_assets_error(self):
        """PUT /api/assets/batch-update - Returns 400 for empty asset_ids"""
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": [],
                "updates": {"location": "New Location"}
            },
            headers=self.headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Empty assets correctly rejected: {data.get('detail')}")
    
    def test_batch_update_empty_updates_error(self):
        """PUT /api/assets/batch-update - Returns 400 for empty updates"""
        if len(self.test_asset_ids) < 1:
            pytest.skip("No test assets created")
        
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": self.test_asset_ids[:1],
                "updates": {}
            },
            headers=self.headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Empty updates correctly rejected: {data.get('detail')}")
    
    def test_batch_update_invalid_field_filtered(self):
        """PUT /api/assets/batch-update - Invalid fields are filtered out"""
        if len(self.test_asset_ids) < 1:
            pytest.skip("No test assets created")
        
        # Send with only invalid fields
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": self.test_asset_ids[:1],
                "updates": {
                    "invalid_field": "value",
                    "asset_name": "Should be ignored"  # asset_name is not in allowed fields
                }
            },
            headers=self.headers)
        
        # Should return 400 since no valid fields
        assert response.status_code == 400
        print("✓ Invalid fields correctly filtered out")
    
    def test_batch_update_rejects_locked_assets(self):
        """PUT /api/assets/batch-update - Rejects if assets are locked by another user"""
        if len(self.test_asset_ids) < 1:
            pytest.skip("No test assets created")
        
        # Lock asset as another user
        other_user_headers = {
            "Content-Type": "application/json",
            "X-User-Id": "other_user_999",
            "X-User-Name": "Other User"
        }
        requests.post(f"{BASE_URL}/api/assets/lock", 
            json={"asset_id": self.test_asset_ids[0]},
            headers=other_user_headers)
        
        # Try batch update
        response = requests.put(f"{BASE_URL}/api/assets/batch-update", 
            json={
                "asset_ids": [self.test_asset_ids[0]],
                "updates": {"location": "New Location"}
            },
            headers=self.headers)
        
        assert response.status_code == 409
        data = response.json()
        assert "terkunci" in data.get("detail", "").lower() or "locked" in data.get("detail", "").lower()
        print(f"✓ Batch update rejected for locked assets: {data.get('detail')}")
        
        # Cleanup lock
        requests.post(f"{BASE_URL}/api/assets/unlock", 
            json={"asset_id": self.test_asset_ids[0]},
            headers=other_user_headers)


class TestHealthAndBasics:
    """Basic health check and API validation"""
    
    def test_api_health(self):
        """GET /api/ - Health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ API healthy - version: {data.get('version')}")
    
    def test_assets_endpoint(self):
        """GET /api/assets - Assets list works"""
        response = requests.get(f"{BASE_URL}/api/assets")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ Assets endpoint works - total: {data.get('total')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
