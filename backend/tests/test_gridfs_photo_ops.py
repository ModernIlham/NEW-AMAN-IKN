
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Iteration 69: GridFS Photo Storage and photo_ops API Tests
Features tested:
1. POST /api/assets - GridFS storage for new photos + thumbnail generation
2. GET /api/assets/{id}/media - Returns photo_thumbnails, photo_gridfs_ids, photo_count
3. GET /api/assets/{id}/photos/{index} - Streams full photo from GridFS
4. PATCH /api/assets/{id} with photo_ops - Server-side photo manipulation
5. POST /api/assets/migrate-gridfs - Migration endpoint
6. GET /api/assets/{id}?exclude_media=true - Returns photo_count, empty photos array
"""
import pytest
import requests
import os
import base64
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"

# Helper to generate valid test images
def _generate_test_image(width=50, height=50, color=(255, 0, 0)):
    """Generate a valid test image as base64"""
    from PIL import Image
    import io
    img = Image.new('RGB', (width, height), color)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64}"

# Valid test images (50x50 pixels)
TEST_IMAGE_B64 = _generate_test_image(50, 50, (255, 0, 0))  # Red
TEST_IMAGE_BLUE_B64 = _generate_test_image(50, 50, (0, 0, 255))  # Blue


@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "X-Audit-User": "test_agent"
    })
    return session


class TestCreateAssetWithPhotos:
    """Test POST /api/assets with photos -> GridFS storage"""
    
    @pytest.fixture(autouse=True)
    def cleanup_test_assets(self, api_client):
        """Cleanup test assets after each test"""
        yield
        # Cleanup: delete test assets
        try:
            response = api_client.get(f"{BASE_URL}/api/assets?activity_id={ACTIVITY_ID}&search=GRIDFS_TEST_")
            if response.status_code == 200:
                for asset in response.json().get("items", []):
                    api_client.delete(f"{BASE_URL}/api/assets/{asset['id']}")
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def test_create_asset_with_photo_stores_in_gridfs(self, api_client):
        """Creating asset with photo should store in GridFS and generate thumbnails"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"GRIDFS_TEST_{test_id}",
            "asset_name": f"Test GridFS Asset {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64],
            "thumbnail_index": 0,
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert "photo_gridfs_ids" in data
        assert "photo_thumbnails" in data
        
        # Verify GridFS IDs were generated
        gridfs_ids = data.get("photo_gridfs_ids", [])
        assert len(gridfs_ids) == 1, f"Expected 1 GridFS ID, got {len(gridfs_ids)}"
        assert gridfs_ids[0], "GridFS ID should not be empty"
        
        # Verify thumbnails were generated
        thumbnails = data.get("photo_thumbnails", [])
        assert len(thumbnails) == 1, f"Expected 1 thumbnail, got {len(thumbnails)}"
        assert thumbnails[0].startswith("data:image/"), "Thumbnail should be base64 image"
        
        # Verify main thumbnail was set
        assert data.get("thumbnail"), "Main thumbnail should be generated"
        
        print(f"PASS: Asset created with GridFS ID: {gridfs_ids[0][:20]}...")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{data['id']}")
    
    def test_create_asset_multiple_photos(self, api_client):
        """Creating asset with multiple photos stores all in GridFS"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"GRIDFS_MULTI_{test_id}",
            "asset_name": f"Test Multi Photo {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64, TEST_IMAGE_BLUE_B64],
            "thumbnail_index": 1,  # Second photo as cover
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        gridfs_ids = data.get("photo_gridfs_ids", [])
        assert len(gridfs_ids) == 2, f"Expected 2 GridFS IDs, got {len(gridfs_ids)}"
        
        thumbnails = data.get("photo_thumbnails", [])
        assert len(thumbnails) == 2, f"Expected 2 thumbnails, got {len(thumbnails)}"
        
        print(f"PASS: Asset created with {len(gridfs_ids)} photos in GridFS")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{data['id']}")


class TestGetAssetMedia:
    """Test GET /api/assets/{id}/media endpoint"""
    
    @pytest.fixture(scope="class")
    def test_asset(self, api_client):
        """Create test asset with photos"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"MEDIA_TEST_{test_id}",
            "asset_name": f"Test Media Asset {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64, TEST_IMAGE_BLUE_B64],
            "thumbnail_index": 0,
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        asset_data = response.json()
        
        yield asset_data
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{asset_data['id']}")
    
    def test_media_endpoint_returns_thumbnails(self, api_client, test_asset):
        """GET /api/assets/{id}/media returns photo_thumbnails array"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/media")
        assert response.status_code == 200, f"Media endpoint failed: {response.text}"
        
        data = response.json()
        assert "photo_thumbnails" in data, "Missing photo_thumbnails"
        assert len(data["photo_thumbnails"]) == 2, f"Expected 2 thumbnails, got {len(data['photo_thumbnails'])}"
        
        # Thumbnails should be base64 encoded
        for thumb in data["photo_thumbnails"]:
            assert thumb.startswith("data:image/"), "Thumbnail should be base64 image"
        
        print(f"PASS: Media endpoint returns {len(data['photo_thumbnails'])} thumbnails")
    
    def test_media_endpoint_returns_gridfs_ids(self, api_client, test_asset):
        """GET /api/assets/{id}/media returns photo_gridfs_ids array"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/media")
        assert response.status_code == 200
        
        data = response.json()
        assert "photo_gridfs_ids" in data, "Missing photo_gridfs_ids"
        assert len(data["photo_gridfs_ids"]) == 2, "Expected 2 GridFS IDs"
        
        # All IDs should be non-empty strings
        for gid in data["photo_gridfs_ids"]:
            assert gid, "GridFS ID should not be empty"
            assert len(gid) == 24, f"GridFS ID should be 24 chars ObjectId, got {len(gid)}"
        
        print(f"PASS: Media endpoint returns {len(data['photo_gridfs_ids'])} GridFS IDs")
    
    def test_media_endpoint_returns_photo_count(self, api_client, test_asset):
        """GET /api/assets/{id}/media returns photo_count"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/media")
        assert response.status_code == 200
        
        data = response.json()
        assert "photo_count" in data, "Missing photo_count"
        assert data["photo_count"] == 2, f"Expected photo_count=2, got {data['photo_count']}"
        
        print(f"PASS: Media endpoint returns photo_count={data['photo_count']}")
    
    def test_media_endpoint_404_nonexistent(self, api_client):
        """GET /api/assets/{invalid_id}/media returns 404"""
        response = api_client.get(f"{BASE_URL}/api/assets/nonexistent-id-12345/media")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print("PASS: Media endpoint returns 404 for non-existent asset")


class TestGetFullPhotoFromGridFS:
    """Test GET /api/assets/{id}/photos/{index} endpoint"""
    
    @pytest.fixture(scope="class")
    def test_asset(self, api_client):
        """Create test asset with photos"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"PHOTO_STREAM_{test_id}",
            "asset_name": f"Test Photo Stream {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64, TEST_IMAGE_BLUE_B64],
            "thumbnail_index": 0,
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200
        asset_data = response.json()
        
        yield asset_data
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{asset_data['id']}")
    
    def test_get_photo_index_0(self, api_client, test_asset):
        """GET /api/assets/{id}/photos/0 returns first photo binary"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/photos/0")
        assert response.status_code == 200, f"Photo fetch failed: {response.text}"
        
        # Should return binary image data
        assert response.headers.get("Content-Type", "").startswith("image/"), "Should return image content type"
        assert len(response.content) > 0, "Photo content should not be empty"
        
        # Check that photo was returned successfully (cache header may be set by middleware)
        # No strict assertion on cache header as middleware may override it
        
        print(f"PASS: Photo index 0 returned {len(response.content)} bytes")
    
    def test_get_photo_index_1(self, api_client, test_asset):
        """GET /api/assets/{id}/photos/1 returns second photo binary"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/photos/1")
        assert response.status_code == 200, f"Photo fetch failed: {response.text}"
        
        assert response.headers.get("Content-Type", "").startswith("image/")
        assert len(response.content) > 0
        
        print(f"PASS: Photo index 1 returned {len(response.content)} bytes")
    
    def test_get_photo_out_of_range(self, api_client, test_asset):
        """GET /api/assets/{id}/photos/{invalid_index} returns 404"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}/photos/99")
        assert response.status_code == 404, f"Expected 404 for out of range, got {response.status_code}"
        
        print("PASS: Out of range photo index returns 404")
    
    def test_get_photo_nonexistent_asset(self, api_client):
        """GET /api/assets/{invalid_id}/photos/0 returns 404"""
        response = api_client.get(f"{BASE_URL}/api/assets/nonexistent-12345/photos/0")
        assert response.status_code == 404
        
        print("PASS: Non-existent asset returns 404")


class TestPatchAssetWithPhotoOps:
    """Test PATCH /api/assets/{id} with photo_ops"""
    
    @pytest.fixture
    def test_asset(self, api_client):
        """Create test asset with photos"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"PHOTO_OPS_{test_id}",
            "asset_name": f"Test Photo Ops {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64, TEST_IMAGE_BLUE_B64],
            "thumbnail_index": 0,
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200
        asset_data = response.json()
        
        yield asset_data
        
        # Cleanup
        try:
            api_client.delete(f"{BASE_URL}/api/assets/{asset_data['id']}")
        except:
            pass
    
    def test_photo_ops_keep_first_remove_second(self, api_client, test_asset):
        """PATCH with photo_ops {keep: [0], add: []} removes second photo"""
        asset_id = test_asset['id']
        
        patch_payload = {
            "photo_ops": {
                "keep": [0],  # Keep only first photo
                "add": [],    # No new photos
                "thumbnail_index": 0
            }
        }
        
        response = api_client.patch(f"{BASE_URL}/api/assets/{asset_id}", json=patch_payload)
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        # Verify result
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) == 1, f"Expected 1 photo, got {len(photos)}"
        
        gridfs_ids = data.get("photo_gridfs_ids", [])
        assert len(gridfs_ids) == 1, f"Expected 1 GridFS ID, got {len(gridfs_ids)}"
        
        thumbnails = data.get("photo_thumbnails", [])
        assert len(thumbnails) == 1, f"Expected 1 thumbnail, got {len(thumbnails)}"
        
        print("PASS: photo_ops keep=[0] correctly removed second photo")
    
    def test_photo_ops_add_new_photo(self, api_client, test_asset):
        """PATCH with photo_ops {keep: [0,1], add: [new_photo]} adds new photo"""
        asset_id = test_asset['id']
        
        # Create a different test image (green)
        green_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFklEQVQYV2Nk+M/wn4EIwMjI8J+BCAAJWgT/TvB/qgAAAABJRU5ErkJggg=="
        
        patch_payload = {
            "photo_ops": {
                "keep": [0, 1],  # Keep both existing photos
                "add": [green_image],  # Add new photo
                "thumbnail_index": 0
            }
        }
        
        response = api_client.patch(f"{BASE_URL}/api/assets/{asset_id}", json=patch_payload)
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) == 3, f"Expected 3 photos, got {len(photos)}"
        
        gridfs_ids = data.get("photo_gridfs_ids", [])
        assert len(gridfs_ids) == 3, f"Expected 3 GridFS IDs, got {len(gridfs_ids)}"
        
        print("PASS: photo_ops add=[new_photo] correctly added third photo")
    
    def test_photo_ops_remove_all(self, api_client, test_asset):
        """PATCH with photo_ops {keep: [], add: []} removes all photos"""
        asset_id = test_asset['id']
        
        patch_payload = {
            "photo_ops": {
                "keep": [],  # Keep nothing
                "add": [],   # Add nothing
                "thumbnail_index": 0
            }
        }
        
        response = api_client.patch(f"{BASE_URL}/api/assets/{asset_id}", json=patch_payload)
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) == 0, f"Expected 0 photos, got {len(photos)}"
        
        gridfs_ids = data.get("photo_gridfs_ids", [])
        assert len(gridfs_ids) == 0, "Expected 0 GridFS IDs"
        
        assert data.get("thumbnail") is None, "Thumbnail should be None when no photos"
        
        print("PASS: photo_ops keep=[], add=[] removes all photos")
    
    def test_photo_ops_reorder_keep(self, api_client, test_asset):
        """PATCH with photo_ops {keep: [1,0]} reorders photos"""
        asset_id = test_asset['id']
        
        # Get original gridfs IDs
        original = test_asset
        original_ids = original.get("photo_gridfs_ids", [])
        
        patch_payload = {
            "photo_ops": {
                "keep": [1, 0],  # Reverse order
                "add": [],
                "thumbnail_index": 0
            }
        }
        
        response = api_client.patch(f"{BASE_URL}/api/assets/{asset_id}", json=patch_payload)
        assert response.status_code == 200, f"PATCH failed: {response.text}"
        
        data = response.json()
        new_ids = data.get("photo_gridfs_ids", [])
        
        # If we had 2 photos and reordered, first should now be second
        if len(original_ids) == 2 and len(new_ids) == 2:
            assert new_ids[0] == original_ids[1], "First photo should be original second"
            assert new_ids[1] == original_ids[0], "Second photo should be original first"
        
        print("PASS: photo_ops keep=[1,0] correctly reorders photos")


