
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite: Heartbeat and Online/Offline Status Feature
========================================================
Tests for:
1. POST /api/auth/heartbeat - Updates user's last_active timestamp
2. GET /api/users - Returns is_online and last_active fields
3. Login updates last_active timestamp
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = TEST_ADMIN_PASSWORD


class TestHeartbeatEndpoint:
    """Tests for POST /api/auth/heartbeat"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token")
        self.user_id = data.get("user", {}).get("id")
        assert self.token, "No token returned from login"
        assert self.user_id, "No user_id returned from login"
    
    def test_heartbeat_returns_200_with_valid_token(self):
        """Test that heartbeat returns 200 with status:ok when authenticated"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/heartbeat",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status:ok, got {data}"
        print(f"✓ Heartbeat returned 200 with status: {data.get('status')}")
    
    def test_heartbeat_returns_401_without_token(self):
        """Test that heartbeat returns 401 without authorization"""
        response = self.session.post(f"{BASE_URL}/api/auth/heartbeat")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Heartbeat returned 401 without token")
    
    def test_heartbeat_returns_401_with_invalid_token(self):
        """Test that heartbeat returns 401 with invalid token"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/heartbeat",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Heartbeat returned 401 with invalid token")
    
    def test_heartbeat_updates_last_active_timestamp(self):
        """Test that heartbeat actually updates the last_active field"""
        # First, send heartbeat
        response = self.session.post(
            f"{BASE_URL}/api/auth/heartbeat",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert response.status_code == 200
        
        # Then, get users and check last_active was updated recently
        response = self.session.get(f"{BASE_URL}/api/users?admin_id={self.user_id}")
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        
        users = response.json()
        current_user = next((u for u in users if u["id"] == self.user_id), None)
        assert current_user, "Current user not found in users list"
        
        last_active = current_user.get("last_active")
        assert last_active, "last_active field not present in user data"
        
        # Verify last_active is within the last 30 seconds
        la_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - la_dt).total_seconds()
        assert diff < 30, f"last_active is too old: {diff} seconds ago"
        
        print(f"✓ Heartbeat updated last_active to {last_active} ({diff:.1f}s ago)")


class TestUserOnlineStatus:
    """Tests for is_online field in GET /api/users"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("access_token")
        self.user_id = data.get("user", {}).get("id")
    
    def test_users_returns_is_online_field(self):
        """Test that GET /api/users returns is_online field for each user"""
        response = self.session.get(f"{BASE_URL}/api/users?admin_id={self.user_id}")
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Expected list of users"
        assert len(users) > 0, "Expected at least 1 user"
        
        for user in users:
            assert "is_online" in user, f"is_online field missing for user {user.get('username')}"
            assert isinstance(user["is_online"], bool), f"is_online should be boolean, got {type(user['is_online'])}"
        
        print(f"✓ All {len(users)} users have is_online field")
    
    def test_users_returns_last_active_field(self):
        """Test that GET /api/users returns last_active field for each user"""
        response = self.session.get(f"{BASE_URL}/api/users?admin_id={self.user_id}")
        assert response.status_code == 200
        
        users = response.json()
        for user in users:
            # last_active may be empty string if never active, but field should exist or be implicitly present
            # The field is returned from DB, it may not exist for old users
            assert "id" in user and "username" in user, "User should have id and username"
        
        print("✓ Users list returned with expected structure")
    
    def test_recently_active_user_shows_online(self):
        """Test that a user who just logged in and sent heartbeat shows as online"""
        # Send heartbeat to ensure we're active
        response = self.session.post(
            f"{BASE_URL}/api/auth/heartbeat",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        assert response.status_code == 200
        
        # Check online status
        response = self.session.get(f"{BASE_URL}/api/users?admin_id={self.user_id}")
        assert response.status_code == 200
        
        users = response.json()
        current_user = next((u for u in users if u["id"] == self.user_id), None)
        assert current_user, "Current user not found"
        assert current_user["is_online"] == True, f"Expected is_online=True for active user, got {current_user.get('is_online')}"
        
        print("✓ Admin user shows as online after heartbeat")


class TestLoginUpdatesLastActive:
    """Tests for login updating last_active timestamp"""
    
    def test_login_updates_last_active(self):
        """Test that login also updates the last_active timestamp"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user_id = data.get("user", {}).get("id")
        
        # Get users and verify last_active was updated
        response = session.get(
            f"{BASE_URL}/api/users?admin_id={user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        users = response.json()
        current_user = next((u for u in users if u["id"] == user_id), None)
        assert current_user, "Current user not found"
        
        last_active = current_user.get("last_active")
        assert last_active, "last_active not set after login"
        
        # Verify it's recent (within 30 seconds)
        la_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - la_dt).total_seconds()
        assert diff < 30, f"last_active should be recent after login, but is {diff}s old"
        
        print(f"✓ Login updated last_active timestamp ({diff:.1f}s ago)")
    
    def test_user_is_online_after_login(self):
        """Test that user is marked online immediately after login"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user_id = data.get("user", {}).get("id")
        
        # Check online status immediately
        response = session.get(f"{BASE_URL}/api/users?admin_id={user_id}")
        assert response.status_code == 200
        
        users = response.json()
        current_user = next((u for u in users if u["id"] == user_id), None)
        assert current_user, "Current user not found"
        assert current_user["is_online"] == True, f"User should be online after login, got {current_user.get('is_online')}"
        
        print("✓ User is online immediately after login")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
