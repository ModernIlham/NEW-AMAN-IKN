#!/usr/bin/env python3
"""
Backend Testing Script for New Features
Test 1: Import validation - Kode Aset matches Category Description
Test 2: Export CSV/Excel with Document Checklist  
Test 3: Bulk delete assets endpoint
Test 4: Document file endpoint

Based on review_request requirements
"""

import requests
import json
import csv
import io
import sys
import time
import base64
from typing import Dict, Any, Optional

# Backend URL from environment
BACKEND_URL = "https://asset-crud-auth.preview.emergentagent.com/api"

class NewFeaturesTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.test_results = {
            "test1_import_validation": False,
            "test2_export_document_checklist": False, 
            "test3_bulk_delete": False,
            "test4_document_file_endpoint": False
        }
        # Store created data for cleanup
        self.created_categories = []
        self.created_activities = []
        self.created_assets = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def register_and_login(self) -> bool:
        """Register test user and login"""
        try:
            # Register new user
            register_data = {
                "name": "Test User Feature",
                "username": "testfeatures", 
                "password": "test123"
            }
            
            self.log("Registering test user...")
            response = self.session.post(f"{BACKEND_URL}/auth/register", json=register_data)
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.user_id = data.get("user", {}).get("id")
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.log("✅ Registration successful")
                return True
            elif response.status_code == 400 and "sudah digunakan" in response.text:
                # User exists, try login
                self.log("User exists, trying login...")
                login_data = {"username": "testfeatures", "password": "test123"}
                response = self.session.post(f"{BACKEND_URL}/auth/login", json=login_data)
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.user_id = data.get("user", {}).get("id")
                    self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                    self.log("✅ Login successful")
                    return True
                else:
                    self.log(f"❌ Login failed: {response.status_code} - {response.text}", "ERROR")
                    return False
            else:
                self.log(f"❌ Registration failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Auth error: {e}", "ERROR")
            return False

    def create_category(self, kode_aset: str, label: str) -> bool:
        """Create category with specific kode_aset and label"""
        try:
            category_data = {
                "kode_aset": kode_aset,
                "label": label
            }
            
            self.log(f"Creating category: {kode_aset} - {label}")
            response = self.session.post(f"{BACKEND_URL}/categories", json=category_data)
            
            if response.status_code == 200:
                data = response.json()
                self.created_categories.append(data.get("id"))
                self.log(f"✅ Category created: {kode_aset} - {label}")
                return True
            else:
                self.log(f"❌ Category creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Category creation error: {e}", "ERROR")
            return False

    def create_activity(self, nomor_surat: str, nama_kegiatan: str) -> Optional[str]:
        """Create inventory activity and return ID"""
        try:
            activity_data = {
                "nomor_surat": nomor_surat,
                "nama_kegiatan": nama_kegiatan,
                "tanggal_mulai": "2024-01-01",
                "tanggal_selesai": "2024-12-31",
                "status": "Aktif",
                "keterangan": f"Test activity for {nama_kegiatan}"
            }
            
            self.log(f"Creating activity: {nama_kegiatan}")
            response = self.session.post(f"{BACKEND_URL}/inventory-activities", json=activity_data)
            
            if response.status_code == 200:
                data = response.json()
                activity_id = data.get("id")
                self.created_activities.append(activity_id)
                self.log(f"✅ Activity created with ID: {activity_id}")
                return activity_id
            else:
                self.log(f"❌ Activity creation failed: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Activity creation error: {e}", "ERROR")
            return None

    def create_asset_with_documents(self, activity_id: str) -> Optional[str]:
        """Create an asset with document_checklist containing photos and notes"""
        try:
            # Create a simple base64 image (1x1 pixel red)
            test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            
            asset_data = {
                "asset_code": "3030103001",
                "NUP": "1",
                "asset_name": "Test Asset with Documents",
                "category": "Laptop Dell",
                "brand": "Dell",
                "model": "Test Model",
                "location": "Test Location",
                "condition": "Baik",
                "status": "Aktif",
                "activity_id": activity_id,
                "document_checklist": [
                    {
                        "name": "KTP",
                        "checked": True,
                        "notes": "Sudah lengkap",
                        "photos": [test_image_base64],
                        "documents": []
                    },
                    {
                        "name": "NPWP",
                        "checked": False,
                        "notes": "Belum ada",
                        "photos": [],
                        "documents": []
                    }
                ]
            }
            
            self.log("Creating asset with document checklist...")
            response = self.session.post(f"{BACKEND_URL}/assets", json=asset_data)
            
            if response.status_code == 200:
                data = response.json()
                asset_id = data.get("id")
                self.created_assets.append(asset_id)
                self.log(f"✅ Asset created with ID: {asset_id}")
                return asset_id
            else:
                self.log(f"❌ Asset creation failed: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Asset creation error: {e}", "ERROR")
            return None

    def import_csv_test(self, csv_content: str, activity_id: str) -> Dict[str, Any]:
        """Import CSV to specific activity"""
        try:
            url = f"{BACKEND_URL}/import?activity_id={activity_id}"
            
            files = {
                'file': ('test_import.csv', io.StringIO(csv_content), 'text/csv')
            }
            
            self.log("Importing CSV...")
            response = self.session.post(url, files=files)
            
            return {
                "status_code": response.status_code,
                "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
        except Exception as e:
            self.log(f"❌ Import error: {e}", "ERROR")
            return {"status_code": 0, "response": str(e)}

    def test_1_import_validation(self) -> bool:
        """Test 1: Import validation - Kode Aset matches Category Description"""
        self.log("\n=== TEST 1: Import Validation - Kode Aset matches Category Description ===")
        
        try:
            # Step 1: Create category with kode_aset "3030103001" and label "Laptop Dell"
            if not self.create_category("3030103001", "Laptop Dell"):
                return False
            
            # Step 2: Create activity for testing
            activity_id = self.create_activity("TEST/001/2025", "Test Kegiatan")
            if not activity_id:
                return False
            
            # Step 3: Try to import CSV with asset_code "3030103001" but category "Wrong Category" - should fail
            wrong_csv = """asset_code,NUP,asset_name,category,brand,model,location,condition,status
3030103001,1,Test Laptop,Wrong Category,Dell,Latitude,Office,Baik,Aktif"""
            
            self.log("Testing import with wrong category...")
            result = self.import_csv_test(wrong_csv, activity_id)
            
            if result["status_code"] == 200:
                response_data = result["response"]
                if not response_data.get("success") and "error" in str(response_data).lower():
                    self.log("✅ Import correctly rejected with wrong category")
                elif response_data.get("errors") and any("deskripsi" in str(err).lower() for err in response_data.get("errors", [])):
                    self.log("✅ Import correctly rejected with category validation error")
                else:
                    self.log(f"❌ Expected validation error, got: {response_data}", "ERROR")
                    return False
            else:
                self.log(f"❌ Expected validation response, got status {result['status_code']}: {result['response']}", "ERROR")
                return False
            
            # Step 4: Try to import with correct category "Laptop Dell" - should succeed
            correct_csv = """asset_code,NUP,asset_name,category,brand,model,location,condition,status
3030103001,2,Test Laptop,Laptop Dell,Dell,Latitude,Office,Baik,Aktif"""
            
            self.log("Testing import with correct category...")
            result = self.import_csv_test(correct_csv, activity_id)
            
            if result["status_code"] == 200 and result["response"].get("success"):
                self.log("✅ Import succeeded with correct category")
            else:
                self.log(f"❌ Import failed with correct category: {result['response']}", "ERROR")
                return False
            
            # Step 5: Create an asset manually with asset_code "3030103001", NUP "1"
            manual_asset_data = {
                "asset_code": "3030103001",
                "NUP": "1",
                "asset_name": "Manual Test Asset",
                "category": "Laptop Dell",
                "brand": "Dell",
                "activity_id": activity_id
            }
            
            self.log("Creating manual asset...")
            response = self.session.post(f"{BACKEND_URL}/assets", json=manual_asset_data)
            
            if response.status_code == 200:
                manual_asset = response.json()
                self.created_assets.append(manual_asset.get("id"))
                self.log("✅ Manual asset created")
            else:
                self.log(f"❌ Manual asset creation failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Step 6: Try to import again with same asset_code "3030103001", NUP "1" - should fail with duplicate error
            duplicate_csv = """asset_code,NUP,asset_name,category,brand,model,location,condition,status
3030103001,1,Duplicate Laptop,Laptop Dell,Dell,Latitude,Office,Baik,Aktif"""
            
            self.log("Testing import with duplicate asset...")
            result = self.import_csv_test(duplicate_csv, activity_id)
            
            if result["status_code"] == 200:
                response_data = result["response"]
                if not response_data.get("success") and ("duplikat" in str(response_data).lower() or "duplicate" in str(response_data).lower() or "sudah digunakan" in str(response_data).lower()):
                    self.log("✅ Import correctly rejected duplicate asset")
                elif response_data.get("duplicates") or response_data.get("errors"):
                    self.log("✅ Import correctly detected duplicate asset")
                else:
                    self.log(f"❌ Expected duplicate error, got: {response_data}", "ERROR")
                    return False
            else:
                self.log(f"❌ Expected duplicate validation response, got status {result['status_code']}: {result['response']}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Test 1 exception: {e}", "ERROR")
            return False

    def test_2_export_document_checklist(self) -> bool:
        """Test 2: Export CSV/Excel with Document Checklist"""
        self.log("\n=== TEST 2: Export CSV/Excel with Document Checklist ===")
        
        try:
            # Step 1: Create activity and asset with document checklist
            activity_id = self.create_activity("EXP/001/2025", "Export Test Activity")
            if not activity_id:
                return False
            
            asset_id = self.create_asset_with_documents(activity_id)
            if not asset_id:
                return False
            
            # Step 2: Test CSV export
            self.log("Testing CSV export with document checklist...")
            csv_url = f"{BACKEND_URL}/export/csv?activity_id={activity_id}&base_url=http://test.com"
            response = self.session.get(csv_url)
            
            if response.status_code == 200:
                csv_content = response.text
                if "kelengkapan_dokumen" in csv_content:
                    self.log("✅ CSV export contains 'kelengkapan_dokumen' column")
                else:
                    self.log("❌ CSV export missing 'kelengkapan_dokumen' column", "ERROR")
                    return False
            else:
                self.log(f"❌ CSV export failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Step 3: Test XLSX export
            self.log("Testing XLSX export with document checklist...")
            xlsx_url = f"{BACKEND_URL}/export/xlsx?activity_id={activity_id}&base_url=http://test.com"
            response = self.session.get(xlsx_url)
            
            if response.status_code == 200:
                if response.headers.get('content-type') == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    content_length = len(response.content)
                    self.log(f"✅ XLSX export successful, file size: {content_length} bytes")
                else:
                    self.log(f"❌ XLSX export wrong content type: {response.headers.get('content-type')}", "ERROR")
                    return False
            else:
                self.log(f"❌ XLSX export failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Test 2 exception: {e}", "ERROR")
            return False

    def test_3_bulk_delete(self) -> bool:
        """Test 3: Bulk Delete Assets"""
        self.log("\n=== TEST 3: Bulk Delete Assets ===")
        
        try:
            # Step 1: Create activity
            activity_id = self.create_activity("DEL/001/2025", "Bulk Delete Test Activity")
            if not activity_id:
                return False
            
            # Step 2: Create multiple assets in the activity
            assets_created = []
            for i in range(3):
                asset_data = {
                    "asset_code": f"100010000{i}",
                    "NUP": f"{i+1}",
                    "asset_name": f"Test Asset {i+1}",
                    "category": "Test Category",
                    "activity_id": activity_id
                }
                
                response = self.session.post(f"{BACKEND_URL}/assets", json=asset_data)
                if response.status_code == 200:
                    asset = response.json()
                    assets_created.append(asset.get("id"))
                    self.created_assets.append(asset.get("id"))
                else:
                    self.log(f"❌ Failed to create test asset {i+1}: {response.status_code} - {response.text}", "ERROR")
                    return False
            
            self.log(f"✅ Created {len(assets_created)} test assets")
            
            # Step 3: Verify assets exist before deletion
            get_url = f"{BACKEND_URL}/assets?activity_id={activity_id}"
            response = self.session.get(get_url)
            
            if response.status_code == 200:
                data = response.json()
                assets_before = data.get("total", 0)
                self.log(f"Assets before deletion: {assets_before}")
            else:
                self.log(f"❌ Failed to get assets before deletion: {response.status_code}", "ERROR")
                return False
            
            # Step 4: Call bulk delete endpoint
            self.log("Calling bulk delete endpoint...")
            delete_url = f"{BACKEND_URL}/assets/bulk-delete/{activity_id}"
            response = self.session.delete(delete_url)
            
            if response.status_code == 200:
                result = response.json()
                deleted_count = result.get("deleted", 0)
                self.log(f"✅ Bulk delete successful, deleted {deleted_count} assets")
                
                if deleted_count != len(assets_created):
                    self.log(f"⚠️ Expected to delete {len(assets_created)} assets, but deleted {deleted_count}", "WARN")
            else:
                self.log(f"❌ Bulk delete failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
            # Step 5: Verify all assets are deleted
            response = self.session.get(get_url)
            
            if response.status_code == 200:
                data = response.json()
                assets_after = data.get("total", 0)
                if assets_after == 0:
                    self.log("✅ All assets successfully deleted")
                else:
                    self.log(f"❌ Expected 0 assets after deletion, found {assets_after}", "ERROR")
                    return False
            else:
                self.log(f"❌ Failed to verify deletion: {response.status_code}", "ERROR")
                return False
            
            # Step 6: Verify activity still exists after bulk delete
            activity_url = f"{BACKEND_URL}/inventory-activities"
            response = self.session.get(activity_url)
            
            if response.status_code == 200:
                activities = response.json()
                if isinstance(activities, list):
                    found_activity = any(act.get("id") == activity_id for act in activities)
                    if found_activity:
                        self.log("✅ Activity still exists after bulk asset deletion")
                    else:
                        self.log("❌ Activity was deleted along with assets", "ERROR")
                        return False
                else:
                    self.log("⚠️ Unexpected activities response format", "WARN")
            else:
                self.log(f"❌ Failed to verify activity existence: {response.status_code}", "ERROR")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"❌ Test 3 exception: {e}", "ERROR")
            return False

    def test_4_document_file_endpoint(self) -> bool:
        """Test 4: Document File Endpoint"""
        self.log("\n=== TEST 4: Document File Endpoint ===")
        
        try:
            # Step 1: Create activity and asset with document checklist containing photos
            activity_id = self.create_activity("DOC/001/2025", "Document File Test Activity")
            if not activity_id:
                return False
            
            asset_id = self.create_asset_with_documents(activity_id)
            if not asset_id:
                return False
            
            # Step 2: Test document file endpoint
            self.log("Testing document file endpoint...")
            doc_file_url = f"{BACKEND_URL}/assets/{asset_id}/doc-file/0/photo/0"
            response = self.session.get(doc_file_url)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    self.log(f"✅ Document file endpoint returned image: {content_type}")
                    return True
                else:
                    self.log(f"❌ Expected image content type, got: {content_type}", "ERROR")
                    return False
            else:
                self.log(f"❌ Document file endpoint failed: {response.status_code} - {response.text}", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"❌ Test 4 exception: {e}", "ERROR")
            return False

    def cleanup(self):
        """Clean up test data"""
        self.log("\n=== CLEANUP ===")
        
        # Clean up assets
        for asset_id in self.created_assets:
            try:
                response = self.session.delete(f"{BACKEND_URL}/assets/{asset_id}")
                if response.status_code == 200:
                    self.log(f"✅ Asset {asset_id} cleaned up")
                else:
                    self.log(f"⚠️ Asset {asset_id} cleanup failed: {response.status_code}", "WARN")
            except Exception as e:
                self.log(f"⚠️ Asset cleanup error: {e}", "WARN")
        
        # Clean up activities
        for activity_id in self.created_activities:
            try:
                response = self.session.delete(f"{BACKEND_URL}/inventory-activities/{activity_id}")
                if response.status_code == 200:
                    self.log(f"✅ Activity {activity_id} cleaned up")
                else:
                    self.log(f"⚠️ Activity {activity_id} cleanup failed: {response.status_code}", "WARN")
            except Exception as e:
                self.log(f"⚠️ Activity cleanup error: {e}", "WARN")
        
        # Clean up categories
        for category_id in self.created_categories:
            try:
                response = self.session.delete(f"{BACKEND_URL}/categories/{category_id}")
                if response.status_code == 200:
                    self.log(f"✅ Category {category_id} cleaned up")
                else:
                    self.log(f"⚠️ Category {category_id} cleanup failed: {response.status_code}", "WARN")
            except Exception as e:
                self.log(f"⚠️ Category cleanup error: {e}", "WARN")

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        self.log("=== NEW FEATURES TESTING STARTED ===")
        
        # Authentication
        if not self.register_and_login():
            self.log("❌ Authentication failed, aborting tests", "ERROR")
            return self.test_results
        
        # Run tests
        self.test_results["test1_import_validation"] = self.test_1_import_validation()
        self.test_results["test2_export_document_checklist"] = self.test_2_export_document_checklist()
        self.test_results["test3_bulk_delete"] = self.test_3_bulk_delete()
        self.test_results["test4_document_file_endpoint"] = self.test_4_document_file_endpoint()
        
        # Cleanup
        self.cleanup()
        
        # Summary
        self.log("\n=== TEST RESULTS SUMMARY ===")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{test_name}: {status}")
        
        self.log(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        return self.test_results

def main():
    """Main test runner"""
    tester = NewFeaturesTester()
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()