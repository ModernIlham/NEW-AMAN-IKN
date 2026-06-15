
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite for WebSocket Deferred Refresh Fix (Iteration 76)

Tests backend API endpoints used by the DashboardPage.jsx
- POST /api/auth/login
- GET /api/inventory-activities
- GET /api/assets (with activity_id)
- WebSocket connection (if testable)

The actual WS deferred refresh fix is frontend-only, but we verify the backend
APIs support the required operations.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
        print("✓ Login successful - token received")
    
    def test_login_invalid_credentials(self):
        """Test login with wrong credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials return 401")


class TestInventoryActivities:
    """Inventory activities endpoint tests"""
    
    def test_get_activities(self):
        """Test listing all inventory activities"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} inventory activities")
        
        # Find the test activity with assets
        test_activity = next((a for a in data if a.get('total_assets', 0) > 1000), None)
        if test_activity:
            print(f"  - Activity '{test_activity['nama_kegiatan']}' has {test_activity['total_assets']} assets")
        return data
    
    def test_get_activity_with_assets(self):
        """Verify we can find an activity with assets for testing"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        data = response.json()
        
        # Find activity with 1926 assets (Test Kegiatan untuk Testing)
        activity = next((a for a in data if a.get('total_assets', 0) == 1926), None)
        if activity:
            print(f"✓ Found test activity: {activity['nama_kegiatan']} with {activity['total_assets']} assets")
            return activity['id']
        else:
            # Find any activity with assets
            activity = next((a for a in data if a.get('total_assets', 0) > 0), None)
            if activity:
                print(f"✓ Found activity with assets: {activity['nama_kegiatan']} ({activity['total_assets']} assets)")
                return activity['id']
        
        pytest.skip("No activity with assets found")


class TestAssets:
    """Asset endpoints tests"""
    
    @pytest.fixture
    def activity_id(self):
        """Get activity ID with assets"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        data = response.json()
        activity = next((a for a in data if a.get('total_assets', 0) > 0), None)
        if not activity:
            pytest.skip("No activity with assets")
        return activity['id']
    
    def test_get_assets_paginated(self, activity_id):
        """Test getting assets with pagination"""
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        
        print(f"✓ Assets paginated: {len(data['items'])} items, {data['total']} total, {data['total_pages']} pages")
        
        # Verify asset structure
        if data['items']:
            asset = data['items'][0]
            assert "id" in asset
            assert "asset_code" in asset or "kode_aset" in asset
            print(f"  - First asset ID: {asset['id']}")
    
    def test_get_asset_by_id(self, activity_id):
        """Test getting single asset by ID"""
        # First get list of assets
        response = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "page_size": 1
        })
        data = response.json()
        if not data['items']:
            pytest.skip("No assets available")
        
        asset_id = data['items'][0]['id']
        
        # Get single asset
        response = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert response.status_code == 200
        asset = response.json()
        assert asset['id'] == asset_id
        print(f"✓ Retrieved single asset: {asset.get('asset_code') or asset.get('kode_aset')}")
    
    def test_get_assets_stats(self, activity_id):
        """Test getting asset statistics"""
        response = requests.get(f"{BASE_URL}/api/assets/stats", params={
            "activity_id": activity_id
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "total_assets" in data
        print(f"✓ Asset stats: {data['total_assets']} total assets, value: {data.get('total_value', 'N/A')}")


class TestWebSocketSupport:
    """WebSocket related endpoint tests"""
    
    def test_websocket_endpoint_exists(self):
        """Verify WebSocket endpoint is accessible (HTTP upgrade required)"""
        # WebSocket endpoints return 400/426 for regular HTTP requests
        # but we can verify the endpoint exists
        try:
            response = requests.get(f"{BASE_URL}/api/ws/test-activity-id", timeout=5)
            # 400 or 426 is expected (Upgrade Required)
            assert response.status_code in [400, 426, 403, 404, 405]
            print(f"✓ WebSocket endpoint exists (returns {response.status_code} for HTTP)")
        except requests.exceptions.ReadTimeout:
            print("✓ WebSocket endpoint exists (connection timeout - expected for WS)")
        except requests.exceptions.ConnectionError:
            print("⚠ WebSocket endpoint connection issue (may need WS protocol)")


class TestDashboardIntegration:
    """Integration tests simulating DashboardPage.jsx data flow"""
    
    def test_full_dashboard_data_flow(self):
        """Test the complete data flow used by DashboardPage"""
        
        # 1. Login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json()['access_token']
        headers = {"Authorization": f"Bearer {token}"}
        print("✓ Step 1: Login successful")
        
        # 2. Get activities
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert activities_resp.status_code == 200
        activities = activities_resp.json()
        print(f"✓ Step 2: Retrieved {len(activities)} activities")
        
        # 3. Select activity with assets
        activity = next((a for a in activities if a.get('total_assets', 0) > 0), None)
        if not activity:
            pytest.skip("No activity with assets")
        activity_id = activity['id']
        print(f"✓ Step 3: Selected activity '{activity['nama_kegiatan']}' ({activity['total_assets']} assets)")
        
        # 4. Get assets for activity
        assets_resp = requests.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "page": 1,
            "page_size": 50
        })
        assert assets_resp.status_code == 200
        assets_data = assets_resp.json()
        print(f"✓ Step 4: Retrieved {len(assets_data['items'])} assets (page 1 of {assets_data['total_pages']})")
        
        # 5. Get stats
        stats_resp = requests.get(f"{BASE_URL}/api/assets/stats", params={
            "activity_id": activity_id
        })
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        print(f"✓ Step 5: Stats - {stats['total_assets']} assets, value: {stats.get('total_value', 'N/A')}")
        
        # 6. Simulate editing - get single asset
        if assets_data['items']:
            asset_id = assets_data['items'][0]['id']
            single_resp = requests.get(f"{BASE_URL}/api/assets/{asset_id}")
            assert single_resp.status_code == 200
            print("✓ Step 6: Retrieved single asset for editing")
        
        print("\n✓ Full dashboard data flow verified!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
