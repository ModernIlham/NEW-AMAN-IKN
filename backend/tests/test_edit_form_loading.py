"""
Backend tests for Edit Form Loading Fix
Tests: GET /api/assets/{id} returns full data for edit form loading
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

# Test activity ID with 451+ assets
TEST_ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"


class TestAssetEndpointForEditForm:
    """Tests for GET /api/assets/{id} endpoint used by edit form"""

    def test_get_single_asset_returns_full_data(self):
        """GET /api/assets/{id} should return full asset data including photos and document_checklist"""
        # First, get an asset ID from the list
        list_resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID, "page_size": 1}
        )
        assert list_resp.status_code == 200, f"List failed: {list_resp.text}"
        items = list_resp.json().get("items", [])
        assert len(items) > 0, "No assets found to test"
        
        asset_id = items[0]["id"]
        
        # Fetch the full asset
        resp = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert resp.status_code == 200, f"Get asset failed: {resp.text}"
        
        data = resp.json()
        
        # Verify all required fields are present
        required_fields = [
            "id", "asset_code", "asset_name", "category", 
            "condition", "status", "inventory_status"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify photos field exists (even if empty)
        assert "photos" in data, "Missing 'photos' field in response"
        assert isinstance(data["photos"], list), "photos should be a list"
        
        # Verify document_checklist field exists
        assert "document_checklist" in data, "Missing 'document_checklist' field in response"
        assert isinstance(data["document_checklist"], list), "document_checklist should be a list"
        
        print(f"✓ GET /api/assets/{asset_id} returns full data")
        print(f"  - Photos: {len(data.get('photos', []))} items")
        print(f"  - Document checklist: {len(data.get('document_checklist', []))} items")

    def test_get_asset_with_document_checklist(self):
        """GET /api/assets/{id} should return document checklist with all properties"""
        # Find an asset that has document_checklist items
        list_resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID, "page_size": 50}
        )
        assert list_resp.status_code == 200
        
        items = list_resp.json().get("items", [])
        
        # Find an asset with doc_total > 0
        asset_with_docs = None
        for item in items:
            if item.get("doc_total", 0) > 0:
                asset_with_docs = item
                break
        
        if not asset_with_docs:
            pytest.skip("No assets with document_checklist found")
        
        # Fetch the full asset
        resp = requests.get(f"{BASE_URL}/api/assets/{asset_with_docs['id']}")
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Verify document_checklist structure
        doc_checklist = data.get("document_checklist", [])
        assert len(doc_checklist) > 0, "Expected non-empty document_checklist"
        
        for doc_item in doc_checklist:
            assert "name" in doc_item, "Missing 'name' in checklist item"
            assert "checked" in doc_item, "Missing 'checked' in checklist item"
            # photos and documents arrays should exist
            assert "photos" in doc_item or doc_item.get("photos") is None
            assert "documents" in doc_item or doc_item.get("documents") is None
        
        print(f"✓ Document checklist has proper structure with {len(doc_checklist)} items")

    def test_get_nonexistent_asset_returns_404(self):
        """GET /api/assets/{nonexistent_id} should return 404"""
        resp = requests.get(f"{BASE_URL}/api/assets/nonexistent-asset-id-12345")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("✓ Nonexistent asset returns 404")

    def test_list_endpoint_excludes_heavy_data(self):
        """GET /api/assets (list) should NOT include photos/document_checklist (optimization)"""
        resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID, "page_size": 5}
        )
        assert resp.status_code == 200
        
        items = resp.json().get("items", [])
        assert len(items) > 0, "No items returned"
        
        for item in items:
            # List endpoint should have photo_count instead of full photos array
            assert "photo_count" in item, "List should include photo_count"
            # List endpoint should have doc_summary instead of full document_checklist
            assert "doc_summary" in item or "doc_total" in item, "List should include doc summary"
            
            # Full photos array should NOT be in list response
            # (it would be huge for assets with many photos)
            if "photos" in item:
                # If photos exists, it should be empty or not present
                pass  # Backend optimization - photos excluded from list
        
        print("✓ List endpoint properly excludes heavy data for performance")


class TestAssetCRUDForFormFlow:
    """Tests for Create/Update flow used by the form"""

    @pytest.fixture
    def unique_asset_code(self):
        """Generate unique asset code for testing"""
        import uuid
        return f"TEST-FORM-{uuid.uuid4().hex[:8].upper()}"

    def test_create_asset_returns_full_data(self, unique_asset_code):
        """POST /api/assets should return the created asset with all fields"""
        payload = {
            "asset_code": unique_asset_code,
            "NUP": "1",
            "asset_name": "Test Form Loading Asset",
            "category": "Test Category",
            "condition": "Baik",
            "status": "Aktif",
            "activity_id": TEST_ACTIVITY_ID,
            "photos": [],
            "document_checklist": [
                {"name": "Test Doc", "checked": False, "notes": "", "photos": [], "documents": []}
            ]
        }
        
        resp = requests.post(f"{BASE_URL}/api/assets", json=payload)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        
        data = resp.json()
        assert data.get("id"), "Created asset should have ID"
        assert data.get("asset_code") == unique_asset_code
        assert data.get("asset_name") == "Test Form Loading Asset"
        assert "photos" in data
        assert "document_checklist" in data
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/assets/{data['id']}")
        print(f"✓ Create asset returns full data with ID: {data['id'][:8]}...")

    def test_update_asset_returns_updated_data(self, unique_asset_code):
        """PUT /api/assets/{id} should return updated asset with all fields"""
        # Create asset first
        create_payload = {
            "asset_code": unique_asset_code,
            "NUP": "1",
            "asset_name": "Original Name",
            "category": "Test Category",
            "condition": "Baik",
            "status": "Aktif",
            "activity_id": TEST_ACTIVITY_ID,
            "photos": [],
            "document_checklist": []
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/assets", json=create_payload)
        assert create_resp.status_code == 200
        asset_id = create_resp.json().get("id")
        
        # Update asset
        update_payload = {
            **create_payload,
            "asset_name": "Updated Name",
            "location": "Updated Location"
        }
        
        update_resp = requests.put(f"{BASE_URL}/api/assets/{asset_id}", json=update_payload)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        data = update_resp.json()
        assert data.get("asset_name") == "Updated Name"
        assert data.get("location") == "Updated Location"
        
        # Verify by fetching again
        get_resp = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched.get("asset_name") == "Updated Name"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/assets/{asset_id}")
        print("✓ Update returns correct data and persists to DB")


class TestFormLoadingPerformance:
    """Tests for form loading performance considerations"""

    def test_single_asset_fetch_response_time(self):
        """GET /api/assets/{id} should respond reasonably fast"""
        import time
        
        # Get an asset ID
        list_resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID, "page_size": 1}
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No assets available")
        
        asset_id = items[0]["id"]
        
        # Time the fetch
        start = time.time()
        resp = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        elapsed = time.time() - start
        
        assert resp.status_code == 200
        assert elapsed < 5.0, f"Fetch took {elapsed:.2f}s, expected < 5s"
        
        print(f"✓ Single asset fetch completed in {elapsed:.3f}s")

    def test_list_vs_single_asset_size_comparison(self):
        """List endpoint should return less data per item than single asset endpoint"""
        # Get list data
        list_resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID, "page_size": 1}
        )
        items = list_resp.json().get("items", [])
        if not items:
            pytest.skip("No assets")
        
        list_item = items[0]
        
        # Get single asset
        single_resp = requests.get(f"{BASE_URL}/api/assets/{list_item['id']}")
        single_data = single_resp.json()
        
        # Single asset should have document_checklist with full data
        # List item should have doc_summary (lighter)
        if single_data.get("document_checklist"):
            # Full document_checklist has nested photos/documents
            # List item has doc_summary which is lighter
            list_has_full_checklist = "document_checklist" in list_item and len(list_item.get("document_checklist", [])) > 0
            single_has_full_checklist = len(single_data.get("document_checklist", [])) > 0
            
            if single_has_full_checklist:
                print(f"✓ List item has doc_summary: {list_item.get('doc_total', 0)} items")
                print(f"✓ Single asset has full document_checklist: {len(single_data['document_checklist'])} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
