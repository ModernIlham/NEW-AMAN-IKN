#!/usr/bin/env python3

import requests
import json
import sys
import base64
import io
from datetime import datetime
from PIL import Image

class NewEndpointsTester:
    def __init__(self, base_url="https://asset-crud-auth.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.user_data = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_assets = []
        self.created_activities = []
        self.created_users = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_request(self, method, endpoint, data=None, files=None, headers=None):
        """Make API request with error handling"""
        url = f"{self.base_url}/{endpoint}"
        
        request_headers = {"Content-Type": "application/json"}
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        if headers:
            request_headers.update(headers)
        
        try:
            if method == "GET":
                response = requests.get(url, headers=request_headers, timeout=15)
            elif method == "POST":
                if files:
                    del request_headers["Content-Type"]
                    response = requests.post(url, data=data, files=files, headers=request_headers, timeout=15)
                else:
                    response = requests.post(url, json=data, headers=request_headers, timeout=15)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=request_headers, timeout=15)
            elif method == "DELETE":
                response = requests.delete(url, headers=request_headers, timeout=15)
            
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            return None

    def setup_authentication(self):
        """Set up authentication for testing"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        user_data = {
            "username": f"newtest_{timestamp}",
            "password": "test123",
            "name": "New Test User"
        }
        
        response = self.run_request("POST", "auth/register", user_data)
        if response and response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.user_data = data.get("user")
            return True
        return False

    def create_test_asset(self):
        """Create a test asset to use for other tests"""
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_data = buffer.getvalue()
        test_image_base64 = base64.b64encode(img_data).decode('utf-8')
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        asset_data = {
            "asset_code": f"12345{timestamp[-5:]}",
            "NUP": "NEW001",
            "asset_name": "Test Asset for New Endpoints",
            "category": "Elektronik",
            "brand": "Test Brand",
            "model": "Test Model",
            "kode_register": "2C089D3BEB8BB483E063BAAAD80A726F",
            "serial_number": "SN001TEST",
            "purchase_date": "2024-01-01",
            "purchase_price": "5000000",
            "location": "Test Location",
            "department": "Test Dept",
            "user": "Test User",
            "condition": "Baik",
            "status": "Aktif",
            "nomor_spm": "02847T/621001/2024",
            "perolehan_dari_nama": "Test Source",
            "nomor_kontrak": "TEST-001/2024",
            "nomor_bukti_perolehan": "BAST-001/2024",
            "supplier": "Test Supplier",
            "notes": "Test asset for new endpoints",
            "document_checklist": [
                {"name": "STNK", "checked": True, "notes": "Available"},
                {"name": "BPKB", "checked": False, "notes": "Missing"}
            ],
            "photo": f"data:image/png;base64,{test_image_base64}"
        }
        
        response = self.run_request("POST", "assets", asset_data)
        if response and response.status_code == 200:
            created_asset = response.json()
            asset_id = created_asset.get("id")
            self.created_assets.append(asset_id)
            return asset_id
        return None

    def test_asset_validation_endpoint(self):
        """Test POST /api/assets/validate - NEW ENDPOINT"""
        print("\n🔍 Testing Asset Validation Endpoint...")
        
        # Test 1: Invalid data (category not in list, asset_code wrong format)
        invalid_data = {
            "asset_code": "123",  # Should be 10 digits
            "asset_name": "Test Asset",
            "category": "Invalid"  # Not in valid categories
        }
        
        response = self.run_request("POST", "assets/validate", invalid_data)
        if response and response.status_code == 200:
            result = response.json()
            if not result.get("valid", True) and len(result.get("errors", [])) > 0:
                self.log_test("Asset Validation - Invalid Data (POST /api/assets/validate)", True)
            else:
                self.log_test("Asset Validation - Invalid Data (POST /api/assets/validate)", False, f"Should return errors: {result}")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Asset Validation - Invalid Data (POST /api/assets/validate)", False, error_detail)

        # Test 2: Valid data
        valid_data = {
            "asset_code": "3030103001",  # 10 digits
            "asset_name": "Test Asset",
            "category": "Elektronik"  # Valid category
        }
        
        response = self.run_request("POST", "assets/validate", valid_data)
        if response and response.status_code == 200:
            result = response.json()
            if result.get("valid", False):
                self.log_test("Asset Validation - Valid Data (POST /api/assets/validate)", True)
            else:
                self.log_test("Asset Validation - Valid Data (POST /api/assets/validate)", False, f"Should be valid: {result}")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Asset Validation - Valid Data (POST /api/assets/validate)", False, error_detail)

    def test_asset_card_pdf_endpoint(self):
        """Test GET /api/assets/{asset_id}/card - NEW ENDPOINT"""
        print("\n📄 Testing Asset Card PDF Endpoint...")
        
        # First create a test asset
        asset_id = self.create_test_asset()
        if not asset_id:
            self.log_test("Asset Card PDF (GET /api/assets/{id}/card)", False, "Failed to create test asset")
            return
        
        # Test getting asset card PDF
        response = self.run_request("GET", f"assets/{asset_id}/card")
        if response and response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type:
                # Check if we have actual PDF content (PDF files start with %PDF)
                content = response.content
                if content.startswith(b'%PDF'):
                    self.log_test("Asset Card PDF (GET /api/assets/{id}/card)", True)
                else:
                    self.log_test("Asset Card PDF (GET /api/assets/{id}/card)", False, "Response not a valid PDF")
            else:
                self.log_test("Asset Card PDF (GET /api/assets/{id}/card)", False, f"Wrong content type: {content_type}")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Asset Card PDF (GET /api/assets/{id}/card)", False, error_detail)

    def test_inventory_activities_crud(self):
        """Test Inventory Activities CRUD - NEW ENDPOINTS"""
        print("\n📋 Testing Inventory Activities Endpoints...")
        
        # Test 1: Create inventory activity (POST /api/inventory-activities)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        activity_data = {
            "nomor_surat": f"INV/{timestamp}/2024",
            "nama_kegiatan": "Test Inventory Activity",
            "deskripsi": "Test description for activity",
            "tanggal_mulai": "2024-01-01",
            "tanggal_selesai": "2024-01-31",
            "penanggung_jawab": "Test Admin",
            "photos": [],
            "asset_ids": []
        }
        
        response = self.run_request("POST", "inventory-activities", activity_data)
        created_activity_id = None
        if response and response.status_code == 200:
            created_activity = response.json()
            created_activity_id = created_activity.get("id")
            if created_activity_id:
                self.created_activities.append(created_activity_id)
                self.log_test("Create Inventory Activity (POST /api/inventory-activities)", True)
            else:
                self.log_test("Create Inventory Activity (POST /api/inventory-activities)", False, "No ID returned")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Create Inventory Activity (POST /api/inventory-activities)", False, error_detail)

        # Test 2: Get all inventory activities (GET /api/inventory-activities)
        response = self.run_request("GET", "inventory-activities")
        if response and response.status_code == 200:
            activities = response.json()
            if isinstance(activities, list):
                # Check if our created activity is in the list
                found = any(act.get("nomor_surat") == activity_data["nomor_surat"] for act in activities)
                if found:
                    self.log_test("Get Inventory Activities (GET /api/inventory-activities)", True)
                else:
                    self.log_test("Get Inventory Activities (GET /api/inventory-activities)", False, "Created activity not found")
            else:
                self.log_test("Get Inventory Activities (GET /api/inventory-activities)", False, "Response not a list")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Get Inventory Activities (GET /api/inventory-activities)", False, error_detail)

        # Test 3: Try to create duplicate (should fail)
        duplicate_data = activity_data.copy()
        response = self.run_request("POST", "inventory-activities", duplicate_data)
        if response and response.status_code == 400:
            # Should fail with duplicate nomor_surat
            self.log_test("Create Duplicate Activity - Should Fail (POST /api/inventory-activities)", True)
        else:
            self.log_test("Create Duplicate Activity - Should Fail (POST /api/inventory-activities)", False, "Should have failed with 400 status")

        # Test 4: Delete inventory activity (DELETE /api/inventory-activities/{id})
        if created_activity_id:
            response = self.run_request("DELETE", f"inventory-activities/{created_activity_id}")
            if response and response.status_code == 200:
                self.log_test("Delete Inventory Activity (DELETE /api/inventory-activities/{id})", True)
                self.created_activities.remove(created_activity_id)
            else:
                error_detail = response.json().get("detail", "Unknown error") if response else "No response"
                self.log_test("Delete Inventory Activity (DELETE /api/inventory-activities/{id})", False, error_detail)

    def test_user_management_endpoints(self):
        """Test User Management Endpoints - NEW ENDPOINTS"""
        print("\n👥 Testing User Management Endpoints...")
        
        # Test 1: Get all users (GET /api/users)
        response = self.run_request("GET", "users")
        if response and response.status_code == 200:
            users = response.json()
            if isinstance(users, list) and len(users) > 0:
                # Check if current user is in the list
                current_username = self.user_data.get("username") if self.user_data else None
                found = any(user.get("username") == current_username for user in users)
                if found:
                    self.log_test("Get Users List (GET /api/users)", True)
                else:
                    self.log_test("Get Users List (GET /api/users)", False, "Current user not found in list")
            else:
                self.log_test("Get Users List (GET /api/users)", False, "No users returned or wrong format")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Get Users List (GET /api/users)", False, error_detail)

        # Get user ID for further tests
        user_id = self.user_data.get("id") if self.user_data else None
        if not user_id:
            self.log_test("User Management Tests", False, "No user ID available")
            return

        # Test 2: Toggle user active status (PUT /api/users/{user_id}/toggle-active)
        response = self.run_request("PUT", f"users/{user_id}/toggle-active")
        if response and response.status_code == 200:
            result = response.json()
            if "is_active" in result:
                self.log_test("Toggle User Active Status (PUT /api/users/{id}/toggle-active)", True)
                # Toggle back to active
                self.run_request("PUT", f"users/{user_id}/toggle-active")
            else:
                self.log_test("Toggle User Active Status (PUT /api/users/{id}/toggle-active)", False, "No is_active field in response")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Toggle User Active Status (PUT /api/users/{id}/toggle-active)", False, error_detail)

        # Test 3: Change user password (PUT /api/users/{user_id}/change-password)
        password_data = {"new_password": "newpass123"}
        response = self.run_request("PUT", f"users/{user_id}/change-password", password_data)
        if response and response.status_code == 200:
            result = response.json()
            if "message" in result:
                self.log_test("Change User Password (PUT /api/users/{id}/change-password)", True)
            else:
                self.log_test("Change User Password (PUT /api/users/{id}/change-password)", False, "No message in response")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Change User Password (PUT /api/users/{id}/change-password)", False, error_detail)

    def test_template_downloads_again(self):
        """Test template downloads - mentioned in review request"""
        print("\n📥 Testing Template Downloads...")
        
        # Test Excel template
        response = self.run_request("GET", "templates/xlsx")
        if response and response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'spreadsheet' in content_type or 'excel' in content_type:
                self.log_test("Template Excel Download (GET /api/templates/xlsx)", True)
            else:
                self.log_test("Template Excel Download (GET /api/templates/xlsx)", False, f"Wrong content type: {content_type}")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Template Excel Download (GET /api/templates/xlsx)", False, error_detail)

        # Test CSV template
        response = self.run_request("GET", "templates/csv")
        if response and response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'csv' in content_type or 'text' in content_type:
                self.log_test("Template CSV Download (GET /api/templates/csv)", True)
            else:
                self.log_test("Template CSV Download (GET /api/templates/csv)", False, f"Wrong content type: {content_type}")
        else:
            error_detail = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_test("Template CSV Download (GET /api/templates/csv)", False, error_detail)

    def cleanup_test_data(self):
        """Clean up test data created during tests"""
        # Clean up assets
        for asset_id in self.created_assets:
            try:
                response = self.run_request("DELETE", f"assets/{asset_id}")
                if response and response.status_code == 200:
                    print(f"🧹 Cleaned up test asset: {asset_id}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup asset {asset_id}: {e}")

        # Clean up activities
        for activity_id in self.created_activities:
            try:
                response = self.run_request("DELETE", f"inventory-activities/{activity_id}")
                if response and response.status_code == 200:
                    print(f"🧹 Cleaned up test activity: {activity_id}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup activity {activity_id}: {e}")

    def run_new_endpoint_tests(self):
        """Run tests for NEW endpoints as specified in review request"""
        print("🚀 Testing NEW Inventory Management API Endpoints")
        print("📝 Focus: Asset Validation, Asset Card PDF, Inventory Activities, User Management, Templates")
        print("=" * 80)
        
        # Setup authentication
        if not self.setup_authentication():
            print("❌ Authentication setup failed. Stopping tests.")
            return False

        # Test NEW endpoints as specified in review request
        self.test_asset_validation_endpoint()
        self.test_asset_card_pdf_endpoint()
        self.test_inventory_activities_crud()
        self.test_user_management_endpoints()
        self.test_template_downloads_again()

        # Cleanup
        self.cleanup_test_data()

        # Summary
        print("\n" + "=" * 80)
        print(f"📊 NEW Endpoints Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"✨ Success Rate: {success_rate:.1f}%")
        
        # Show failed tests
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"   • {test['test']}: {test['details']}")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All NEW endpoint tests passed!")
            return True
        else:
            print("⚠️  Some NEW endpoint tests failed. Check the details above.")
            return False

def main():
    tester = NewEndpointsTester()
    success = tester.run_new_endpoint_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())