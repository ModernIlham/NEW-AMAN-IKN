"""
Test DOK badge bug fixes - Backend API tests
Tests:
1. /api/assets/{asset_id}/doc-file/{item_idx}/{file_type}/{file_idx} endpoint
2. Analytics endpoint response validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDocFileEndpoint:
    """Test the doc-file streaming endpoint for DOK badge functionality"""
    
    def test_api_health(self):
        """Check API is running"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("API health check: PASSED")
    
    def test_get_activities(self):
        """Get all activities to find test data"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} activities")
        return data
    
    def test_get_assets_with_doc_checklist(self):
        """Find an asset with document_checklist data"""
        # Get activities first
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities")
        activities = activities_resp.json()
        
        for activity in activities:
            activity_id = activity.get("id")
            assets_resp = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page_size=10")
            if assets_resp.status_code == 200:
                assets_data = assets_resp.json()
                for asset in assets_data.get("items", []):
                    # Check if asset has doc_summary with photos
                    doc_summary = asset.get("doc_summary", [])
                    for idx, doc in enumerate(doc_summary):
                        if doc.get("photo_count", 0) > 0 or doc.get("has_photos"):
                            print(f"Found asset {asset['id']} with doc_checklist photos at index {idx}")
                            return asset["id"], idx
        
        pytest.skip("No assets with document_checklist photos found")
        return None, None
    
    def test_doc_file_photo_endpoint(self):
        """Test GET /api/assets/{asset_id}/doc-file/{item_idx}/photo/{file_idx}"""
        asset_id, item_idx = self.test_get_assets_with_doc_checklist()
        if not asset_id:
            pytest.skip("No test asset found")
        
        # Test photo endpoint
        url = f"{BASE_URL}/api/assets/{asset_id}/doc-file/{item_idx}/photo/0"
        response = requests.get(url)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type", "").startswith("image/"), \
            f"Expected image content-type, got {response.headers.get('content-type')}"
        print(f"Doc file photo endpoint: PASSED - Content-Type: {response.headers.get('content-type')}")
    
    def test_doc_file_invalid_index(self):
        """Test doc-file endpoint with invalid indices returns 404"""
        asset_id, _ = self.test_get_assets_with_doc_checklist()
        if not asset_id:
            pytest.skip("No test asset found")
        
        # Invalid item index
        url = f"{BASE_URL}/api/assets/{asset_id}/doc-file/999/photo/0"
        response = requests.get(url)
        assert response.status_code == 404, f"Expected 404 for invalid item index, got {response.status_code}"
        print("Invalid item index returns 404: PASSED")
    
    def test_doc_file_invalid_asset(self):
        """Test doc-file endpoint with invalid asset_id returns 404"""
        url = f"{BASE_URL}/api/assets/invalid-asset-id-123/doc-file/0/photo/0"
        response = requests.get(url)
        assert response.status_code == 404, f"Expected 404 for invalid asset, got {response.status_code}"
        print("Invalid asset ID returns 404: PASSED")


class TestAnalyticsEndpoint:
    """Test analytics endpoint for chart tooltip data"""
    
    def test_analytics_endpoint(self):
        """Test GET /api/assets/analytics returns valid data structure"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Validate response structure
        expected_keys = ["by_category", "by_condition", "by_status", "by_location", "by_department"]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"
            assert isinstance(data[key], list), f"{key} should be a list"
        
        print("Analytics endpoint structure: PASSED")
        print(f"  by_category: {len(data['by_category'])} items")
        print(f"  by_condition: {len(data['by_condition'])} items")
        print(f"  by_status: {len(data['by_status'])} items")
        print(f"  by_location: {len(data['by_location'])} items")
        print(f"  by_department: {len(data['by_department'])} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
