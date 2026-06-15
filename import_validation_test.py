#!/usr/bin/env python3
"""
Focused Import Validation Test
Test the import validation feature using existing categories or create minimal test
"""

import requests
import json
import csv
import io
import sys
import time
from typing import Dict, Any, Optional

# Backend URL from environment
BACKEND_URL = "https://asset-crud-auth.preview.emergentagent.com/api"

class ImportValidationTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def register_and_login(self) -> bool:
        """Register test user and login"""
        try:
            register_data = {
                "name": "Import Test User",
                "username": "importtest", 
                "password": "test123"
            }
            
            self.log("Registering test user...")
            response = self.session.post(f"{BACKEND_URL}/auth/register", json=register_data)
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                self.log("✅ Registration successful")
                return True
            elif response.status_code == 400 and "sudah digunakan" in response.text:
                # User exists, try login
                self.log("User exists, trying login...")
                login_data = {"username": "importtest", "password": "test123"}
                response = self.session.post(f"{BACKEND_URL}/auth/login", json=login_data)
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                    self.log("✅ Login successful")
                    return True
            
            self.log(f"❌ Authentication failed: {response.status_code} - {response.text}", "ERROR")
            return False
                
        except Exception as e:
            self.log(f"❌ Auth error: {e}", "ERROR")
            return False

    def get_categories(self) -> list:
        """Get existing categories"""
        try:
            response = self.session.get(f"{BACKEND_URL}/categories/all")
            if response.status_code == 200:
                categories = response.json()
                self.log(f"Found {len(categories)} existing categories")
                return categories
            else:
                self.log(f"❌ Failed to get categories: {response.status_code}", "ERROR")
                return []
        except Exception as e:
            self.log(f"❌ Categories error: {e}", "ERROR")
            return []

    def create_activity(self, nomor_surat: str, nama_kegiatan: str) -> Optional[str]:
        """Create inventory activity and return ID"""
        try:
            activity_data = {
                "nomor_surat": nomor_surat,
                "nama_kegiatan": nama_kegiatan,
                "tanggal_mulai": "2024-01-01",
                "tanggal_selesai": "2024-12-31",
                "status": "Aktif",
                "keterangan": f"Test activity for import validation"
            }
            
            response = self.session.post(f"{BACKEND_URL}/inventory-activities", json=activity_data)
            
            if response.status_code == 200:
                data = response.json()
                activity_id = data.get("id")
                self.log(f"✅ Activity created with ID: {activity_id}")
                return activity_id
            else:
                self.log(f"❌ Activity creation failed: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Activity creation error: {e}", "ERROR")
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

    def test_import_validation(self) -> bool:
        """Test import validation without needing to create categories"""
        self.log("\n=== TESTING IMPORT VALIDATION ===")
        
        try:
            # Create activity for testing
            activity_id = self.create_activity("TESTVAL/001/2025", "Import Validation Test")
            if not activity_id:
                return False
            
            # Get existing categories to understand the validation
            categories = self.get_categories()
            
            if not categories:
                self.log("⚠️ No categories found, cannot test category validation", "WARN")
                # Test with a non-existent category to see validation behavior
                test_csv = """asset_code,NUP,asset_name,category,brand,model,location,condition,status
1234567890,1,Test Asset,NonExistent Category,Test Brand,Test Model,Test Location,Baik,Aktif"""
                
                result = self.import_csv_test(test_csv, activity_id)
                
                if result["status_code"] == 200:
                    response_data = result["response"]
                    if not response_data.get("success") and "kategori" in str(response_data).lower():
                        self.log("✅ Import validation correctly rejected non-existent category")
                        return True
                    else:
                        self.log(f"❌ Expected category validation error, got: {response_data}", "ERROR")
                        return False
                else:
                    self.log(f"❌ Import failed unexpectedly: {result['status_code']} - {result['response']}", "ERROR")
                    return False
            else:
                # Find a category with kode_aset to test validation
                category_with_kode = None
                for cat in categories:
                    if cat.get("kode_aset") and len(cat.get("kode_aset", "")) >= 10:
                        category_with_kode = cat
                        break
                
                if category_with_kode:
                    kode_aset = category_with_kode["kode_aset"]
                    correct_label = category_with_kode["label"]
                    
                    self.log(f"Testing with existing category: {kode_aset} -> {correct_label}")
                    
                    # Test 1: Import with wrong category description
                    wrong_csv = f"""asset_code,NUP,asset_name,category,brand,model,location,condition,status
{kode_aset},1,Test Asset,Wrong Category Description,Test Brand,Test Model,Test Location,Baik,Aktif"""
                    
                    result = self.import_csv_test(wrong_csv, activity_id)
                    
                    if result["status_code"] == 200:
                        response_data = result["response"]
                        if not response_data.get("success") and ("deskripsi" in str(response_data).lower() or "tidak sesuai" in str(response_data).lower() or "error" in str(response_data).lower()):
                            self.log("✅ Import validation correctly rejected wrong category description")
                        else:
                            self.log(f"❌ Expected validation error for wrong category, got: {response_data}", "ERROR")
                            return False
                    else:
                        self.log(f"❌ Import failed with status {result['status_code']}: {result['response']}", "ERROR")
                        return False
                    
                    # Test 2: Import with correct category description
                    correct_csv = f"""asset_code,NUP,asset_name,category,brand,model,location,condition,status
{kode_aset},2,Test Asset Correct,{correct_label},Test Brand,Test Model,Test Location,Baik,Aktif"""
                    
                    result = self.import_csv_test(correct_csv, activity_id)
                    
                    if result["status_code"] == 200:
                        response_data = result["response"]
                        if response_data.get("success"):
                            self.log("✅ Import succeeded with correct category description")
                            
                            # Test 3: Try importing duplicate asset (same asset_code + NUP)
                            duplicate_csv = f"""asset_code,NUP,asset_name,category,brand,model,location,condition,status
{kode_aset},2,Duplicate Asset,{correct_label},Test Brand,Test Model,Test Location,Baik,Aktif"""
                            
                            result = self.import_csv_test(duplicate_csv, activity_id)
                            
                            if result["status_code"] == 200:
                                response_data = result["response"]
                                if not response_data.get("success") and ("duplikat" in str(response_data).lower() or "sudah digunakan" in str(response_data).lower() or "duplicate" in str(response_data).lower()):
                                    self.log("✅ Import validation correctly detected duplicate asset")
                                    return True
                                else:
                                    self.log(f"❌ Expected duplicate validation error, got: {response_data}", "ERROR")
                                    return False
                            else:
                                self.log(f"❌ Duplicate test failed with status {result['status_code']}: {result['response']}", "ERROR")
                                return False
                        else:
                            self.log(f"❌ Import failed with correct category: {response_data}", "ERROR")
                            return False
                    else:
                        self.log(f"❌ Import failed with status {result['status_code']}: {result['response']}", "ERROR")
                        return False
                else:
                    self.log("⚠️ No categories with kode_aset found, testing basic category validation", "WARN")
                    
                    # Use first category for basic validation test
                    first_cat = categories[0]
                    cat_label = first_cat["label"]
                    
                    # Test with wrong category name
                    wrong_csv = f"""asset_code,NUP,asset_name,category,brand,model,location,condition,status
1234567890,1,Test Asset,Wrong Category Name,Test Brand,Test Model,Test Location,Baik,Aktif"""
                    
                    result = self.import_csv_test(wrong_csv, activity_id)
                    
                    if result["status_code"] == 200:
                        response_data = result["response"]
                        if not response_data.get("success") and ("kategori" in str(response_data).lower() or "category" in str(response_data).lower()):
                            self.log("✅ Import validation correctly rejected invalid category")
                            return True
                        else:
                            self.log(f"❌ Expected category validation error, got: {response_data}", "ERROR")
                            return False
                    else:
                        self.log(f"❌ Import failed with status {result['status_code']}: {result['response']}", "ERROR")
                        return False
            
            # Cleanup
            try:
                self.session.delete(f"{BACKEND_URL}/inventory-activities/{activity_id}")
                self.log("✅ Test activity cleaned up")
            except:
                pass
            
        except Exception as e:
            self.log(f"❌ Test exception: {e}", "ERROR")
            return False

def main():
    """Main test runner"""
    tester = ImportValidationTester()
    
    # Authentication
    if not tester.register_and_login():
        tester.log("❌ Authentication failed, aborting test", "ERROR")
        sys.exit(1)
    
    # Run test
    success = tester.test_import_validation()
    
    if success:
        tester.log("✅ Import validation test PASSED")
        sys.exit(0)
    else:
        tester.log("❌ Import validation test FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()