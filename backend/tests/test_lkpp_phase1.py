"""
LKPP 85/2025 Phase 1 Testing: Berlebih & Sengketa Features
Tests:
1. GET /api/inventory/classifications - returns 5 statuses including Berlebih and Sengketa
2. POST /api/assets - accepts new fields for Berlebih and Sengketa
3. GET /api/inventory-activities/{id}/rekapitulasi - returns berlebih and sengketa counts
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_user(api_client):
    """Register and login a test user"""
    unique_id = uuid.uuid4().hex[:8]
    username = f"TEST_lkpp_user_{unique_id}"
    password = "TestPassword123!"
    email = f"test_lkpp_{unique_id}@test.com"
    
    # Register user
    register_response = api_client.post(f"{BASE_URL}/api/auth/register", json={
        "username": username,
        "password": password,
        "email": email
    })
    
    if register_response.status_code not in [200, 201]:
        # Try login if registration fails (user might exist)
        login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": password
        })
        if login_response.status_code == 200:
            return login_response.json()
        pytest.skip(f"Could not register/login test user: {register_response.text}")
    
    user_data = register_response.json()
    return {"user_id": user_data.get("user", {}).get("id") or user_data.get("id"), "username": username}

@pytest.fixture(scope="module")
def test_activity(api_client, test_user):
    """Create a test inventory activity"""
    unique_id = uuid.uuid4().hex[:8]
    response = api_client.post(f"{BASE_URL}/api/inventory-activities", json={
        "nama_kegiatan": f"TEST LKPP Activity {unique_id}",
        "nomor_surat": f"TEST/{unique_id}/2025",
        "tanggal_mulai": "2025-01-01",
        "tanggal_selesai": "2025-12-31",
        "user_id": test_user.get("user_id")
    })
    
    if response.status_code not in [200, 201]:
        pytest.skip(f"Could not create test activity: {response.text}")
    
    activity = response.json()
    yield activity
    
    # Cleanup - delete activity
    try:
        api_client.delete(f"{BASE_URL}/api/inventory-activities/{activity.get('id')}")
    except:
        pass


# ============================================================================
# TEST: Classifications Endpoint
# ============================================================================

class TestInventoryClassifications:
    """Test /api/inventory/classifications endpoint returns 5 statuses"""
    
    def test_classifications_endpoint_returns_200(self, api_client):
        """Test that classifications endpoint returns 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/inventory/classifications")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_classifications_returns_five_inventory_statuses(self, api_client):
        """Test that inventory_statuses contains all 5 status types"""
        response = api_client.get(f"{BASE_URL}/api/inventory/classifications")
        data = response.json()
        
        assert "inventory_statuses" in data, "Response should contain 'inventory_statuses'"
        statuses = data["inventory_statuses"]
        
        expected_statuses = ["Belum Diinventarisasi", "Ditemukan", "Tidak Ditemukan", "Berlebih", "Sengketa"]
        assert len(statuses) == 5, f"Expected 5 statuses, got {len(statuses)}"
        
        for status in expected_statuses:
            assert status in statuses, f"Missing status: {status}"
    
    def test_classifications_returns_berlebih_info(self, api_client):
        """Test that berlebih_info is included with proper structure"""
        response = api_client.get(f"{BASE_URL}/api/inventory/classifications")
        data = response.json()
        
        assert "berlebih_info" in data, "Response should contain 'berlebih_info'"
        berlebih_info = data["berlebih_info"]
        
        assert "pengertian" in berlebih_info, "berlebih_info should have 'pengertian'"
        assert "contoh" in berlebih_info, "berlebih_info should have 'contoh'"
        assert "tindak_lanjut" in berlebih_info, "berlebih_info should have 'tindak_lanjut'"
        
        # Check content
        assert len(berlebih_info["contoh"]) > 0, "berlebih_info should have examples"
        assert len(berlebih_info["tindak_lanjut"]) > 0, "berlebih_info should have tindak_lanjut options"
    
    def test_classifications_returns_sengketa_info(self, api_client):
        """Test that sengketa_info is included with proper structure"""
        response = api_client.get(f"{BASE_URL}/api/inventory/classifications")
        data = response.json()
        
        assert "sengketa_info" in data, "Response should contain 'sengketa_info'"
        sengketa_info = data["sengketa_info"]
        
        assert "pengertian" in sengketa_info, "sengketa_info should have 'pengertian'"
        assert "contoh" in sengketa_info, "sengketa_info should have 'contoh'"
        assert "tindak_lanjut" in sengketa_info, "sengketa_info should have 'tindak_lanjut'"
        
        # Check content
        assert len(sengketa_info["contoh"]) > 0, "sengketa_info should have examples"
        assert len(sengketa_info["tindak_lanjut"]) > 0, "sengketa_info should have tindak_lanjut options"


