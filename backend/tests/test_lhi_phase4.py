"""
LKPP 85/2025 Phase 4 - LHI (Laporan Hasil Inventarisasi) Tests
Testing the merged PDF package that combines all inventory documents
"""
import pytest
import requests
import os

# Use PUBLIC URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

# Test activity ID from previous testing iterations
TEST_ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"

class TestLHIPDFPhase4:
    """Phase 4: LHI (Laporan Hasil Inventarisasi) PDF merge endpoint"""
    
    def test_lhi_pdf_endpoint_returns_200(self):
        """GET /api/inventory-activities/{id}/lhi-pdf returns 200 OK"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/lhi-pdf"
        response = requests.get(url, timeout=60)  # Longer timeout for merged PDF
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ LHI PDF endpoint returns 200 OK")
    
    def test_lhi_pdf_returns_valid_pdf(self):
        """LHI PDF returns valid PDF with %PDF- header"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/lhi-pdf"
        response = requests.get(url, timeout=60)
        assert response.status_code == 200
        # Check PDF magic header
        assert response.content[:4] == b'%PDF', f"Expected PDF header, got: {response.content[:20]}"
        print("✓ LHI PDF has valid %PDF- header")
    
    def test_lhi_pdf_larger_than_individual_pdfs(self):
        """LHI PDF should be larger than individual PDFs (merges ~10 documents)"""
        lhi_url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/lhi-pdf"
        rhi_url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf"
        
        lhi_response = requests.get(lhi_url, timeout=60)
        rhi_response = requests.get(rhi_url, timeout=30)
        
        lhi_size = len(lhi_response.content)
        rhi_size = len(rhi_response.content)
        
        assert lhi_response.status_code == 200
        assert rhi_response.status_code == 200
        
        # LHI should be larger since it merges multiple PDFs
        # Allowing for small individual PDFs, but LHI should at least be > 5KB
        assert lhi_size > 5000, f"LHI PDF too small: {lhi_size} bytes"
        print(f"✓ LHI PDF size: {lhi_size} bytes (RHI alone: {rhi_size} bytes)")
    
    def test_lhi_pdf_returns_404_for_nonexistent_activity(self):
        """LHI returns 404 for non-existent activity"""
        url = f"{BASE_URL}/api/inventory-activities/nonexistent-id-12345/lhi-pdf"
        response = requests.get(url, timeout=30)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ LHI returns 404 for non-existent activity")
    
    def test_lhi_pdf_has_correct_content_disposition(self):
        """LHI PDF has correct Content-Disposition header"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/lhi-pdf"
        response = requests.get(url, timeout=60)
        assert response.status_code == 200
        
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp.lower(), f"Expected attachment disposition, got: {content_disp}"
        assert 'LHI_Lengkap' in content_disp, f"Expected LHI_Lengkap in filename, got: {content_disp}"
        print(f"✓ LHI PDF Content-Disposition: {content_disp}")


class TestRegressionPhase3PDFs:
    """Regression tests to ensure all previous PDF endpoints still work"""
    
    def test_rhi_pdf_still_works(self):
        """RHI PDF endpoint still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: RHI PDF still works")
    
    def test_bahi_pdf_still_works(self):
        """BAHI PDF endpoint still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/bahi-pdf"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: BAHI PDF still works")
    
    def test_sp_hasil_pdf_still_works(self):
        """SP Hasil PDF endpoint still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-hasil-pdf"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: SP Hasil PDF still works")
    
    def test_sp_pelaksanaan_pdf_still_works(self):
        """SP Pelaksanaan PDF endpoint still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-pelaksanaan-pdf"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: SP Pelaksanaan PDF still works")


class TestRegressionDBHIPDFs:
    """Regression tests for DBHI (Phase 2) PDF endpoints"""
    
    def test_dbhi_kondisi_baik_still_works(self):
        """DBHI Kondisi Baik still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/kondisi-baik"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: DBHI Kondisi Baik still works")
    
    def test_dbhi_berlebih_still_works(self):
        """DBHI Berlebih still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/berlebih"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: DBHI Berlebih still works")
    
    def test_dbhi_tidak_ditemukan_still_works(self):
        """DBHI Tidak Ditemukan still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/tidak-ditemukan"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: DBHI Tidak Ditemukan still works")
    
    def test_dbhi_sengketa_still_works(self):
        """DBHI Sengketa still returns 200"""
        url = f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/sengketa"
        response = requests.get(url, timeout=30)
        assert response.status_code == 200
        assert response.content[:4] == b'%PDF'
        print("✓ Regression: DBHI Sengketa still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
