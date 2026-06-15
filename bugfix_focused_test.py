#!/usr/bin/env python3
"""
FOCUSED BUGFIX ROUND Backend Testing
Testing the most critical bug fixes with fresh admin credentials
"""

import asyncio
import json
import base64
import zipfile
import io
import uuid
from datetime import datetime, timezone
import aiohttp
import motor.motor_asyncio

# Configuration
BASE_URL = "https://asset-crud-auth.preview.emergentagent.com/api"
ADMIN_EMAIL = "bugfix_admin_test2"
ADMIN_PASSWORD = "BugfixTest123"

# Test results tracking
test_results = []

def log_test(test_name, status, details=""):
    """Log test result"""
    result = {
        "test": test_name,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    status_icon = "✅" if status == "PASS" else "❌"
    print(f"{status_icon} {test_name}: {status}")
    if details:
        print(f"   Details: {details}")

async def get_auth_token():
    """Get admin authentication token"""
    async with aiohttp.ClientSession() as session:
        login_data = {
            "username": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        async with session.post(f"{BASE_URL}/auth/login", json=login_data) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
            else:
                text = await resp.text()
                raise Exception(f"Login failed: {resp.status} - {text}")

async def get_mongo_client():
    """Get direct MongoDB connection for raw document manipulation"""
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["inventory_db"]
    return client, db

def create_sample_photo():
    """Create a small sample JPEG photo as base64"""
    # Create a minimal 1x1 red pixel JPEG
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x01, 0x00, 0x48, 0x00, 0x48, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x11, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0x02, 0x11, 0x01, 0x03, 0x11, 0x01,
        0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08, 0xFF, 0xC4,
        0x00, 0x14, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xDA, 0x00, 0x0C,
        0x03, 0x01, 0x00, 0x02, 0x11, 0x03, 0x11, 0x00, 0x3F, 0x00, 0x80, 0xFF, 0xD9
    ])
    return f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode()}"

