
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite for System Backup & Restore APIs
Tests: GET /api/backup/stats, GET /api/backup/create, POST /api/backup/restore
Author: Testing Agent - Iteration 56
"""

import pytest
import requests
import os
import zipfile
import io
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = TEST_ADMIN_PASSWORD


class TestBackupRestoreAPIs:
    """Test backup and restore API endpoints (admin only)"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed - skipping backup tests")
    
    @pytest.fixture(scope="class")
    def non_admin_token(self):
        """Try to get a non-admin token for permission testing"""
        # First, get admin token to check if there are non-admin users
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "operator",  # Try common non-admin username
            "password": "operator123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    # =========================================================================
    # TEST: GET /api/backup/stats - Get collection statistics
    # =========================================================================
    
    def test_backup_stats_returns_200_for_admin(self, admin_token):
        """GET /api/backup/stats should return 200 with collection stats for admin"""
        response = requests.get(
            f"{BASE_URL}/api/backup/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "collections" in data, "Response should contain 'collections'"
        assert "total_records" in data, "Response should contain 'total_records'"
        
        # Verify expected collections are present
        expected_collections = ["users", "categories", "activities", "assets", "report_settings", "audit_logs"]
        for col in expected_collections:
            assert col in data["collections"], f"Collection '{col}' should be in stats"
        
        print(f"Backup stats: {data['total_records']} total records across {len(data['collections'])} collections")
    
    def test_backup_stats_requires_auth(self):
        """GET /api/backup/stats should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/backup/stats")
        assert response.status_code in [401, 422], f"Expected 401/422 without auth, got {response.status_code}"
    
    def test_backup_stats_requires_admin(self, non_admin_token):
        """GET /api/backup/stats should return 403 for non-admin users"""
        if non_admin_token is None:
            pytest.skip("No non-admin user available for testing")
        
        response = requests.get(
            f"{BASE_URL}/api/backup/stats",
            headers={"Authorization": f"Bearer {non_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
    
    # =========================================================================
    # TEST: GET /api/backup/create - Create and download backup ZIP
    # =========================================================================
    
    def test_backup_create_returns_zip_for_admin(self, admin_token):
        """GET /api/backup/create should return ZIP file for admin"""
        response = requests.get(
            f"{BASE_URL}/api/backup/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "application/zip" in content_type or "application/octet-stream" in content_type, \
            f"Expected zip content type, got {content_type}"
        
        # Check content disposition
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, "Response should be an attachment"
        assert ".zip" in content_disp, "Filename should end with .zip"
        
        print(f"Backup created successfully, Content-Disposition: {content_disp}")
    
    def test_backup_zip_structure(self, admin_token):
        """GET /api/backup/create should return valid ZIP with expected files"""
        response = requests.get(
            f"{BASE_URL}/api/backup/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert response.status_code == 200
        
        # Parse as ZIP file
        zip_buffer = io.BytesIO(response.content)
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                names = zf.namelist()
                
                # Check required files
                assert "metadata.json" in names, "ZIP must contain metadata.json"
                assert "users.json" in names, "ZIP must contain users.json"
                assert "categories.json" in names, "ZIP must contain categories.json"
                assert "activities.json" in names, "ZIP must contain activities.json"
                assert "assets.json" in names, "ZIP must contain assets.json"
                
                # Validate metadata structure
                metadata = json.loads(zf.read("metadata.json"))
                assert "version" in metadata, "Metadata should have version"
                assert "created_at" in metadata, "Metadata should have created_at"
                assert "created_by" in metadata, "Metadata should have created_by"
                assert "collections" in metadata, "Metadata should have collections"
                assert "total_records" in metadata, "Metadata should have total_records"
                
                print(f"Backup ZIP contains {len(names)} files: {names[:10]}...")
                print(f"Metadata: version={metadata.get('version')}, created_by={metadata.get('created_by')}, total={metadata.get('total_records')}")
                
        except zipfile.BadZipFile:
            pytest.fail("Response is not a valid ZIP file")
    
    def test_backup_create_requires_auth(self):
        """GET /api/backup/create should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/backup/create")
        assert response.status_code in [401, 422], f"Expected 401/422 without auth, got {response.status_code}"
    
    def test_backup_create_requires_admin(self, non_admin_token):
        """GET /api/backup/create should return 403 for non-admin users"""
        if non_admin_token is None:
            pytest.skip("No non-admin user available for testing")
        
        response = requests.get(
            f"{BASE_URL}/api/backup/create",
            headers={"Authorization": f"Bearer {non_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
    
    # =========================================================================
    # TEST: POST /api/backup/restore - Upload and restore from backup ZIP
    # =========================================================================
    
    def test_restore_rejects_non_zip_file(self, admin_token):
        """POST /api/backup/restore should reject non-ZIP files"""
        # Create a fake text file
        fake_file = io.BytesIO(b"This is not a zip file")
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("fake_backup.txt", fake_file, "text/plain")}
        )
        # Should reject because filename doesn't end with .zip
        assert response.status_code == 400, f"Expected 400 for non-zip file, got {response.status_code}"
        
        data = response.json()
        assert "ZIP" in data.get("detail", "").upper() or "zip" in data.get("detail", "").lower(), \
            f"Error should mention ZIP format: {data}"
    
    def test_restore_rejects_invalid_zip(self, admin_token):
        """POST /api/backup/restore should reject corrupted ZIP files"""
        # Create a file that looks like zip but isn't valid
        fake_zip = io.BytesIO(b"PK\x03\x04corrupted zip data here")
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("fake_backup.zip", fake_zip, "application/zip")}
        )
        assert response.status_code == 400, f"Expected 400 for invalid zip, got {response.status_code}"
        print(f"Invalid ZIP rejection: {response.json()}")
    
    def test_restore_rejects_zip_without_metadata(self, admin_token):
        """POST /api/backup/restore should reject ZIP without metadata.json"""
        # Create a valid ZIP but without metadata.json
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("users.json", "[]")
            zf.writestr("categories.json", "[]")
        zip_buffer.seek(0)
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("no_metadata.zip", zip_buffer, "application/zip")}
        )
        assert response.status_code == 400, f"Expected 400 for ZIP without metadata, got {response.status_code}"
        
        data = response.json()
        assert "metadata" in data.get("detail", "").lower(), f"Error should mention metadata: {data}"
    
    def test_restore_rejects_zip_missing_required_collections(self, admin_token):
        """POST /api/backup/restore should reject ZIP missing required collections"""
        # Create a ZIP with metadata but missing some required collections
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            metadata = {"version": "3.0.0", "created_at": "2024-01-01T00:00:00", "collections": {}, "total_records": 0}
            zf.writestr("metadata.json", json.dumps(metadata))
            zf.writestr("users.json", "[]")
            # Missing: categories.json, activities.json, assets.json
        zip_buffer.seek(0)
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("incomplete.zip", zip_buffer, "application/zip")}
        )
        assert response.status_code == 400, f"Expected 400 for incomplete ZIP, got {response.status_code}"
        
        data = response.json()
        detail = data.get("detail", "").lower()
        assert "tidak lengkap" in detail or "tidak ditemukan" in detail or "missing" in detail, \
            f"Error should mention missing collections: {data}"
    
    def test_restore_requires_auth(self):
        """POST /api/backup/restore should return 401 without auth"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("metadata.json", "{}")
        zip_buffer.seek(0)
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            files={"file": ("backup.zip", zip_buffer, "application/zip")}
        )
        assert response.status_code in [401, 422], f"Expected 401/422 without auth, got {response.status_code}"
    
    def test_restore_requires_admin(self, non_admin_token):
        """POST /api/backup/restore should return 403 for non-admin users"""
        if non_admin_token is None:
            pytest.skip("No non-admin user available for testing")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("metadata.json", "{}")
        zip_buffer.seek(0)
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            files={"file": ("backup.zip", zip_buffer, "application/zip")}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
    
    # =========================================================================
    # TEST: Full backup-restore cycle
    # =========================================================================
    
    def test_backup_and_restore_full_cycle(self, admin_token):
        """Full cycle: create backup, then restore from it"""
        # Step 1: Create backup
        backup_response = requests.get(
            f"{BASE_URL}/api/backup/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert backup_response.status_code == 200, f"Backup creation failed: {backup_response.text}"
        
        # Step 2: Restore from the same backup
        zip_content = backup_response.content
        restore_response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("backup.zip", io.BytesIO(zip_content), "application/zip")},
            timeout=120
        )
        
        assert restore_response.status_code == 200, f"Restore failed: {restore_response.text}"
        
        data = restore_response.json()
        assert "message" in data, "Restore response should have message"
        assert "restored" in data, "Restore response should have restored stats"
        assert "total_restored" in data, "Restore response should have total_restored"
        
        print(f"Restore successful: {data.get('message')}")
        print(f"Total restored: {data.get('total_restored')} records")
        print(f"Collections restored: {data.get('restored')}")
    
    def test_login_works_after_restore(self, admin_token):
        """Verify login still works after restore (password hashes preserved)"""
        # First do a backup-restore cycle
        backup_response = requests.get(
            f"{BASE_URL}/api/backup/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert backup_response.status_code == 200
        
        restore_response = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("backup.zip", io.BytesIO(backup_response.content), "application/zip")},
            timeout=120
        )
        assert restore_response.status_code == 200
        
        # Now try to login again
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed after restore: {login_response.text}"
        
        data = login_response.json()
        assert "access_token" in data, "Login response should have access_token after restore"
        print("Login successful after restore - password hashes preserved correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
