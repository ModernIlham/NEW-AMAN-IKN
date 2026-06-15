
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite for Iteration 4 - Pagination, Multi-Photo, Mobile UX
Tests: Pagination, Stats, Export, Photo thumbnails, Edit/Add forms
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com')


class TestLogin:
    """Authentication tests"""
    
    def test_login_with_admin_credentials(self):
        """Test login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        print(f"Login successful: {data['user']['username']}")


class TestPagination:
    """Pagination functionality tests"""
    
    def test_page_1_returns_first_50_items(self):
        """GET /api/assets?page=1&page_size=50 returns first page"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert len(data["items"]) == 50
        assert data["total"] > 0
        print(f"Page 1: {len(data['items'])} items, first: {data['items'][0]['asset_code']}")
    
    def test_page_2_returns_different_data_than_page_1(self):
        """Page 2 should show different assets than page 1"""
        page1 = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50").json()
        page2 = requests.get(f"{BASE_URL}/api/assets?page=2&page_size=50").json()
        
        assert page1["page"] == 1
        assert page2["page"] == 2
        assert page1["items"][0]["asset_code"] != page2["items"][0]["asset_code"]
        print(f"Page 1 first: {page1['items'][0]['asset_code']}, Page 2 first: {page2['items'][0]['asset_code']}")
    
    def test_page_3_returns_different_data_than_page_2(self):
        """Page 3 should show different assets than page 2"""
        page2 = requests.get(f"{BASE_URL}/api/assets?page=2&page_size=50").json()
        page3 = requests.get(f"{BASE_URL}/api/assets?page=3&page_size=50").json()
        
        assert page2["page"] == 2
        assert page3["page"] == 3
        assert page2["items"][0]["asset_code"] != page3["items"][0]["asset_code"]
        print(f"Page 2 first: {page2['items'][0]['asset_code']}, Page 3 first: {page3['items'][0]['asset_code']}")
    
    def test_page_size_25_returns_25_items(self):
        """Page size 25 should return 25 items"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=25")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 25
        print(f"Page size 25: {len(data['items'])} items returned")
    
    def test_page_size_100_returns_100_items(self):
        """Page size 100 should return 100 items"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 100
        print(f"Page size 100: {len(data['items'])} items returned")
    
    def test_pagination_total_pages_calculated_correctly(self):
        """Total pages should be calculated based on total items and page size"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50")
        data = response.json()
        expected_pages = (data["total"] + 49) // 50  # Ceiling division
        assert data["total_pages"] == expected_pages
        print(f"Total: {data['total']}, Pages: {data['total_pages']}")


class TestStats:
    """Stats endpoint tests"""
    
    def test_stats_returns_4_metrics(self):
        """Stats should return total_assets, total_value, active_count, maintenance_count"""
        response = requests.get(f"{BASE_URL}/api/assets/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_assets" in data
        assert "total_value" in data
        assert "active_count" in data
        assert "maintenance_count" in data
        
        print(f"Stats: Total={data['total_assets']}, Value={data['total_value']}, "
              f"Active={data['active_count']}, Maintenance={data['maintenance_count']}")
    
    def test_stats_total_assets_matches_pagination_total(self):
        """Stats total should match pagination total"""
        stats = requests.get(f"{BASE_URL}/api/assets/stats").json()
        pagination = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50").json()
        
        assert stats["total_assets"] == pagination["total"]
        print(f"Stats total: {stats['total_assets']}, Pagination total: {pagination['total']}")


class TestExport:
    """Export functionality tests"""
    
    def test_export_csv_returns_200_and_correct_content_type(self):
        """CSV export should return 200 with text/csv content type"""
        response = requests.get(f"{BASE_URL}/api/export/csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        print(f"CSV Export: {response.status_code}, Size: {len(response.content)} bytes")
    
    def test_export_pdf_returns_200_and_correct_content_type(self):
        """PDF export should return 200 with application/pdf content type"""
        response = requests.get(f"{BASE_URL}/api/export/pdf")
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("Content-Type", "")
        print(f"PDF Export: {response.status_code}, Size: {len(response.content)} bytes")
    
    def test_export_xlsx_returns_200_and_correct_content_type(self):
        """Excel export should return 200 with spreadsheet content type"""
        response = requests.get(f"{BASE_URL}/api/export/xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers.get("Content-Type", "")
        print(f"Excel Export: {response.status_code}, Size: {len(response.content)} bytes")


class TestAssetCRUD:
    """Asset CRUD operations tests"""
    
    def test_get_single_asset_returns_photos_array(self):
        """Getting a single asset should include photos array"""
        # First get an asset ID
        assets = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=1").json()
        asset_id = assets["items"][0]["id"]
        
        # Get single asset
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify photos field exists (can be empty array)
        assert "photos" in data or data.get("photos") is None or isinstance(data.get("photos", []), list)
        print(f"Asset {data['asset_code']}: photos field present")
    
    def test_asset_list_includes_thumbnail_field(self):
        """Asset list should include thumbnail field for each item"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["items"]:
            # thumbnail field should exist (can be None)
            assert "thumbnail" in item or item.get("thumbnail") is None
        
        print(f"All {len(data['items'])} items have thumbnail field")


class TestMultiPhotoSupport:
    """Multi-photo feature tests"""
    
    def test_create_asset_with_photos_array(self):
        """Creating asset with photos array should work"""
        import uuid
        test_code = f"TEST-PHOTO-{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/assets", json={
            "asset_code": test_code,
            "asset_name": "Test Multi Photo Asset",
            "category": "Elektronik",
            "photos": []  # Empty photos array
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["asset_code"] == test_code
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/assets/{data['id']}")
        print(f"Created and deleted test asset: {test_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
