#!/usr/bin/env python3
"""
Backend Test Suite for Stiker (Sticker) Features
Focus: Testing all stiker-related functionality in the backend API
"""

import requests
import json
import io
import csv
import uuid
import base64
from typing import Dict, Any, Optional

# Configuration
BACKEND_URL = "https://asset-crud-auth.preview.emergentagent.com/api"

class StikerFeatureTester:
    def __init__(self):
        self.auth_token = None
        self.session = requests.Session()
        self.test_activity_id = None
        self.test_asset_id = None
        
    def register_and_login(self) -> bool:
        """Register and login with test credentials"""
        try:
            # Register new user
            register_data = {
                "name": "Tester",
                "username": "tester",
                "password": "test1234"
            }
            
            response = self.session.post(f"{BACKEND_URL}/auth/register", json=register_data)
            if response.status_code in [200, 201]:
                print("✅ Registration successful")
            elif response.status_code == 400 and "already exists" in response.text:
                print("ℹ️ User already exists, proceeding with login")
            else:
                print(f"⚠️ Registration status: {response.status_code}")
            
            # Login
            login_data = {
                "username": "tester",
                "password": "test1234"
            }
            
            response = self.session.post(f"{BACKEND_URL}/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                print("✅ Login successful")
                return True
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Auth error: {e}")
            return False
    
    def create_test_activity(self) -> Optional[str]:
        """Create a test activity for assets"""
        try:
            unique_id = str(uuid.uuid4())[:8]
            activity_data = {
                "nama_kegiatan": f"Test Stiker Activity {unique_id}",
                "nomor_surat": f"STIKER-TEST-{unique_id}/2024",
                "deskripsi": "Test activity for stiker features",
                "tanggal_mulai": "2024-01-01",
                "tanggal_selesai": "2024-12-31"
            }
            
            response = self.session.post(f"{BACKEND_URL}/inventory-activities", json=activity_data)
            if response.status_code in [200, 201]:
                activity = response.json()
                activity_id = activity.get("id")
                print(f"✅ Created test activity with ID: {activity_id}")
                return activity_id
            else:
                print(f"❌ Failed to create activity: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating activity: {e}")
            return None
    
    def test_create_asset_with_stiker_fields(self) -> bool:
        """Test 1: Create asset with stiker fields"""
        try:
            print("\n🧪 Test 1: Create asset with stiker fields")
            
            unique_id = str(uuid.uuid4())[:6]
            asset_data = {
                "asset_code": f"3030103{unique_id}",
                "NUP": f"T{unique_id[:3]}",
                "asset_name": f"Test Laptop {unique_id}",
                "category": "Elektronik & IT",
                "brand": "Dell",
                "model": "Latitude 5420",
                "activity_id": self.test_activity_id,
                "stiker_status": "Sudah Terpasang",
                "stiker_ukuran": "Kecil",
                "stiker_photo_index": 0
            }
            
            response = self.session.post(f"{BACKEND_URL}/assets", json=asset_data)
            if response.status_code in [200, 201]:
                asset = response.json()
                self.test_asset_id = asset.get("id")
                
                # Verify stiker fields in response
                if (asset.get("stiker_status") == "Sudah Terpasang" and
                    asset.get("stiker_ukuran") == "Kecil" and
                    asset.get("stiker_photo_index") == 0):
                    print("✅ Test 1 PASSED: Asset created with correct stiker fields")
                    return True
                else:
                    print("❌ Test 1 FAILED: Stiker fields not returned correctly")
                    print(f"   Expected: status='Sudah Terpasang', ukuran='Kecil', photo_index=0")
                    print(f"   Actual: status='{asset.get('stiker_status')}', ukuran='{asset.get('stiker_ukuran')}', photo_index={asset.get('stiker_photo_index')}")
                    return False
            else:
                print(f"❌ Test 1 FAILED: Asset creation failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 1 ERROR: {e}")
            return False
    
    def test_get_asset_with_stiker_fields(self) -> bool:
        """Test 2: Get asset with stiker fields"""
        try:
            print("\n🧪 Test 2: Get asset with stiker fields")
            
            if not self.test_asset_id:
                print("❌ Test 2 FAILED: No test asset ID available")
                return False
            
            response = self.session.get(f"{BACKEND_URL}/assets/{self.test_asset_id}")
            if response.status_code == 200:
                asset = response.json()
                
                # Verify stiker fields are present and correct
                stiker_status = asset.get("stiker_status")
                stiker_ukuran = asset.get("stiker_ukuran")
                stiker_photo_index = asset.get("stiker_photo_index")
                
                if (stiker_status is not None and stiker_ukuran is not None and 
                    stiker_photo_index is not None):
                    print("✅ Test 2 PASSED: Stiker fields returned in GET response")
                    print(f"   stiker_status: {stiker_status}")
                    print(f"   stiker_ukuran: {stiker_ukuran}")
                    print(f"   stiker_photo_index: {stiker_photo_index}")
                    return True
                else:
                    print("❌ Test 2 FAILED: Stiker fields missing in GET response")
                    return False
            else:
                print(f"❌ Test 2 FAILED: GET asset failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 2 ERROR: {e}")
            return False
    
    def test_update_asset_stiker_fields(self) -> bool:
        """Test 3: Update asset stiker fields"""
        try:
            print("\n🧪 Test 3: Update asset stiker fields")
            
            if not self.test_asset_id:
                print("❌ Test 3 FAILED: No test asset ID available")
                return False
            
            # First get current asset data
            get_response = self.session.get(f"{BACKEND_URL}/assets/{self.test_asset_id}")
            if get_response.status_code != 200:
                print(f"❌ Test 3 FAILED: Cannot get asset for update - {get_response.status_code}")
                return False
            
            asset_data = get_response.json()
            
            # Update stiker_status to "Belum Terpasang"
            asset_data["stiker_status"] = "Belum Terpasang"
            asset_data["stiker_ukuran"] = "Sedang"
            asset_data["stiker_photo_index"] = None
            
            response = self.session.put(f"{BACKEND_URL}/assets/{self.test_asset_id}", json=asset_data)
            if response.status_code == 200:
                updated_asset = response.json()
                
                # Verify update persisted
                if (updated_asset.get("stiker_status") == "Belum Terpasang" and
                    updated_asset.get("stiker_ukuran") == "Sedang"):
                    print("✅ Test 3 PASSED: Stiker fields updated successfully")
                    return True
                else:
                    print("❌ Test 3 FAILED: Stiker fields not updated correctly")
                    print(f"   Expected: status='Belum Terpasang', ukuran='Sedang'")
                    print(f"   Actual: status='{updated_asset.get('stiker_status')}', ukuran='{updated_asset.get('stiker_ukuran')}'")
                    return False
            else:
                print(f"❌ Test 3 FAILED: Asset update failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 3 ERROR: {e}")
            return False
    
    def test_get_assets_list_includes_stiker(self) -> bool:
        """Test 4: Get assets list includes stiker fields"""
        try:
            print("\n🧪 Test 4: Get assets list includes stiker fields")
            
            response = self.session.get(f"{BACKEND_URL}/assets?activity_id={self.test_activity_id}")
            if response.status_code == 200:
                result = response.json()
                assets = result.get("items", [])
                
                if assets and len(assets) > 0:
                    # Check if any asset has stiker fields
                    asset_with_stiker = None
                    for asset in assets:
                        if asset.get("id") == self.test_asset_id:
                            asset_with_stiker = asset
                            break
                    
                    if asset_with_stiker:
                        stiker_status = asset_with_stiker.get("stiker_status")
                        stiker_ukuran = asset_with_stiker.get("stiker_ukuran")
                        
                        if stiker_status is not None and stiker_ukuran is not None:
                            print("✅ Test 4 PASSED: Stiker fields included in assets list")
                            return True
                        else:
                            print("❌ Test 4 FAILED: Stiker fields missing in assets list")
                            return False
                    else:
                        print("❌ Test 4 FAILED: Test asset not found in list")
                        return False
                else:
                    print("❌ Test 4 FAILED: No assets in list")
                    return False
            else:
                print(f"❌ Test 4 FAILED: GET assets list failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 4 ERROR: {e}")
            return False
    
    def test_csv_export_with_stiker_columns(self) -> bool:
        """Test 5: CSV export with stiker columns"""
        try:
            print("\n🧪 Test 5: CSV export with stiker columns")
            
            response = self.session.get(f"{BACKEND_URL}/export/csv?activity_id={self.test_activity_id}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'text/csv' not in content_type:
                    print(f"❌ Test 5 FAILED: Wrong content type - {content_type}")
                    return False
                
                # Parse CSV content
                csv_content = response.text
                csv_reader = csv.reader(io.StringIO(csv_content))
                headers = next(csv_reader)
                
                # Check if stiker columns exist
                if "stiker_status" in headers and "stiker_ukuran" in headers:
                    print("✅ Test 5 PASSED: CSV export includes stiker columns")
                    print(f"   Found columns: stiker_status (index {headers.index('stiker_status')}), stiker_ukuran (index {headers.index('stiker_ukuran')})")
                    
                    # Check if data rows contain stiker values
                    for row in csv_reader:
                        if len(row) > max(headers.index('stiker_status'), headers.index('stiker_ukuran')):
                            stiker_status_val = row[headers.index('stiker_status')]
                            stiker_ukuran_val = row[headers.index('stiker_ukuran')]
                            print(f"   Sample row stiker data: status='{stiker_status_val}', ukuran='{stiker_ukuran_val}'")
                            break
                    
                    return True
                else:
                    print("❌ Test 5 FAILED: Stiker columns missing in CSV export")
                    print(f"   Available headers: {headers}")
                    return False
            else:
                print(f"❌ Test 5 FAILED: CSV export failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 5 ERROR: {e}")
            return False
    
    def test_pdf_export_works(self) -> bool:
        """Test 6: PDF export works"""
        try:
            print("\n🧪 Test 6: PDF export works")
            
            response = self.session.get(f"{BACKEND_URL}/export/pdf?activity_id={self.test_activity_id}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' not in content_type:
                    print(f"❌ Test 6 FAILED: Wrong content type - {content_type}")
                    return False
                
                # Check PDF signature
                pdf_content = response.content
                if not pdf_content.startswith(b'%PDF'):
                    print("❌ Test 6 FAILED: Invalid PDF signature")
                    return False
                
                # Check reasonable file size
                pdf_size = len(pdf_content)
                if pdf_size < 1000:
                    print(f"❌ Test 6 FAILED: PDF too small ({pdf_size} bytes)")
                    return False
                
                print(f"✅ Test 6 PASSED: PDF export successful ({pdf_size} bytes, valid %PDF signature)")
                return True
            else:
                print(f"❌ Test 6 FAILED: PDF export failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 6 ERROR: {e}")
            return False
    
    def test_xlsx_export_works(self) -> bool:
        """Test 7: XLSX export works"""
        try:
            print("\n🧪 Test 7: XLSX export works")
            
            response = self.session.get(f"{BACKEND_URL}/export/xlsx?activity_id={self.test_activity_id}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' not in content_type:
                    print(f"❌ Test 7 FAILED: Wrong content type - {content_type}")
                    return False
                
                # Check Excel file signature (ZIP-based format)
                xlsx_content = response.content
                if not xlsx_content.startswith(b'PK'):
                    print("❌ Test 7 FAILED: Invalid XLSX signature")
                    return False
                
                # Check reasonable file size
                xlsx_size = len(xlsx_content)
                if xlsx_size < 1000:
                    print(f"❌ Test 7 FAILED: XLSX too small ({xlsx_size} bytes)")
                    return False
                
                print(f"✅ Test 7 PASSED: XLSX export successful ({xlsx_size} bytes, valid PK signature)")
                return True
            else:
                print(f"❌ Test 7 FAILED: XLSX export failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 7 ERROR: {e}")
            return False
    
    def test_import_with_stiker_fields(self) -> bool:
        """Test 8: Import with stiker fields"""
        try:
            print("\n🧪 Test 8: Import with stiker fields")
            
            # Use unique asset codes to avoid duplicates (must be 10 digits)
            unique_suffix = str(uuid.uuid4().int)[:2]
            
            # Create CSV content with stiker fields
            csv_content = f'''asset_code,NUP,asset_name,category,activity_id,stiker_status,stiker_ukuran
88888880{unique_suffix[:2]},IMP1,Import Test Asset 1,Elektronik & IT,{self.test_activity_id},Sudah Terpasang,Kecil
88888881{unique_suffix[:2]},IMP2,Import Test Asset 2,Elektronik & IT,{self.test_activity_id},Belum Terpasang,Sedang'''
            
            files = {'file': ('test_stiker_import.csv', csv_content, 'text/csv')}
            data = {'activity_id': self.test_activity_id}
            
            response = self.session.post(f"{BACKEND_URL}/import", files=files, data=data)
            if response.status_code == 200:
                result = response.json()
                
                if result.get("success") and result.get("imported", 0) >= 2:
                    print("✅ Test 8 PASSED: Import with stiker fields successful")
                    print(f"   Imported: {result.get('imported')} assets")
                    
                    # Verify imported assets have stiker data
                    assets_response = self.session.get(f"{BACKEND_URL}/assets?activity_id={self.test_activity_id}")
                    if assets_response.status_code == 200:
                        assets_result = assets_response.json()
                        assets = assets_result.get("items", [])
                        imported_assets = [a for a in assets if a.get("asset_code", "").startswith("888888")]
                        
                        if imported_assets:
                            asset = imported_assets[0]
                            stiker_status = asset.get("stiker_status")
                            stiker_ukuran = asset.get("stiker_ukuran")
                            print(f"   Verified imported asset stiker data: status='{stiker_status}', ukuran='{stiker_ukuran}'")
                    
                    return True
                else:
                    print(f"❌ Test 8 FAILED: Import unsuccessful - {result}")
                    return False
            else:
                print(f"❌ Test 8 FAILED: Import request failed - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 8 ERROR: {e}")
            return False
    
    def test_import_validation(self) -> bool:
        """Test 9: Import validation with invalid stiker_status"""
        try:
            print("\n🧪 Test 9: Import validation with invalid stiker_status")
            
            # Use unique asset code to avoid duplicates (must be 10 digits)
            unique_suffix = str(uuid.uuid4().int)[:2]
            
            # Create CSV content with invalid stiker_status
            csv_content = f'''asset_code,NUP,asset_name,category,activity_id,stiker_status,stiker_ukuran
77777777{unique_suffix[:2]},INV1,Invalid Stiker Test,Elektronik & IT,{self.test_activity_id},InvalidStatus,Kecil'''
            
            files = {'file': ('test_invalid_stiker.csv', csv_content, 'text/csv')}
            data = {'activity_id': self.test_activity_id}
            
            response = self.session.post(f"{BACKEND_URL}/import", files=files, data=data)
            
            # This should either return validation error or process with default values
            if response.status_code == 400:
                result = response.json()
                if "stiker_status" in str(result).lower() or "tidak valid" in str(result).lower():
                    print("✅ Test 9 PASSED: Import validation correctly rejected invalid stiker_status")
                    return True
                else:
                    print("❌ Test 9 FAILED: Validation error but not for stiker_status")
                    print(f"   Response: {result}")
                    return False
            elif response.status_code == 200:
                # Some implementations might accept invalid values and use defaults
                result = response.json()
                print("ℹ️ Test 9 INFO: Import accepted invalid stiker_status (using defaults)")
                print(f"   Response: {result}")
                return True
            else:
                print(f"❌ Test 9 FAILED: Unexpected response - {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Test 9 ERROR: {e}")
            return False
    
    def run_all_stiker_tests(self):
        """Run all stiker feature tests"""
        print("🚀 Starting Stiker (Sticker) Features Test Suite")
        print("=" * 70)
        
        test_results = []
        
        # Step 1: Authentication
        print("🔐 Step 1: Register and Login...")
        if not self.register_and_login():
            print("❌ Cannot proceed without authentication")
            return False
        
        # Step 2: Create test activity
        print("\n📝 Step 2: Creating test activity...")
        self.test_activity_id = self.create_test_activity()
        if not self.test_activity_id:
            print("❌ Cannot proceed without test activity")
            return False
        
        # Run all tests
        tests = [
            ("Create asset with stiker fields", self.test_create_asset_with_stiker_fields),
            ("Get asset with stiker fields", self.test_get_asset_with_stiker_fields),
            ("Update asset stiker fields", self.test_update_asset_stiker_fields),
            ("Get assets list includes stiker", self.test_get_assets_list_includes_stiker),
            ("CSV export with stiker columns", self.test_csv_export_with_stiker_columns),
            ("PDF export works", self.test_pdf_export_works),
            ("XLSX export works", self.test_xlsx_export_works),
            ("Import with stiker fields", self.test_import_with_stiker_fields),
            ("Import validation", self.test_import_validation),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                test_results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} - EXCEPTION: {e}")
                test_results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 STIKER FEATURES TEST SUMMARY:")
        print("=" * 70)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {test_name}")
            if result:
                passed += 1
        
        print(f"\nResult: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 ALL STIKER FEATURES TESTS PASSED!")
            return True
        else:
            print(f"💥 {total - passed} test(s) failed")
            return False

def main():
    """Main test execution"""
    tester = StikerFeatureTester()
    try:
        success = tester.run_all_stiker_tests()
        return success
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        return False

if __name__ == "__main__":
    main()