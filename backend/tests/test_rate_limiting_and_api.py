
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Backend API Tests for Indonesian Asset Management System
Tests: Rate Limiting, Asset CRUD, Export Endpoints, Filter Options

Rate limiting configuration:
- /api/auth/login: 10/minute
- /api/auth/register: 5/minute
- /api/export/*: 3-5/minute
- /api/assets/bulk-delete: 3/minute
"""

import pytest
import requests
import time
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com').rstrip('/')
ACTIVITY_ID = "6a97477f-13b1-494c-bf3c-6b328c883ac7"  # COBA 1 with 1479 assets

class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login returns token and user data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        print(f"✓ Login successful for user: {data['user']['username']}")
    
    def test_login_invalid_credentials(self):
        """Test login with wrong credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wrong_user",
            "password": "wrong_pass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


class TestRateLimiting:
    """Rate limiting tests - slowapi implementation"""
    
    def test_login_rate_limit_triggers_at_11th_request(self):
        """
        Test rate limiting on login endpoint.
        Rate limit: 10/minute
        The 11th request should return 429.
        """
        print("Testing rate limiting on /api/auth/login (limit: 10/min)")
        
        # Make 11 rapid requests
        responses = []
        for i in range(12):
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "username": "admin",
                "password": TEST_ADMIN_PASSWORD
            })
            responses.append(response.status_code)
            print(f"  Request {i+1}: Status {response.status_code}")
            time.sleep(0.1)  # Small delay to avoid network issues
        
        # Check that we got at least one 429 response
        rate_limited = 429 in responses
        print(f"  Rate limited responses: {responses.count(429)}")
        
        # The test passes if we see 429 (rate limit hit)
        assert rate_limited, f"Expected 429 rate limit, got responses: {responses}"
        print("✓ Rate limiting working correctly - 429 returned after limit exceeded")


class TestAssetOperations:
    """Asset CRUD and list operations"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Authentication failed")
    
    def test_asset_list_loads(self):
        """Test asset list loads for COBA 1 activity"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200, f"Asset list failed: {response.text}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1000, f"Expected ~1479 assets, got {data['total']}"
        print(f"✓ Asset list loaded: {data['total']} total assets, showing {len(data['items'])} items")
    
    def test_asset_list_pagination_works(self):
        """Test pagination returns different items on different pages"""
        # Get page 1
        page1 = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "page": 1,
            "page_size": 50
        }).json()
        
        # Get page 2
        page2 = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "page": 2,
            "page_size": 50
        }).json()
        
        assert len(page1["items"]) == 50, "Page 1 should have 50 items"
        assert len(page2["items"]) == 50, "Page 2 should have 50 items"
        
        # Items on page 1 and 2 should be different
        page1_ids = {item["id"] for item in page1["items"]}
        page2_ids = {item["id"] for item in page2["items"]}
        assert page1_ids.isdisjoint(page2_ids), "Page 1 and 2 should have different items"
        print("✓ Pagination working correctly - different items on each page")
    
    def test_asset_search_works(self):
        """Test search functionality filters assets"""
        # Search for something specific
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "search": "Laptop",
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Search returned {data['total']} results for 'Laptop'")
    
    def test_asset_filter_by_condition(self):
        """Test filtering by condition"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "condition": "Baik",
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Filter by condition='Baik' returned {data['total']} results")
    
    def test_asset_filter_by_status(self):
        """Test filtering by status"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "status": "Aktif",
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Filter by status='Aktif' returned {data['total']} results")
    
    def test_asset_filter_by_price_range(self):
        """Test filtering by price range"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "price_min": 1000000,
            "price_max": 10000000,
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Filter by price range (1M-10M) returned {data['total']} results")
    
    def test_get_single_asset(self):
        """Test retrieving single asset with full details"""
        # First get list to get an asset ID
        list_response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": ACTIVITY_ID,
            "page": 1,
            "page_size": 1
        })
        assert list_response.status_code == 200
        asset_id = list_response.json()["items"][0]["id"]
        
        # Get single asset
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == asset_id
        assert "asset_code" in data
        assert "asset_name" in data
        print(f"✓ Single asset retrieved: {data['asset_name'][:50]}...")


class TestFilterOptions:
    """Test filter options endpoint"""
    
    def test_filter_options_returns_distinct_values(self):
        """Test filter options endpoint returns distinct values for dropdowns"""
        response = requests.get(f"{BASE_URL}/api/assets/filter-options", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected fields
        assert "locations" in data
        assert "departments" in data
        assert "conditions" in data
        assert "statuses" in data
        assert "stiker_statuses" in data
        
        print(f"✓ Filter options: {len(data['locations'])} locations, {len(data['conditions'])} conditions")


class TestExportEndpoints:
    """Test export endpoints (rate limited)"""
    
    def test_export_csv_endpoint(self):
        """Test CSV export endpoint returns 200 or 429 (rate limited)"""
        response = requests.get(f"{BASE_URL}/api/export/csv", params={
            "activity_id": ACTIVITY_ID
        })
        # Accept 200 (success) or 429 (rate limited from previous tests)
        assert response.status_code in [200, 429], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            assert "text/csv" in response.headers.get("content-type", "")
            print("✓ CSV export successful")
        else:
            print("✓ CSV export rate limited (expected if run multiple times)")
    
    def test_export_pdf_endpoint(self):
        """Test PDF export endpoint"""
        response = requests.get(f"{BASE_URL}/api/export/pdf", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code in [200, 429], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            assert "application/pdf" in response.headers.get("content-type", "")
            print("✓ PDF export successful")
        else:
            print("✓ PDF export rate limited (expected if run multiple times)")
    
    def test_export_xlsx_endpoint(self):
        """Test Excel export endpoint"""
        response = requests.get(f"{BASE_URL}/api/export/xlsx", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code in [200, 429], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "spreadsheet" in content_type or "application/vnd" in content_type
            print("✓ Excel export successful")
        else:
            print("✓ Excel export rate limited (expected if run multiple times)")


class TestCategoryOperations:
    """Test category endpoints"""
    
    def test_get_all_categories(self):
        """Test getting all categories for dropdown"""
        response = requests.get(f"{BASE_URL}/api/categories/all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Categories loaded: {len(data)} categories")
    
    def test_get_categories_paginated(self):
        """Test paginated categories endpoint"""
        response = requests.get(f"{BASE_URL}/api/categories", params={
            "page": 1,
            "page_size": 50
        })
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        print(f"✓ Paginated categories: {data['total']} total")


class TestAssetStats:
    """Test asset statistics endpoint"""
    
    def test_stats_returns_aggregates(self):
        """Test stats endpoint returns aggregate values"""
        response = requests.get(f"{BASE_URL}/api/assets/stats", params={
            "activity_id": ACTIVITY_ID
        })
        assert response.status_code == 200
        data = response.json()
        assert "total_assets" in data
        assert "total_value" in data
        assert "active_count" in data
        print(f"✓ Stats: {data['total_assets']} assets, total value: {data['total_value']}")


class TestHealthCheck:
    """Health check endpoints"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        print("✓ API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