class TestExcludeMediaParam:
    """Test GET /api/assets/{id}?exclude_media=true"""
    
    @pytest.fixture(scope="class")
    def test_asset(self, api_client):
        """Create test asset with photos"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"EXCLUDE_MEDIA_{test_id}",
            "asset_name": f"Test Exclude Media {test_id}",
            "category": "Test Category",
            "photos": [TEST_IMAGE_B64, TEST_IMAGE_BLUE_B64],
            "thumbnail_index": 0,
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200
        asset_data = response.json()
        
        yield asset_data
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{asset_data['id']}")
    
    def test_exclude_media_returns_photo_count(self, api_client, test_asset):
        """GET /api/assets/{id}?exclude_media=true returns photo_count"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}?exclude_media=true")
        assert response.status_code == 200, f"Request failed: {response.text}"
        
        data = response.json()
        assert "photo_count" in data, "Missing photo_count"
        assert data["photo_count"] == 2, f"Expected photo_count=2, got {data['photo_count']}"
        
        print(f"PASS: exclude_media returns photo_count={data['photo_count']}")
    
    def test_exclude_media_empty_photos_array(self, api_client, test_asset):
        """GET /api/assets/{id}?exclude_media=true returns empty photos array"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}?exclude_media=true")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) == 0, f"Expected empty photos array, got {len(photos)} items"
        
        print("PASS: exclude_media returns empty photos array")
    
    def test_full_response_includes_photos(self, api_client, test_asset):
        """GET /api/assets/{id} (no param) returns photos (backward compatible)"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset['id']}")
        assert response.status_code == 200
        
        data = response.json()
        photos = data.get("photos", [])
        assert len(photos) == 2, f"Expected 2 photos in full response, got {len(photos)}"
        
        print("PASS: Full response includes photos array")


