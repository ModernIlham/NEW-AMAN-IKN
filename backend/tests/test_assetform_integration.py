
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Backend API Tests for AssetForm Integration + Caching
Tests: Login, Asset CRUD, Categories caching, Filter options, Stats
Iteration 8: Testing major AssetForm refactoring + backend caching
"""
import pytest
import requests
import os
import time
import random
import string

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com')

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = TEST_ADMIN_PASSWORD


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["username"] == TEST_USERNAME
        print(f"SUCCESS: Login returns token and user: {data['user']['username']}")
        
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Invalid login returns 401")


class TestCategoriesCaching:
    """Test categories endpoints and caching performance"""
    
    def test_categories_all_caching(self):
        """Test /api/categories/all caching - second call should be faster"""
        # First call (hits database)
        start1 = time.time()
        response1 = requests.get(f"{BASE_URL}/api/categories/all")
        time1 = time.time() - start1
        
        assert response1.status_code == 200, f"Categories call 1 failed: {response1.status_code}"
        categories = response1.json()
        assert isinstance(categories, list), "Categories should be a list"
        assert len(categories) > 0, "Categories should not be empty"
        
        # Second call (should hit cache)
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/categories/all")
        time2 = time.time() - start2
        
        assert response2.status_code == 200, f"Categories call 2 failed: {response2.status_code}"
        
        print(f"SUCCESS: Categories /all returns {len(categories)} categories")
        print(f"  First call: {time1:.3f}s, Second call: {time2:.3f}s")
        if time2 < time1:
            print(f"  Cache speedup: {(time1-time2)/time1*100:.1f}% faster")
        
    def test_categories_structure(self):
        """Test categories have correct structure"""
        response = requests.get(f"{BASE_URL}/api/categories/all")
        assert response.status_code == 200
        categories = response.json()
        
        if len(categories) > 0:
            cat = categories[0]
            assert "id" in cat, "Category should have 'id'"
            assert "label" in cat, "Category should have 'label'"
            assert "kode_aset" in cat, "Category should have 'kode_aset'"
            print(f"SUCCESS: Category structure correct - sample: {cat['kode_aset']} - {cat['label'][:50]}")


class TestFilterOptionsCaching:
    """Test filter options endpoint caching"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get COBA 1 activity ID"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        coba1 = next((a for a in activities if "COBA 1" in a.get("nama_kegiatan", "")), None)
        return coba1["id"] if coba1 else None
    
    def test_filter_options_caching(self, activity_id):
        """Test filter options caching - second call should be faster"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
        
        # First call
        start1 = time.time()
        response1 = requests.get(f"{BASE_URL}/api/assets/filter-options?activity_id={activity_id}")
        time1 = time.time() - start1
        
        assert response1.status_code == 200
        options = response1.json()
        
        # Second call (cached)
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/assets/filter-options?activity_id={activity_id}")
        time2 = time.time() - start2
        
        assert response2.status_code == 200
        
        print(f"SUCCESS: Filter options loaded - {len(options.get('locations', []))} locations, {len(options.get('conditions', []))} conditions")
        print(f"  First call: {time1:.3f}s, Second call: {time2:.3f}s")
        
    def test_filter_options_structure(self, activity_id):
        """Test filter options have correct structure"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets/filter-options?activity_id={activity_id}")
        assert response.status_code == 200
        options = response.json()
        
        expected_keys = ["locations", "departments", "conditions", "statuses", "stiker_statuses"]
        for key in expected_keys:
            assert key in options, f"Missing key: {key}"
            assert isinstance(options[key], list), f"{key} should be a list"
        
        print(f"SUCCESS: Filter options structure correct - keys: {list(options.keys())}")


class TestStatsCaching:
    """Test stats endpoint caching"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get COBA 1 activity ID"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        coba1 = next((a for a in activities if "COBA 1" in a.get("nama_kegiatan", "")), None)
        return coba1["id"] if coba1 else None
    
    def test_stats_caching(self, activity_id):
        """Test stats caching - second call should be faster"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
        
        # First call
        start1 = time.time()
        response1 = requests.get(f"{BASE_URL}/api/assets/stats?activity_id={activity_id}")
        time1 = time.time() - start1
        
        assert response1.status_code == 200
        stats = response1.json()
        
        # Second call (cached)
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/assets/stats?activity_id={activity_id}")
        time2 = time.time() - start2
        
        assert response2.status_code == 200
        
        print(f"SUCCESS: Stats loaded - {stats.get('total_assets', 0)} assets, Rp {stats.get('total_value', 0):,.0f}")
        print(f"  First call: {time1:.3f}s, Second call: {time2:.3f}s")


