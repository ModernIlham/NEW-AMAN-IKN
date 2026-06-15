
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Password Validation for Registration
Tests password strength validation in /api/auth/request-otp endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

class TestPasswordValidation:
    """Password validation tests for registration endpoint"""
    
    def test_request_otp_rejects_short_password(self):
        """Test that /api/auth/request-otp rejects passwords less than 8 chars"""
        response = requests.post(f"{BASE_URL}/api/auth/request-otp", json={
            "email": f"short_pass_test_{int(time.time())}@example.com",
            "password": "short",  # Less than 8 chars
            "name": "Test User"
        })
        
        # Should reject with 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "8 karakter" in data.get("detail", ""), f"Error message should mention 8 characters: {data}"
        print(f"✓ Short password rejected with message: {data.get('detail')}")
    
    def test_request_otp_accepts_valid_password(self):
        """Test that /api/auth/request-otp accepts valid password (8+ chars)"""
        response = requests.post(f"{BASE_URL}/api/auth/request-otp", json={
            "email": f"valid_pass_test_{int(time.time())}@example.com",
            "password": "ValidPass123!",  # Meets all criteria
            "name": "Test User"
        })
        
        # Should succeed with 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "email" in data or "message" in data, f"Expected successful response: {data}"
        print(f"✓ Valid password accepted: {data.get('message', 'OTP requested')}")
    
    def test_request_otp_exactly_8_chars(self):
        """Test password with exactly 8 characters is accepted"""
        response = requests.post(f"{BASE_URL}/api/auth/request-otp", json={
            "email": f"exact8_test_{int(time.time())}@example.com",
            "password": "Pass123!",  # Exactly 8 chars
            "name": "Test User"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Password with exactly 8 chars accepted")
    
    def test_request_otp_7_chars_rejected(self):
        """Test password with 7 characters is rejected"""
        response = requests.post(f"{BASE_URL}/api/auth/request-otp", json={
            "email": f"seven_char_test_{int(time.time())}@example.com",
            "password": "Pass12!",  # 7 chars
            "name": "Test User"
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Password with 7 chars rejected")


class TestLoginValidation:
    """Tests for login endpoint"""
    
    def test_admin_login_works(self):
        """Test that admin user can login with username 'admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data, "Expected access_token in response"
        assert data.get("user", {}).get("username") == "admin", "Expected admin username"
        print(f"✓ Admin login successful: {data.get('user', {}).get('name')}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test that invalid credentials are rejected"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
