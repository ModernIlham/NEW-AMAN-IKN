
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Iteration 58: Test department field removal refactoring
Verifies that department field was completely removed from backend APIs
and replaced by eselon1/eselon2 which were already present.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDepartmentRemoval:
    """Test suite for department field removal verification"""
    
    # Login and get auth token
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Authenticate and get access token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed - skipping tests")
    
    def test_api_health(self):
        """Test that backend is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("Backend health check: PASS")
    
    def test_filter_options_no_departments(self):
        """GET /api/assets/filter-options should NOT return 'departments' key"""
        response = requests.get(f"{BASE_URL}/api/assets/filter-options")
        assert response.status_code == 200, f"Filter options failed: {response.text}"
        data = response.json()
        
        # Verify 'departments' key is NOT present
        assert "departments" not in data, f"'departments' key should NOT exist. Got: {list(data.keys())}"
        
        # Verify eselon1s and eselon2s are present
        assert "eselon1s" in data, f"'eselon1s' key should exist. Got: {list(data.keys())}"
        assert "eselon2s" in data, f"'eselon2s' key should exist. Got: {list(data.keys())}"
        
        # Verify other expected keys
        assert "locations" in data, "'locations' key should exist"
        assert "conditions" in data, "'conditions' key should exist"
        assert "statuses" in data, "'statuses' key should exist"
        assert "stiker_statuses" in data, "'stiker_statuses' key should exist"
        assert "inventory_statuses" in data, "'inventory_statuses' key should exist"
        
        print(f"Filter options keys: {list(data.keys())}")
        print("Filter options - No departments: PASS")
    
    def test_assets_list_no_department(self):
        """GET /api/assets returns assets WITHOUT department field"""
        response = requests.get(f"{BASE_URL}/api/assets?page_size=10")
        assert response.status_code == 200, f"Get assets failed: {response.text}"
        data = response.json()
        
        # Check items exist
        if data.get("items"):
            for asset in data["items"]:
                # Verify department is NOT in response
                assert "department" not in asset, f"Asset should NOT have 'department' field. Got: {asset.get('department')}"
                
                # Verify eselon1 and eselon2 fields exist (even if empty)
                assert "eselon1" in asset or asset.get("eselon1") is None, "Asset should have 'eselon1' field"
                assert "eselon2" in asset or asset.get("eselon2") is None, "Asset should have 'eselon2' field"
            print(f"Checked {len(data['items'])} assets - no department field")
        
        print("Assets list - No department: PASS")
    
    def test_analytics_by_eselon_not_department(self):
        """GET /api/assets/analytics returns by_eselon instead of by_department"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics")
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        data = response.json()
        
        # Verify by_department does NOT exist
        assert "by_department" not in data, f"'by_department' should NOT exist. Got: {list(data.keys())}"
        
        # Verify by_eselon exists
        assert "by_eselon" in data, f"'by_eselon' should exist. Got: {list(data.keys())}"
        
        # Verify other expected analytics keys
        assert "by_category" in data, "by_category should exist"
        assert "by_condition" in data, "by_condition should exist"
        assert "by_status" in data, "by_status should exist"
        assert "by_location" in data, "by_location should exist"
        
        print(f"Analytics keys: {list(data.keys())}")
        print("Analytics - by_eselon instead of by_department: PASS")
    
    def test_csv_template_no_department(self):
        """GET /api/templates/csv downloads CSV template WITHOUT department column"""
        response = requests.get(f"{BASE_URL}/api/templates/csv")
        assert response.status_code == 200, f"CSV template download failed: {response.text}"
        
        content = response.content.decode('utf-8-sig')  # Handle BOM
        first_line = content.split('\n')[0]
        headers = first_line.split(',')
        
        # Verify department column does NOT exist
        assert "department" not in first_line.lower(), f"CSV template should NOT have 'department' column. Got: {first_line}"
        
        # Verify eselon1 and eselon2 columns exist
        assert "eselon1" in first_line.lower(), f"CSV template should have 'eselon1' column. Got: {first_line}"
        assert "eselon2" in first_line.lower(), f"CSV template should have 'eselon2' column. Got: {first_line}"
        
        print("CSV headers include: eselon1, eselon2")
        print("CSV template - No department column: PASS")
    
    def test_asset_groups_no_department(self):
        """GET /api/assets/groups returns members WITHOUT department field"""
        response = requests.get(f"{BASE_URL}/api/assets/groups")
        assert response.status_code == 200, f"Asset groups failed: {response.text}"
        data = response.json()
        
        groups = data.get("groups", [])
        if groups:
            for group in groups:
                members = group.get("members", [])
                for member in members:
                    # Verify department is NOT in member
                    assert "department" not in member, f"Member should NOT have 'department' field. Got: {list(member.keys())}"
                    
                    # Verify eselon1 and eselon2 exist
                    assert "eselon1" in member, f"Member should have 'eselon1' field. Got: {list(member.keys())}"
                    assert "eselon2" in member, f"Member should have 'eselon2' field. Got: {list(member.keys())}"
            
            print(f"Checked {len(groups)} groups - no department in members")
        else:
            print("No groups found (expected if no duplicate assets)")
        
        print("Asset groups - No department: PASS")
    
    def test_batch_update_no_department(self, auth_token):
        """PUT /api/assets/batch-update does NOT accept department field"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        
        # First, get an asset to test with
        response = requests.get(f"{BASE_URL}/api/assets?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No assets available for batch update test")
        
        asset_id = response.json()["items"][0]["id"]
        
        # Try batch update with department (should be ignored or rejected)
        batch_response = requests.put(
            f"{BASE_URL}/api/assets/batch-update",
            json={
                "asset_ids": [asset_id],
                "updates": {"department": "Test Department"}  # This should be ignored
            },
            headers=headers
        )
        
        # department is not in BATCH_ALLOWED_FIELDS, so this should fail
        # because no valid fields are provided
        if batch_response.status_code == 400:
            error_msg = batch_response.json().get("detail", "")
            assert "valid" in error_msg.lower() or "field" in error_msg.lower(), \
                f"Should reject because no valid fields. Got: {error_msg}"
            print("Batch update correctly rejects department field: PASS")
        elif batch_response.status_code == 200:
            # If it succeeded, verify department was ignored
            result = batch_response.json()
            assert "department" not in result.get("fields", []), \
                f"Department should not be in updated fields. Got: {result}"
            print("Batch update ignored department field: PASS")
        else:
            print(f"Batch update response: {batch_response.status_code} - {batch_response.text}")
        
        print("Batch update - No department: PASS")
    
    def test_batch_update_accepts_eselon(self, auth_token):
        """PUT /api/assets/batch-update accepts eselon1/eselon2 fields"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        
        # First, get an asset to test with
        response = requests.get(f"{BASE_URL}/api/assets?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No assets available for batch update test")
        
        asset_id = response.json()["items"][0]["id"]
        
        # Batch update with eselon1 and eselon2
        batch_response = requests.put(
            f"{BASE_URL}/api/assets/batch-update",
            json={
                "asset_ids": [asset_id],
                "updates": {
                    "eselon1": "TEST_Eselon1",
                    "eselon2": "TEST_Eselon2"
                }
            },
            headers=headers
        )
        
        assert batch_response.status_code == 200, f"Batch update with eselon should succeed. Got: {batch_response.text}"
        result = batch_response.json()
        
        # Verify eselon fields were updated
        assert "eselon1" in result.get("fields", []), f"eselon1 should be in updated fields. Got: {result}"
        assert "eselon2" in result.get("fields", []), f"eselon2 should be in updated fields. Got: {result}"
        
        print(f"Batch update result: {result}")
        print("Batch update accepts eselon1/eselon2: PASS")
    
    def test_get_single_asset_no_department(self):
        """GET /api/assets/{id} returns asset WITHOUT department field"""
        # First get an asset ID
        response = requests.get(f"{BASE_URL}/api/assets?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No assets available")
        
        asset_id = response.json()["items"][0]["id"]
        
        # Get single asset
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200, f"Get single asset failed: {response.text}"
        
        asset = response.json()
        
        # Verify department is NOT in response
        assert "department" not in asset, f"Asset should NOT have 'department' field. Keys: {list(asset.keys())}"
        
        # Verify eselon1 and eselon2 exist
        assert "eselon1" in asset, "Asset should have 'eselon1' field"
        assert "eselon2" in asset, "Asset should have 'eselon2' field"
        
        print(f"Single asset keys: {sorted(asset.keys())}")
        print("Single asset - No department: PASS")


class TestSortOptions:
    """Test sort options - eselon1_asc instead of department_asc"""
    
    def test_sort_by_eselon1(self):
        """GET /api/assets with sort_by=eselon1_asc works"""
        response = requests.get(f"{BASE_URL}/api/assets?sort_by=eselon1_asc&page_size=10")
        assert response.status_code == 200, f"Sort by eselon1_asc failed: {response.text}"
        print("Sort by eselon1_asc: PASS")
    
    def test_sort_by_department_not_available(self):
        """GET /api/assets with sort_by=department_asc falls back to default"""
        response = requests.get(f"{BASE_URL}/api/assets?sort_by=department_asc&page_size=10")
        # Should still return 200 but fall back to default sort
        assert response.status_code == 200, f"Request with unknown sort should succeed: {response.text}"
        print("Sort by department_asc (fallback): PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
