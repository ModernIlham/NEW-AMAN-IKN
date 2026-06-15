#!/usr/bin/env python3

# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Tests for Pagination, Stats, and Export endpoints
Focus: Server-side pagination, aggregated stats, export downloads
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com')


class TestAuthentication:
    """Test admin login credentials"""
    
    def test_admin_login_success(self):
        """Login with admin/admin123 credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["username"] == "admin"
        print("Admin login successful - token received")
        return data["access_token"]

    def test_admin_login_wrong_password(self):
        """Login with wrong password should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestPagination:
    """Test pagination functionality for assets"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin login failed")

    def test_paginated_response_structure(self, auth_token):
        """Verify paginated response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50")
        assert response.status_code == 200
        
        data = response.json()
        # Verify pagination fields exist
        assert "items" in data, "Missing 'items' field"
        assert "total" in data, "Missing 'total' field"
        assert "page" in data, "Missing 'page' field"
        assert "page_size" in data, "Missing 'page_size' field"
        assert "total_pages" in data, "Missing 'total_pages' field"
        
        # Verify data types
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)
        assert isinstance(data["total_pages"], int)
        
        print(f"Total assets: {data['total']}, Page: {data['page']}, Page size: {data['page_size']}, Total pages: {data['total_pages']}")

    def test_page_size_limit(self, auth_token):
        """Test page_size returns correct number of items"""
        for page_size in [25, 50, 100]:
            response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size={page_size}")
            assert response.status_code == 200
            
            data = response.json()
            items_count = len(data["items"])
            # Should return at most page_size items (or less if fewer total)
            assert items_count <= page_size, f"Expected at most {page_size} items, got {items_count}"
            assert data["page_size"] == page_size
            print(f"Page size {page_size}: returned {items_count} items")

    def test_page_navigation(self, auth_token):
        """Test navigating between pages"""
        # Get first page
        response1 = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=25")
        assert response1.status_code == 200
        data1 = response1.json()
        
        if data1["total_pages"] >= 2:
            # Get second page
            response2 = requests.get(f"{BASE_URL}/api/assets?page=2&page_size=25")
            assert response2.status_code == 200
            data2 = response2.json()
            
            assert data2["page"] == 2
            # Items should be different between pages
            if data1["items"] and data2["items"]:
                assert data1["items"][0]["id"] != data2["items"][0]["id"], "Page 1 and 2 should have different items"
            print("Page navigation works - Page 1 and 2 have different items")
        else:
            print(f"Only {data1['total_pages']} page(s) - skipping page 2 check")

    def test_page_size_min_clamp(self, auth_token):
        """Test that page_size is clamped to minimum 10"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=5")
        assert response.status_code == 200
        
        data = response.json()
        # Server should clamp page_size to min 10
        assert data["page_size"] >= 10, f"Expected page_size >= 10, got {data['page_size']}"
        print(f"Min page_size clamp works - requested 5, got {data['page_size']}")

    def test_page_size_max_clamp(self, auth_token):
        """Test that page_size is clamped to maximum 200"""
        response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=500")
        assert response.status_code == 200
        
        data = response.json()
        # Server should clamp page_size to max 200
        assert data["page_size"] <= 200, f"Expected page_size <= 200, got {data['page_size']}"
        print(f"Max page_size clamp works - requested 500, got {data['page_size']}")

    def test_search_with_pagination(self, auth_token):
        """Test search functionality with pagination"""
        response = requests.get(f"{BASE_URL}/api/assets?search=laptop&page=1&page_size=25")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"Search 'laptop' found {data['total']} results")

    def test_category_filter_with_pagination(self, auth_token):
        """Test category filter with pagination"""
        response = requests.get(f"{BASE_URL}/api/assets?category=Elektronik&page=1&page_size=25")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        # All items should have the filtered category
        for item in data["items"]:
            assert item["category"] == "Elektronik", f"Expected category 'Elektronik', got {item['category']}"
        print(f"Category filter 'Elektronik' found {data['total']} results")


class TestStats:
    """Test stats endpoint for aggregated data"""
    
    def test_stats_response_structure(self):
        """Verify stats endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/assets/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify stats fields exist
        assert "total_assets" in data, "Missing 'total_assets' field"
        assert "total_value" in data, "Missing 'total_value' field"
        assert "active_count" in data, "Missing 'active_count' field"
        assert "maintenance_count" in data, "Missing 'maintenance_count' field"
        
        # Verify data types
        assert isinstance(data["total_assets"], int)
        assert isinstance(data["total_value"], (int, float))
        assert isinstance(data["active_count"], int)
        assert isinstance(data["maintenance_count"], int)
        
        print(f"Stats: Total={data['total_assets']}, Value={data['total_value']}, Active={data['active_count']}, Maintenance={data['maintenance_count']}")

    def test_stats_consistency_with_pagination(self):
        """Verify stats total matches paginated total"""
        stats_response = requests.get(f"{BASE_URL}/api/assets/stats")
        pagination_response = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=50")
        
        assert stats_response.status_code == 200
        assert pagination_response.status_code == 200
        
        stats_data = stats_response.json()
        pagination_data = pagination_response.json()
        
        assert stats_data["total_assets"] == pagination_data["total"], \
            f"Stats total ({stats_data['total_assets']}) != Pagination total ({pagination_data['total']})"
        print(f"Stats total ({stats_data['total_assets']}) matches pagination total")

    def test_stats_with_search_filter(self):
        """Test stats with search filter applied"""
        response = requests.get(f"{BASE_URL}/api/assets/stats?search=laptop")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_assets" in data
        print(f"Stats with search 'laptop': {data['total_assets']} assets")

    def test_stats_with_category_filter(self):
        """Test stats with category filter applied"""
        response = requests.get(f"{BASE_URL}/api/assets/stats?category=Elektronik")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_assets" in data
        print(f"Stats with category 'Elektronik': {data['total_assets']} assets")


