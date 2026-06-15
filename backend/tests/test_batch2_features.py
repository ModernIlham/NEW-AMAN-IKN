
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Batch 2 Feature Tests - Row Locking, Asset Groups
Testing features:
1. POST /api/assets/lock - Lock row by user
2. POST /api/assets/unlock - Release lock
3. POST /api/assets/heartbeat - Renew lock TTL
4. GET /api/assets/locks - Get all active locks
5. GET /api/assets/groups?activity_id=X - Get grouped assets by same code/name/date/brand/price
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = TEST_ADMIN_PASSWORD

# Test user identifiers
USER1_ID = f"test_user_1_{uuid.uuid4().hex[:8]}"
USER1_NAME = "Test User 1"
USER2_ID = f"test_user_2_{uuid.uuid4().hex[:8]}"
USER2_NAME = "Test User 2"


@pytest.fixture(scope="module")
def session():
    """Shared requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Get auth token for admin user"""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Authentication failed - {resp.text}")


@pytest.fixture(scope="module")
def test_activity_id(session, auth_token):
    """Get an existing activity ID for testing"""
    resp = session.get(f"{BASE_URL}/api/inventory-activities")
    if resp.status_code == 200:
        activities = resp.json()
        if activities:
            # Look for test activity first
            for act in activities:
                if "Test" in act.get("nama_kegiatan", ""):
                    return act["id"]
            # Fall back to first activity
            return activities[0]["id"]
    pytest.skip("No activities found for testing")


@pytest.fixture(scope="module")
def test_asset_id(session, auth_token, test_activity_id):
    """Get an existing asset ID for testing"""
    resp = session.get(f"{BASE_URL}/api/assets", params={"activity_id": test_activity_id, "page_size": 1})
    if resp.status_code == 200:
        items = resp.json().get("items", [])
        if items:
            return items[0]["id"]
    pytest.skip("No assets found for testing")


class TestRowLocking:
    """Tests for row locking endpoints (concurrent editing protection)"""

    def test_lock_asset_first_user(self, session, test_asset_id):
        """Test: First user can lock an asset"""
        resp = session.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER1_ID, "x-user-name": USER1_NAME}
        )
        assert resp.status_code == 200, f"Lock request failed: {resp.text}"
        data = resp.json()
        assert data.get("locked") == True, "First user should be able to lock"
        print(f"✓ First user ({USER1_NAME}) locked asset {test_asset_id[:8]}...")

    def test_lock_asset_second_user_blocked(self, session, test_asset_id):
        """Test: Second user is blocked from locking same asset"""
        resp = session.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER2_ID, "x-user-name": USER2_NAME}
        )
        assert resp.status_code == 200, f"Lock request failed: {resp.text}"
        data = resp.json()
        assert data.get("locked") == False, "Second user should be blocked"
        assert data.get("locked_by") == USER1_NAME, f"Should show locked_by as '{USER1_NAME}'"
        assert data.get("locked_by_id") == USER1_ID, "Should include locked_by_id"
        print(f"✓ Second user ({USER2_NAME}) blocked, asset locked by {data.get('locked_by')}")

    def test_heartbeat_renews_lock_for_owner(self, session, test_asset_id):
        """Test: Heartbeat renews lock for the owner"""
        resp = session.post(
            f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER1_ID, "x-user-name": USER1_NAME}
        )
        assert resp.status_code == 200, f"Heartbeat failed: {resp.text}"
        data = resp.json()
        assert data.get("renewed") == True, "Owner should be able to renew lock"
        print(f"✓ Heartbeat renewed lock for {USER1_NAME}")

    def test_heartbeat_fails_for_non_owner(self, session, test_asset_id):
        """Test: Heartbeat fails for non-owner"""
        resp = session.post(
            f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER2_ID, "x-user-name": USER2_NAME}
        )
        assert resp.status_code == 200, f"Heartbeat request failed: {resp.text}"
        data = resp.json()
        assert data.get("renewed") == False, "Non-owner should not renew lock"
        print(f"✓ Heartbeat rejected for non-owner {USER2_NAME}")

    def test_get_all_locks(self, session, test_asset_id):
        """Test: Get all active locks returns locked assets"""
        resp = session.get(f"{BASE_URL}/api/assets/locks")
        assert resp.status_code == 200, f"Get locks failed: {resp.text}"
        data = resp.json()
        assert "locks" in data, "Response should contain 'locks' key"
        locks = data["locks"]
        assert isinstance(locks, dict), "Locks should be a dictionary"
        # Check if our test asset is in locks
        if test_asset_id in locks:
            lock_info = locks[test_asset_id]
            assert lock_info.get("user_name") == USER1_NAME
            assert lock_info.get("user_id") == USER1_ID
            print(f"✓ Active locks: {len(locks)} found, test asset locked by {lock_info.get('user_name')}")
        else:
            print(f"✓ Active locks retrieved: {len(locks)} found")

    def test_unlock_asset_by_owner(self, session, test_asset_id):
        """Test: Owner can unlock their asset"""
        resp = session.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER1_ID}
        )
        assert resp.status_code == 200, f"Unlock failed: {resp.text}"
        data = resp.json()
        assert data.get("unlocked") == True, "Owner should be able to unlock"
        print(f"✓ Asset unlocked by {USER1_NAME}")

    def test_unlock_does_not_error_for_non_owner(self, session, test_asset_id):
        """Test: Unlock by non-owner doesn't error (no-op)"""
        resp = session.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER2_ID}
        )
        assert resp.status_code == 200, f"Unlock request should not error: {resp.text}"
        data = resp.json()
        assert data.get("unlocked") == True, "Should return unlocked=true even if wasn't locked"
        print("✓ Unlock by non-owner handled gracefully")

    def test_relocking_after_unlock(self, session, test_asset_id):
        """Test: After unlock, any user can lock again"""
        # Second user should now be able to lock
        resp = session.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER2_ID, "x-user-name": USER2_NAME}
        )
        assert resp.status_code == 200, f"Re-lock failed: {resp.text}"
        data = resp.json()
        assert data.get("locked") == True, "After unlock, second user should lock"
        print(f"✓ After unlock, {USER2_NAME} successfully locked asset")
        
        # Cleanup: unlock
        session.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": test_asset_id},
            headers={"x-user-id": USER2_ID}
        )


