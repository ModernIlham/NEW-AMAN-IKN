"""
Test suite for Satker (Satuan Kerja) feature in inventory management
Tests:
- POST /api/inventory-activities validates kode_satker and nama_satker as required
- GET /api/satker-list returns unique satker pairs with counts
- GET /api/satker-lookup provides auto-fill data
- Satker consistency validation (same kode = same nama)
"""
import os
import pytest
import requests
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSatkerBasicValidation:
    """Test that kode_satker and nama_satker are required fields"""
    
    def test_create_activity_without_kode_satker_fails(self):
        """POST should reject activity without kode_satker"""
        payload = {
            "nomor_surat": f"TEST_SATKER_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Test Kegiatan Satker Validation",
            "kode_satker": "",  # Empty - should fail
            "nama_satker": "Test Satker Name"
        }
        response = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Kode Satker" in data.get("detail", ""), f"Expected error about Kode Satker, got: {data}"
        print(f"✓ Empty kode_satker rejected with: {data['detail']}")
    
    def test_create_activity_without_nama_satker_fails(self):
        """POST should reject activity without nama_satker"""
        payload = {
            "nomor_surat": f"TEST_SATKER_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Test Kegiatan Satker Validation",
            "kode_satker": "001234",
            "nama_satker": ""  # Empty - should fail
        }
        response = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Nama Satker" in data.get("detail", ""), f"Expected error about Nama Satker, got: {data}"
        print(f"✓ Empty nama_satker rejected with: {data['detail']}")
    
    def test_create_activity_with_valid_satker(self):
        """POST should succeed with both kode_satker and nama_satker provided"""
        unique_code = f"TST{uuid.uuid4().hex[:4].upper()}"
        payload = {
            "nomor_surat": f"TEST_SATKER_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Test Kegiatan With Satker",
            "kode_satker": unique_code,
            "nama_satker": f"Test Satker {unique_code}"
        }
        response = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("kode_satker") == unique_code
        assert data.get("nama_satker") == f"Test Satker {unique_code}"
        assert "id" in data
        print(f"✓ Activity created with satker: {unique_code} - {data['nama_satker']}")
        
        # Cleanup - delete the test activity
        activity_id = data["id"]
        cleanup = requests.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        print(f"  Cleanup: deleted activity {activity_id}, status={cleanup.status_code}")
        return data


class TestSatkerListEndpoint:
    """Test GET /api/satker-list endpoint"""
    
    def test_satker_list_returns_data(self):
        """GET /api/satker-list should return list of unique satker with counts"""
        response = requests.get(f"{BASE_URL}/api/satker-list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ /api/satker-list returns {len(data)} satker entries")
        
        # If there are entries, verify structure
        if len(data) > 0:
            first = data[0]
            assert "kode_satker" in first, "Missing kode_satker in response"
            assert "nama_satker" in first, "Missing nama_satker in response"
            assert "count" in first, "Missing count in response"
            print(f"  First satker: {first['kode_satker']} - {first['nama_satker']} ({first['count']} activities)")


