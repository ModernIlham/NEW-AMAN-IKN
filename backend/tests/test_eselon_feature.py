"""
Test suite for Eselon I / Eselon II nested structure feature
- Backend: Activity eselon1 stores List[dict] with {nama, eselon2: [str]}
- Backend: POST /api/inventory-activities saves nested eselon1 data
- Backend: GET /api/satker-lookup returns eselon1 with nested eselon2
- Backend: GET /api/assets/filter-options returns eselon1s and eselon2s arrays
- Backend: GET /api/assets supports eselon1_filter and eselon2_filter query params
- Backend: GET /api/export/csv includes eselon1,eselon2 columns and activity header info
"""
import os
import pytest
import requests
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_session():
    """Shared requests session with default headers"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_activity_with_nested_eselon(api_session):
    """Create an activity with nested eselon1 structure for testing"""
    unique_id = str(uuid.uuid4())[:8]
    activity_payload = {
        "nomor_surat": f"TEST/ESELON/{unique_id}",
        "nama_kegiatan": f"Test Eselon Feature {unique_id}",
        "deskripsi": "Testing nested eselon1/eselon2",
        "tanggal_mulai": "2024-01-01",
        "tanggal_selesai": "2024-12-31",
        "penanggung_jawab": "Test User",
        "kode_satker": f"SATKER{unique_id}",
        "nama_satker": f"Test Satker Eselon {unique_id}",
        "eselon1": [
            {"nama": "Direktorat Jenderal A", "eselon2": ["Direktorat A1", "Direktorat A2", "Direktorat A3"]},
            {"nama": "Direktorat Jenderal B", "eselon2": ["Direktorat B1", "Direktorat B2"]},
            {"nama": "Inspektorat Jenderal", "eselon2": ["Inspektur I", "Inspektur II"]}
        ],
        "tim_peneliti": [{"nama": "Tester", "jabatan": "QA", "nip": "123"}],
        "kasatker_nama": "Test Kasatker",
        "kasatker_nip": "987654321",
        "alamat_satker": "Jakarta Pusat"
    }
    
    response = api_session.post(f"{BASE_URL}/api/inventory-activities", json=activity_payload)
    assert response.status_code in [200, 201], f"Failed to create activity: {response.text}"
    activity = response.json()
    
    yield activity
    
    # Cleanup: delete activity after tests
    api_session.delete(f"{BASE_URL}/api/inventory-activities/{activity['id']}")


class TestNestedEselon1Structure:
    """Test nested eselon1 List[dict] with {nama, eselon2: [str]} structure"""
    
    def test_activity_eselon1_is_list_of_dicts(self, api_session, test_activity_with_nested_eselon):
        """Verify eselon1 is stored as List[dict] with nama and eselon2 fields"""
        activity_id = test_activity_with_nested_eselon["id"]
        response = api_session.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert response.status_code == 200
        
        activity = response.json()
        eselon1 = activity.get("eselon1", [])
        
        # Check it's a list
        assert isinstance(eselon1, list), f"eselon1 should be a list, got {type(eselon1)}"
        assert len(eselon1) == 3, f"Expected 3 eselon1 entries, got {len(eselon1)}"
        
        # Check each item is dict with nama and eselon2
        for item in eselon1:
            assert isinstance(item, dict), f"eselon1 item should be dict, got {type(item)}"
            assert "nama" in item, "eselon1 item should have 'nama' key"
            assert "eselon2" in item, "eselon1 item should have 'eselon2' key"
            assert isinstance(item["eselon2"], list), f"eselon2 should be a list, got {type(item['eselon2'])}"
        
        print("✅ Activity eselon1 structure verified: List[dict] with {nama, eselon2}")
    
    def test_activity_eselon1_contains_correct_data(self, api_session, test_activity_with_nested_eselon):
        """Verify eselon1 contains the correct nested data"""
        activity_id = test_activity_with_nested_eselon["id"]
        response = api_session.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert response.status_code == 200
        
        activity = response.json()
        eselon1 = activity.get("eselon1", [])
        
        # Find Direktorat Jenderal A
        dir_a = next((e for e in eselon1 if e["nama"] == "Direktorat Jenderal A"), None)
        assert dir_a is not None, "Direktorat Jenderal A not found"
        assert "Direktorat A1" in dir_a["eselon2"], "Direktorat A1 not in eselon2"
        assert "Direktorat A2" in dir_a["eselon2"], "Direktorat A2 not in eselon2"
        assert len(dir_a["eselon2"]) == 3, f"Expected 3 eselon2 for Dir A, got {len(dir_a['eselon2'])}"
        
        print("✅ Nested eselon1 data verified correctly")


class TestSatkerLookupWithEselon1:
    """Test GET /api/satker-lookup returns eselon1 with nested eselon2"""
    
    def test_satker_lookup_returns_eselon1(self, api_session, test_activity_with_nested_eselon):
        """GET /api/satker-lookup should return eselon1 array for auto-fill"""
        kode = test_activity_with_nested_eselon["kode_satker"]
        response = api_session.get(f"{BASE_URL}/api/satker-lookup", params={"kode": kode})
        assert response.status_code == 200
        
        data = response.json()
        assert data is not None, "satker-lookup should return data"
        assert "kode_satker" in data, "Response should have kode_satker"
        assert "nama_satker" in data, "Response should have nama_satker"
        assert "eselon1" in data, "Response should have eselon1 field"
        
        eselon1 = data.get("eselon1", [])
        assert isinstance(eselon1, list), f"eselon1 should be list, got {type(eselon1)}"
        assert len(eselon1) == 3, f"Expected 3 eselon1 entries, got {len(eselon1)}"
        
        # Verify nested structure
        for item in eselon1:
            assert "nama" in item, "eselon1 item should have nama"
            assert "eselon2" in item, "eselon1 item should have eselon2"
        
        print(f"✅ satker-lookup returns eselon1 with nested eselon2 for kode={kode}")


class TestAssetEselonFilters:
    """Test asset eselon1/eselon2 filter functionality"""
    
    @pytest.fixture(scope="class")
    def test_asset_with_eselon(self, api_session, test_activity_with_nested_eselon):
        """Create an asset with eselon1 and eselon2 fields"""
        unique_id = str(uuid.uuid4())[:6]
        asset_payload = {
            "asset_code": f"AST{unique_id}",
            "asset_name": f"Test Asset Eselon {unique_id}",
            "category": "Electronics",
            "activity_id": test_activity_with_nested_eselon["id"],
            "eselon1": "Direktorat Jenderal A",
            "eselon2": "Direktorat A1",
            "location": "Jakarta",
            "condition": "Baik",
            "status": "Aktif"
        }
        
        response = api_session.post(f"{BASE_URL}/api/assets", json=asset_payload)
        assert response.status_code in [200, 201], f"Failed to create asset: {response.text}"
        asset = response.json()
        
        yield asset
        
        # Cleanup
        api_session.delete(f"{BASE_URL}/api/assets/{asset['id']}")
    
    def test_filter_options_includes_eselon1s_and_eselon2s(self, api_session, test_activity_with_nested_eselon, test_asset_with_eselon):
        """GET /api/assets/filter-options should return eselon1s and eselon2s arrays"""
        activity_id = test_activity_with_nested_eselon["id"]
        response = api_session.get(f"{BASE_URL}/api/assets/filter-options", params={"activity_id": activity_id})
        assert response.status_code == 200
        
        data = response.json()
        assert "eselon1s" in data, "filter-options should include eselon1s"
        assert "eselon2s" in data, "filter-options should include eselon2s"
        
        eselon1s = data.get("eselon1s", [])
        eselon2s = data.get("eselon2s", [])
        
        assert isinstance(eselon1s, list), f"eselon1s should be list, got {type(eselon1s)}"
        assert isinstance(eselon2s, list), f"eselon2s should be list, got {type(eselon2s)}"
        
        # Should contain the values from our test asset
        assert "Direktorat Jenderal A" in eselon1s, f"eselon1s should contain 'Direktorat Jenderal A', got {eselon1s}"
        assert "Direktorat A1" in eselon2s, f"eselon2s should contain 'Direktorat A1', got {eselon2s}"
        
        print(f"✅ filter-options returns eselon1s: {eselon1s}, eselon2s: {eselon2s}")
    
    def test_assets_filter_by_eselon1(self, api_session, test_activity_with_nested_eselon, test_asset_with_eselon):
        """GET /api/assets supports eselon1_filter query param"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        response = api_session.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "eselon1_filter": "Direktorat Jenderal A"
        })
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        assert len(items) >= 1, f"Should find at least 1 asset with eselon1 filter, got {len(items)}"
        
        # Verify all returned items have matching eselon1
        for item in items:
            assert "Direktorat Jenderal A" in (item.get("eselon1") or ""), "Asset should have matching eselon1"
        
        print(f"✅ eselon1_filter works: found {len(items)} assets")
    
    def test_assets_filter_by_eselon2(self, api_session, test_activity_with_nested_eselon, test_asset_with_eselon):
        """GET /api/assets supports eselon2_filter query param"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        response = api_session.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "eselon2_filter": "Direktorat A1"
        })
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        assert len(items) >= 1, f"Should find at least 1 asset with eselon2 filter, got {len(items)}"
        
        for item in items:
            assert "Direktorat A1" in (item.get("eselon2") or ""), "Asset should have matching eselon2"
        
        print(f"✅ eselon2_filter works: found {len(items)} assets")
    
    def test_assets_filter_by_both_eselon(self, api_session, test_activity_with_nested_eselon, test_asset_with_eselon):
        """GET /api/assets supports combined eselon1_filter + eselon2_filter"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        response = api_session.get(f"{BASE_URL}/api/assets", params={
            "activity_id": activity_id,
            "eselon1_filter": "Direktorat Jenderal A",
            "eselon2_filter": "Direktorat A1"
        })
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        assert len(items) >= 1, f"Should find at least 1 asset with combined filter, got {len(items)}"
        
        for item in items:
            assert "Direktorat Jenderal A" in (item.get("eselon1") or "")
            assert "Direktorat A1" in (item.get("eselon2") or "")
        
        print(f"✅ Combined eselon1+eselon2 filter works: found {len(items)} assets")


