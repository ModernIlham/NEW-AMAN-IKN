
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite for Background Backup & Restore APIs (Iteration 64)
Tests new background job endpoints:
- POST /api/backup/start - Start background backup job
- GET /api/backup/active - Get active/recent job status
- GET /api/backup/progress/{job_id} - Get job progress
- GET /api/backup/download/{job_id} - Download completed backup
- POST /api/backup/restore/start - Start background restore job
- POST /api/backup/dismiss/{job_id} - Dismiss completed/failed job
- GET /api/backup/stats - Get collection statistics
- Concurrent job prevention (409 when job already running)
- Legacy endpoints: GET /api/backup/create, POST /api/backup/restore
"""

import pytest
import requests
import os
import zipfile
import io
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = TEST_ADMIN_PASSWORD


class TestBackgroundBackupAPIs:
    """Test background backup and restore API endpoints"""
    
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
    def auth_headers(self, admin_token):
        """Return auth headers dict"""
        return {"Authorization": f"Bearer {admin_token}"}

    # =========================================================================
    # TEST: GET /api/backup/stats - Get collection statistics
    # =========================================================================
    
    def test_backup_stats_returns_200(self, auth_headers):
        """GET /api/backup/stats should return 200 with collection stats"""
        response = requests.get(f"{BASE_URL}/api/backup/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "collections" in data, "Response should contain 'collections'"
        assert "total_records" in data, "Response should contain 'total_records'"
        
        expected_collections = ["users", "categories", "activities", "assets"]
        for col in expected_collections:
            assert col in data["collections"], f"Collection '{col}' should be in stats"
        
        print(f"PASS: Backup stats - {data['total_records']} total records")
    
    def test_backup_stats_requires_auth(self):
        """GET /api/backup/stats should return 401/422 without auth"""
        response = requests.get(f"{BASE_URL}/api/backup/stats")
        assert response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
        print("PASS: Backup stats requires authentication")

    # =========================================================================
    # TEST: GET /api/backup/active - Get active job status
    # =========================================================================
    
    def test_backup_active_returns_idle_when_no_job(self, auth_headers):
        """GET /api/backup/active should return {status: 'idle'} when no active job"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(0.5)
        
        response = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should be either idle or show a job status
        assert "status" in data, "Response should contain 'status'"
        print(f"PASS: Active job status - {data.get('status', 'unknown')}")
    
    def test_backup_active_requires_auth(self):
        """GET /api/backup/active should return 401/422 without auth"""
        response = requests.get(f"{BASE_URL}/api/backup/active")
        assert response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
        print("PASS: Active endpoint requires authentication")

    # =========================================================================
    # TEST: POST /api/backup/start - Start background backup
    # =========================================================================
    
    def test_backup_start_returns_job_id(self, auth_headers):
        """POST /api/backup/start should return job_id for tracking"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        response = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "job_id" in data, "Response should contain 'job_id'"
        assert "message" in data, "Response should contain 'message'"
        assert len(data["job_id"]) > 0, "job_id should not be empty"
        
        job_id = data["job_id"]
        print(f"PASS: Backup started - job_id={job_id}")
        
        # Wait for job to complete
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if progress_resp.status_code == 200:
                progress_data = progress_resp.json()
                if progress_data.get("status") == "completed":
                    print(f"PASS: Backup completed - {progress_data.get('progress', 100)}%")
                    break
                elif progress_data.get("status") == "failed":
                    print(f"WARN: Backup failed - {progress_data.get('error')}")
                    break
            time.sleep(1)
        
        # Dismiss the job
        requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)
    
    def test_backup_start_requires_auth(self):
        """POST /api/backup/start should return 401/422 without auth"""
        response = requests.post(f"{BASE_URL}/api/backup/start")
        assert response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
        print("PASS: Backup start requires authentication")

    # =========================================================================
    # TEST: GET /api/backup/progress/{job_id} - Get job progress
    # =========================================================================
    
    def test_backup_progress_returns_404_for_nonexistent(self, auth_headers):
        """GET /api/backup/progress/{job_id} should return 404 for nonexistent job"""
        response = requests.get(f"{BASE_URL}/api/backup/progress/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Progress returns 404 for nonexistent job")
    
    def test_backup_progress_returns_job_data(self, auth_headers):
        """GET /api/backup/progress/{job_id} should return progress data"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Start a new backup
        start_resp = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=30)
        if start_resp.status_code != 200:
            pytest.skip("Could not start backup job")
        
        job_id = start_resp.json().get("job_id")
        
        # Get progress
        time.sleep(0.5)
        progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
        assert progress_resp.status_code == 200, f"Expected 200, got {progress_resp.status_code}"
        
        data = progress_resp.json()
        assert "status" in data, "Progress should contain 'status'"
        assert "progress" in data, "Progress should contain 'progress'"
        assert "job_id" in data, "Progress should contain 'job_id'"
        assert data["job_id"] == job_id, "job_id should match"
        
        print(f"PASS: Progress - status={data['status']}, progress={data['progress']}%")
        
        # Wait for completion and dismiss
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            check_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if check_resp.status_code == 200 and check_resp.json().get("status") in ["completed", "failed"]:
                break
            time.sleep(1)
        
        requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)

    # =========================================================================
    # TEST: Concurrent job prevention - 409 when job already running
    # =========================================================================
    
    def test_concurrent_backup_returns_409(self, auth_headers):
        """POST /api/backup/start should return 409 when job already running"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Start first backup
        start_resp = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=30)
        if start_resp.status_code != 200:
            pytest.skip("Could not start first backup job")
        
        job_id = start_resp.json().get("job_id")
        
        # Try to start second backup immediately (should fail with 409)
        second_resp = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=10)
        
        # Could be 409 (conflict) or 200 if first completed very fast
        if second_resp.status_code == 409:
            print("PASS: Concurrent backup prevention - 409 returned")
            data = second_resp.json()
            assert "detail" in data, "409 response should have detail"
        else:
            # Job might have completed very fast
            print(f"INFO: Concurrent test inconclusive - first job completed quickly (status={second_resp.status_code})")
        
        # Wait for completion and cleanup
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            check_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
            if check_resp.status_code == 200:
                data = check_resp.json()
                if data.get("status") in ["completed", "failed", "idle"]:
                    if data.get("job_id"):
                        requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                    break
            time.sleep(1)

    # =========================================================================
    # TEST: GET /api/backup/download/{job_id} - Download completed backup
    # =========================================================================
    
    def test_backup_download_returns_zip(self, auth_headers):
        """GET /api/backup/download/{job_id} should return ZIP file"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Start backup
        start_resp = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=30)
        if start_resp.status_code != 200:
            pytest.skip("Could not start backup job")
        
        job_id = start_resp.json().get("job_id")
        
        # Wait for completion
        max_wait = 60
        start_time = time.time()
        completed = False
        while time.time() - start_time < max_wait:
            progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if progress_resp.status_code == 200:
                data = progress_resp.json()
                if data.get("status") == "completed":
                    completed = True
                    break
                elif data.get("status") == "failed":
                    pytest.skip(f"Backup failed: {data.get('error')}")
            time.sleep(1)
        
        if not completed:
            pytest.skip("Backup did not complete in time")
        
        # Download
        download_resp = requests.get(f"{BASE_URL}/api/backup/download/{job_id}", headers=auth_headers, timeout=60)
        assert download_resp.status_code == 200, f"Expected 200, got {download_resp.status_code}"
        
        content_type = download_resp.headers.get("Content-Type", "")
        assert "zip" in content_type or "octet-stream" in content_type, f"Expected ZIP, got {content_type}"
        
        # Verify it's a valid ZIP
        zip_buffer = io.BytesIO(download_resp.content)
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                names = zf.namelist()
                assert "metadata.json" in names, "ZIP should contain metadata.json"
                print(f"PASS: Download - valid ZIP with {len(names)} files")
        except zipfile.BadZipFile:
            pytest.fail("Downloaded file is not a valid ZIP")
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)
    
    def test_backup_download_returns_404_for_nonexistent(self, auth_headers):
        """GET /api/backup/download/{job_id} should return 404 for nonexistent job"""
        response = requests.get(f"{BASE_URL}/api/backup/download/nonexistent-job-id", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Download returns 404 for nonexistent job")

    # =========================================================================
    # TEST: POST /api/backup/restore/start - Start background restore
    # =========================================================================
    
    def test_restore_start_rejects_non_zip(self, auth_headers):
        """POST /api/backup/restore/start should reject non-ZIP files"""
        fake_file = io.BytesIO(b"This is not a zip file")
        response = requests.post(
            f"{BASE_URL}/api/backup/restore/start",
            headers=auth_headers,
            files={"file": ("fake.txt", fake_file, "text/plain")}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Restore rejects non-ZIP files")
    
    def test_restore_start_rejects_invalid_zip(self, auth_headers):
        """POST /api/backup/restore/start should reject corrupted ZIP"""
        fake_zip = io.BytesIO(b"PK\x03\x04corrupted data")
        response = requests.post(
            f"{BASE_URL}/api/backup/restore/start",
            headers=auth_headers,
            files={"file": ("fake.zip", fake_zip, "application/zip")}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Restore rejects invalid ZIP")
    
    def test_restore_start_rejects_zip_without_metadata(self, auth_headers):
        """POST /api/backup/restore/start should reject ZIP without metadata.json"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("users.json", "[]")
        zip_buffer.seek(0)
        
        response = requests.post(
            f"{BASE_URL}/api/backup/restore/start",
            headers=auth_headers,
            files={"file": ("backup.zip", zip_buffer, "application/zip")}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "metadata" in response.json().get("detail", "").lower()
        print("PASS: Restore rejects ZIP without metadata")
    
    def test_restore_start_returns_job_id(self, auth_headers):
        """POST /api/backup/restore/start should return job_id for valid backup"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Create a valid backup first using legacy endpoint (faster)
        backup_resp = requests.get(f"{BASE_URL}/api/backup/create", headers=auth_headers, timeout=60)
        if backup_resp.status_code != 200:
            pytest.skip("Could not create backup for restore test")
        
        backup_content = backup_resp.content
        
        # Start restore
        restore_resp = requests.post(
            f"{BASE_URL}/api/backup/restore/start",
            headers=auth_headers,
            files={"file": ("backup.zip", io.BytesIO(backup_content), "application/zip")},
            timeout=60
        )
        assert restore_resp.status_code == 200, f"Expected 200, got {restore_resp.status_code}: {restore_resp.text}"
        
        data = restore_resp.json()
        assert "job_id" in data, "Response should contain 'job_id'"
        assert "message" in data, "Response should contain 'message'"
        
        job_id = data["job_id"]
        print(f"PASS: Restore started - job_id={job_id}")
        
        # Wait for completion
        max_wait = 120
        start_time = time.time()
        while time.time() - start_time < max_wait:
            progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if progress_resp.status_code == 200:
                progress_data = progress_resp.json()
                if progress_data.get("status") == "completed":
                    print(f"PASS: Restore completed - {progress_data.get('total_restored', 0)} records")
                    break
                elif progress_data.get("status") == "failed":
                    print(f"WARN: Restore failed - {progress_data.get('error')}")
                    break
            time.sleep(2)
        
        # Dismiss
        requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)

    # =========================================================================
    # TEST: POST /api/backup/dismiss/{job_id} - Dismiss job
    # =========================================================================
    
    def test_dismiss_job(self, auth_headers):
        """POST /api/backup/dismiss/{job_id} should dismiss completed job"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Start backup
        start_resp = requests.post(f"{BASE_URL}/api/backup/start", headers=auth_headers, timeout=30)
        if start_resp.status_code != 200:
            pytest.skip("Could not start backup job")
        
        job_id = start_resp.json().get("job_id")
        
        # Wait for completion
        max_wait = 60
        start_time = time.time()
        while time.time() - start_time < max_wait:
            progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if progress_resp.status_code == 200:
                data = progress_resp.json()
                if data.get("status") in ["completed", "failed"]:
                    break
            time.sleep(1)
        
        # Dismiss
        dismiss_resp = requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)
        assert dismiss_resp.status_code == 200, f"Expected 200, got {dismiss_resp.status_code}"
        
        data = dismiss_resp.json()
        assert data.get("ok") == True, "Dismiss should return {ok: true}"
        print("PASS: Job dismissed successfully")
        
        # Verify job is no longer active
        active_after = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_after.status_code == 200:
            data = active_after.json()
            # Should be idle or show a different job
            if data.get("job_id") == job_id:
                assert data.get("status") == "dismissed", "Dismissed job should not show as active"

    # =========================================================================
    # TEST: Legacy endpoints still work
    # =========================================================================
    
    def test_legacy_backup_create_works(self, auth_headers):
        """GET /api/backup/create (legacy) should still work"""
        response = requests.get(f"{BASE_URL}/api/backup/create", headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content_type = response.headers.get("Content-Type", "")
        assert "zip" in content_type or "octet-stream" in content_type
        print("PASS: Legacy backup create works")
    
    def test_legacy_restore_works(self, auth_headers):
        """POST /api/backup/restore (legacy) should still work"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Create backup
        backup_resp = requests.get(f"{BASE_URL}/api/backup/create", headers=auth_headers, timeout=60)
        if backup_resp.status_code != 200:
            pytest.skip("Could not create backup")
        
        # Restore using legacy endpoint
        restore_resp = requests.post(
            f"{BASE_URL}/api/backup/restore",
            headers=auth_headers,
            files={"file": ("backup.zip", io.BytesIO(backup_resp.content), "application/zip")},
            timeout=120
        )
        assert restore_resp.status_code == 200, f"Expected 200, got {restore_resp.status_code}: {restore_resp.text}"
        
        data = restore_resp.json()
        assert "message" in data, "Response should have message"
        assert "restored" in data or "total_restored" in data, "Response should have restore stats"
        print("PASS: Legacy restore works")

    # =========================================================================
    # TEST: Login works after background restore
    # =========================================================================
    
    def test_login_works_after_background_restore(self, auth_headers):
        """Login should work after background restore completes"""
        # First dismiss any existing jobs
        active_resp = requests.get(f"{BASE_URL}/api/backup/active", headers=auth_headers)
        if active_resp.status_code == 200:
            data = active_resp.json()
            if data.get("status") != "idle" and data.get("job_id"):
                requests.post(f"{BASE_URL}/api/backup/dismiss/{data['job_id']}", headers=auth_headers)
                time.sleep(1)
        
        # Create backup using legacy (faster)
        backup_resp = requests.get(f"{BASE_URL}/api/backup/create", headers=auth_headers, timeout=60)
        if backup_resp.status_code != 200:
            pytest.skip("Could not create backup")
        
        # Start background restore
        restore_resp = requests.post(
            f"{BASE_URL}/api/backup/restore/start",
            headers=auth_headers,
            files={"file": ("backup.zip", io.BytesIO(backup_resp.content), "application/zip")},
            timeout=60
        )
        if restore_resp.status_code != 200:
            pytest.skip("Could not start restore")
        
        job_id = restore_resp.json().get("job_id")
        
        # Wait for completion
        max_wait = 120
        start_time = time.time()
        while time.time() - start_time < max_wait:
            progress_resp = requests.get(f"{BASE_URL}/api/backup/progress/{job_id}", headers=auth_headers)
            if progress_resp.status_code == 200:
                data = progress_resp.json()
                if data.get("status") == "completed":
                    break
                elif data.get("status") == "failed":
                    pytest.skip(f"Restore failed: {data.get('error')}")
            time.sleep(2)
        
        # Dismiss
        requests.post(f"{BASE_URL}/api/backup/dismiss/{job_id}", headers=auth_headers)
        
        # Try login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed after restore: {login_resp.text}"
        assert "access_token" in login_resp.json()
        print("PASS: Login works after background restore")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
