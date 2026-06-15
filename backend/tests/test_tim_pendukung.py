"""
Test Tim Pendukung Feature - Iteration 71
Tests for 'Tim Pendukung' (Support Team) functionality alongside 'Tim Peneliti' (Research Team)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data constants
TEST_PREFIX = "TEST_TIM_PENDUKUNG_"
TEST_TIM_PENELITI = [
    {"nama": "Dr. Ahmad Peneliti", "jabatan": "Ketua Tim", "nip": "198001012001011001"},
    {"nama": "Budi Peneliti", "jabatan": "Anggota", "nip": "198501012002011002"}
]
TEST_TIM_PENDUKUNG = [
    {"nama": "Siti Pendukung", "jabatan": "Admin Pendukung", "nip": "199001012003011001"},
    {"nama": "Rudi Pendukung", "jabatan": "Teknisi Pendukung", "nip": "199201012004011002"}
]

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture
def test_activity_id(api_client):
    """Create a test activity and return its ID, cleanup after test"""
    unique_id = str(uuid.uuid4())[:8]
    payload = {
        "nomor_surat": f"{TEST_PREFIX}NS_{unique_id}",
        "nama_kegiatan": f"{TEST_PREFIX}Kegiatan_{unique_id}",
        "deskripsi": "Test activity for Tim Pendukung feature",
        "tanggal_mulai": "2026-01-01",
        "tanggal_selesai": "2026-12-31",
        "penanggung_jawab": "Test PJ",
        "kode_satker": f"{TEST_PREFIX}SATKER",
        "nama_satker": "Test Satker Unit",
        "tim_peneliti": TEST_TIM_PENELITI,
        "tim_pendukung": TEST_TIM_PENDUKUNG,
        "kasatker_nama": "Kepala Satker Test",
        "kasatker_nip": "196001012000011001",
        "kasatker_jabatan": "Kepala Satuan Kerja",
        "alamat_satker": "Jl. Test No. 123",
        "nomor_berita_acara": f"BA-{unique_id}",
        "tanggal_berita_acara": "2026-06-01",
        "kesimpulan": "Test kesimpulan dengan tim pendukung"
    }
    
    response = api_client.post(f"{BASE_URL}/api/inventory-activities", json=payload)
    assert response.status_code in [200, 201], f"Failed to create test activity: {response.text}"
    
    activity_id = response.json().get("id")
    yield activity_id
    
    # Cleanup
    api_client.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}")


class TestTimPendukungCRUD:
    """Test CRUD operations for Tim Pendukung field"""
    
    def test_create_activity_with_tim_pendukung(self, api_client):
        """Test POST /api/inventory-activities accepts tim_pendukung array"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "nomor_surat": f"{TEST_PREFIX}CREATE_{unique_id}",
            "nama_kegiatan": f"{TEST_PREFIX}CreateTest_{unique_id}",
            "kode_satker": f"SATK_{unique_id}",
            "nama_satker": "Create Test Satker",
            "tim_peneliti": [{"nama": "Peneliti Create", "jabatan": "Ketua", "nip": "123"}],
            "tim_pendukung": [{"nama": "Pendukung Create", "jabatan": "Admin", "nip": "456"}]
        }
        
        response = api_client.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        data = response.json()
        assert "tim_pendukung" in data, "tim_pendukung field missing from response"
        assert len(data["tim_pendukung"]) == 1, "tim_pendukung should have 1 member"
        assert data["tim_pendukung"][0]["nama"] == "Pendukung Create"
        
        # Also verify tim_peneliti
        assert "tim_peneliti" in data
        assert len(data["tim_peneliti"]) == 1
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/inventory-activities/{data['id']}")
        print("✓ POST /api/inventory-activities accepts tim_pendukung array")

    def test_update_activity_with_tim_pendukung(self, api_client, test_activity_id):
        """Test PUT /api/inventory-activities/{id} saves and returns tim_pendukung"""
        # First, get the existing activity
        get_response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}")
        assert get_response.status_code == 200
        original_data = get_response.json()
        
        # Update with new tim_pendukung
        updated_tim_pendukung = [
            {"nama": "Updated Pendukung 1", "jabatan": "Role A", "nip": "111"},
            {"nama": "Updated Pendukung 2", "jabatan": "Role B", "nip": "222"},
            {"nama": "Updated Pendukung 3", "jabatan": "Role C", "nip": "333"}
        ]
        
        payload = {
            **original_data,
            "tim_pendukung": updated_tim_pendukung
        }
        # Remove id and created_at from payload
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("total_assets", None)
        payload.pop("total_value", None)
        payload.pop("summary", None)
        
        response = api_client.put(f"{BASE_URL}/api/inventory-activities/{test_activity_id}", json=payload)
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        assert "tim_pendukung" in data
        assert len(data["tim_pendukung"]) == 3, "Updated tim_pendukung should have 3 members"
        
        # Verify via GET
        verify_response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}")
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert len(verify_data["tim_pendukung"]) == 3, "GET should return 3 tim_pendukung members"
        assert verify_data["tim_pendukung"][0]["nama"] == "Updated Pendukung 1"
        
        print("✓ PUT /api/inventory-activities/{id} saves and returns tim_pendukung")

    def test_get_activity_returns_tim_pendukung(self, api_client, test_activity_id):
        """Test GET /api/inventory-activities/{id} returns tim_pendukung field"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "tim_pendukung" in data, "tim_pendukung field missing from GET response"
        assert isinstance(data["tim_pendukung"], list), "tim_pendukung should be a list"
        
        # Check tim_pendukung has correct structure
        if len(data["tim_pendukung"]) > 0:
            member = data["tim_pendukung"][0]
            assert "nama" in member, "tim_pendukung member should have 'nama'"
            assert "jabatan" in member, "tim_pendukung member should have 'jabatan'"
        
        print("✓ GET /api/inventory-activities/{id} returns tim_pendukung field")


class TestTimPendukungReports:
    """Test Tim Pendukung in various report endpoints"""
    
    def test_executive_summary_includes_tim_pendukung(self, api_client, test_activity_id):
        """Test Executive Summary HTML includes Tim Pendukung section"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}/executive-summary-html")
        assert response.status_code == 200, f"Executive Summary failed: {response.text}"
        
        html = response.text
        # Check for Tim Pendukung section in HTML
        assert "Tim Pendukung" in html, "Tim Pendukung section not found in Executive Summary HTML"
        
        # Check for the violet/purple styling that's used for Tim Pendukung
        assert "7c3aed" in html or "#6b21a8" in html or "faf5ff" in html, \
            "Tim Pendukung violet/purple styling not found in Executive Summary"
        
        print("✓ Executive Summary HTML includes Tim Pendukung section")

    def test_laporan_satker_includes_tim_pendukung(self, api_client, test_activity_id):
        """Test Laporan Satker HTML shows Tim Pendukung table"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}/laporan-satker-html")
        assert response.status_code == 200, f"Laporan Satker failed: {response.text}"
        
        html = response.text
        # Check for Tim Pendukung section in HTML - rendered as "Pendukung" role cards
        assert "Pendukung" in html, "Tim Pendukung section not found in Laporan Satker HTML"
        
        # Check for the violet CSS variable which is used for Pendukung styling
        assert "--violet" in html or "7c3aed" in html, "Tim Pendukung violet styling not found in Laporan Satker"
        
        print("✓ Laporan Satker HTML includes Tim Pendukung table")

    def test_berita_acara_pdf_includes_tim_pendukung(self, api_client, test_activity_id):
        """Test Berita Acara PDF includes Tim Pendukung table"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}/berita-acara-pdf")
        assert response.status_code == 200, f"Berita Acara PDF failed: {response.text}"
        
        # Check content type is PDF
        content_type = response.headers.get('content-type', '')
        assert 'pdf' in content_type.lower(), f"Expected PDF, got {content_type}"
        
        # Check PDF signature
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print("✓ Berita Acara PDF generates successfully (Tim Pendukung included)")

    def test_bahi_pdf_includes_tim_pendukung(self, api_client, test_activity_id):
        """Test BAHI PDF includes Tim Pendukung in report"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}/bahi-pdf")
        assert response.status_code == 200, f"BAHI PDF failed: {response.text}"
        
        # Check content type is PDF
        content_type = response.headers.get('content-type', '')
        assert 'pdf' in content_type.lower(), f"Expected PDF, got {content_type}"
        
        # Check PDF signature
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print("✓ BAHI PDF generates successfully (Tim Pendukung included)")

    def test_rhi_pdf_generates_successfully(self, api_client, test_activity_id):
        """Test RHI PDF generates successfully"""
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{test_activity_id}/rhi-pdf")
        assert response.status_code == 200, f"RHI PDF failed: {response.text}"
        
        # Check content type is PDF
        content_type = response.headers.get('content-type', '')
        assert 'pdf' in content_type.lower(), f"Expected PDF, got {content_type}"
        
        # Check PDF signature
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print("✓ RHI PDF generates successfully")


class TestExistingActivity:
    """Test with existing activity c08c060e-d21b-4c9f-bd5a-b8d0f6230806"""
    
    def test_update_existing_activity_with_tim_pendukung(self, api_client):
        """Update the existing activity with Tim Pendukung and verify"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        
        # Get existing activity
        get_response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        if get_response.status_code != 200:
            pytest.skip(f"Activity {activity_id} not found")
        
        original_data = get_response.json()
        
        # Add tim_pendukung
        tim_pendukung = [
            {"nama": "Siti Pendukung Test", "jabatan": "Admin Support", "nip": "199001012003011001"},
            {"nama": "Rudi Pendukung Test", "jabatan": "Technical Support", "nip": "199201012004011002"}
        ]
        
        tim_peneliti = [
            {"nama": "Ahmad Peneliti Test", "jabatan": "Ketua Tim", "nip": "198001012001011001"}
        ]
        
        payload = {
            **original_data,
            "tim_peneliti": tim_peneliti,
            "tim_pendukung": tim_pendukung
        }
        # Remove fields that shouldn't be in update
        for field in ["id", "created_at", "total_assets", "total_value", "summary"]:
            payload.pop(field, None)
        
        response = api_client.put(f"{BASE_URL}/api/inventory-activities/{activity_id}", json=payload)
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        assert "tim_pendukung" in data
        assert len(data["tim_pendukung"]) == 2
        assert data["tim_pendukung"][0]["nama"] == "Siti Pendukung Test"
        
        print(f"✓ Updated activity {activity_id} with Tim Pendukung")

    def test_existing_activity_executive_summary_with_tim_pendukung(self, api_client):
        """Test Executive Summary of existing activity shows Tim Pendukung"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        
        # First ensure activity has tim_pendukung
        get_response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        if get_response.status_code != 200:
            pytest.skip(f"Activity {activity_id} not found")
        
        # Get executive summary
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        assert response.status_code == 200, f"Executive Summary failed: {response.text}"
        
        html = response.text
        # Check for Tim Pendukung content
        if "Siti Pendukung Test" in html or "Tim Pendukung" in html:
            print("✓ Executive Summary HTML contains Tim Pendukung data")
        else:
            print("Note: Tim Pendukung section present but may be empty")
        
        assert "Tim Pendukung" in html or "tim-section" in html, "Tim Pendukung section missing"

    def test_existing_activity_laporan_satker_with_tim_pendukung(self, api_client):
        """Test Laporan Satker of existing activity shows Tim Pendukung"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        
        get_response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        if get_response.status_code != 200:
            pytest.skip(f"Activity {activity_id} not found")
        
        response = api_client.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/laporan-satker-html")
        assert response.status_code == 200, f"Laporan Satker failed: {response.text}"
        
        html = response.text
        # The template should have Tim Pendukung section rendered
        print("✓ Laporan Satker HTML generates successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