class TestCSVExportWithEselon:
    """Test CSV export includes eselon1, eselon2 columns and activity header"""
    
    def test_csv_export_has_eselon_columns(self, api_session, test_activity_with_nested_eselon):
        """GET /api/export/csv includes eselon1,eselon2 columns"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        # Create a test asset first
        unique_id = str(uuid.uuid4())[:6]
        asset_payload = {
            "asset_code": f"CSV{unique_id}",
            "asset_name": f"CSV Test Asset {unique_id}",
            "category": "Test",
            "activity_id": activity_id,
            "eselon1": "Direktorat Jenderal B",
            "eselon2": "Direktorat B1"
        }
        create_resp = api_session.post(f"{BASE_URL}/api/assets", json=asset_payload)
        assert create_resp.status_code in [200, 201]
        asset = create_resp.json()
        
        try:
            # Request CSV export
            response = api_session.get(f"{BASE_URL}/api/export/csv", params={"activity_id": activity_id})
            assert response.status_code == 200, f"CSV export failed: {response.text}"
            
            csv_content = response.text
            lines = csv_content.split('\n')
            
            # Find header line (skip comment lines starting with #)
            header_line = None
            for line in lines:
                if not line.startswith('#') and 'asset_code' in line.lower():
                    header_line = line.lower()
                    break
            
            assert header_line is not None, "CSV should have header line with asset_code"
            assert 'eselon1' in header_line, f"CSV header should include eselon1, got: {header_line}"
            assert 'eselon2' in header_line, f"CSV header should include eselon2, got: {header_line}"
            
            print("✅ CSV export has eselon1 and eselon2 columns")
            
        finally:
            # Cleanup
            api_session.delete(f"{BASE_URL}/api/assets/{asset['id']}")
    
    def test_csv_export_has_activity_header_info(self, api_session, test_activity_with_nested_eselon):
        """GET /api/export/csv includes activity header comments with eselon1 info"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        # Create a test asset
        unique_id = str(uuid.uuid4())[:6]
        asset_payload = {
            "asset_code": f"CSVH{unique_id}",
            "asset_name": f"CSV Header Test {unique_id}",
            "category": "Test",
            "activity_id": activity_id
        }
        create_resp = api_session.post(f"{BASE_URL}/api/assets", json=asset_payload)
        assert create_resp.status_code in [200, 201]
        asset = create_resp.json()
        
        try:
            response = api_session.get(f"{BASE_URL}/api/export/csv", params={"activity_id": activity_id})
            assert response.status_code == 200
            
            csv_content = response.text
            
            # Check for activity header info (comment lines)
            has_kegiatan = '# Kegiatan:' in csv_content
            has_nomor_surat = '# Nomor Surat:' in csv_content
            has_eselon_header = '# Eselon I:' in csv_content
            
            assert has_kegiatan, "CSV should have '# Kegiatan:' header"
            assert has_nomor_surat, "CSV should have '# Nomor Surat:' header"
            assert has_eselon_header, "CSV should have '# Eselon I:' header with nested eselon2 info"
            
            # Verify eselon1 data in header
            if has_eselon_header:
                eselon_lines = [l for l in csv_content.split('\n') if l.startswith('# Eselon I:')]
                assert len(eselon_lines) >= 1, "Should have at least one Eselon I line"
                # Check that Eselon II info is included
                assert 'Eselon II:' in csv_content, "CSV header should include 'Eselon II:' info"
            
            print("✅ CSV export has activity header info with eselon1/eselon2")
            
        finally:
            api_session.delete(f"{BASE_URL}/api/assets/{asset['id']}")