class TestExports:
    """Test export functionality (CSV, PDF, Excel)"""
    
    def test_export_csv(self):
        """Test CSV export endpoint"""
        response = requests.get(f"{BASE_URL}/api/export/csv")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type or "text/plain" in content_type, \
            f"Expected CSV content type, got {content_type}"
        
        # Check content disposition header
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition, "Expected attachment disposition"
        assert ".csv" in disposition, "Expected .csv in filename"
        
        # Verify CSV content structure
        content = response.text
        lines = content.strip().split('\n')
        assert len(lines) > 1, "Expected CSV with header and data"
        
        header = lines[0]
        assert "asset_code" in header, "Expected asset_code in CSV header"
        print(f"CSV export successful - {len(lines)-1} data rows")

    def test_export_pdf(self):
        """Test PDF export endpoint"""
        response = requests.get(f"{BASE_URL}/api/export/pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got {content_type}"
        
        # Check content disposition header
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition, "Expected attachment disposition"
        assert ".pdf" in disposition, "Expected .pdf in filename"
        
        # Verify PDF magic bytes
        content = response.content
        assert content[:4] == b'%PDF', "Expected PDF magic bytes"
        print(f"PDF export successful - {len(content)} bytes")

    def test_export_xlsx(self):
        """Test Excel export endpoint"""
        response = requests.get(f"{BASE_URL}/api/export/xlsx")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "openxmlformats" in content_type or "spreadsheet" in content_type, \
            f"Expected Excel content type, got {content_type}"
        
        # Check content disposition header
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition, "Expected attachment disposition"
        assert ".xlsx" in disposition, "Expected .xlsx in filename"
        
        # Verify XLSX magic bytes (PK ZIP)
        content = response.content
        assert content[:2] == b'PK', "Expected XLSX (ZIP) magic bytes"
        print(f"Excel export successful - {len(content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
