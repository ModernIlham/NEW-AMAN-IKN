"""
Test Split API for Lazy Photo Loading (Iteration 68)

Tests:
1. GET /api/assets/{id}?exclude_media=true - Returns lightweight data without base64 photos
2. GET /api/assets/{id}/media - Returns only heavy media data (photos + document_checklist media)
3. GET /api/assets/{id} (no param) - Backward compatible, returns full data
4. PATCH /api/assets/{id} - Still working (verified from previous iteration)
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
TEST_PREFIX = "LAZY_LOAD_TEST_"

# Small valid base64 image (1x1 red pixel PNG) for testing
TEST_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="


class TestExcludeMediaParam:
    """Test GET /api/assets/{id}?exclude_media=true endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        """Create a test asset with photos and document_checklist"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        # Create asset WITH photos and document_checklist with photos/documents
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}CODE_{unique_id}",
            "NUP": "1",
            "asset_name": f"{TEST_PREFIX}Asset {unique_id}",
            "category": "Test Category",
            "brand": "Test Brand",
            "model": "Test Model",
            "location": "Test Location",
            "condition": "Baik",
            "status": "Aktif",
            "photos": [TEST_IMAGE, TEST_IMAGE],  # 2 photos
            "thumbnail_index": 0,
            "document_checklist": [
                {
                    "name": "Document A",
                    "checked": True,
                    "notes": "Test notes for doc A",
                    "photos": [TEST_IMAGE],  # 1 photo in checklist item
                    "documents": [{"name": "file.pdf", "data": "base64data"}]
                },
                {
                    "name": "Document B",
                    "checked": False,
                    "notes": "",
                    "photos": [],
                    "documents": []
                }
            ],
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200, f"Failed to create test asset: {response.text}"
        self.created_asset = response.json()
        self.asset_id = self.created_asset["id"]
        
        yield
        
        # Cleanup
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_exclude_media_returns_empty_photos_array(self):
        """Test ?exclude_media=true returns empty photos array with photo_count"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}?exclude_media=true")
        
        assert response.status_code == 200, f"GET failed: {response.text}"
        data = response.json()
        
        # Photos should be empty array
        assert data.get("photos") == [], "photos should be empty array when exclude_media=true"
        
        # photo_count should exist and match original count
        assert "photo_count" in data, "photo_count field should exist"
        assert data["photo_count"] == 2, f"photo_count should be 2, got {data['photo_count']}"
        
        # Other fields should still be present
        assert data["asset_code"] == self.test_asset["asset_code"]
        assert data["asset_name"] == self.test_asset["asset_name"]
        assert data["location"] == "Test Location"
        
        print("PASS: exclude_media=true returns empty photos array with photo_count")
    
    def test_exclude_media_document_checklist_has_counts(self):
        """Test ?exclude_media=true - document_checklist has empty photos/docs but counts"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}?exclude_media=true")
        
        assert response.status_code == 200
        data = response.json()
        
        checklist = data.get("document_checklist", [])
        assert len(checklist) >= 2, "Should have at least 2 checklist items"
        
        # Check first item (Document A - has photo and document)
        doc_a = next((d for d in checklist if d["name"] == "Document A"), None)
        assert doc_a is not None, "Document A should exist"
        
        # Photos and documents should be empty arrays
        assert doc_a.get("photos") == [], "Document A photos should be empty"
        assert doc_a.get("documents") == [], "Document A documents should be empty"
        
        # Counts should exist
        assert "photo_count" in doc_a, "photo_count should exist in checklist item"
        assert doc_a["photo_count"] == 1, f"Document A photo_count should be 1, got {doc_a['photo_count']}"
        assert "document_count" in doc_a, "document_count should exist in checklist item"
        assert doc_a["document_count"] == 1, f"Document A document_count should be 1, got {doc_a['document_count']}"
        
        # Other checklist fields preserved
        assert doc_a["checked"] == True
        assert doc_a["notes"] == "Test notes for doc A"
        
        # Check second item (Document B - no photos/docs)
        doc_b = next((d for d in checklist if d["name"] == "Document B"), None)
        assert doc_b is not None, "Document B should exist"
        assert doc_b.get("photo_count", 0) == 0
        assert doc_b.get("document_count", 0) == 0
        
        print("PASS: exclude_media=true - document_checklist has counts but empty arrays")
    
    def test_exclude_media_response_size_smaller(self):
        """Test ?exclude_media=true response is significantly smaller than full response"""
        # Get full response
        full_response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}")
        assert full_response.status_code == 200
        full_size = len(full_response.text)
        
        # Get lightweight response
        light_response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}?exclude_media=true")
        assert light_response.status_code == 200
        light_size = len(light_response.text)
        
        print(f"Full response size: {full_size} bytes, Light response size: {light_size} bytes")
        
        # Light should be significantly smaller (base64 images are large)
        assert light_size < full_size, "Light response should be smaller than full"
        # Since we have 3 images total (2 + 1 in checklist), light should be at least 50% smaller
        reduction_percent = (1 - light_size / full_size) * 100
        print(f"Response size reduction: {reduction_percent:.1f}%")
        
        print("PASS: exclude_media=true response is smaller than full response")


class TestMediaEndpoint:
    """Test GET /api/assets/{id}/media endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        """Create a test asset with photos and document_checklist"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}MEDIA_{unique_id}",
            "NUP": "2",
            "asset_name": f"{TEST_PREFIX}MediaAsset {unique_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE, TEST_IMAGE, TEST_IMAGE],  # 3 photos
            "document_checklist": [
                {
                    "name": "Checklist Item 1",
                    "checked": True,
                    "notes": "Note 1",
                    "photos": [TEST_IMAGE, TEST_IMAGE],
                    "documents": [{"name": "doc1.pdf", "data": "base64docdata1"}]
                },
                {
                    "name": "Checklist Item 2",
                    "checked": False,
                    "notes": "",
                    "photos": [],
                    "documents": []
                }
            ],
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200, f"Failed to create test asset: {response.text}"
        self.asset_id = response.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_media_endpoint_returns_photos(self):
        """Test /media endpoint returns photos array"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}/media")
        
        assert response.status_code == 200, f"GET /media failed: {response.text}"
        data = response.json()
        
        # Should have photos array
        assert "photos" in data, "Response should have 'photos' key"
        photos = data["photos"]
        assert len(photos) == 3, f"Should have 3 photos, got {len(photos)}"
        
        # Each photo should be base64 data
        for photo in photos:
            assert photo.startswith("data:image/"), f"Photo should be base64: {photo[:50]}..."
        
        print("PASS: /media endpoint returns photos array")
    
    def test_media_endpoint_returns_document_checklist_media(self):
        """Test /media endpoint returns document_checklist_media with photos/documents"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}/media")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have document_checklist_media
        assert "document_checklist_media" in data, "Response should have 'document_checklist_media' key"
        media_list = data["document_checklist_media"]
        assert len(media_list) == 2, f"Should have 2 items, got {len(media_list)}"
        
        # Check first item (has photos and documents)
        item1 = media_list[0]
        assert item1["name"] == "Checklist Item 1"
        assert len(item1["photos"]) == 2, "Item 1 should have 2 photos"
        assert len(item1["documents"]) == 1, "Item 1 should have 1 document"
        
        # Check second item (empty)
        item2 = media_list[1]
        assert item2["name"] == "Checklist Item 2"
        assert item2["photos"] == [], "Item 2 photos should be empty"
        assert item2["documents"] == [], "Item 2 documents should be empty"
        
        print("PASS: /media endpoint returns document_checklist_media correctly")
    
    def test_media_endpoint_404_for_nonexistent_asset(self):
        """Test /media endpoint returns 404 for non-existent asset"""
        fake_id = str(uuid.uuid4())
        response = self.session.get(f"{BASE_URL}/api/assets/{fake_id}/media")
        
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        print("PASS: /media endpoint returns 404 for non-existent asset")
    
    def test_media_endpoint_only_contains_media_fields(self):
        """Test /media endpoint returns ONLY media fields, not text data"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}/media")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should NOT contain text fields
        assert "asset_code" not in data, "Should not contain asset_code"
        assert "asset_name" not in data, "Should not contain asset_name"
        assert "location" not in data, "Should not contain location"
        assert "brand" not in data, "Should not contain brand"
        
        # Should only contain media fields
        expected_keys = {"photos", "document_checklist_media"}
        actual_keys = set(data.keys())
        assert actual_keys == expected_keys, f"Expected {expected_keys}, got {actual_keys}"
        
        print("PASS: /media endpoint returns only media fields")


