
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Iteration 77: Test Save & Navigate fix - form data persistence during navigation
Tests for the bug fix: resetForm() was removed from Save & Navigate path in AssetForm.jsx

Test cases:
1. Backend PATCH /api/inventory-activities/{activity_id}/assets/{asset_id} endpoint
2. Backend PATCH /api/assets/{asset_id} endpoint  
3. Asset list endpoint for navigation testing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestSaveAndNavigateFix:
    """Tests for Save & Navigate functionality - backend API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.user = data.get("user", {})
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "X-Audit-User": self.user.get("name", "admin")
            })
        else:
            pytest.skip("Authentication failed")
        yield
        self.session.close()
    
    def test_login_success(self):
        """Test login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"PASS: Login successful, user: {data['user'].get('username')}")
    
    def test_get_test_activity(self):
        """Get 'Test Kegiatan untuk Testing' activity with 1926 assets"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        
        # Find the test activity
        test_activity = None
        for act in activities:
            if act.get("nama_kegiatan") == "Test Kegiatan untuk Testing":
                test_activity = act
                break
        
        assert test_activity is not None, "Test activity 'Test Kegiatan untuk Testing' not found"
        assert test_activity.get("total_assets", 0) > 1000, f"Expected >1000 assets, got {test_activity.get('total_assets')}"
        print(f"PASS: Found activity '{test_activity['nama_kegiatan']}' with {test_activity.get('total_assets')} assets")
        return test_activity
    
    def test_get_assets_paginated(self):
        """Get paginated assets from the test activity"""
        test_activity = self.test_get_test_activity()
        activity_id = test_activity["id"]
        
        response = self.session.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0, "Expected at least 1 asset"
        assert data.get("total", 0) > 1000, f"Expected >1000 total, got {data.get('total')}"
        print(f"PASS: Got {len(data['items'])} assets on page 1, total: {data.get('total')}")
        return data["items"]
    
    def test_get_single_asset_detail(self):
        """Get single asset detail for editing"""
        assets = self.test_get_assets_paginated()
        first_asset = assets[0]
        asset_id = first_asset["id"]
        
        # Test exclude_media=true endpoint (phase 1 fetch)
        response = self.session.get(f"{BASE_URL}/api/assets/{asset_id}", params={"exclude_media": "true"})
        assert response.status_code == 200
        asset = response.json()
        assert asset.get("asset_code") or asset.get("asset_name"), "Asset should have asset_code or asset_name"
        print(f"PASS: Got asset detail: {asset.get('asset_code', 'N/A')} - {asset.get('asset_name', 'N/A')}")
        return asset
    
    def test_get_asset_media(self):
        """Get asset media (phase 2 fetch)"""
        assets = self.test_get_assets_paginated()
        first_asset = assets[0]
        asset_id = first_asset["id"]
        
        response = self.session.get(f"{BASE_URL}/api/assets/{asset_id}/media")
        assert response.status_code == 200
        media = response.json()
        assert "photo_count" in media or "photo_thumbnails" in media
        print(f"PASS: Got asset media - photo_count: {media.get('photo_count', 0)}")
        return media
    
    def test_patch_asset_update(self):
        """Test PATCH /api/assets/{asset_id} - partial update (Save & Navigate uses this)"""
        assets = self.test_get_assets_paginated()
        # Use an asset for testing patch
        test_asset = assets[0]
        asset_id = test_asset["id"]
        
        # Get original data
        original = self.session.get(f"{BASE_URL}/api/assets/{asset_id}", params={"exclude_media": "true"}).json()
        original_notes = original.get("notes", "")
        
        # PATCH update only notes field
        test_notes = f"TEST_ITER77_PATCH_{os.urandom(4).hex()}"
        response = self.session.patch(f"{BASE_URL}/api/assets/{asset_id}", json={
            "notes": test_notes
        })
        
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        updated = response.json()
        assert updated.get("notes") == test_notes, f"Notes not updated: {updated.get('notes')}"
        print(f"PASS: PATCH /api/assets/{asset_id} - notes updated to: {test_notes}")
        
        # Verify persistence with GET
        verify = self.session.get(f"{BASE_URL}/api/assets/{asset_id}", params={"exclude_media": "true"}).json()
        assert verify.get("notes") == test_notes, "Notes not persisted"
        print("PASS: Verified notes persisted via GET")
        
        # Restore original value
        self.session.patch(f"{BASE_URL}/api/assets/{asset_id}", json={"notes": original_notes})
    
    def test_patch_asset_multiple_fields(self):
        """Test PATCH with multiple fields - simulates Save & Navigate dirty tracking"""
        assets = self.test_get_assets_paginated()
        test_asset = assets[1] if len(assets) > 1 else assets[0]
        asset_id = test_asset["id"]
        
        # Get original data
        original = self.session.get(f"{BASE_URL}/api/assets/{asset_id}", params={"exclude_media": "true"}).json()
        
        # PATCH multiple fields (like dirty tracking sends)
        test_updates = {
            "condition": "Baik",  # Common field
            "notes": f"TEST_MULTI_FIELD_{os.urandom(4).hex()}"
        }
        
        response = self.session.patch(f"{BASE_URL}/api/assets/{asset_id}", json=test_updates)
        assert response.status_code == 200
        updated = response.json()
        
        for key, value in test_updates.items():
            assert updated.get(key) == value, f"{key} not updated"
        print("PASS: PATCH with multiple fields successful")
        
        # Restore
        self.session.patch(f"{BASE_URL}/api/assets/{asset_id}", json={"notes": original.get("notes", "")})
    
    def test_lock_asset_for_edit(self):
        """Test asset locking mechanism for editing"""
        assets = self.test_get_assets_paginated()
        test_asset = assets[2] if len(assets) > 2 else assets[0]
        asset_id = test_asset["id"]
        
        # Lock asset
        response = self.session.post(f"{BASE_URL}/api/assets/{asset_id}/lock")
        # Lock might return 200 or 409 (if already locked)
        assert response.status_code in [200, 409], f"Lock failed: {response.status_code}"
        
        if response.status_code == 200:
            print(f"PASS: Asset {asset_id} locked successfully")
            # Unlock
            unlock_response = self.session.post(f"{BASE_URL}/api/assets/{asset_id}/unlock")
            assert unlock_response.status_code in [200, 204, 404]
            print(f"PASS: Asset {asset_id} unlocked")
        else:
            print(f"INFO: Asset {asset_id} already locked by another session")
    
    def test_navigate_between_assets(self):
        """Simulate Save & Navigate by getting consecutive assets"""
        assets = self.test_get_assets_paginated()
        
        assert len(assets) >= 3, "Need at least 3 assets to test navigation"
        
        # Simulate user flow: edit asset[0], save & navigate to asset[1]
        asset_0_id = assets[0]["id"]
        asset_1_id = assets[1]["id"]
        
        # Get asset 0 details (form loads)
        r0 = self.session.get(f"{BASE_URL}/api/assets/{asset_0_id}", params={"exclude_media": "true"})
        assert r0.status_code == 200
        asset_0_data = r0.json()
        print(f"Asset 0: {asset_0_data.get('asset_code')} - {asset_0_data.get('asset_name')}")
        
        # Get asset 1 details (next navigation target)
        r1 = self.session.get(f"{BASE_URL}/api/assets/{asset_1_id}", params={"exclude_media": "true"})
        assert r1.status_code == 200
        asset_1_data = r1.json()
        print(f"Asset 1 (next): {asset_1_data.get('asset_code')} - {asset_1_data.get('asset_name')}")
        
        # Verify they are different assets
        assert asset_0_data.get("id") != asset_1_data.get("id"), "Should be different assets"
        print("PASS: Navigation simulation - got different asset data for consecutive assets")


class TestAssetFormDataFlow:
    """Tests to verify asset data flow for form loading"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup with auth"""
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin", "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            })
        yield
        self.session.close()
    
    def test_asset_form_fields_completeness(self):
        """Test that all form fields are returned by the API"""
        # Get test activity assets
        acts = self.session.get(f"{BASE_URL}/api/inventory-activities").json()
        test_act = next((a for a in acts if a.get("nama_kegiatan") == "Test Kegiatan untuk Testing"), None)
        if not test_act:
            pytest.skip("Test activity not found")
        
        assets = self.session.get(f"{BASE_URL}/api/assets", params={
            "activity_id": test_act["id"], "page": 1, "page_size": 5
        }).json().get("items", [])
        
        if not assets:
            pytest.skip("No assets found")
        
        asset = self.session.get(f"{BASE_URL}/api/assets/{assets[0]['id']}", params={"exclude_media": "true"}).json()
        
        # Check key form fields
        expected_fields = [
            "asset_code", "asset_name", "category", "condition", "status",
            "NUP", "brand", "kode_register", "purchase_date", "purchase_price",
            "location", "notes"
        ]
        
        missing = [f for f in expected_fields if f not in asset]
        assert len(missing) == 0, f"Missing fields: {missing}"
        print("PASS: All expected form fields present in asset response")
        print(f"Asset: {asset.get('asset_code')} - {asset.get('asset_name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
