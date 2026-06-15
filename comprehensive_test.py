#!/usr/bin/env python3
"""
Updated comprehensive backend test with correct admin credentials
"""

import asyncio
import httpx
import json
import uuid
import time
import base64
import websockets
from typing import Dict, Any, List, Optional
import random
import string

# Configuration
BASE_URL = "https://asset-crud-auth.preview.emergentagent.com/api"
TIMEOUT = 30.0

# Admin credentials found from the system
ADMIN_EMAIL = "pending_user_lom58sdp@test.com"
ADMIN_PASSWORD = "Test1234"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.test_data = {}
        
    def assert_test(self, condition: bool, test_name: str, error_msg: str = ""):
        if condition:
            self.passed += 1
            print(f"✅ {test_name}")
        else:
            self.failed += 1
            error_detail = f"❌ {test_name}: {error_msg}"
            self.errors.append(error_detail)
            print(error_detail)
            
    def print_summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{total} PASSED ({self.passed/total*100:.1f}%)")
        if self.errors:
            print(f"\nFAILED TESTS:")
            for error in self.errors:
                print(f"  {error}")
        print(f"{'='*60}")

def generate_random_email():
    """Generate a random email for testing"""
    random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_user_{random_id}@test.com"

def generate_small_base64_png():
    """Generate a small base64 PNG for testing"""
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU8qAAAAAElFTkSuQmCC"
    )
    return base64.b64encode(png_data).decode()