class TestSatkerLookupEndpoint:
    """Test GET /api/satker-lookup endpoint for auto-fill"""
    
    def test_satker_lookup_by_kode(self):
        """GET /api/satker-lookup?kode=xxx should return matching satker"""
        # First create an activity with known satker
        unique_code = f"LKP{uuid.uuid4().hex[:4].upper()}"
        create_payload = {
            "nomor_surat": f"TEST_LOOKUP_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Test for Lookup",
            "kode_satker": unique_code,
            "nama_satker": f"Satker Lookup Test {unique_code}"
        }
        create_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=create_payload)
        assert create_resp.status_code == 200, f"Setup failed: {create_resp.text}"
        created = create_resp.json()
        activity_id = created["id"]
        
        try:
            # Now lookup by kode
            lookup_resp = requests.get(f"{BASE_URL}/api/satker-lookup", params={"kode": unique_code})
            assert lookup_resp.status_code == 200, f"Expected 200, got {lookup_resp.status_code}"
            lookup_data = lookup_resp.json()
            
            if lookup_data:
                assert lookup_data.get("kode_satker") == unique_code
                assert lookup_data.get("nama_satker") == f"Satker Lookup Test {unique_code}"
                print(f"✓ Lookup by kode '{unique_code}' returns: {lookup_data}")
            else:
                print(f"⚠ Lookup returned null for kode '{unique_code}'")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}")
            print("  Cleanup: deleted test activity")
    
    def test_satker_lookup_nonexistent_returns_null(self):
        """GET /api/satker-lookup with nonexistent kode should return null"""
        response = requests.get(f"{BASE_URL}/api/satker-lookup", params={"kode": "NONEXIST999"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data is None, f"Expected null for nonexistent kode, got: {data}"
        print("✓ Nonexistent kode returns null")


class TestSatkerConsistency:
    """Test satker consistency validation - same kode must have same nama"""
    
    def test_satker_consistency_same_kode_different_nama_fails(self):
        """Creating activity with existing kode_satker but different nama_satker should fail"""
        unique_code = f"CON{uuid.uuid4().hex[:4].upper()}"
        
        # First activity with satker
        first_payload = {
            "nomor_surat": f"TEST_CON1_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "First Activity with Satker",
            "kode_satker": unique_code,
            "nama_satker": "Original Satker Name"
        }
        first_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=first_payload)
        assert first_resp.status_code == 200, f"First create failed: {first_resp.text}"
        first_id = first_resp.json()["id"]
        
        try:
            # Second activity with same kode but different nama - should fail
            second_payload = {
                "nomor_surat": f"TEST_CON2_{uuid.uuid4().hex[:8]}",
                "nama_kegiatan": "Second Activity Different Nama",
                "kode_satker": unique_code,  # Same kode
                "nama_satker": "Different Satker Name"  # Different nama - should fail
            }
            second_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=second_payload)
            assert second_resp.status_code == 400, f"Expected 400 for inconsistent satker, got {second_resp.status_code}"
            error_data = second_resp.json()
            assert "sudah terdaftar" in error_data.get("detail", "").lower() or "harus sama" in error_data.get("detail", "").lower()
            print(f"✓ Inconsistent satker rejected: {error_data['detail']}")
        finally:
            # Cleanup first activity
            requests.delete(f"{BASE_URL}/api/inventory-activities/{first_id}")
            print("  Cleanup: deleted first test activity")
    
    def test_satker_consistency_same_kode_same_nama_succeeds(self):
        """Creating activity with existing kode_satker and same nama_satker should succeed"""
        unique_code = f"CON{uuid.uuid4().hex[:4].upper()}"
        
        # First activity
        first_payload = {
            "nomor_surat": f"TEST_CONS1_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "First Activity Same Satker",
            "kode_satker": unique_code,
            "nama_satker": "Same Satker Name"
        }
        first_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=first_payload)
        assert first_resp.status_code == 200, f"First create failed: {first_resp.text}"
        first_id = first_resp.json()["id"]
        
        try:
            # Second activity with SAME kode and SAME nama - should succeed
            second_payload = {
                "nomor_surat": f"TEST_CONS2_{uuid.uuid4().hex[:8]}",
                "nama_kegiatan": "Second Activity Same Satker",
                "kode_satker": unique_code,  # Same kode
                "nama_satker": "Same Satker Name"  # Same nama - should succeed
            }
            second_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=second_payload)
            assert second_resp.status_code == 200, f"Expected 200, got {second_resp.status_code}: {second_resp.text}"
            second_id = second_resp.json()["id"]
            print("✓ Activity with same satker created successfully")
            
            # Verify satker list shows this satker with count 2
            list_resp = requests.get(f"{BASE_URL}/api/satker-list")
            satker_list = list_resp.json()
            matching = [s for s in satker_list if s.get("kode_satker") == unique_code]
            if matching:
                assert matching[0]["count"] == 2, f"Expected count 2, got {matching[0]['count']}"
                print(f"  Satker list shows count: {matching[0]['count']}")
            
            # Cleanup second
            requests.delete(f"{BASE_URL}/api/inventory-activities/{second_id}")
        finally:
            # Cleanup first
            requests.delete(f"{BASE_URL}/api/inventory-activities/{first_id}")
            print("  Cleanup: deleted test activities")


