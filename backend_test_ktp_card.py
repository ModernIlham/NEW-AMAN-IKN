#!/usr/bin/env python3

"""
KTP Card PDF Generation Testing Suite
Tests the improved KTP card PDF generation endpoint following the review request specs
"""

import requests
import json
import os
import sys
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://asset-crud-auth.preview.emergentagent.com/api"

def log_test(test_name, success, details=""):
    """Log test results with clear formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"    Details: {details}")
    if not success:
        print(f"    Error: {details}")
    print()

def test_ktp_card_pdf_generation():
    """
    Test the improved KTP card PDF generation endpoint following review request steps:
    1. First login with testuser/test1234 to get auth token
    2. Create a test asset with full data
    3. Call GET /api/assets/{asset_id}/card with the created asset ID
    4. Verify response properties
    """
    print("🎯 Testing KTP Card PDF Generation - Following Review Request Steps...")
    
    try:
        # Step 1: Login with testuser/test1234 to get auth token
        print("Step 1: Logging in with testuser/test1234...")
        login_data = {
            "username": "testuser",
            "password": "test1234"
        }
        
        login_response = requests.post(f"{BACKEND_URL}/auth/login", json=login_data)
        if login_response.status_code != 200:
            log_test("Login with testuser/test1234", False, f"HTTP {login_response.status_code}: {login_response.text}")
            return False
            
        auth_data = login_response.json()
        auth_token = auth_data.get('access_token')
        user_info = auth_data.get('user', {})
        
        if not auth_token:
            log_test("Login with testuser/test1234", False, "No access token received")
            return False
            
        log_test("Login with testuser/test1234", True, f"User: {user_info.get('username')}, Role: {user_info.get('role')}")
        
        # Step 2: Create a test asset with full data
        print("Step 2: Creating test asset with full data...")
        
        # First get an activity to link the asset to
        activities_response = requests.get(f"{BACKEND_URL}/inventory-activities")
        if activities_response.status_code != 200:
            log_test("Get inventory activities", False, f"HTTP {activities_response.status_code}")
            return False
            
        activities = activities_response.json()
        activity_id = activities[0]['id'] if activities else None
        
        # Generate unique identifiers for this test
        timestamp = int(datetime.now().timestamp())
        
        asset_data = {
            "asset_code": f"303010{timestamp % 10000:04d}",
            "NUP": f"{timestamp % 100:03d}",
            "asset_name": "Test KTP Card Asset - Laptop Dell Precision",
            "category": "Elektronik & IT",
            "serial_number": f"DL{timestamp % 1000000:06d}",
            "brand": "Dell",
            "model": "Precision 5570",
            "condition": "Baik",
            "status": "Aktif",
            "department": "IT Development",
            "location": "Ruang Server - Lantai 3",
            "user": "Test User KTP Card",
            "purchase_date": "2024-01-15",
            "nomor_spm": f"{timestamp % 10000:05d}T/621001/2024",
            "nomor_kontrak": f"SP-{timestamp % 1000:03d}/PPK.I/OIKN/2024",
            "nomor_bukti_perolehan": f"BAST-{timestamp % 1000:03d}/PPK.I/OIKN/2024",
            "purchase_price": "25000000",
            "kode_register": f"{timestamp % 16**32:032X}",
            "notes": "Test asset for KTP card PDF generation testing",
            "activity_id": activity_id
        }
        
        create_response = requests.post(f"{BACKEND_URL}/assets", json=asset_data)
        if create_response.status_code != 200:
            log_test("Create test asset with full data", False, f"HTTP {create_response.status_code}: {create_response.text}")
            return False
            
        created_asset = create_response.json()
        asset_id = created_asset['id']
        
        log_test("Create test asset with full data", True, 
                f"Asset ID: {asset_id}, Code: {asset_data['asset_code']}, NUP: {asset_data['NUP']}")
        
        # Step 3: Call GET /api/assets/{asset_id}/card with the created asset ID
        print("Step 3: Calling GET /api/assets/{asset_id}/card...")
        
        card_response = requests.get(f"{BACKEND_URL}/assets/{asset_id}/card")
        
        # Step 4: Verify response properties
        print("Step 4: Verifying response properties...")
        
        success_count = 0
        total_checks = 4
        
        # Check 1: Response is HTTP 200
        if card_response.status_code == 200:
            log_test("Response is HTTP 200", True, f"Status code: {card_response.status_code}")
            success_count += 1
        else:
            log_test("Response is HTTP 200", False, f"Expected 200, got {card_response.status_code}: {card_response.text}")
        
        # Check 2: Response content-type is application/pdf
        content_type = card_response.headers.get('content-type', '')
        if 'application/pdf' in content_type:
            log_test("Response content-type is application/pdf", True, f"Content-Type: {content_type}")
            success_count += 1
        else:
            log_test("Response content-type is application/pdf", False, f"Expected application/pdf, got: {content_type}")
        
        # Check 3: Response body starts with %PDF signature
        pdf_content = card_response.content
        if pdf_content.startswith(b'%PDF'):
            log_test("Response body starts with %PDF signature", True, f"PDF signature detected: {pdf_content[:8]}")
            success_count += 1
        else:
            log_test("Response body starts with %PDF signature", False, f"Expected %PDF, got: {pdf_content[:20]}")
        
        # Check 4: Response has reasonable size (should be several KB)
        pdf_size = len(pdf_content)
        if pdf_size > 1000:  # At least 1KB
            log_test("Response has reasonable size (several KB)", True, f"PDF size: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
            success_count += 1
        else:
            log_test("Response has reasonable size (several KB)", False, f"PDF too small: {pdf_size} bytes")
        
        # Additional verification: Check Content-Disposition header
        content_disposition = card_response.headers.get('content-disposition', '')
        if 'attachment' in content_disposition and 'kartu_inventaris_' in content_disposition:
            log_test("Content-Disposition header correct", True, f"Header: {content_disposition}")
        else:
            log_test("Content-Disposition header correct", False, f"Unexpected header: {content_disposition}")
        
        # Cleanup: Delete the test asset
        print("Cleanup: Deleting test asset...")
        delete_response = requests.delete(f"{BACKEND_URL}/assets/{asset_id}")
        if delete_response.status_code == 200:
            log_test("Cleanup test asset", True, "Asset deleted successfully")
        else:
            log_test("Cleanup test asset", False, f"Delete failed: HTTP {delete_response.status_code}")
        
        # Overall result
        if success_count >= total_checks:
            log_test("KTP Card PDF Generation - OVERALL", True, f"All {success_count}/{total_checks} core checks passed")
            return True
        else:
            log_test("KTP Card PDF Generation - OVERALL", False, f"Only {success_count}/{total_checks} core checks passed")
            return False
            
    except Exception as e:
        log_test("KTP Card PDF Generation Test", False, f"Exception: {str(e)}")
        return False

def test_card_generation_edge_cases():
    """Test card generation with various edge cases and data scenarios"""
    print("🧪 Testing Card Generation Edge Cases...")
    
    try:
        # Test 1: Asset with minimal data
        print("Testing minimal data asset...")
        
        # Get activity for testing
        activities_response = requests.get(f"{BACKEND_URL}/inventory-activities")
        activities = activities_response.json()
        activity_id = activities[0]['id'] if activities else None
        
        timestamp = int(datetime.now().timestamp())
        
        minimal_asset_data = {
            "asset_code": f"505050{timestamp % 10000:04d}",
            "NUP": "MIN",
            "asset_name": "Minimal Test Asset",
            "category": "Lainnya",
            "activity_id": activity_id
        }
        
        create_response = requests.post(f"{BACKEND_URL}/assets", json=minimal_asset_data)
        if create_response.status_code == 200:
            asset = create_response.json()
            asset_id = asset['id']
            
            # Test card generation
            card_response = requests.get(f"{BACKEND_URL}/assets/{asset_id}/card")
            
            if card_response.status_code == 200 and card_response.content.startswith(b'%PDF'):
                log_test("Minimal data asset card generation", True, f"PDF generated: {len(card_response.content)} bytes")
            else:
                log_test("Minimal data asset card generation", False, f"Failed: HTTP {card_response.status_code}")
            
            # Cleanup
            requests.delete(f"{BACKEND_URL}/assets/{asset_id}")
        else:
            log_test("Create minimal asset for testing", False, f"HTTP {create_response.status_code}")
        
        # Test 2: Non-existent asset ID
        print("Testing non-existent asset ID...")
        fake_id = "00000000-0000-0000-0000-000000000000"
        card_response = requests.get(f"{BACKEND_URL}/assets/{fake_id}/card")
        
        if card_response.status_code == 404:
            log_test("Non-existent asset returns 404", True, "Correctly returns 404 for missing asset")
        else:
            log_test("Non-existent asset returns 404", False, f"Expected 404, got {card_response.status_code}")
        
        return True
        
    except Exception as e:
        log_test("Card generation edge cases", False, f"Exception: {str(e)}")
        return False

def test_card_design_validation():
    """Test specific aspects of the card design implementation"""
    print("🎨 Testing Card Design Implementation...")
    
    try:
        # Create a comprehensive test asset
        activities_response = requests.get(f"{BACKEND_URL}/inventory-activities")
        activities = activities_response.json()
        activity_id = activities[0]['id'] if activities else None
        
        timestamp = int(datetime.now().timestamp())
        
        comprehensive_asset = {
            "asset_code": f"202420{timestamp % 10000:04d}",
            "NUP": "DESIGN",
            "asset_name": "Comprehensive Design Test Asset - Very Long Name That Should Be Handled Properly",
            "category": "Elektronik & IT",
            "serial_number": "DESIGN123456789",
            "brand": "TestBrand",
            "model": "TestModel Pro Max Ultra",
            "condition": "Baik",
            "status": "Aktif",
            "department": "Design Test Department",
            "location": "Test Location - Building A Floor 5 Room 501",
            "user": "Design Test User Full Name",
            "purchase_date": "2024-02-15",
            "nomor_spm": f"{timestamp % 10000:05d}D/DESIGN/2024",
            "nomor_kontrak": "DESIGN-CONTRACT-2024-001/VERY/LONG/PATH",
            "nomor_bukti_perolehan": "DESIGN-BAST-2024-001/ACQUISITION/PROOF",
            "purchase_price": "99999999",
            "kode_register": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
            "notes": "This is a comprehensive test with very detailed notes to test text handling and layout in the card design",
            "activity_id": activity_id
        }
        
        create_response = requests.post(f"{BACKEND_URL}/assets", json=comprehensive_asset)
        if create_response.status_code != 200:
            log_test("Create comprehensive test asset", False, f"HTTP {create_response.status_code}")
            return False
            
        asset = create_response.json()
        asset_id = asset['id']
        log_test("Create comprehensive test asset", True, f"Asset ID: {asset_id}")
        
        # Generate card PDF
        card_response = requests.get(f"{BACKEND_URL}/assets/{asset_id}/card")
        
        if card_response.status_code == 200:
            pdf_content = card_response.content
            pdf_size = len(pdf_content)
            
            # Validate PDF structure
            if pdf_content.startswith(b'%PDF'):
                # Check for reasonable size (LaTeX-inspired design should be substantial)
                if pdf_size > 2000:  # At least 2KB for comprehensive design
                    log_test("Card design PDF generation", True, 
                            f"Generated comprehensive card: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
                    
                    # Check Content-Disposition includes asset code
                    content_disposition = card_response.headers.get('content-disposition', '')
                    expected_filename = f"kartu_inventaris_{comprehensive_asset['asset_code']}.pdf"
                    if expected_filename in content_disposition:
                        log_test("Filename includes asset code", True, f"Correct filename in header")
                    else:
                        log_test("Filename includes asset code", False, f"Expected {expected_filename} in {content_disposition}")
                    
                else:
                    log_test("Card design PDF generation", False, f"PDF too small for comprehensive data: {pdf_size} bytes")
            else:
                log_test("Card design PDF generation", False, "Not a valid PDF")
        else:
            log_test("Card design PDF generation", False, f"HTTP {card_response.status_code}: {card_response.text}")
        
        # Cleanup
        delete_response = requests.delete(f"{BACKEND_URL}/assets/{asset_id}")
        log_test("Cleanup comprehensive asset", delete_response.status_code == 200, "")
        
        return True
        
    except Exception as e:
        log_test("Card design validation", False, f"Exception: {str(e)}")
        return False

def main():
    """Run KTP Card PDF generation tests"""
    print("🚀 Starting KTP Card PDF Generation Testing Suite")
    print(f"Testing against: {BACKEND_URL}")
    print("Focus: GET /api/assets/{asset_id}/card endpoint")
    print("=" * 70)
    
    results = {
        'ktp_card_pdf_generation': False,
        'card_edge_cases': False,
        'card_design_validation': False
    }
    
    # Main test: KTP Card PDF Generation (following review request steps)
    results['ktp_card_pdf_generation'] = test_ktp_card_pdf_generation()
    
    # Additional tests
    results['card_edge_cases'] = test_card_generation_edge_cases()
    results['card_design_validation'] = test_card_design_validation()
    
    # Summary
    print("=" * 70)
    print("🎯 FINAL TEST RESULTS:")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        display_name = test_name.replace('_', ' ').title()
        print(f"{status} | {display_name}")
    
    print("=" * 70)
    print(f"📊 Summary: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    # Specific focus result
    main_test_passed = results['ktp_card_pdf_generation']
    focus_status = "✅ SUCCESS" if main_test_passed else "❌ FAILED"
    print(f"\n🎯 FOCUS TEST RESULT: {focus_status}")
    print(f"   GET /api/assets/{{asset_id}}/card endpoint test: {focus_status}")
    
    return results

if __name__ == "__main__":
    main()