async def get_admin_token() -> Optional[str]:
    """Get admin token for testing"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        login_request = {
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        
        response = await client.post(f"{BASE_URL}/auth/login", json=login_request)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None

async def test_new_registration_feature(results: TestResults):
    """Test the new registration behavior"""
    print("\n🔴 TESTING NEW FEATURE: Registration creates INACTIVE users pending admin approval")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test new user registration (should be inactive)
        print("\n--- Testing new user registration behavior ---")
        
        fresh_email = generate_random_email()
        register_request = {
            "username": fresh_email,
            "password": "Test1234",
            "name": "Test User"
        }
        
        response = await client.post(f"{BASE_URL}/auth/register", json=register_request)
        results.assert_test(
            response.status_code == 200,
            "New user registration succeeds",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            register_data = response.json()
            
            results.assert_test(
                register_data.get("pending_approval") == True,
                "New user: pending_approval: true",
                f"pending_approval: {register_data.get('pending_approval')}"
            )
            
            results.assert_test(
                register_data.get("access_token") is None,
                "New user: access_token: null",
                f"access_token: {register_data.get('access_token')}"
            )
            
            user_data = register_data.get("user", {})
            results.assert_test(
                user_data.get("is_active") == False,
                "New user: is_active: false",
                f"is_active: {user_data.get('is_active')}"
            )
            
            results.assert_test(
                user_data.get("role") == "viewer",
                "New user: role: viewer",
                f"role: {user_data.get('role')}"
            )
            
            message = register_data.get("message", "")
            results.assert_test(
                "administrator" in message.lower(),
                "Message mentions administrator",
                f"Message: {message}"
            )
            
            # Store for admin activation test
            results.test_data["pending_user_id"] = user_data.get("id")
            results.test_data["pending_user_email"] = fresh_email
            results.test_data["pending_user_password"] = "Test1234"
            
            # Test login with inactive user (should fail)
            login_request = {
                "username": fresh_email,
                "password": "Test1234"
            }
            
            response = await client.post(f"{BASE_URL}/auth/login", json=login_request)
            results.assert_test(
                response.status_code == 403,
                "Login with inactive user returns 403",
                f"Expected 403, got {response.status_code}: {response.text}"
            )
            
            if response.status_code == 403:
                error_detail = response.json().get("detail", "")
                results.assert_test(
                    "dinonaktifkan" in error_detail.lower(),
                    "403 error mentions deactivation",
                    f"Detail: {error_detail}"
                )

async def test_admin_activation_flow(results: TestResults):
    """Test admin activation of pending users"""
    print("\n--- Testing Admin Activation Flow ---")
    
    admin_token = await get_admin_token()
    if not admin_token:
        results.assert_test(False, "Admin activation flow", "Could not get admin token")
        return
    
    pending_user_id = results.test_data.get("pending_user_id")
    pending_user_email = results.test_data.get("pending_user_email")
    pending_user_password = results.test_data.get("pending_user_password")
    
    if not pending_user_id:
        results.assert_test(False, "Admin activation flow", "No pending user ID available")
        return
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get admin user ID
        response = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        if response.status_code == 200:
            admin_data = response.json()
            admin_id = admin_data.get("id")
            
            # Activate the pending user
            response = await client.put(
                f"{BASE_URL}/users/{pending_user_id}/toggle-active?admin_id={admin_id}",
                headers=headers
            )
            
            results.assert_test(
                response.status_code == 200,
                "Admin can activate pending user",
                f"Expected 200, got {response.status_code}: {response.text}"
            )
            
            if response.status_code == 200:
                activation_data = response.json()
                results.assert_test(
                    activation_data.get("is_active") == True,
                    "User is_active toggled to true",
                    f"is_active: {activation_data.get('is_active')}"
                )
                
                # Now try to login with the activated user
                login_request = {
                    "username": pending_user_email,
                    "password": pending_user_password
                }
                
                response = await client.post(f"{BASE_URL}/auth/login", json=login_request)
                results.assert_test(
                    response.status_code == 200,
                    "Activated user can login successfully",
                    f"Expected 200, got {response.status_code}: {response.text}"
                )
                
                if response.status_code == 200:
                    login_data = response.json()
                    user_token = login_data.get("access_token")
                    results.assert_test(
                        user_token is not None,
                        "Login returns valid access_token",
                        "No access_token in response"
                    )
                    
                    # Verify /auth/me with the new token
                    if user_token:
                        headers = {"Authorization": f"Bearer {user_token}"}
                        response = await client.get(f"{BASE_URL}/auth/me", headers=headers)
                        
                        results.assert_test(
                            response.status_code == 200,
                            "/auth/me works with activated user token",
                            f"Expected 200, got {response.status_code}: {response.text}"
                        )
                        
                        if response.status_code == 200:
                            me_data = response.json()
                            results.assert_test(
                                me_data.get("is_active") == True,
                                "/auth/me shows user as active",
                                f"is_active: {me_data.get('is_active')}"
                            )

async def test_functional_regression(results: TestResults):
    """Test core functionality regression"""
    print("\n🟠 PILLAR 1 — FUNCTIONAL REGRESSION (Happy Path)")
    
    admin_token = await get_admin_token()
    if not admin_token:
        results.assert_test(False, "Functional regression", "Could not get admin token")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test Activities CRUD
        print("\n--- Testing Activities CRUD ---")
        
        activity_data = {
            "name": f"Test Activity {uuid.uuid4().hex[:8]}",
            "description": "Test activity for regression testing",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "tim_peneliti": [
                {"nama": "Dr. Ahmad Rahman", "jabatan": "Ketua Tim"},
                {"nama": "Siti Nurhaliza", "jabatan": "Anggota"}
            ],
            "kasatker_nama": "Dr. Budi Santoso",
            "kasatker_nip": "196505151990031002",
            "kasatker_jabatan": "Kepala Satuan Kerja",
            "alamat_satker": "Jl. Pattimura No. 20 Jakarta",
            "nomor_berita_acara": "BA-001/TIM/2024",
            "kesimpulan": "Dari hasil penelitian ditemukan beberapa BMN tidak ditemukan"
        }
        
        response = await client.post(f"{BASE_URL}/inventory-activities", json=activity_data, headers=headers)
        results.assert_test(
            response.status_code == 200,
            "Create activity with Phase-2 fields",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        activity_id = None
        if response.status_code == 200:
            activity = response.json()
            activity_id = activity.get("id")
            results.test_data["test_activity_id"] = activity_id
            
            # Verify fields persisted
            response = await client.get(f"{BASE_URL}/inventory-activities/{activity_id}", headers=headers)
            results.assert_test(
                response.status_code == 200,
                "Get activity returns all fields",
                f"Expected 200, got {response.status_code}: {response.text}"
            )
            
            if response.status_code == 200:
                retrieved_activity = response.json()
                results.assert_test(
                    retrieved_activity.get("kasatker_nama") == "Dr. Budi Santoso",
                    "Activity kasatker_nama persisted correctly",
                    f"Expected 'Dr. Budi Santoso', got {retrieved_activity.get('kasatker_nama')}"
                )

        # Test Assets CRUD with OCC + version
        print("\n--- Testing Assets CRUD with OCC + version ---")
        
        if activity_id:
            asset_data = {
                "asset_name": "Test Laptop Dell",
                "asset_code": "3030103001",
                "NUP": f"NUP{random.randint(100000, 999999)}",
                "category": "Laptop Dell",
                "brand": "Dell",
                "model": "Latitude 5520",
                "serial_number": f"SN{uuid.uuid4().hex[:8]}",
                "purchase_date": "2023-01-15",
                "purchase_price": "15000000",
                "condition": "Baik",
                "location": "Ruang IT",
                "status": "Aktif",
                "activity_id": activity_id,
                "inventory_status": "Ditemukan",
                "stiker_status": "Sudah Terpasang",
                "stiker_ukuran": "Sedang",
                "koordinat_latitude": "-6.175110",
                "koordinat_longitude": "106.865036",
                "photos": [generate_small_base64_png()]
            }
            
            response = await client.post(f"{BASE_URL}/assets", json=asset_data, headers=headers)
            results.assert_test(
                response.status_code == 200,
                "Create asset with full field set",
                f"Expected 200, got {response.status_code}: {response.text}"
            )
            
            if response.status_code == 200:
                asset = response.json()
                asset_id = asset.get("id")
                results.test_data["test_asset_id"] = asset_id
                
                results.assert_test(
                    asset.get("version") == 1,
                    "Asset created with version=1",
                    f"Expected version=1, got {asset.get('version')}"
                )
                
                # Test list projection includes version
                response = await client.get(f"{BASE_URL}/assets?activity_id={activity_id}&limit=50", headers=headers)
                if response.status_code == 200:
                    assets_list = response.json()
                    assets = assets_list.get("assets", [])
                    if assets:
                        first_asset = assets[0]
                        results.assert_test(
                            "version" in first_asset,
                            "Assets list includes version field",
                            "Version field missing in list response"
                        )
                
                # Test OCC with PATCH
                if asset_id:
                    update_data = {
                        "asset_name": "Updated Test Laptop Dell",
                        "condition": "Sangat Baik"
                    }
                    
                    # Correct If-Match should succeed
                    headers_with_match = {**headers, "If-Match": "1"}
                    response = await client.patch(f"{BASE_URL}/assets/{asset_id}", json=update_data, headers=headers_with_match)
                    results.assert_test(
                        response.status_code == 200,
                        "PATCH with correct If-Match succeeds",
                        f"Expected 200, got {response.status_code}: {response.text}"
                    )
                    
                    if response.status_code == 200:
                        updated_asset = response.json()
                        results.assert_test(
                            updated_asset.get("version") == 2,
                            "Version incremented to 2 after PATCH",
                            f"Expected version=2, got {updated_asset.get('version')}"
                        )
                    
                    # Stale If-Match should return 409
                    headers_stale = {**headers, "If-Match": "1"}
                    response = await client.patch(f"{BASE_URL}/assets/{asset_id}", json=update_data, headers=headers_stale)
                    results.assert_test(
                        response.status_code == 409,
                        "PATCH with stale If-Match returns 409",
                        f"Expected 409, got {response.status_code}: {response.text}"
                    )
                    
                    if response.status_code == 409:
                        conflict_data = response.json()
                        detail = conflict_data.get("detail", {})
                        results.assert_test(
                            "current_version" in detail and "your_version" in detail,
                            "409 response includes version conflict details",
                            f"Detail: {detail}"
                        )

        # Test Idempotency
        print("\n--- Testing Idempotency ---")
        
        if activity_id:
            idempotent_asset_data = {
                "asset_name": "Idempotent Test Asset",
                "asset_code": "3030103002",
                "NUP": f"NUP{random.randint(100000, 999999)}",
                "category": "Laptop Dell",
                "activity_id": activity_id
            }
            
            idempotency_key = f"key-{uuid.uuid4().hex}"
            headers_with_key = {**headers, "Idempotency-Key": idempotency_key}
            
            # First request
            response1 = await client.post(f"{BASE_URL}/assets", json=idempotent_asset_data, headers=headers_with_key)
            results.assert_test(
                response1.status_code == 200,
                "First idempotent POST succeeds",
                f"Expected 200, got {response1.status_code}: {response1.text}"
            )
            
            if response1.status_code == 200:
                asset1 = response1.json()
                asset1_id = asset1.get("id")
                
                # Second request with same key
                response2 = await client.post(f"{BASE_URL}/assets", json=idempotent_asset_data, headers=headers_with_key)
                if response2.status_code == 200:
                    asset2 = response2.json()
                    asset2_id = asset2.get("id")
                    
                    results.assert_test(
                        asset1_id == asset2_id,
                        "Idempotent requests return same asset ID",
                        f"First ID: {asset1_id}, Second ID: {asset2_id}"
                    )

        # Test Atomic Lock race
        print("\n--- Testing Atomic Lock race ---")
        
        test_asset_id = results.test_data.get("test_asset_id")
        if test_asset_id:
            async def attempt_lock():
                async with httpx.AsyncClient(timeout=TIMEOUT) as lock_client:
                    response = await lock_client.post(f"{BASE_URL}/assets/lock", json={"asset_id": test_asset_id}, headers=headers)
                    return response.status_code, response.json() if response.status_code == 200 else None
            
            # Run 5 concurrent lock attempts
            tasks = [attempt_lock() for _ in range(5)]
            lock_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_locks = 0
            failed_locks = 0
            
            for result in lock_results:
                if isinstance(result, tuple):
                    status_code, data = result
                    if status_code == 200 and data and data.get("locked") == True:
                        successful_locks += 1
                    elif status_code == 200 and data and data.get("locked") == False:
                        failed_locks += 1
            
            results.assert_test(
                successful_locks == 1,
                "Exactly 1 lock succeeds from concurrent attempts",
                f"Expected 1 success, got {successful_locks}"
            )
            
            # Unlock for cleanup
            await client.post(f"{BASE_URL}/assets/unlock", json={"asset_id": test_asset_id}, headers=headers)

async def test_import_export_functionality(results: TestResults):
    """Test import/export functionality"""
    print("\n--- Testing Import/Export functionality ---")
    
    admin_token = await get_admin_token()
    if not admin_token:
        results.assert_test(False, "Import/Export test", "Could not get admin token")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    activity_id = results.test_data.get("test_activity_id")
    
    if not activity_id:
        results.assert_test(False, "Import/Export test", "No test activity available")
        return
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test CSV export
        response = await client.get(f"{BASE_URL}/export/csv?activity_id={activity_id}", headers=headers)
        results.assert_test(
            response.status_code == 200,
            "CSV export works",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            csv_content = response.text
            results.assert_test(
                "kelengkapan_dokumen" in csv_content and "stiker_status" in csv_content,
                "CSV contains required columns",
                "Missing kelengkapan_dokumen or stiker_status columns"
            )
        
        # Test XLSX export
        response = await client.get(f"{BASE_URL}/export/xlsx?activity_id={activity_id}", headers=headers)
        results.assert_test(
            response.status_code == 200,
            "XLSX export works",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            content = response.content
            results.assert_test(
                content.startswith(b'\x50\x4b'),
                "XLSX export has correct file signature",
                f"File starts with: {content[:4]}"
            )
        
        # Test PDF export
        response = await client.get(f"{BASE_URL}/export/pdf?activity_id={activity_id}", headers=headers)
        results.assert_test(
            response.status_code == 200,
            "PDF export works",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            content = response.content
            results.assert_test(
                content.startswith(b'%PDF'),
                "PDF export has correct file signature",
                f"File starts with: {content[:4]}"
            )

async def test_reports_functionality(results: TestResults):
    """Test reports and PDF generation"""
    print("\n--- Testing Reports functionality ---")
    
    admin_token = await get_admin_token()
    if not admin_token:
        results.assert_test(False, "Reports test", "Could not get admin token")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    activity_id = results.test_data.get("test_activity_id")
    
    if not activity_id:
        results.assert_test(False, "Reports test", "No test activity available")
        return
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Test rekapitulasi
        response = await client.get(f"{BASE_URL}/inventory-activities/{activity_id}/rekapitulasi", headers=headers)
        results.assert_test(
            response.status_code == 200,
            "Rekapitulasi endpoint works",
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        
        if response.status_code == 200:
            recap_data = response.json()
            results.assert_test(
                "total_bmn_diteliti" in recap_data,
                "Rekapitulasi contains totals",
                "Missing total_bmn_diteliti in response"
            )
        
        # Test PDF reports
        pdf_endpoints = [
            "berita-acara-pdf",
            "sptjm-pdf", 
            "surat-koreksi-pdf"
        ]
        
        for endpoint in pdf_endpoints:
            response = await client.get(f"{BASE_URL}/inventory-activities/{activity_id}/{endpoint}", headers=headers)
            results.assert_test(
                response.status_code == 200,
                f"{endpoint} works",
                f"Expected 200, got {response.status_code}: {response.text}"
            )
            
            if response.status_code == 200:
                content = response.content
                results.assert_test(
                    content.startswith(b'%PDF'),
                    f"{endpoint} returns valid PDF",
                    f"File starts with: {content[:4]}"
                )

async def cleanup_test_data(results: TestResults):
    """Clean up test data created during testing"""
    print("\n--- Cleaning up test data ---")
    
    admin_token = await get_admin_token()
    if not admin_token:
        print("⚠️ Could not get admin token for cleanup")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Clean up test activity (this will cascade delete assets)
        activity_id = results.test_data.get("test_activity_id")
        if activity_id:
            response = await client.delete(f"{BASE_URL}/inventory-activities/{activity_id}", headers=headers)
            if response.status_code == 200:
                print(f"✅ Cleaned up test activity {activity_id}")
            else:
                print(f"⚠️ Failed to clean up test activity {activity_id}: {response.status_code}")

async def main():
    """Main test execution"""
    print("🚀 Starting COMPREHENSIVE BACKEND TEST — AMAN Inventarisasi v2.1")
    print(f"Backend URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print("="*80)
    
    results = TestResults()
    
    try:
        # NEW FEATURE TESTS (HIGHEST PRIORITY)
        await test_new_registration_feature(results)
        await test_admin_activation_flow(results)
        
        # FUNCTIONAL REGRESSION
        await test_functional_regression(results)
        
        # ADDITIONAL FUNCTIONALITY TESTS
        await test_import_export_functionality(results)
        await test_reports_functionality(results)
        
    except Exception as e:
        print(f"❌ Test execution error: {str(e)}")
        results.errors.append(f"Test execution error: {str(e)}")
    
    finally:
        # Cleanup
        await cleanup_test_data(results)
        
        # Print final results
        results.print_summary()
        
        return results

if __name__ == "__main__":
    asyncio.run(main())