class TestSatkerUpdateValidation:
    """Test PUT /api/inventory-activities/{id} also validates satker"""
    
    def test_update_activity_empty_kode_satker_fails(self):
        """PUT should reject update with empty kode_satker"""
        unique_code = f"UPD{uuid.uuid4().hex[:4].upper()}"
        
        # Create an activity first
        create_payload = {
            "nomor_surat": f"TEST_UPD_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Test Update Validation",
            "kode_satker": unique_code,
            "nama_satker": f"Satker {unique_code}"
        }
        create_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=create_payload)
        assert create_resp.status_code == 200
        activity = create_resp.json()
        activity_id = activity["id"]
        
        try:
            # Try to update with empty kode_satker
            update_payload = {
                "nomor_surat": activity["nomor_surat"],
                "nama_kegiatan": activity["nama_kegiatan"],
                "kode_satker": "",  # Empty - should fail
                "nama_satker": activity["nama_satker"]
            }
            update_resp = requests.put(f"{BASE_URL}/api/inventory-activities/{activity_id}", json=update_payload)
            assert update_resp.status_code == 400, f"Expected 400, got {update_resp.status_code}"
            error = update_resp.json()
            assert "Kode Satker" in error.get("detail", "")
            print(f"✓ Update with empty kode_satker rejected: {error['detail']}")
        finally:
            requests.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}")
    
    def test_update_activity_inconsistent_satker_fails(self):
        """PUT should reject update that creates inconsistent satker"""
        code1 = f"UD1{uuid.uuid4().hex[:3].upper()}"
        code2 = f"UD2{uuid.uuid4().hex[:3].upper()}"
        
        # Create first activity
        first_payload = {
            "nomor_surat": f"TEST_UDI1_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "First for Update Test",
            "kode_satker": code1,
            "nama_satker": "First Satker Name"
        }
        first_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=first_payload)
        assert first_resp.status_code == 200
        first_id = first_resp.json()["id"]
        
        # Create second activity with different satker
        second_payload = {
            "nomor_surat": f"TEST_UDI2_{uuid.uuid4().hex[:8]}",
            "nama_kegiatan": "Second for Update Test",
            "kode_satker": code2,
            "nama_satker": "Second Satker Name"
        }
        second_resp = requests.post(f"{BASE_URL}/api/inventory-activities", json=second_payload)
        assert second_resp.status_code == 200
        second_id = second_resp.json()["id"]
        
        try:
            # Try to update second to use first's kode but different nama
            update_payload = {
                "nomor_surat": second_payload["nomor_surat"],
                "nama_kegiatan": second_payload["nama_kegiatan"],
                "kode_satker": code1,  # Use first's kode
                "nama_satker": "Different Name From First"  # But different nama - should fail
            }
            update_resp = requests.put(f"{BASE_URL}/api/inventory-activities/{second_id}", json=update_payload)
            assert update_resp.status_code == 400, f"Expected 400, got {update_resp.status_code}: {update_resp.text}"
            error = update_resp.json()
            print(f"✓ Update with inconsistent satker rejected: {error['detail']}")
        finally:
            requests.delete(f"{BASE_URL}/api/inventory-activities/{first_id}")
            requests.delete(f"{BASE_URL}/api/inventory-activities/{second_id}")
            print("  Cleanup: deleted test activities")


# Cleanup any existing test data at module start
@pytest.fixture(autouse=True, scope="module")
def cleanup_test_data():
    """Cleanup TEST_ prefixed activities before and after tests"""
    def delete_test_activities():
        try:
            resp = requests.get(f"{BASE_URL}/api/inventory-activities")
            if resp.status_code == 200:
                activities = resp.json()
                for act in activities:
                    if act.get("nomor_surat", "").startswith("TEST_"):
                        requests.delete(f"{BASE_URL}/api/inventory-activities/{act['id']}")
        except Exception as e:
            print(f"Cleanup warning: {e}")
    
    delete_test_activities()
    yield
    delete_test_activities()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