async def test_critical_occ_fix():
    """Test the critical OCC fix for legacy assets"""
    print("\n=== CRITICAL OCC FIX TEST ===")
    
    token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    client, db = await get_mongo_client()
    
    try:
        # Create activity
        async with aiohttp.ClientSession() as session:
            activity_data = {
                "name": f"OCC Test Activity {uuid.uuid4().hex[:8]}",
                "description": "Test activity for OCC testing",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "nomor_surat": f"TEST/OCC/{uuid.uuid4().hex[:6].upper()}",
                "nama_kegiatan": f"OCC Test Activity {uuid.uuid4().hex[:8]}",
                "kode_satker": "123456",
                "nama_satker": "Test Satker"
            }
            async with session.post(f"{BASE_URL}/inventory-activities", json=activity_data, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    text = await resp.text()
                    log_test("OCC-Setup", "FAIL", f"Failed to create activity: {text}")
                    return
                activity = await resp.json()
                activity_id = activity["id"]
        
        # Create asset normally first
        async with aiohttp.ClientSession() as session:
            asset_data = {
                "asset_code": f"OCC{uuid.uuid4().hex[:6].upper()}",
                "NUP": f"NUP{uuid.uuid4().hex[:8]}",
                "asset_name": "OCC Test Asset",
                "category": "Test Category",
                "activity_id": activity_id
            }
            async with session.post(f"{BASE_URL}/assets", json=asset_data, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    text = await resp.text()
                    log_test("OCC-Asset-Create", "FAIL", f"Failed to create asset: {text}")
                    return
                asset = await resp.json()
                asset_id = asset["id"]
                log_test("OCC-Asset-Create", "PASS", f"Created asset {asset_id}")
        
        # Manually remove version field to simulate legacy/restored data
        await db.assets.update_one({"id": asset_id}, {"$unset": {"version": ""}})
        log_test("OCC-Remove-Version", "PASS", "Manually removed version field from asset")
        
        # Try to PATCH this asset with If-Match: 1 - should succeed (this is the critical fix)
        async with aiohttp.ClientSession() as session:
            patch_data = {"asset_name": "Updated Asset Name via OCC Fix"}
            patch_headers = {**headers, "If-Match": "1"}
            async with session.patch(f"{BASE_URL}/assets/{asset_id}", json=patch_data, headers=patch_headers) as resp:
                if resp.status == 200:
                    updated_asset = await resp.json()
                    if updated_asset.get("version") == 2:
                        log_test("OCC-CRITICAL-FIX", "PASS", "✅ CRITICAL: PATCH with If-Match:1 succeeded on legacy asset and bumped version to 2")
                    else:
                        log_test("OCC-CRITICAL-FIX", "FAIL", f"Version not bumped correctly: {updated_asset.get('version')}")
                else:
                    text = await resp.text()
                    log_test("OCC-CRITICAL-FIX", "FAIL", f"❌ CRITICAL: PATCH failed with status {resp.status}: {text}")
        
        # Test regression - normal OCC still works
        async with aiohttp.ClientSession() as session:
            patch_data = {"asset_name": "Stale Update Attempt"}
            patch_headers = {**headers, "If-Match": "1"}  # Stale version
            async with session.patch(f"{BASE_URL}/assets/{asset_id}", json=patch_data, headers=patch_headers) as resp:
                if resp.status == 409:
                    log_test("OCC-Regression", "PASS", "✅ Regression OK: Stale If-Match correctly rejected with 409")
                else:
                    log_test("OCC-Regression", "FAIL", f"Expected 409 but got {resp.status}")
        
    finally:
        client.close()

async def test_critical_backup_restore():
    """Test the critical backup/restore fix"""
    print("\n=== CRITICAL BACKUP/RESTORE FIX TEST ===")
    
    token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Create activity and asset with photo
    async with aiohttp.ClientSession() as session:
        activity_data = {
            "name": f"Backup Test {uuid.uuid4().hex[:8]}",
            "description": "Test activity for backup testing",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "nomor_surat": f"TEST/BACKUP/{uuid.uuid4().hex[:6].upper()}",
            "nama_kegiatan": f"Backup Test {uuid.uuid4().hex[:8]}",
            "kode_satker": "123456",
            "nama_satker": "Test Satker"
        }
        async with session.post(f"{BASE_URL}/inventory-activities", json=activity_data, headers=headers) as resp:
            if resp.status not in [200, 201]:
                text = await resp.text()
                log_test("BACKUP-Setup", "FAIL", f"Failed to create activity: {text}")
                return
            activity = await resp.json()
            activity_id = activity["id"]
            log_test("BACKUP-Setup", "PASS", f"Created activity {activity_id}")
        
        # Create asset with photo
        photo_b64 = create_sample_photo()
        asset_data = {
            "asset_code": f"BACKUP{uuid.uuid4().hex[:6].upper()}",
            "NUP": f"NUP{uuid.uuid4().hex[:8]}",
            "asset_name": "Backup Test Asset",
            "category": "Test Category",
            "activity_id": activity_id,
            "photos": [photo_b64]
        }
        async with session.post(f"{BASE_URL}/assets", json=asset_data, headers=headers) as resp:
            if resp.status not in [200, 201]:
                text = await resp.text()
                log_test("BACKUP-Asset", "FAIL", f"Failed to create asset: {text}")
                return
            asset = await resp.json()
            asset_id = asset["id"]
            log_test("BACKUP-Asset", "PASS", f"Created asset {asset_id} with photo")
    
    # Start backup
    backup_job_id = None
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_URL}/backup/start", headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                log_test("BACKUP-Start", "FAIL", f"Failed to start backup: {text}")
                return
            backup_data = await resp.json()
            backup_job_id = backup_data["job_id"]
            log_test("BACKUP-Start", "PASS", f"Started backup job {backup_job_id}")
        
        # Wait for completion
        max_wait = 60
        wait_time = 0
        while wait_time < max_wait:
            async with session.get(f"{BASE_URL}/backup/progress/{backup_job_id}", headers=headers) as resp:
                if resp.status == 200:
                    progress = await resp.json()
                    if progress["status"] == "completed":
                        log_test("BACKUP-Complete", "PASS", "Backup completed successfully")
                        break
                    elif progress["status"] == "failed":
                        log_test("BACKUP-Complete", "FAIL", f"Backup failed: {progress.get('error', '')}")
                        return
                    else:
                        await asyncio.sleep(2)
                        wait_time += 2
                else:
                    log_test("BACKUP-Progress", "FAIL", f"Failed to get progress: {resp.status}")
                    return
        
        if wait_time >= max_wait:
            log_test("BACKUP-Complete", "FAIL", "Backup timed out")
            return
    
    # Download and inspect backup
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/backup/download/{backup_job_id}", headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                log_test("BACKUP-Download", "FAIL", f"Failed to download backup: {text}")
                return
            backup_zip_data = await resp.read()
            log_test("BACKUP-Download", "PASS", f"Downloaded backup ZIP ({len(backup_zip_data)} bytes)")
    
    # Inspect ZIP for critical fixes
    try:
        zip_buffer = io.BytesIO(backup_zip_data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            zip_contents = zf.namelist()
            
            # Check metadata.json
            if "metadata.json" in zip_contents:
                metadata = json.loads(zf.read("metadata.json"))
                collections = metadata.get("collections", {})
                
                # CRITICAL FIX 1: Check inventory_activities collection (was "activities" before)
                if "inventory_activities" in collections and collections["inventory_activities"] >= 1:
                    log_test("BACKUP-CRITICAL-FIX-1", "PASS", "✅ CRITICAL: inventory_activities collection properly backed up")
                else:
                    log_test("BACKUP-CRITICAL-FIX-1", "FAIL", f"❌ CRITICAL: inventory_activities missing or zero: {collections}")
                
                # CRITICAL FIX 2: Check GridFS files
                if "gridfs_files" in collections and collections["gridfs_files"] >= 1:
                    log_test("BACKUP-CRITICAL-FIX-2", "PASS", "✅ CRITICAL: GridFS files properly backed up")
                else:
                    log_test("BACKUP-CRITICAL-FIX-2", "FAIL", f"❌ CRITICAL: GridFS files missing or zero: {collections}")
            
            # Check actual files exist
            if "inventory_activities.json" in zip_contents:
                log_test("BACKUP-Activities-File", "PASS", "inventory_activities.json exists in backup")
            else:
                log_test("BACKUP-Activities-File", "FAIL", "inventory_activities.json missing from backup")
            
            if "gridfs/manifest.json" in zip_contents:
                log_test("BACKUP-GridFS-File", "PASS", "GridFS manifest exists in backup")
            else:
                log_test("BACKUP-GridFS-File", "FAIL", "GridFS manifest missing from backup")
    
    except Exception as e:
        log_test("BACKUP-Inspect", "FAIL", f"Failed to inspect ZIP: {e}")

async def test_critical_regression():
    """Test critical regression scenarios"""
    print("\n=== CRITICAL REGRESSION TEST ===")
    
    token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Create test activity
    async with aiohttp.ClientSession() as session:
        activity_data = {
            "name": f"Regression Test {uuid.uuid4().hex[:8]}",
            "description": "Test activity for regression testing",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "nomor_surat": f"TEST/REGRESS/{uuid.uuid4().hex[:6].upper()}",
            "nama_kegiatan": f"Regression Test {uuid.uuid4().hex[:8]}",
            "kode_satker": "123456",
            "nama_satker": "Test Satker"
        }
        async with session.post(f"{BASE_URL}/inventory-activities", json=activity_data, headers=headers) as resp:
            if resp.status not in [200, 201]:
                text = await resp.text()
                log_test("REGRESS-Setup", "FAIL", f"Failed to create activity: {text}")
                return
            activity = await resp.json()
            activity_id = activity["id"]
            log_test("REGRESS-Setup", "PASS", f"Created activity {activity_id}")
    
    # Test Idempotency-Key functionality
    idempotency_key = f"test-key-{uuid.uuid4().hex[:8]}"
    asset_data = {
        "asset_code": f"IDEM{uuid.uuid4().hex[:6].upper()}",
        "NUP": f"NUP{uuid.uuid4().hex[:8]}",
        "asset_name": "Idempotency Test Asset",
        "category": "Test Category",
        "activity_id": activity_id
    }
    
    first_asset_id = None
    async with aiohttp.ClientSession() as session:
        # First call with idempotency key
        idem_headers = {**headers, "Idempotency-Key": idempotency_key}
        async with session.post(f"{BASE_URL}/assets", json=asset_data, headers=idem_headers) as resp:
            if resp.status in [200, 201]:
                first_asset = await resp.json()
                first_asset_id = first_asset["id"]
                log_test("REGRESS-Idempotency-1", "PASS", f"First idempotency call succeeded: {first_asset_id}")
            else:
                text = await resp.text()
                log_test("REGRESS-Idempotency-1", "FAIL", f"First call failed: {text}")
                return
        
        # Second call with same idempotency key - should return same asset
        async with session.post(f"{BASE_URL}/assets", json=asset_data, headers=idem_headers) as resp:
            if resp.status in [200, 201]:
                second_asset = await resp.json()
                if second_asset["id"] == first_asset_id:
                    log_test("REGRESS-Idempotency-2", "PASS", "✅ Idempotency working: same asset ID returned")
                else:
                    log_test("REGRESS-Idempotency-2", "FAIL", f"Different asset ID: {second_asset['id']} vs {first_asset_id}")
            else:
                text = await resp.text()
                log_test("REGRESS-Idempotency-2", "FAIL", f"Second call failed: {text}")
    
    # Test assets list includes version field
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/assets?activity_id={activity_id}", headers=headers) as resp:
            if resp.status == 200:
                assets_data = await resp.json()
                items = assets_data.get("items", [])
                if items and "version" in items[0]:
                    log_test("REGRESS-Version-Field", "PASS", f"✅ Assets list includes version field: {items[0]['version']}")
                else:
                    log_test("REGRESS-Version-Field", "FAIL", f"Version field missing: {items[0].keys() if items else 'no items'}")
            else:
                text = await resp.text()
                log_test("REGRESS-Version-Field", "FAIL", f"Failed to get assets list: {text}")

async def main():
    """Run focused BUGFIX tests"""
    print("🚀 Starting FOCUSED BUGFIX ROUND Backend Tests")
    print("=" * 60)
    
    try:
        # Test the three critical fixes
        await test_critical_occ_fix()
        await test_critical_backup_restore()
        await test_critical_regression()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 FOCUSED TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(test_results)
        passed_tests = len([r for r in test_results if r["status"] == "PASS"])
        failed_tests = len([r for r in test_results if r["status"] == "FAIL"])
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Highlight critical results
        critical_tests = [r for r in test_results if "CRITICAL" in r["test"]]
        critical_passed = len([r for r in critical_tests if r["status"] == "PASS"])
        critical_failed = len([r for r in critical_tests if r["status"] == "FAIL"])
        
        print(f"\n🔥 CRITICAL FIXES: {critical_passed}/{len(critical_tests)} PASSED")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in test_results:
                if result["status"] == "FAIL":
                    print(f"  - {result['test']}: {result['details']}")
        
        print("\n" + "=" * 60)
        
        return failed_tests == 0
        
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)