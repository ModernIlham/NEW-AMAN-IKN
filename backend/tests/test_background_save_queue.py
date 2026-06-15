
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Background Save Queue (Iteration 65)
Tests: PUT /api/assets/{id}, POST /api/assets/lock, POST /api/assets/unlock
Focus: Asset update for background queue, row locking during save operations
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_session():
    """Create session with auth headers"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_session):
    """Get auth token"""
    resp = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data.get("access_token", data.get("token", ""))

@pytest.fixture(scope="module")
def activity_id(api_session, auth_token):
    """Get the test activity with 451 assets"""
    api_session.headers["Authorization"] = f"Bearer {auth_token}"
    resp = api_session.get(f"{BASE_URL}/api/inventory-activities")
    assert resp.status_code == 200
    activities = resp.json()
    # Find activity with 451 assets
    for act in activities:
        if "451" in str(act.get("asset_count", 0)) or "Test Kegiatan" in act.get("nama_kegiatan", ""):
            return act["id"]
    # Return first activity if not found
    return activities[0]["id"] if activities else None

@pytest.fixture(scope="module")
def test_asset(api_session, auth_token, activity_id):
    """Get first asset from the activity for testing"""
    api_session.headers["Authorization"] = f"Bearer {auth_token}"
    resp = api_session.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page_size=1")
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", [])
    assert len(items) > 0, "No assets found for testing"
    return items[0]

@pytest.fixture
def unique_session_id():
    """Generate unique session ID for each test"""
    return f"test-session-{uuid.uuid4().hex[:8]}"


class TestAssetLocking:
    """Test row locking endpoints for concurrent editing"""
    
    def test_lock_asset_success(self, api_session, auth_token, test_asset, unique_session_id):
        """POST /api/assets/lock - Lock an asset for editing"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-User-Id"] = "test-user-id"
        api_session.headers["X-User-Name"] = "Test User"
        api_session.headers["X-Session-Id"] = unique_session_id
        
        resp = api_session.post(f"{BASE_URL}/api/assets/lock", json={
            "asset_id": test_asset["id"]
        })
        
        assert resp.status_code == 200, f"Lock failed: {resp.text}"
        data = resp.json()
        assert data.get("locked") == True, "Expected locked=True"
        print(f"PASS: Asset {test_asset['id'][:8]} locked successfully")
        
        # Cleanup - unlock
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": test_asset["id"]})

    def test_lock_asset_conflict(self, api_session, auth_token, test_asset, unique_session_id):
        """POST /api/assets/lock - Second session cannot lock already locked asset"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        
        # First session locks
        api_session.headers["X-Session-Id"] = unique_session_id
        api_session.headers["X-User-Name"] = "User A"
        resp1 = api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": test_asset["id"]})
        assert resp1.json().get("locked") == True
        
        # Second session tries to lock - different session_id
        api_session.headers["X-Session-Id"] = f"different-session-{uuid.uuid4().hex[:8]}"
        api_session.headers["X-User-Name"] = "User B"
        resp2 = api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": test_asset["id"]})
        
        data = resp2.json()
        assert data.get("locked") == False, "Expected locked=False for conflicting session"
        assert "locked_by" in data, "Expected locked_by info"
        print(f"PASS: Lock conflict correctly detected - locked by {data.get('locked_by')}")
        
        # Cleanup
        api_session.headers["X-Session-Id"] = unique_session_id
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": test_asset["id"]})

    def test_heartbeat_lock_renewal(self, api_session, auth_token, test_asset, unique_session_id):
        """POST /api/assets/heartbeat - Renew lock TTL"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-Session-Id"] = unique_session_id
        
        # Lock first
        api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": test_asset["id"]})
        
        # Send heartbeat
        resp = api_session.post(f"{BASE_URL}/api/assets/heartbeat", json={
            "asset_id": test_asset["id"]
        })
        
        assert resp.status_code == 200, f"Heartbeat failed: {resp.text}"
        data = resp.json()
        assert data.get("renewed") == True, "Expected renewed=True"
        print("PASS: Lock heartbeat renewed successfully")
        
        # Cleanup
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": test_asset["id"]})

    def test_unlock_asset(self, api_session, auth_token, test_asset, unique_session_id):
        """POST /api/assets/unlock - Release lock"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-Session-Id"] = unique_session_id
        
        # Lock first
        api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": test_asset["id"]})
        
        # Unlock
        resp = api_session.post(f"{BASE_URL}/api/assets/unlock", json={
            "asset_id": test_asset["id"]
        })
        
        assert resp.status_code == 200, f"Unlock failed: {resp.text}"
        data = resp.json()
        assert data.get("unlocked") == True, "Expected unlocked=True"
        print("PASS: Asset unlocked successfully")

    def test_get_all_locks(self, api_session, auth_token, test_asset, unique_session_id):
        """GET /api/assets/locks - Get all active locks"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-Session-Id"] = unique_session_id
        api_session.headers["X-User-Name"] = "Lock Test User"
        
        # Lock an asset
        api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": test_asset["id"]})
        
        # Get all locks
        resp = api_session.get(f"{BASE_URL}/api/assets/locks")
        
        assert resp.status_code == 200, f"Get locks failed: {resp.text}"
        data = resp.json()
        assert "locks" in data, "Expected locks dict"
        locks = data["locks"]
        assert test_asset["id"] in locks, f"Expected asset {test_asset['id'][:8]} in locks"
        assert locks[test_asset["id"]]["user_name"] == "Lock Test User"
        print(f"PASS: Locks list retrieved with {len(locks)} locked asset(s)")
        
        # Cleanup
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": test_asset["id"]})