class TestUpdateActivityEselon:
    """Test updating activity preserves/modifies eselon1 structure"""
    
    def test_update_activity_eselon1(self, api_session, test_activity_with_nested_eselon):
        """PUT /api/inventory-activities/{id} preserves and updates eselon1"""
        activity_id = test_activity_with_nested_eselon["id"]
        
        # Get current activity
        get_resp = api_session.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert get_resp.status_code == 200
        current = get_resp.json()
        
        # Update with modified eselon1
        updated_eselon1 = [
            {"nama": "Updated Direktorat X", "eselon2": ["Unit X1", "Unit X2"]},
            {"nama": "Updated Direktorat Y", "eselon2": ["Unit Y1"]}
        ]
        
        update_payload = {
            "nomor_surat": current["nomor_surat"],
            "nama_kegiatan": current["nama_kegiatan"],
            "kode_satker": current["kode_satker"],
            "nama_satker": current["nama_satker"],
            "eselon1": updated_eselon1
        }
        
        response = api_session.put(f"{BASE_URL}/api/inventory-activities/{activity_id}", json=update_payload)
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify update
        verify_resp = api_session.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert verify_resp.status_code == 200
        updated = verify_resp.json()
        
        eselon1 = updated.get("eselon1", [])
        assert len(eselon1) == 2, f"Updated eselon1 should have 2 entries, got {len(eselon1)}"
        
        names = [e["nama"] for e in eselon1]
        assert "Updated Direktorat X" in names, "Should contain 'Updated Direktorat X'"
        assert "Updated Direktorat Y" in names, "Should contain 'Updated Direktorat Y'"
        
        print("✅ Activity eselon1 update works correctly")
        
        # Restore original eselon1 for other tests
        restore_payload = {
            "nomor_surat": current["nomor_surat"],
            "nama_kegiatan": current["nama_kegiatan"],
            "kode_satker": current["kode_satker"],
            "nama_satker": current["nama_satker"],
            "eselon1": [
                {"nama": "Direktorat Jenderal A", "eselon2": ["Direktorat A1", "Direktorat A2", "Direktorat A3"]},
                {"nama": "Direktorat Jenderal B", "eselon2": ["Direktorat B1", "Direktorat B2"]},
                {"nama": "Inspektorat Jenderal", "eselon2": ["Inspektur I", "Inspektur II"]}
            ]
        }
        api_session.put(f"{BASE_URL}/api/inventory-activities/{activity_id}", json=restore_payload)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
