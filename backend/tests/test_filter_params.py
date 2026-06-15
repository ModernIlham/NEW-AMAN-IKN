"""
Test suite for new filter parameters: nomor_spm and perolehan_dari
Tests for iteration 48 - Advanced Filter & Gallery Card/Lightbox redesign
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com').rstrip('/')


class TestFilterParams:
    """Test nomor_spm and perolehan_dari query params in GET /api/assets"""
    
    def test_assets_endpoint_accessible(self):
        """Verify GET /api/assets is accessible"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✅ GET /api/assets accessible - total: {data['total']}")
    
    def test_filter_by_nomor_spm_param_accepted(self):
        """Verify nomor_spm query param is accepted (no 400/422 error)"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=10&nomor_spm=TEST123")
        assert response.status_code == 200, f"nomor_spm param should be accepted, got {response.status_code}: {response.text}"
        data = response.json()
        assert "items" in data
        print(f"✅ nomor_spm filter param accepted - returned {len(data['items'])} items")
    
    def test_filter_by_perolehan_dari_param_accepted(self):
        """Verify perolehan_dari query param is accepted (maps to supplier field)"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=10&perolehan_dari=Pengadaan")
        assert response.status_code == 200, f"perolehan_dari param should be accepted, got {response.status_code}: {response.text}"
        data = response.json()
        assert "items" in data
        print(f"✅ perolehan_dari filter param accepted - returned {len(data['items'])} items")
    
    def test_combined_filters_spm_and_perolehan(self):
        """Test combining nomor_spm and perolehan_dari params"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=10&nomor_spm=SPM&perolehan_dari=Hibah")
        assert response.status_code == 200, f"Combined params failed: {response.status_code}: {response.text}"
        data = response.json()
        assert "items" in data
        print(f"✅ Combined nomor_spm + perolehan_dari params accepted - returned {len(data['items'])} items")
    
    def test_all_existing_filters_still_work(self):
        """Verify all existing filters still work alongside new ones"""
        response = requests.get(
            f"{BASE_URL}/api/assets?page=1&page_size=10"
            "&condition=Baik"
            "&status=Aktif"
            "&nomor_spm=SPM"
            "&perolehan_dari=PT"
        )
        assert response.status_code == 200, f"All filters combined failed: {response.status_code}"
        data = response.json()
        assert "items" in data
        print(f"✅ All filters combined work - returned {len(data['items'])} items")
    
    def test_response_includes_doc_summary_fields(self):
        """Verify response includes doc_summary for gallery card DOK badge"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=1")
        assert response.status_code == 200
        data = response.json()
        
        if data['items']:
            asset = data['items'][0]
            # Check for new computed fields needed by gallery card
            assert "doc_total" in asset or "doc_checked" in asset or "doc_summary" in asset, \
                "Expected doc_total/doc_checked/doc_summary fields for DOK badge"
            print(f"✅ Response includes document summary fields: doc_total={asset.get('doc_total')}, doc_checked={asset.get('doc_checked')}")
        else:
            print("⚠️ No assets found to verify doc_summary fields")
    
    def test_get_single_asset_returns_full_data(self):
        """Verify GET /api/assets/{id} returns full asset data for lightbox"""
        # First get list to find an asset ID
        list_response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=1")
        assert list_response.status_code == 200
        items = list_response.json().get('items', [])
        
        if not items:
            pytest.skip("No assets found to test single asset endpoint")
        
        asset_id = items[0]['id']
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200, f"GET /api/assets/{asset_id} failed: {response.status_code}"
        
        asset = response.json()
        # Verify essential fields for lightbox
        expected_fields = ['id', 'asset_code', 'asset_name', 'nomor_spm', 'purchase_date', 
                          'purchase_price', 'condition', 'location', 'department', 'user',
                          'inventory_status', 'stiker_status']
        for field in expected_fields:
            assert field in asset, f"Missing field {field} in single asset response"
        
        print(f"✅ GET /api/assets/{asset_id} returns full data with all required fields for lightbox")


class TestFilterOptionsEndpoint:
    """Test filter options endpoint"""
    
    def test_filter_options_accessible(self):
        """Verify GET /api/assets/filter-options works"""
        response = requests.get(f"{BASE_URL}/api/assets/filter-options")
        assert response.status_code == 200, f"filter-options failed: {response.status_code}"
        data = response.json()
        
        # Verify expected keys
        expected_keys = ['locations', 'departments', 'conditions', 'statuses', 'stiker_statuses', 'inventory_statuses']
        for key in expected_keys:
            assert key in data, f"Missing {key} in filter-options response"
        
        print(f"✅ Filter options endpoint returns all expected fields: {list(data.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