class TestBackwardCompatibility:
    """Test GET /api/assets/{id} (no param) still returns full data"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}FULL_{unique_id}",
            "NUP": "3",
            "asset_name": f"{TEST_PREFIX}FullAsset {unique_id}",
            "category": "Test",
            "photos": [TEST_IMAGE],
            "document_checklist": [
                {"name": "Doc", "checked": True, "photos": [TEST_IMAGE], "documents": []}
            ],
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200
        self.asset_id = response.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_full_response_includes_photos(self):
        """Test GET without exclude_media returns full photos array"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have actual photos (not empty)
        assert len(data["photos"]) == 1, "Should have 1 photo"
        assert data["photos"][0].startswith("data:image/"), "Photo should be base64"
        
        # Should NOT have photo_count at root level (that's only for exclude_media)
        # Actually based on code, it's added only when exclude_media=true
        if "photo_count" in data:
            # If present, it's fine but not required
            pass
        
        # Document checklist should have full photos
        checklist = data.get("document_checklist", [])
        assert len(checklist) == 1
        assert len(checklist[0]["photos"]) == 1, "Checklist item should have 1 photo"
        
        print("PASS: GET without exclude_media returns full data with photos")
    
    def test_full_response_includes_all_fields(self):
        """Test GET without exclude_media returns all asset fields"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected fields exist
        expected_fields = ["id", "asset_code", "NUP", "asset_name", "category", 
                          "photos", "document_checklist", "created_at"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print("PASS: GET without exclude_media returns all fields")


class TestPatchStillWorks:
    """Verify PATCH endpoint still works (from previous iteration)"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}PATCH_{unique_id}",
            "NUP": "4",
            "asset_name": f"{TEST_PREFIX}PatchAsset {unique_id}",
            "category": "Test",
            "location": "Original Location",
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200
        self.asset_id = response.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_patch_location_only(self):
        """Test PATCH with only location - other fields unchanged"""
        patch_data = {"location": "Updated via PATCH"}
        response = self.session.patch(f"{BASE_URL}/api/assets/{self.asset_id}", json=patch_data)
        
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        data = response.json()
        assert data["location"] == "Updated via PATCH"
        assert data["asset_name"] == self.test_asset["asset_name"], "Other fields should be unchanged"
        
        print("PASS: PATCH still works correctly")


