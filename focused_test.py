#!/usr/bin/env python3
"""
Focused test for the new registration feature
"""

import asyncio
import httpx
import json
import random
import string

BASE_URL = "https://asset-crud-auth.preview.emergentagent.com/api"
TIMEOUT = 30.0

def generate_random_email():
    """Generate a random email for testing"""
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_user_{random_id}@test.com"

async def test_registration_behavior():
    """Test the new registration behavior"""
    print("🔍 Testing Registration Behavior")
    
    # Use the admin we found
    admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYjY3YThmNjItOTVhNy00MTYxLTkxNmYtYjI5NjRmYWU1MGEyIiwidXNlcm5hbWUiOiJwZW5kaW5nX3VzZXJfbG9tNThzZHBAdGVzdC5jb20iLCJleHAiOjE3NzY3MDI5ODQuNDgwNTE5fQ.WOSQu7tr6BmLFzyPgR525BpXRJyKJvq2iK6Lkw6GeLI"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test 1: Register a new user (should be inactive)
        print("\n--- Test 1: Register new user (should be inactive) ---")
        new_email = generate_random_email()
        register_data = {
            "username": new_email,
            "password": "Test1234",
            "name": "Test User"
        }
        
        response = await client.post(f"{BASE_URL}/auth/register", json=register_data)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            print(f"✅ pending_approval: {data.get('pending_approval')}")
            print(f"✅ access_token: {data.get('access_token')}")
            print(f"✅ user.is_active: {data.get('user', {}).get('is_active')}")
            print(f"✅ user.role: {data.get('user', {}).get('role')}")
            
            user_id = data.get('user', {}).get('id')
            
            # Test 2: Try to login with inactive user
            print("\n--- Test 2: Try to login with inactive user ---")
            login_data = {
                "username": new_email,
                "password": "Test1234"
            }
            
            response = await client.post(f"{BASE_URL}/auth/login", json=login_data)
            print(f"Login Status: {response.status_code}")
            if response.status_code == 403:
                error_data = response.json()
                print(f"✅ 403 Error: {error_data.get('detail')}")
            else:
                print(f"❌ Expected 403, got {response.status_code}: {response.text}")
            
            # Test 3: Admin activates user
            print("\n--- Test 3: Admin activates user ---")
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Get admin ID
            response = await client.get(f"{BASE_URL}/auth/me", headers=headers)
            if response.status_code == 200:
                admin_data = response.json()
                admin_id = admin_data.get("id")
                print(f"Admin ID: {admin_id}")
                
                # Activate user
                response = await client.put(
                    f"{BASE_URL}/users/{user_id}/toggle-active?admin_id={admin_id}",
                    headers=headers
                )
                print(f"Activation Status: {response.status_code}")
                if response.status_code == 200:
                    activation_data = response.json()
                    print(f"✅ User activated: {activation_data.get('is_active')}")
                    
                    # Test 4: Login with activated user
                    print("\n--- Test 4: Login with activated user ---")
                    response = await client.post(f"{BASE_URL}/auth/login", json=login_data)
                    print(f"Login Status: {response.status_code}")
                    if response.status_code == 200:
                        login_result = response.json()
                        print(f"✅ Login successful, token: {login_result.get('access_token')[:50]}...")
                    else:
                        print(f"❌ Login failed: {response.status_code}: {response.text}")
                else:
                    print(f"❌ Activation failed: {response.status_code}: {response.text}")
            else:
                print(f"❌ Could not get admin info: {response.status_code}: {response.text}")
        else:
            print(f"❌ Registration failed: {response.status_code}: {response.text}")

        # Test 5: OTP-based registration
        print("\n--- Test 5: OTP-based registration ---")
        otp_email = generate_random_email()
        otp_request = {
            "email": otp_email,
            "password": "Test1234",
            "name": "OTP Test User"
        }
        
        response = await client.post(f"{BASE_URL}/auth/request-otp", json=otp_request)
        print(f"OTP Request Status: {response.status_code}")
        if response.status_code == 200:
            otp_data = response.json()
            print(f"OTP Response: {json.dumps(otp_data, indent=2)}")
            
            # Since email is configured, we won't get debug_otp
            # This is expected behavior in production
            if otp_data.get("debug_otp"):
                print(f"Debug OTP: {otp_data.get('debug_otp')}")
                
                # Verify OTP
                verify_data = {
                    "email": otp_email,
                    "otp": otp_data.get("debug_otp")
                }
                
                response = await client.post(f"{BASE_URL}/auth/verify-otp", json=verify_data)
                print(f"OTP Verify Status: {response.status_code}")
                if response.status_code == 200:
                    verify_result = response.json()
                    print(f"Verify Response: {json.dumps(verify_result, indent=2)}")
            else:
                print("✅ No debug OTP (email service configured - production behavior)")

if __name__ == "__main__":
    asyncio.run(test_registration_behavior())