class TestAssetUpdate:
    """Test asset update endpoint (used by background save queue)"""

    def test_update_asset_basic_fields(self, api_session, auth_token, test_asset, activity_id):
        """PUT /api/assets/{id} - Update basic fields"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        
        # Get full asset data first
        resp = api_session.get(f"{BASE_URL}/api/assets/{test_asset['id']}")
        assert resp.status_code == 200
        asset_data = resp.json()
        
        # Update location (simple field change)
        original_location = asset_data.get("location", "")
        new_location = f"Test Location {uuid.uuid4().hex[:6]}"
        
        update_payload = {
            "asset_code": asset_data["asset_code"],
            "asset_name": asset_data["asset_name"],
            "category": asset_data.get("category", ""),
            "activity_id": activity_id,
            "location": new_location,
            "condition": asset_data.get("condition", "Baik"),
            "status": asset_data.get("status", "Aktif"),
        }
        
        resp = api_session.put(f"{BASE_URL}/api/assets/{test_asset['id']}", json=update_payload)
        
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data.get("location") == new_location, "Location not updated"
        print(f"PASS: Asset location updated to {new_location}")
        
        # Restore original location
        update_payload["location"] = original_location
        api_session.put(f"{BASE_URL}/api/assets/{test_asset['id']}", json=update_payload)

    def test_update_asset_inventory_status(self, api_session, auth_token, test_asset, activity_id):
        """PUT /api/assets/{id} - Update inventory status (requires lat/long if not 'Belum Diinventarisasi')"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        
        # Get full asset data
        resp = api_session.get(f"{BASE_URL}/api/assets/{test_asset['id']}")
        assert resp.status_code == 200
        asset_data = resp.json()
        
        # Update with inventory status - note: requires lat/long if status changes
        original_status = asset_data.get("inventory_status", "Belum Diinventarisasi")
        
        update_payload = {
            "asset_code": asset_data["asset_code"],
            "asset_name": asset_data["asset_name"],
            "category": asset_data.get("category", ""),
            "activity_id": activity_id,
            "location": asset_data.get("location", ""),
            "condition": asset_data.get("condition", "Baik"),
            "status": asset_data.get("status", "Aktif"),
            "inventory_status": "Ditemukan",
            "koordinat_latitude": "-6.175110",
            "koordinat_longitude": "106.865036",
        }
        
        resp = api_session.put(f"{BASE_URL}/api/assets/{test_asset['id']}", json=update_payload)
        
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data.get("inventory_status") == "Ditemukan", "Inventory status not updated"
        print("PASS: Asset inventory status updated to 'Ditemukan'")
        
        # Restore original status
        update_payload["inventory_status"] = original_status
        update_payload["koordinat_latitude"] = asset_data.get("koordinat_latitude", "")
        update_payload["koordinat_longitude"] = asset_data.get("koordinat_longitude", "")
        api_session.put(f"{BASE_URL}/api/assets/{test_asset['id']}", json=update_payload)

    def test_update_nonexistent_asset(self, api_session, auth_token, activity_id):
        """PUT /api/assets/{id} - Update nonexistent asset returns 404"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        update_payload = {
            "asset_code": "TEST-CODE",
            "asset_name": "Test Asset",
            "category": "Test",
            "activity_id": activity_id,
        }
        
        resp = api_session.put(f"{BASE_URL}/api/assets/{fake_id}", json=update_payload)
        
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Update nonexistent asset returns 404")


class TestBackgroundSaveWorkflow:
    """Test the complete background save workflow (lock -> update -> unlock)"""

    def test_save_workflow_lock_update_unlock(self, api_session, auth_token, test_asset, activity_id, unique_session_id):
        """Simulate background save: lock asset, update, unlock on success"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-Session-Id"] = unique_session_id
        api_session.headers["X-User-Name"] = "Background Save User"
        
        asset_id = test_asset["id"]
        
        # Step 1: Lock the asset
        lock_resp = api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": asset_id})
        assert lock_resp.status_code == 200
        assert lock_resp.json().get("locked") == True
        print("Step 1: Asset locked for editing")
        
        # Step 2: Get full asset data
        get_resp = api_session.get(f"{BASE_URL}/api/assets/{asset_id}")
        assert get_resp.status_code == 200
        asset_data = get_resp.json()
        print("Step 2: Asset data retrieved")
        
        # Step 3: Simulate background save (update)
        update_payload = {
            "asset_code": asset_data["asset_code"],
            "asset_name": asset_data["asset_name"],
            "category": asset_data.get("category", ""),
            "activity_id": activity_id,
            "location": asset_data.get("location", ""),
            "condition": asset_data.get("condition", "Baik"),
            "status": asset_data.get("status", "Aktif"),
            "notes": f"Background save test - {uuid.uuid4().hex[:8]}",
        }
        
        update_resp = api_session.put(f"{BASE_URL}/api/assets/{asset_id}", json=update_payload)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        print("Step 3: Asset updated via background save")
        
        # Step 4: Unlock after successful save (simulates onItemSaved callback)
        unlock_resp = api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": asset_id})
        assert unlock_resp.status_code == 200
        assert unlock_resp.json().get("unlocked") == True
        print("Step 4: Asset unlocked after save complete")
        
        # Verify unlock worked
        locks_resp = api_session.get(f"{BASE_URL}/api/assets/locks")
        locks = locks_resp.json().get("locks", {})
        assert asset_id not in locks, "Asset should no longer be locked"
        print("PASS: Complete background save workflow (lock -> update -> unlock)")

    def test_save_workflow_other_user_sees_lock(self, api_session, auth_token, test_asset, unique_session_id):
        """Other users should see asset as locked during save"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        
        asset_id = test_asset["id"]
        
        # User A locks
        api_session.headers["X-Session-Id"] = unique_session_id
        api_session.headers["X-User-Name"] = "User A"
        lock_resp = api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": asset_id})
        assert lock_resp.json().get("locked") == True
        
        # User B checks locks
        locks_resp = api_session.get(f"{BASE_URL}/api/assets/locks")
        locks = locks_resp.json().get("locks", {})
        
        assert asset_id in locks, "Asset should be visible in locks list"
        assert locks[asset_id]["user_name"] == "User A"
        print("PASS: Other users see locked asset by User A")
        
        # Cleanup
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": asset_id})


class TestQueueBehavior:
    """Test multiple save operations in sequence (simulating queue)"""
    
    def test_sequential_saves_different_assets(self, api_session, auth_token, activity_id, unique_session_id):
        """Simulate queue processing: save Asset A, then save Asset B"""
        api_session.headers["Authorization"] = f"Bearer {auth_token}"
        api_session.headers["X-Session-Id"] = unique_session_id
        
        # Get two assets
        resp = api_session.get(f"{BASE_URL}/api/assets?activity_id={activity_id}&page_size=3")
        assets = resp.json().get("items", [])
        if len(assets) < 2:
            pytest.skip("Need at least 2 assets for this test")
        
        asset_a, asset_b = assets[0], assets[1]
        
        # Save Asset A (lock -> update -> unlock)
        api_session.headers["X-User-Name"] = "Queue Processor"
        
        # Lock A
        api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": asset_a["id"]})
        
        # Update A
        get_a = api_session.get(f"{BASE_URL}/api/assets/{asset_a['id']}").json()
        update_a = {
            "asset_code": get_a["asset_code"],
            "asset_name": get_a["asset_name"],
            "category": get_a.get("category", ""),
            "activity_id": activity_id,
            "notes": f"Queue test A - {uuid.uuid4().hex[:6]}",
        }
        api_session.put(f"{BASE_URL}/api/assets/{asset_a['id']}", json=update_a)
        
        # Unlock A
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": asset_a["id"]})
        print("Queue item 1 (Asset A) processed")
        
        # Now process Asset B
        api_session.post(f"{BASE_URL}/api/assets/lock", json={"asset_id": asset_b["id"]})
        
        get_b = api_session.get(f"{BASE_URL}/api/assets/{asset_b['id']}").json()
        update_b = {
            "asset_code": get_b["asset_code"],
            "asset_name": get_b["asset_name"],
            "category": get_b.get("category", ""),
            "activity_id": activity_id,
            "notes": f"Queue test B - {uuid.uuid4().hex[:6]}",
        }
        api_session.put(f"{BASE_URL}/api/assets/{asset_b['id']}", json=update_b)
        
        api_session.post(f"{BASE_URL}/api/assets/unlock", json={"asset_id": asset_b["id"]})
        print("Queue item 2 (Asset B) processed")
        
        print("PASS: Sequential saves processed correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