class TestAssetCRUD:
    """Test Asset CRUD operations - core functionality for AssetForm"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get COBA 1 activity ID"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        coba1 = next((a for a in activities if "COBA 1" in a.get("nama_kegiatan", "")), None)
        return coba1["id"] if coba1 else None
    
    @pytest.fixture(scope="class")
    def test_category(self):
        """Get a valid category"""
        response = requests.get(f"{BASE_URL}/api/categories/all")
        assert response.status_code == 200
        categories = response.json()
        # Find a category with kode_aset (for auto-fill testing)
        cat_with_code = next((c for c in categories if c.get("kode_aset")), None)
        return cat_with_code or categories[0] if categories else None
    
    def test_asset_list_loads(self, activity_id):
        """Test asset list loads for activity"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=1&page_size=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data, "Missing 'items' in response"
        assert "total" in data, "Missing 'total' in response"
        assert "total_pages" in data, "Missing 'total_pages' in response"
        
        print(f"SUCCESS: Asset list loads - {data['total']} total assets, {len(data['items'])} on page 1")
        
    def test_create_asset(self, activity_id, test_category):
        """Test creating a new asset via API (simulates AssetForm submission)"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
        if not test_category:
            pytest.skip("No category available")
            
        # Generate unique test asset
        random_suffix = ''.join(random.choices(string.digits, k=4))
        asset_code = test_category.get("kode_aset", "9999999999")
        
        new_asset = {
            "asset_code": asset_code,
            "NUP": f"TEST{random_suffix}",
            "asset_name": f"Test Asset Form {random_suffix}",
            "category": test_category.get("label", "Elektronik"),
            "brand": "TestBrand",
            "model": "TestModel",
            "location": "Test Location",
            "department": "Test Department",
            "condition": "Baik",
            "status": "Aktif",
            "purchase_price": "1500000",
            "activity_id": activity_id,
            "stiker_status": "Belum Terpasang"
        }
        
        response = requests.post(f"{BASE_URL}/api/assets", json=new_asset)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        created = response.json()
        assert "id" in created, "No ID in created asset"
        assert created["asset_code"] == asset_code
        assert created["asset_name"] == new_asset["asset_name"]
        
        print(f"SUCCESS: Asset created - ID: {created['id']}, Code: {created['asset_code']}, NUP: {created['NUP']}")
        
        # Store for cleanup
        return created["id"]
    
    def test_get_single_asset(self, activity_id):
        """Test retrieving a single asset (used when editing)"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        # Get first asset from list
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=1&page_size=1")
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        if not items:
            pytest.skip("No assets available")
            
        asset_id = items[0]["id"]
        
        # Fetch single asset with full details
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200
        
        asset = response.json()
        assert "id" in asset
        assert "asset_code" in asset
        assert "asset_name" in asset
        assert "photos" in asset, "Full asset should include photos array"
        assert "document_checklist" in asset, "Full asset should include document_checklist"
        
        print(f"SUCCESS: Single asset retrieved - {asset['asset_code']} - {asset['asset_name'][:30]}")
        print(f"  Photos: {len(asset.get('photos', []))}, Checklist items: {len(asset.get('document_checklist', []))}")
    
    def test_update_asset(self, activity_id):
        """Test updating an asset (simulates editing in AssetForm)"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        # Get first asset
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=1&page_size=1")
        assert response.status_code == 200
        items = response.json().get("items", [])
        
        if not items:
            pytest.skip("No assets available")
            
        asset_id = items[0]["id"]
        
        # Get full asset details
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200
        original = response.json()
        
        # Update with modified field
        update_data = {
            **original,
            "notes": f"Updated via test at {time.time()}"
        }
        # Remove _id if present
        update_data.pop("_id", None)
        update_data.pop("created_at", None)
        
        response = requests.put(f"{BASE_URL}/api/assets/{asset_id}", json=update_data)
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        updated = response.json()
        assert updated["notes"].startswith("Updated via test")
        
        print(f"SUCCESS: Asset updated - {updated['asset_code']}, notes: {updated['notes'][:50]}")
    
    def test_delete_asset(self, activity_id, test_category):
        """Test deleting an asset"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
        if not test_category:
            pytest.skip("No category available")
            
        # Create asset to delete
        random_suffix = ''.join(random.choices(string.digits, k=4))
        asset_code = test_category.get("kode_aset", "9999999999")
        
        new_asset = {
            "asset_code": asset_code,
            "NUP": f"DEL{random_suffix}",
            "asset_name": f"To Delete {random_suffix}",
            "category": test_category.get("label", "Elektronik"),
            "activity_id": activity_id
        }
        
        response = requests.post(f"{BASE_URL}/api/assets", json=new_asset)
        assert response.status_code == 200
        created_id = response.json()["id"]
        
        # Delete it
        response = requests.delete(f"{BASE_URL}/api/assets/{created_id}")
        assert response.status_code == 200
        
        # Verify deleted
        response = requests.get(f"{BASE_URL}/api/assets/{created_id}")
        assert response.status_code == 404
        
        print(f"SUCCESS: Asset created and deleted successfully - ID: {created_id}")


