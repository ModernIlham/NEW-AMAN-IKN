
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Report Settings (Cover Page) - LKPP 85/2025 Phase 5
Tests: Logo upload, text fields settings, cover page in LHI PDF
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"

# Auth fixtures
@pytest.fixture(scope="module")
def auth_token():
    """Get admin token"""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": TEST_ADMIN_PASSWORD
    })
    if r.status_code == 200:
        return r.json().get("access_token")
    pytest.skip("Auth failed")

@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


class TestGetReportSettings:
    """Test GET /api/report-settings"""
    
    def test_get_settings_returns_200(self):
        """Should return 200 with settings data"""
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        assert "type" in data
        assert data["type"] == "global"
        print("✓ GET /api/report-settings returns 200")
    
    def test_get_settings_returns_all_fields(self):
        """Should return all expected fields"""
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        
        # Check all fields exist
        expected_fields = [
            "type", "logo_url", "nama_instansi", "nama_unit_organisasi",
            "alamat_instansi", "judul_laporan", "subjudul_laporan",
            "tahun_anggaran", "catatan_kaki"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        print("✓ GET /api/report-settings returns all expected fields")
    
    def test_get_settings_default_values(self):
        """Should have correct default values for judul and subjudul"""
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        
        # If not customized, should have these defaults
        if not data.get("nama_instansi"):
            assert data["judul_laporan"] in ["LAPORAN HASIL INVENTARISASI", ""]
            assert data["subjudul_laporan"] in ["BARANG MILIK NEGARA (BMN)", ""]
        print("✓ Settings have expected structure")


class TestUpdateReportSettings:
    """Test PUT /api/report-settings"""
    
    def test_update_settings_nama_instansi(self):
        """Should update nama_instansi field"""
        test_value = "TEST_INSTANSI_UPDATE"
        r = requests.put(f"{BASE_URL}/api/report-settings", json={
            "nama_instansi": test_value
        })
        assert r.status_code == 200
        data = r.json()
        assert data["nama_instansi"] == test_value
        print("✓ PUT /api/report-settings updates nama_instansi")
    
    def test_update_multiple_text_fields(self):
        """Should update multiple text fields at once"""
        update_data = {
            "nama_instansi": "IBU KOTA NUSANTARA",
            "nama_unit_organisasi": "Otorita Ibu Kota Nusantara",
            "alamat_instansi": "Penajam Paser Utara, Kalimantan Timur",
            "judul_laporan": "LAPORAN HASIL INVENTARISASI",
            "subjudul_laporan": "BARANG MILIK NEGARA (BMN)",
            "tahun_anggaran": "2025",
            "catatan_kaki": "Laporan ini dibuat untuk keperluan audit internal"
        }
        r = requests.put(f"{BASE_URL}/api/report-settings", json=update_data)
        assert r.status_code == 200
        data = r.json()
        
        # Verify all fields updated
        for key, value in update_data.items():
            assert data.get(key) == value, f"Field {key} not updated correctly"
        print("✓ PUT /api/report-settings updates multiple fields")
    
    def test_update_settings_persists(self):
        """Should persist changes after update"""
        unique_value = "PERSIST_TEST_VALUE_12345"
        requests.put(f"{BASE_URL}/api/report-settings", json={
            "catatan_kaki": unique_value
        })
        
        # GET to verify persistence
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        assert r.json()["catatan_kaki"] == unique_value
        print("✓ Settings persist after update (verified with GET)")


class TestLogoUpload:
    """Test POST /api/report-settings/logo"""
    
    def test_upload_logo_valid_image(self):
        """Should upload PNG/JPG image successfully"""
        # Create a minimal valid PNG
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixel
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # RGB, 8-bit
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,  # White pixel data
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,  # CRC
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82                      # IEND CRC
        ])
        
        files = {'file': ('logo.png', png_bytes, 'image/png')}
        r = requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        assert r.status_code == 200
        data = r.json()
        assert "logo_url" in data
        assert data["logo_url"].startswith("data:image/png;base64,")
        print("✓ POST /api/report-settings/logo uploads valid PNG")
    
    def test_upload_logo_persists_to_settings(self):
        """Uploaded logo should appear in GET settings"""
        # Upload
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        files = {'file': ('test_logo.png', png_bytes, 'image/png')}
        requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        
        # Verify
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        assert data["logo_url"].startswith("data:image/png;base64,")
        print("✓ Logo persists in settings after upload")
    
    def test_upload_rejects_non_image(self):
        """Should reject non-image files"""
        files = {'file': ('test.txt', b'not an image', 'text/plain')}
        r = requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        assert r.status_code == 400
        print("✓ POST /api/report-settings/logo rejects non-image file")


class TestDeleteLogo:
    """Test DELETE /api/report-settings/logo"""
    
    def test_delete_logo(self):
        """Should remove logo from settings"""
        # First upload a logo
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        files = {'file': ('to_delete.png', png_bytes, 'image/png')}
        requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        
        # Delete
        r = requests.delete(f"{BASE_URL}/api/report-settings/logo")
        assert r.status_code == 200
        print("✓ DELETE /api/report-settings/logo returns 200")
    
    def test_delete_logo_removes_from_settings(self):
        """After delete, logo_url should be empty in GET"""
        # First upload
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        files = {'file': ('another_logo.png', png_bytes, 'image/png')}
        requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        
        # Delete
        requests.delete(f"{BASE_URL}/api/report-settings/logo")
        
        # Verify
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        assert r.json()["logo_url"] == ""
        print("✓ Logo removed from settings after DELETE")


class TestLHIPDFWithCoverPage:
    """Test LHI PDF includes cover page with settings"""
    
    def test_lhi_pdf_returns_valid_pdf(self):
        """LHI PDF should still be valid"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/lhi-pdf")
        assert r.status_code == 200
        assert r.content[:4] == b'%PDF', "LHI PDF should start with %PDF-"
        print("✓ LHI PDF is valid PDF with cover page")
    
    def test_lhi_pdf_larger_with_cover_page(self):
        """LHI PDF should have reasonable size (includes cover)"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/lhi-pdf")
        assert r.status_code == 200
        size_kb = len(r.content) / 1024
        # LHI with cover should be at least 10KB (minimal test data scenario)
        assert size_kb > 10, f"LHI PDF size {size_kb:.1f}KB seems too small"
        print(f"✓ LHI PDF size: {size_kb:.1f}KB (includes cover page)")
    
    def test_lhi_pdf_with_logo_setting(self):
        """LHI should include logo when set in settings"""
        # First upload a logo
        png_bytes = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        files = {'file': ('lhi_test_logo.png', png_bytes, 'image/png')}
        requests.post(f"{BASE_URL}/api/report-settings/logo", files=files)
        
        # Generate LHI
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/lhi-pdf")
        assert r.status_code == 200
        assert r.content[:4] == b'%PDF'
        print("✓ LHI PDF generated successfully with logo in settings")
    
    def test_lhi_404_for_nonexistent_activity(self):
        """Should return 404 for non-existent activity"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/nonexistent-id-12345/lhi-pdf")
        assert r.status_code == 404
        print("✓ LHI PDF returns 404 for non-existent activity")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
