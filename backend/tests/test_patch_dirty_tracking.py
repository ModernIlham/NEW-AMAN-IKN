"""
Test PATCH /api/assets/{id} - Dirty-Tracking Optimization Feature
Tests partial updates, uniqueness validations, thumbnail regeneration, and backward compatibility.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")

# Activity ID for testing (from context - existing activity with 451 assets)
TEST_ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"

# Test prefix for easy cleanup
TEST_PREFIX = "PATCH_TEST_"


class TestPatchPartialUpdate:
    """Test PATCH endpoint for partial field updates"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        """Create a test asset before each test and clean up after"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Create test asset
        unique_id = str(uuid.uuid4())[:8]
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}CODE_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}Asset {unique_id}",
            "category": "Test Category",
            "brand": "Original Brand",
            "model": "Original Model",
            "location": "Original Location",
            "condition": "Baik",
            "status": "Aktif",
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200, f"Failed to create test asset: {response.text}"
        self.created_asset = response.json()
        self.asset_id = self.created_asset["id"]
        
        yield
        
        # Cleanup - delete test asset
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_patch_single_field_location_only(self):
        """Test PATCH with only location field - other fields should remain unchanged"""
        # PATCH only the location
        patch_data = {"location": "Updated Location Only"}
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        # Verify the update
        updated = response.json()
        assert updated["location"] == "Updated Location Only", "Location should be updated"
        
        # Verify other fields are UNCHANGED
        assert updated["brand"] == "Original Brand", "Brand should NOT change"
        assert updated["model"] == "Original Model", "Model should NOT change"
        assert updated["asset_name"] == self.test_asset["asset_name"], "Name should NOT change"
        assert updated["condition"] == "Baik", "Condition should NOT change"
        
        # Double-check via GET
        get_response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["location"] == "Updated Location Only"
        assert fetched["brand"] == "Original Brand"
        print("PASS: PATCH single field (location) - other fields unchanged")
    
    def test_patch_multiple_fields(self):
        """Test PATCH with multiple fields - only those fields should update"""
        patch_data = {
            "brand": "Updated Brand",
            "model": "Updated Model",
            "notes": "Some notes"
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        updated = response.json()
        
        assert updated["brand"] == "Updated Brand"
        assert updated["model"] == "Updated Model"
        assert updated["notes"] == "Some notes"
        
        # Other fields unchanged
        assert updated["location"] == "Original Location"
        assert updated["condition"] == "Baik"
        print("PASS: PATCH multiple fields - only specified fields updated")
    
    def test_patch_inventory_status_field(self):
        """Test PATCH with inventory_status field"""
        patch_data = {"inventory_status": "Ditemukan"}
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200
        updated = response.json()
        assert updated["inventory_status"] == "Ditemukan"
        print("PASS: PATCH inventory_status field updated successfully")


class TestPatchUniquenessValidation:
    """Test PATCH endpoint uniqueness validations"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        """Create two test assets for uniqueness testing"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        # First asset
        self.asset1 = {
            "asset_code": f"{TEST_PREFIX}UNIQUE1_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}Asset1 {unique_id}",
            "category": "Test Category",
            "kode_register": f"REG1_{unique_id}",
            "activity_id": TEST_ACTIVITY_ID
        }
        r1 = self.session.post(f"{BASE_URL}/api/assets", json=self.asset1)
        assert r1.status_code == 200, f"Failed to create asset1: {r1.text}"
        self.asset1_id = r1.json()["id"]
        
        # Second asset with different code
        self.asset2 = {
            "asset_code": f"{TEST_PREFIX}UNIQUE2_{unique_id}",
            "NUP": "2",
            "asset_name": f"{TEST_PREFIX}Asset2 {unique_id}",
            "category": "Test Category",
            "kode_register": f"REG2_{unique_id}",
            "activity_id": TEST_ACTIVITY_ID
        }
        r2 = self.session.post(f"{BASE_URL}/api/assets", json=self.asset2)
        assert r2.status_code == 200, f"Failed to create asset2: {r2.text}"
        self.asset2_id = r2.json()["id"]
        
        yield
        
        # Cleanup
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset1_id}")
        except:
            pass
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset2_id}")
        except:
            pass
    
    def test_patch_asset_code_nup_uniqueness_violation(self):
        """Test PATCH rejects duplicate asset_code+NUP combination"""
        # Try to change asset2 to have same asset_code + NUP as asset1
        patch_data = {
            "asset_code": self.asset1["asset_code"],
            "NUP": self.asset1["NUP"]  # This combination already exists in asset1
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset2_id}", json=patch_data)
        
        assert response.status_code == 400, f"Should reject duplicate asset_code+NUP: {response.text}"
        assert "sudah digunakan" in response.json().get("detail", "").lower()
        print("PASS: PATCH rejects duplicate asset_code+NUP combination")
    
    def test_patch_kode_register_uniqueness_violation(self):
        """Test PATCH rejects duplicate kode_register"""
        # Try to change asset2's kode_register to match asset1
        patch_data = {
            "kode_register": self.asset1["kode_register"]
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset2_id}", json=patch_data)
        
        assert response.status_code == 400, f"Should reject duplicate kode_register: {response.text}"
        assert "kode register" in response.json().get("detail", "").lower()
        print("PASS: PATCH rejects duplicate kode_register")
    
    def test_patch_unchanged_unique_fields_no_error(self):
        """Test PATCH allows updating other fields without touching unique fields"""
        # PATCH only location - should NOT trigger uniqueness check
        patch_data = {"location": "New Location"}
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset1_id}", json=patch_data)
        
        assert response.status_code == 200, f"Should allow non-unique field update: {response.text}"
        print("PASS: PATCH non-unique fields doesn't trigger uniqueness error")