class TestAssetGroups:
    """Tests for asset grouping endpoint (barang serupa)"""

    def test_get_asset_groups_endpoint(self, session, test_activity_id):
        """Test: Asset groups endpoint returns valid response"""
        resp = session.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": test_activity_id})
        assert resp.status_code == 200, f"Get groups failed: {resp.text}"
        data = resp.json()
        assert "groups" in data, "Response should contain 'groups' key"
        assert "total_groups" in data, "Response should contain 'total_groups' key"
        assert isinstance(data["groups"], list), "Groups should be a list"
        assert isinstance(data["total_groups"], int), "total_groups should be an integer"
        print(f"✓ Asset groups endpoint returned {data['total_groups']} groups")

    def test_asset_groups_structure(self, session, test_activity_id):
        """Test: Asset groups have correct structure"""
        resp = session.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": test_activity_id})
        assert resp.status_code == 200
        groups = resp.json().get("groups", [])
        
        if len(groups) > 0:
            group = groups[0]
            # Check expected fields
            expected_fields = ["asset_code", "asset_name", "count", "asset_ids", "NUPs"]
            for field in expected_fields:
                assert field in group, f"Group should have '{field}' field"
            
            # Count should be >= 2 (only groups with duplicates)
            assert group["count"] >= 2, "Group count should be >= 2 (only groups with duplicates)"
            
            # asset_ids should be a list
            assert isinstance(group["asset_ids"], list), "asset_ids should be a list"
            assert len(group["asset_ids"]) == group["count"], "asset_ids length should match count"
            
            # NUPs should be a list
            assert isinstance(group["NUPs"], list), "NUPs should be a list"
            
            print(f"✓ Group structure valid: {group['asset_name']} has {group['count']} items")
        else:
            print("✓ No duplicate groups found (expected if no duplicate assets exist)")

    def test_asset_groups_without_activity_id(self, session):
        """Test: Asset groups endpoint works without activity_id"""
        resp = session.get(f"{BASE_URL}/api/assets/groups")
        assert resp.status_code == 200, f"Get groups without activity_id failed: {resp.text}"
        data = resp.json()
        assert "groups" in data
        print(f"✓ Groups endpoint works without activity_id filter: {data['total_groups']} groups")


class TestTableColumnsAPI:
    """Verify API returns all required fields for new table column structure"""

    def test_assets_list_contains_required_fields(self, session, test_activity_id):
        """Test: Assets API returns fields needed for Identitas Barang and Nama Barang columns"""
        resp = session.get(f"{BASE_URL}/api/assets", params={"activity_id": test_activity_id, "page_size": 5})
        assert resp.status_code == 200
        items = resp.json().get("items", [])
        
        if len(items) > 0:
            asset = items[0]
            # Fields for Identitas Barang column
            assert "asset_code" in asset, "asset_code required for Identitas Barang"
            assert "NUP" in asset, "NUP required for Identitas Barang"
            assert "category" in asset, "category required for Identitas Barang"
            
            # Fields for Nama Barang column
            assert "asset_name" in asset, "asset_name required for Nama Barang"
            assert "brand" in asset, "brand required for Nama Barang"
            assert "model" in asset, "model required for Nama Barang"
            
            # Other table columns
            assert "department" in asset, "department required"
            assert "location" in asset, "location required"
            assert "purchase_price" in asset, "purchase_price required"
            assert "condition" in asset, "condition required"
            assert "status" in asset, "status required"
            assert "stiker_status" in asset, "stiker_status required"
            assert "inventory_status" in asset, "inventory_status required"
            
            print("✓ All required fields present for table columns")
        else:
            print("✓ No assets to verify, but endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