# ============================================================================
# TEST: Asset Creation with new Berlebih/Sengketa fields
# ============================================================================

class TestAssetCreationBerlebihSengketa:
    """Test POST /api/assets accepts new fields for Berlebih and Sengketa"""
    
    def test_create_asset_with_berlebih_fields(self, api_client, test_activity):
        """Test creating asset with Berlebih status and related fields"""
        unique_id = uuid.uuid4().hex[:8]
        asset_code = "1234567890"  # 10 digit code
        
        asset_data = {
            "asset_code": asset_code,
            "asset_name": f"TEST Berlebih Asset {unique_id}",
            "category": "Peralatan",
            "inventory_status": "Berlebih",
            "keterangan_berlebih": "BMN ditemukan tanpa catatan di gudang",
            "asal_usul_berlebih": "Hibah dari instansi lain belum dicatat",
            "tindak_lanjut": "Akan didaftarkan ke SIMAK-BMN",
            "activity_id": test_activity.get("id")
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=asset_data)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        created_asset = response.json()
        
        # Verify fields are stored
        assert created_asset.get("inventory_status") == "Berlebih", "inventory_status should be 'Berlebih'"
        assert created_asset.get("keterangan_berlebih") == asset_data["keterangan_berlebih"]
        assert created_asset.get("asal_usul_berlebih") == asset_data["asal_usul_berlebih"]
        assert created_asset.get("tindak_lanjut") == asset_data["tindak_lanjut"]
        
        # Verify by GET
        get_response = api_client.get(f"{BASE_URL}/api/assets/{created_asset['id']}")
        assert get_response.status_code == 200
        fetched_asset = get_response.json()
        assert fetched_asset.get("keterangan_berlebih") == asset_data["keterangan_berlebih"]
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{created_asset['id']}")
    
    def test_create_asset_with_sengketa_fields(self, api_client, test_activity):
        """Test creating asset with Sengketa status and related fields"""
        unique_id = uuid.uuid4().hex[:8]
        asset_code = "9876543210"  # 10 digit code
        
        asset_data = {
            "asset_code": asset_code,
            "asset_name": f"TEST Sengketa Asset {unique_id}",
            "category": "Tanah",
            "inventory_status": "Sengketa",
            "nomor_perkara": "123/Pdt.G/2025/PN.JKT",
            "pihak_bersengketa": "PT ABC vs Kementerian XYZ",
            "keterangan_sengketa": "Tanah diklaim milik pihak swasta sejak 2020",
            "tindak_lanjut": "Menunggu putusan pengadilan tingkat banding",
            "activity_id": test_activity.get("id")
        }
        
        response = api_client.post(f"{BASE_URL}/api/assets", json=asset_data)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        created_asset = response.json()
        
        # Verify fields are stored
        assert created_asset.get("inventory_status") == "Sengketa", "inventory_status should be 'Sengketa'"
        assert created_asset.get("nomor_perkara") == asset_data["nomor_perkara"]
        assert created_asset.get("pihak_bersengketa") == asset_data["pihak_bersengketa"]
        assert created_asset.get("keterangan_sengketa") == asset_data["keterangan_sengketa"]
        assert created_asset.get("tindak_lanjut") == asset_data["tindak_lanjut"]
        
        # Verify by GET
        get_response = api_client.get(f"{BASE_URL}/api/assets/{created_asset['id']}")
        assert get_response.status_code == 200
        fetched_asset = get_response.json()
        assert fetched_asset.get("nomor_perkara") == asset_data["nomor_perkara"]
        assert fetched_asset.get("keterangan_sengketa") == asset_data["keterangan_sengketa"]
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/assets/{created_asset['id']}")


# ============================================================================
# TEST: Rekapitulasi Endpoint with Berlebih & Sengketa
# ============================================================================

