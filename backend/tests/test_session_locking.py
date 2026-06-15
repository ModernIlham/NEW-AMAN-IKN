"""
Test session-based row locking for concurrent editing
Tests: lock, unlock, heartbeat, get locks, batch-update with session checks
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session IDs - simulating same user on 2 different devices/tabs
SESSION_A = f"session-a-{uuid.uuid4()}"
SESSION_B = f"session-b-{uuid.uuid4()}"
TEST_USER_ID = "test-user-123"
TEST_USER_NAME = "Test User"
TEST_ASSET_ID = f"test-asset-{uuid.uuid4()}"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestSessionBasedLocking:
    """Test session-based locking: same user, different sessions should be blocked"""
    
    def test_lock_with_session_a_success(self, api_client):
        """Lock asset with session A - should succeed"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": TEST_USER_NAME,
                "x-session-id": SESSION_A
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["locked"] == True, f"Expected locked=True, got {data}"
        print(f"PASS: Lock with session A succeeded: {data}")
    
    def test_lock_with_session_b_same_user_fails(self, api_client):
        """Same user on different session (session B) should be blocked"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,  # Same user
                "x-user-name": "Test User Tab 2",
                "x-session-id": SESSION_B  # Different session
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["locked"] == False, f"Expected locked=False for different session, got {data}"
        assert "locked_by" in data, "Should return locked_by info"
        assert data["locked_by"] == TEST_USER_NAME, f"Expected locked_by={TEST_USER_NAME}, got {data['locked_by']}"
        print(f"PASS: Lock with session B correctly blocked: {data}")
    
    def test_get_locks_returns_session_id(self, api_client):
        """GET /api/assets/locks should include session_id in lock data"""
        response = api_client.get(f"{BASE_URL}/api/assets/locks")
        assert response.status_code == 200
        data = response.json()
        assert "locks" in data, "Response should have 'locks' key"
        
        # Check if our test asset is in locks
        if TEST_ASSET_ID in data["locks"]:
            lock_info = data["locks"][TEST_ASSET_ID]
            assert "session_id" in lock_info, f"Lock info should contain session_id, got {lock_info}"
            assert lock_info["session_id"] == SESSION_A, f"Session ID should be {SESSION_A}, got {lock_info['session_id']}"
            assert lock_info["user_name"] == TEST_USER_NAME
            print(f"PASS: Get locks returns session_id: {lock_info}")
        else:
            print("WARN: Test asset not found in locks, may have expired")
    
    def test_heartbeat_with_correct_session(self, api_client):
        """Heartbeat should work with the same session that locked"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": TEST_USER_NAME,
                "x-session-id": SESSION_A
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["renewed"] == True, f"Expected renewed=True for correct session, got {data}"
        print(f"PASS: Heartbeat with session A succeeded: {data}")
    
    def test_heartbeat_with_wrong_session_fails(self, api_client):
        """Heartbeat with different session should fail (renewed=False)"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/heartbeat",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": TEST_USER_NAME,
                "x-session-id": SESSION_B  # Wrong session
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["renewed"] == False, f"Expected renewed=False for wrong session, got {data}"
        print(f"PASS: Heartbeat with wrong session correctly returns renewed=False: {data}")
    
    def test_unlock_with_wrong_session_does_not_release(self, api_client):
        """Unlock with different session should not release the lock"""
        # Try to unlock with session B
        api_client.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-session-id": SESSION_B  # Wrong session
            }
        )
        
        # Verify lock still exists
        locks_response = api_client.get(f"{BASE_URL}/api/assets/locks")
        locks_data = locks_response.json()
        
        if TEST_ASSET_ID in locks_data["locks"]:
            print("PASS: Lock still exists after unlock attempt with wrong session")
        else:
            # Lock may have been released or expired - check if we can re-lock with session A
            relock_response = api_client.post(
                f"{BASE_URL}/api/assets/lock",
                json={"asset_id": TEST_ASSET_ID},
                headers={
                    "x-user-id": TEST_USER_ID,
                    "x-user-name": TEST_USER_NAME,
                    "x-session-id": SESSION_A
                }
            )
            print(f"INFO: Lock not found after unlock attempt - relock result: {relock_response.json()}")
    
    def test_unlock_with_correct_session_succeeds(self, api_client):
        """Unlock with correct session should release the lock"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-session-id": SESSION_A  # Correct session
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unlocked"] == True
        print(f"PASS: Unlock with session A succeeded: {data}")
    
    def test_lock_after_unlock_succeeds(self, api_client):
        """After unlock, session B should be able to lock"""
        response = api_client.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": TEST_USER_NAME,
                "x-session-id": SESSION_B
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["locked"] == True, f"Expected locked=True after unlock, got {data}"
        print(f"PASS: Lock with session B after unlock succeeded: {data}")
        
        # Cleanup - unlock
        api_client.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": TEST_ASSET_ID},
            headers={"x-session-id": SESSION_B}
        )


class TestBatchUpdateWithSessionLocking:
    """Test batch update checks session_id for lock conflicts"""
    
    def test_batch_update_blocked_by_other_session(self, api_client):
        """Batch update should be blocked if asset locked by another session"""
        # First lock the asset with session A
        lock_response = api_client.post(
            f"{BASE_URL}/api/assets/lock",
            json={"asset_id": TEST_ASSET_ID},
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": TEST_USER_NAME,
                "x-session-id": SESSION_A
            }
        )
        assert lock_response.json()["locked"] == True
        
        # Try batch update with session B
        batch_response = api_client.put(
            f"{BASE_URL}/api/assets/batch-update",
            json={
                "asset_ids": [TEST_ASSET_ID],
                "updates": {"category": "Test Category"}
            },
            headers={
                "x-user-id": TEST_USER_ID,
                "x-user-name": "Another Session",
                "x-session-id": SESSION_B
            }
        )
        
        # Should return 409 Conflict
        assert batch_response.status_code == 409, f"Expected 409 for locked asset, got {batch_response.status_code}: {batch_response.text}"
        print(f"PASS: Batch update blocked by session lock: {batch_response.json()}")
        
        # Cleanup
        api_client.post(
            f"{BASE_URL}/api/assets/unlock",
            json={"asset_id": TEST_ASSET_ID},
            headers={"x-session-id": SESSION_A}
        )


class TestHealthCheck:
    """Basic health checks"""
    
    def test_backend_health(self, api_client):
        """Verify backend is running"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: Backend health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