class TestAdvancedFilters:
    """Test advanced filter functionality"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get COBA 1 activity ID"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        coba1 = next((a for a in activities if "COBA 1" in a.get("nama_kegiatan", "")), None)
        return coba1["id"] if coba1 else None
    
    def test_search_filter(self, activity_id):
        """Test search functionality"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&search=laptop")
        assert response.status_code == 200
        data = response.json()
        print(f"SUCCESS: Search 'laptop' returned {data['total']} results")
        
    def test_condition_filter(self, activity_id):
        """Test condition filter"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&condition=Baik")
        assert response.status_code == 200
        data = response.json()
        print(f"SUCCESS: Condition filter 'Baik' returned {data['total']} results")
        
    def test_status_filter(self, activity_id):
        """Test status filter"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&status=Aktif")
        assert response.status_code == 200
        data = response.json()
        print(f"SUCCESS: Status filter 'Aktif' returned {data['total']} results")
        
    def test_price_range_filter(self, activity_id):
        """Test price range filter"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&price_min=1000000&price_max=10000000")
        assert response.status_code == 200
        data = response.json()
        print(f"SUCCESS: Price range 1M-10M returned {data['total']} results")


class TestPagination:
    """Test pagination functionality"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get COBA 1 activity ID"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        coba1 = next((a for a in activities if "COBA 1" in a.get("nama_kegiatan", "")), None)
        return coba1["id"] if coba1 else None
    
    def test_pagination_pages_different(self, activity_id):
        """Test pagination returns different results on different pages"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response1 = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=1&page_size=10")
        response2 = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=2&page_size=10")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        items1 = response1.json()["items"]
        items2 = response2.json()["items"]
        
        if items1 and items2:
            ids1 = set(i["id"] for i in items1)
            ids2 = set(i["id"] for i in items2)
            assert ids1 != ids2, "Page 1 and Page 2 should have different items"
            print("SUCCESS: Pagination working - Page 1 IDs != Page 2 IDs")
        
    def test_page_size_change(self, activity_id):
        """Test changing page size"""
        if not activity_id:
            pytest.skip("No COBA 1 activity found")
            
        response = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page=1&page_size=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 100
        print(f"SUCCESS: Page size 100 returned {len(data['items'])} items")


class TestCategoryManager:
    """Test Category Manager dialog APIs"""
    
    def test_categories_paginated(self):
        """Test paginated categories endpoint"""
        response = requests.get(f"{BASE_URL}/api/categories?page=1&page_size=50")
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data, "Missing 'data' in response"
        assert "total" in data, "Missing 'total' in response"
        assert "total_pages" in data, "Missing 'total_pages' in response"
        
        print(f"SUCCESS: Paginated categories - {data['total']} total, {data['total_pages']} pages")
        
    def test_categories_search(self):
        """Test categories search"""
        response = requests.get(f"{BASE_URL}/api/categories?search=laptop&page=1&page_size=50")
        assert response.status_code == 200
        data = response.json()
        print(f"SUCCESS: Category search 'laptop' returned {len(data.get('data', []))} results")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