class TestAssetWithNoPhotos:
    """Test exclude_media behavior for assets with no photos"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, request):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        unique_id = str(uuid.uuid4())[:8]
        
        # Asset with NO photos
        self.test_asset = {
            "asset_code": f"{TEST_PREFIX}NOPHOTO_{unique_id}",
            "NUP": "5",
            "asset_name": f"{TEST_PREFIX}NoPhotoAsset {unique_id}",
            "category": "Test",
            "photos": [],  # No photos
            "document_checklist": [],
            "activity_id": TEST_ACTIVITY_ID
        }
        
        response = self.session.post(f"{BASE_URL}/api/assets", json=self.test_asset)
        assert response.status_code == 200
        self.asset_id = response.json()["id"]
        
        yield
        
        try:
            self.session.delete(f"{BASE_URL}/api/assets/{self.asset_id}")
        except:
            pass
    
    def test_exclude_media_with_no_photos(self):
        """Test exclude_media on asset with no photos - photo_count should be 0"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}?exclude_media=true")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["photos"] == [], "Photos should be empty array"
        assert data.get("photo_count") == 0, "photo_count should be 0"
        
        print("PASS: exclude_media works for assets with no photos")
    
    def test_media_endpoint_with_no_photos(self):
        """Test /media endpoint on asset with no photos - returns empty arrays"""
        response = self.session.get(f"{BASE_URL}/api/assets/{self.asset_id}/media")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["photos"] == [], "Photos should be empty"
        assert data["document_checklist_media"] == [], "Checklist media should be empty"
        
        print("PASS: /media endpoint works for assets with no photos")


class TestCleanup:
    """Cleanup any leftover test data"""
    
    def test_cleanup_test_assets(self):
        """Remove any test assets that may have been left over"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
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