class TestRekapitulasiBerlebihSengketa:
    """Test rekapitulasi endpoint returns berlebih/sengketa counts and condition breakdown"""
    
    @pytest.fixture(scope="class")
    def assets_for_rekapitulasi(self, api_client, test_activity):
        """Create test assets for rekapitulasi testing"""
        activity_id = test_activity.get("id")
        created_assets = []
        
        # Create assets with different statuses
        test_assets = [
            {"asset_code": "1111111111", "asset_name": "Ditemukan Baik 1", "inventory_status": "Ditemukan", "condition": "Baik"},
            {"asset_code": "2222222222", "asset_name": "Ditemukan Rusak Ringan", "inventory_status": "Ditemukan", "condition": "Rusak Ringan"},
            {"asset_code": "3333333333", "asset_name": "Ditemukan Rusak Berat", "inventory_status": "Ditemukan", "condition": "Rusak Berat"},
            {"asset_code": "4444444444", "asset_name": "Tidak Ditemukan 1", "inventory_status": "Tidak Ditemukan"},
            {"asset_code": "5555555555", "asset_name": "Berlebih Asset", "inventory_status": "Berlebih", "keterangan_berlebih": "Test"},
            {"asset_code": "6666666666", "asset_name": "Sengketa Asset", "inventory_status": "Sengketa", "nomor_perkara": "001/2025"},
            {"asset_code": "7777777777", "asset_name": "Belum Inventarisasi", "inventory_status": "Belum Diinventarisasi"},
        ]
        
        for asset_data in test_assets:
            asset_data["category"] = "Peralatan"
            asset_data["activity_id"] = activity_id
            response = api_client.post(f"{BASE_URL}/api/assets", json=asset_data)
            if response.status_code in [200, 201]:
                created_assets.append(response.json())
        
        yield created_assets
        
        # Cleanup
        for asset in created_assets:
            try:
                api_client.delete(f"{BASE_URL}/api/assets/{asset['id']}")
            except:
                pass
    
    def test_rekapitulasi_returns_berlebih_count(self, api_client, test_activity, assets_for_rekapitulasi):
        """Test that rekapitulasi returns berlebih count"""
        activity_id = test_activity.get("id")
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/rekapitulasi")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "berlebih" in data, "Response should contain 'berlebih' key"
        assert "count" in data["berlebih"], "berlebih should have 'count'"
        assert "value" in data["berlebih"], "berlebih should have 'value'"
        assert data["berlebih"]["count"] >= 1, f"Expected at least 1 berlebih, got {data['berlebih']['count']}"
    
    def test_rekapitulasi_returns_sengketa_count(self, api_client, test_activity, assets_for_rekapitulasi):
        """Test that rekapitulasi returns sengketa count"""
        activity_id = test_activity.get("id")
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/rekapitulasi")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "sengketa" in data, "Response should contain 'sengketa' key"
        assert "count" in data["sengketa"], "sengketa should have 'count'"
        assert "value" in data["sengketa"], "sengketa should have 'value'"
        assert data["sengketa"]["count"] >= 1, f"Expected at least 1 sengketa, got {data['sengketa']['count']}"
    
    def test_rekapitulasi_returns_ditemukan_condition_breakdown(self, api_client, test_activity, assets_for_rekapitulasi):
        """Test that rekapitulasi returns condition breakdown for 'Ditemukan' assets"""
        activity_id = test_activity.get("id")
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/rekapitulasi")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "ditemukan" in data, "Response should contain 'ditemukan' key"
        ditemukan = data["ditemukan"]
        
        # Check condition breakdowns exist
        assert "kondisi_baik" in ditemukan, "ditemukan should have 'kondisi_baik'"
        assert "kondisi_rusak_ringan" in ditemukan, "ditemukan should have 'kondisi_rusak_ringan'"
        assert "kondisi_rusak_berat" in ditemukan, "ditemukan should have 'kondisi_rusak_berat'"
        
        # Verify structure
        for kondisi in ["kondisi_baik", "kondisi_rusak_ringan", "kondisi_rusak_berat"]:
            assert "count" in ditemukan[kondisi], f"{kondisi} should have 'count'"
            assert "value" in ditemukan[kondisi], f"{kondisi} should have 'value'"
        
        # Verify at least some counts (we created 3 Ditemukan assets)
        total_kondisi = (
            ditemukan["kondisi_baik"]["count"] +
            ditemukan["kondisi_rusak_ringan"]["count"] +
            ditemukan["kondisi_rusak_berat"]["count"]
        )
        assert total_kondisi >= 1, f"Expected at least 1 in condition breakdown, got {total_kondisi}"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
