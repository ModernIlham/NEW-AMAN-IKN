"""
Test Suite for Iteration 60: Select All Pages & Batch Update Chunking
Tests:
- User registration & login
- Activity creation
- Asset creation (400+ for chunking test)
- GET /api/assets/all-ids endpoint
- PUT /api/assets/batch-update with chunking (200+ assets)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthAndSetup:
    """Authentication and basic setup tests"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create a test user for this test session"""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "username": f"testuser_{unique_id}@test.com",
            "name": f"TestUser_{unique_id}",
            "password": "testpass123"
        }
    
    @pytest.fixture(scope="class")
    def auth_token(self, test_user):
        """Register and login to get auth token"""
        # First register
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json=test_user)
        if reg_response.status_code not in [200, 201, 400]:  # 400 = already exists
            pytest.fail(f"Registration failed: {reg_response.status_code} - {reg_response.text}")
        
        # Then login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"]
        })
        if login_response.status_code != 200:
            pytest.fail(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        data = login_response.json()
        return data.get("token") or data.get("access_token")
    
    def test_register_user(self, test_user):
        """Test user registration"""
        unique_id = str(uuid.uuid4())[:8]
        new_user = {
            "username": f"newuser_{unique_id}@test.com",
            "name": f"NewUser_{unique_id}",
            "password": "newpass123"
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=new_user)
        assert response.status_code in [200, 201], f"Register failed: {response.text}"
        data = response.json()
        assert "user" in data or "id" in data or "access_token" in data
        print("✓ User registration successful")
    
    def test_login_user(self, test_user, auth_token):
        """Test user login"""
        assert auth_token is not None, "Auth token should be returned"
        print("✓ User login successful, token received")


class TestSelectAllPagesFeature:
    """Test the Select All Pages and batch update functionality"""
    
    @pytest.fixture(scope="class")
    def api_session(self):
        """Create session with headers"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    @pytest.fixture(scope="class")
    def auth_headers(self, api_session):
        """Get auth headers by logging in"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "username": f"chunktest_{unique_id}@test.com",
            "name": f"ChunkTest_{unique_id}",
            "password": "chunk12345"
        }
        
        # Register
        api_session.post(f"{BASE_URL}/api/auth/register", json=user_data)
        
        # Login
        login_resp = api_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": user_data["username"],
            "password": user_data["password"]
        })
        
        if login_resp.status_code != 200:
            pytest.skip(f"Login failed: {login_resp.text}")
        
        data = login_resp.json()
        token = data.get("token") or data.get("access_token")
        user_id = data.get("user", {}).get("id") or data.get("id", "")
        user_name = user_data["name"]
        
        return {
            "Authorization": f"Bearer {token}",
            "X-User-Id": str(user_id),
            "X-User-Name": user_name
        }
    
    @pytest.fixture(scope="class")
    def test_activity(self, api_session, auth_headers):
        """Create a test activity for bulk asset creation"""
        unique_id = str(uuid.uuid4())[:8]
        activity_data = {
            "nama_kegiatan": f"Bulk_Test_Activity_{unique_id}",
            "nomor_surat": f"SR/{unique_id}/2026",
            "tanggal_mulai": "2026-01-01",
            "tanggal_selesai": "2026-12-31",
            "keterangan": "Test activity for 400+ asset batch update",
            "kode_satker": f"SAT{unique_id}",
            "nama_satker": f"Satker Test {unique_id}"
        }
        
        response = api_session.post(
            f"{BASE_URL}/api/inventory-activities",
            json=activity_data,
            headers=auth_headers
        )
        
        if response.status_code not in [200, 201]:
            pytest.skip(f"Activity creation failed: {response.text}")
        
        activity = response.json()
        activity_id = activity.get("id")
        print(f"✓ Created test activity: {activity_id}")
        
        yield activity_id
        
        # Cleanup - delete activity and its assets after tests
        try:
            api_session.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}", headers=auth_headers)
        except Exception:
            pass
    
    def test_create_activity(self, api_session, auth_headers):
        """Test POST /api/inventory-activities"""
        unique_id = str(uuid.uuid4())[:8]
        activity_data = {
            "nama_kegiatan": f"Activity_Test_{unique_id}",
            "nomor_surat": f"SR/{unique_id}/2026",
            "tanggal_mulai": "2026-01-01",
            "tanggal_selesai": "2026-12-31",
            "keterangan": "Test activity creation",
            "kode_satker": f"SAT{unique_id}",
            "nama_satker": f"Satker Test {unique_id}"
        }
        
        response = api_session.post(
            f"{BASE_URL}/api/inventory-activities",
            json=activity_data,
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201], f"Create activity failed: {response.text}"
        data = response.json()
        assert "id" in data, "Activity should have an id"
        print(f"✓ POST /api/inventory-activities - Activity created: {data['id']}")
    
    def test_create_single_asset(self, api_session, auth_headers, test_activity):
        """Test POST /api/assets - single asset creation"""
        asset_data = {
            "asset_code": f"TEST-SINGLE-{str(uuid.uuid4())[:8]}",
            "NUP": "1",
            "asset_name": "Test Single Asset",
            "activity_id": test_activity,
            "category": "Test Category"
        }
        
        response = api_session.post(
            f"{BASE_URL}/api/assets",
            json=asset_data,
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201], f"Create asset failed: {response.text}"
        data = response.json()
        assert "id" in data, "Asset should have an id"
        print(f"✓ POST /api/assets - Single asset created: {data['id']}")
    
    def test_get_assets_with_pagination(self, api_session, auth_headers, test_activity):
        """Test GET /api/assets with pagination"""
        response = api_session.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": test_activity, "page": 1, "page_size": 10},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get assets failed: {response.text}"
        data = response.json()
        assert "assets" in data or "items" in data, "Response should have assets or items"
        assert "total" in data or "total_items" in data or "totalItems" in data, "Response should have total count"
        print("✓ GET /api/assets with pagination working")
    
    def test_bulk_asset_creation_420_assets(self, api_session, auth_headers, test_activity):
        """Create 420 assets for chunking test"""
        created_ids = []
        batch_size = 50  # Create in batches to avoid timeout
        total_assets = 420
        
        print(f"Creating {total_assets} assets for batch update test...")
        
        for batch_num in range(0, total_assets, batch_size):
            batch_assets = []
            for i in range(batch_size):
                idx = batch_num + i
                if idx >= total_assets:
                    break
                asset_data = {
                    "asset_code": f"BULK-{test_activity[:8]}-{idx:04d}",
                    "NUP": str(idx + 1),
                    "asset_name": f"Bulk Test Asset {idx + 1}",
                    "activity_id": test_activity,
                    "category": "Test Bulk Category",
                    "location": "Initial Location"
                }
                
                response = api_session.post(
                    f"{BASE_URL}/api/assets",
                    json=asset_data,
                    headers=auth_headers,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    created_ids.append(data.get("id"))
            
            print(f"  Created batch {batch_num // batch_size + 1}: {len(created_ids)} assets total")
        
        assert len(created_ids) >= 400, f"Expected at least 400 assets, got {len(created_ids)}"
        print(f"✓ Created {len(created_ids)} assets for bulk testing")
        
        # Store created_ids for later tests
        return created_ids
    
    def test_get_all_asset_ids_endpoint(self, api_session, auth_headers, test_activity):
        """Test GET /api/assets/all-ids - select all pages feature"""
        response = api_session.get(
            f"{BASE_URL}/api/assets/all-ids",
            params={"activity_id": test_activity},
            headers=auth_headers,
            timeout=60
        )
        
        assert response.status_code == 200, f"Get all IDs failed: {response.text}"
        data = response.json()
        assert "ids" in data, "Response should have 'ids' array"
        assert "total" in data, "Response should have 'total' count"
        assert isinstance(data["ids"], list), "ids should be a list"
        
        total = data["total"]
        print(f"✓ GET /api/assets/all-ids returned {total} asset IDs")
        
        # Verify total matches IDs count
        assert len(data["ids"]) == total, f"IDs count mismatch: {len(data['ids'])} vs {total}"
        
        return data["ids"]
    
    def test_batch_update_small_batch(self, api_session, auth_headers, test_activity):
        """Test PUT /api/assets/batch-update with small batch (50 assets)"""
        # First get some asset IDs
        response = api_session.get(
            f"{BASE_URL}/api/assets/all-ids",
            params={"activity_id": test_activity},
            headers=auth_headers
        )
        
        if response.status_code != 200:
            pytest.skip("Could not get asset IDs")
        
        all_ids = response.json().get("ids", [])
        if len(all_ids) < 10:
            pytest.skip("Not enough assets for batch test")
        
        # Take first 50 for small batch test
        batch_ids = all_ids[:50]
        
        update_data = {
            "asset_ids": batch_ids,
            "updates": {
                "location": "Batch Updated Location - Small"
            }
        }
        
        response = api_session.put(
            f"{BASE_URL}/api/assets/batch-update",
            json=update_data,
            headers=auth_headers,
            timeout=60
        )
        
        assert response.status_code == 200, f"Small batch update failed: {response.text}"
        data = response.json()
        assert "updated" in data, "Response should have 'updated' count"
        assert data["updated"] == len(batch_ids), f"Expected {len(batch_ids)} updated, got {data['updated']}"
        print(f"✓ PUT /api/assets/batch-update (50 assets) - Updated {data['updated']} assets")
    
    def test_batch_update_large_batch_420_assets(self, api_session, auth_headers, test_activity):
        """Test PUT /api/assets/batch-update with 400+ assets (chunking verification)"""
        # Get all asset IDs
        response = api_session.get(
            f"{BASE_URL}/api/assets/all-ids",
            params={"activity_id": test_activity},
            headers=auth_headers,
            timeout=60
        )
        
        if response.status_code != 200:
            pytest.skip("Could not get asset IDs")
        
        all_ids = response.json().get("ids", [])
        total_ids = len(all_ids)
        
        if total_ids < 400:
            pytest.skip(f"Not enough assets for 400+ test, only have {total_ids}")
        
        print(f"Testing batch update with {total_ids} assets...")
        
        # Simulate frontend chunking (CHUNK_SIZE = 200)
        CHUNK_SIZE = 200
        chunks = [all_ids[i:i+CHUNK_SIZE] for i in range(0, len(all_ids), CHUNK_SIZE)]
        total_updated = 0
        
        for idx, chunk in enumerate(chunks):
            update_data = {
                "asset_ids": chunk,
                "updates": {
                    "location": f"Batch Chunk {idx + 1} Updated"
                }
            }
            
            response = api_session.put(
                f"{BASE_URL}/api/assets/batch-update",
                json=update_data,
                headers=auth_headers,
                timeout=120
            )
            
            assert response.status_code == 200, f"Chunk {idx + 1} batch update failed: {response.text}"
            data = response.json()
            total_updated += data.get("updated", 0)
            print(f"  Chunk {idx + 1}/{len(chunks)}: Updated {data.get('updated', 0)} assets")
        
        assert total_updated >= 400, f"Expected at least 400 updated, got {total_updated}"
        print(f"✓ PUT /api/assets/batch-update (400+ assets) - Total updated: {total_updated}")
    
    def test_verify_batch_update_persisted(self, api_session, auth_headers, test_activity):
        """Verify batch update changes were persisted to database"""
        response = api_session.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": test_activity, "page": 1, "page_size": 10},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get assets failed: {response.text}"
        data = response.json()
        assets = data.get("assets", data.get("items", []))
        
        # Check that some assets have the updated location
        updated_found = False
        for asset in assets:
            if "Batch" in asset.get("location", ""):
                updated_found = True
                break
        
        assert updated_found, "No assets found with batch updated location"
        print("✓ Batch update changes persisted to database")
    
    def test_get_stats_after_batch_update(self, api_session, auth_headers, test_activity):
        """Test GET /api/assets/stats after batch update"""
        response = api_session.get(
            f"{BASE_URL}/api/assets/stats",
            params={"activity_id": test_activity},
            headers=auth_headers
        )
        
        # Stats endpoint might not exist or return different structure
        if response.status_code == 404:
            pytest.skip("Stats endpoint not available")
        
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        print(f"✓ GET /api/assets/stats - Stats retrieved: {data.keys()}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_bulk_assets(self):
        """Note: Assets are cleaned up via activity deletion in fixtures"""
        print("✓ Test cleanup handled by activity fixture teardown")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