class TestPatchPhotoThumbnail:
    """Test PATCH endpoint photo handling and thumbnail regeneration"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}PHOTO_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}PhotoAsset {unique_id}",
            "category": "Test Category",
            "activity_id": TEST_ACTIVITY_ID
        }
        r = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert r.status_code == 200, f"Failed to create test asset: {r.text}"
        self.asset_id = r.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_patch_with_photos_regenerates_thumbnail(self):
        """Test PATCH with photos triggers thumbnail regeneration"""
        # Small valid base64 image (1x1 red pixel PNG)
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        
        patch_data = {
            "photos": [test_image],
            "thumbnail_index": 0
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200, f"PATCH with photos failed: {response.text}"
        updated = response.json()
        
        # Verify thumbnail was generated
        assert updated.get("thumbnail") is not None, "Thumbnail should be generated"
        assert updated.get("photo") is not None, "Photo should be set"
        print("PASS: PATCH with photos regenerates thumbnail")
    
    def test_patch_without_photos_preserves_existing(self):
        """Test PATCH without photos key preserves existing photos/thumbnails"""
        # First add a photo
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json={"photos": [test_image]})
        
        # Get current state
        before = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}").json()
        assert before.get("thumbnail") is not None
        
        # PATCH only location (no photos key)
        patch_data = {"location": "Updated without photo change"}
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200
        after = response.json()
        
        # Photos and thumbnail should be preserved
        assert after.get("thumbnail") == before.get("thumbnail"), "Thumbnail should be preserved"
        assert after.get("photos") == before.get("photos"), "Photos should be preserved"
        assert after["location"] == "Updated without photo change"
        print("PASS: PATCH without photos key preserves existing photos/thumbnail")


class TestPatchEdgeCases:
    """Test PATCH endpoint edge cases"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}EDGE_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}EdgeAsset {unique_id}",
            "category": "Test Category",
            "activity_id": TEST_ACTIVITY_ID
        }
        r = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert r.status_code == 200, f"Failed to create test asset: {r.text}"
        self.asset_id = r.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_patch_nonexistent_asset_returns_404(self):
        """Test PATCH on non-existent asset returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.patch(f"{BASE_URL}/api/assets/{fake_id}", json={"location": "Test"})
        
        assert response.status_code == 404, f"Should return 404: {response.status_code}"
        print("PASS: PATCH non-existent asset returns 404")
    
    def test_patch_empty_body_returns_400(self):
        """Test PATCH with empty body returns 400"""
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json={})
        
        assert response.status_code == 400, f"Should return 400 for empty body: {response.status_code}"
        print("PASS: PATCH empty body returns 400")
    
    def test_patch_invalid_fields_only_returns_400(self):
        """Test PATCH with only non-patchable fields returns 400"""
        # Try to patch with fields not in PATCHABLE_FIELDS
        patch_data = {
            "id": "new-id",  # Not patchable
            "created_at": "2024-01-01",  # Not patchable
            "invalid_field": "test"  # Not patchable
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 400, f"Should return 400 for invalid fields: {response.status_code}"
        print("PASS: PATCH with only invalid fields returns 400")
    
    def test_patch_with_document_checklist(self):
        """Test PATCH with document_checklist normalizes data"""
        patch_data = {
            "document_checklist": [
                {"name": "Doc1", "checked": True, "notes": "Note 1"},
                {"name": "Doc2", "checked": False}
            ]
        }
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200
        updated = response.json()
        
        checklist = updated.get("document_checklist", [])
        assert len(checklist) == 2
        assert checklist[0]["name"] == "Doc1"
        assert checklist[0]["checked"] == True
        assert checklist[1]["name"] == "Doc2"
        assert checklist[1]["checked"] == False
        print("PASS: PATCH with document_checklist normalizes correctly")


class TestPutBackwardCompatibility:
    """Test PUT endpoint still works (backward compatibility)"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}PUT_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}PutAsset {unique_id}",
            "category": "Test",
            "brand": "Original",
            "location": "Original Location",
            "condition": "Baik",
            "status": "Aktif",
            "activity_id": TEST_ACTIVITY_ID
        }
        r = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert r.status_code == 200
        self.asset_id = r.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_put_full_update_works(self):
        """Test PUT endpoint still accepts full asset update"""
        full_update = {
            **self.test_asset,
            "brand": "Updated Brand",
            "location": "Updated Location",
            "notes": "Updated via PUT"
        }
        response = self.session.put(f"{BASE_URL}/api/assets/{self.asset_id}", json=full_update)
        
        assert response.status_code == 200, f"PUT should work: {response.text}"
        updated = response.json()
        
        assert updated["brand"] == "Updated Brand"
        assert updated["location"] == "Updated Location"
        assert updated["notes"] == "Updated via PUT"
        print("PASS: PUT endpoint works for backward compatibility")
    
    def test_put_nonexistent_returns_404(self):
        """Test PUT on non-existent asset returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.put(f"{BASE_URL}/api/assets/{fake_id}", json=self.test_asset)
        
        assert response.status_code == 404
        print("PASS: PUT non-existent asset returns 404")


class TestCleanup:
    """Cleanup any leftover test data"""
    
    def test_cleanup_test_assets(self):
        """Remove any test assets that may have been left over"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Fetch assets with test prefix
        response = session.get(
            f"{BASE_URL}/api/assets",
            params={"search": TEST_PREFIX, "activity_id": TEST_ACTIVITY_ID, "page_size": 100}
        )
        
        if response.status_code == 200:
            items = response.json().get("items", [])
            deleted = 0
            for asset in items:
                if TEST_PREFIX in asset.get("asset_code", "") or TEST_PREFIX in asset.get("asset_name", ""):
                    try:
                        session.delete(f"{BASE_URL}/api/assets/{asset['id']}")
                        deleted += 1
                    except:
                        pass
            print(f"PASS: Cleaned up {deleted} test assets")
        else:
            print("PASS: No cleanup needed")