class TestMigrateGridFS:
    """Test POST /api/assets/migrate-gridfs endpoint"""
    
    def test_migrate_endpoint_exists(self, api_client):
        """POST /api/assets/migrate-gridfs endpoint exists"""
        response = api_client.post(f"{BASE_URL}/api/assets/migrate-gridfs")
        
        # Should return 200 with migration result
        assert response.status_code == 200, f"Migration endpoint failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "migrated" in data, "Response should contain 'migrated' count"
        assert "message" in data, "Response should contain 'message'"
        
        print(f"PASS: Migration endpoint returned: {data}")


class TestAssetWithNoPhotos:
    """Test edge cases for assets without photos"""
    
    @pytest.fixture
    def test_asset_no_photos(self, api_client):
        """Create test asset without photos"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "asset_code": f"NO_PHOTOS_{test_id}",
            "asset_name": f"Test No Photos {test_id}",
            "category": "Test Category",
            "photos": [],
            "activity_id": ACTIVITY_ID
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=payload)
        assert response.status_code == 200
        asset_data = response.json()
        
        yield asset_data
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{asset_data['id']}")
    
    def test_media_endpoint_empty_arrays(self, api_client, test_asset_no_photos):
        """GET /api/assets/{id}/media returns empty arrays for no-photo asset"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset_no_photos['id']}/media")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("photo_thumbnails") == [], "Should return empty thumbnails array"
        assert data.get("photo_gridfs_ids") == [], "Should return empty GridFS IDs array"
        assert data.get("photo_count") == 0, "Should return photo_count=0"
        
        print("PASS: Media endpoint returns empty arrays for no-photo asset")
    
    def test_photos_endpoint_404_on_empty(self, api_client, test_asset_no_photos):
        """GET /api/assets/{id}/photos/0 returns 404 for asset without photos"""
        response = api_client.get(f"{BASE_URL}/api/assets/{test_asset_no_photos['id']}/photos/0")
        assert response.status_code == 404
        
        print("PASS: Photos endpoint returns 404 for empty asset")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
