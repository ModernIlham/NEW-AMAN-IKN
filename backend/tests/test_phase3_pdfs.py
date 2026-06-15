"""
Test Suite for LKPP 85/2025 Phase 3: Official Report PDFs
- RHI (Rekapitulasi Hasil Inventarisasi)
- BAHI (Berita Acara Hasil Inventarisasi - comprehensive)
- Surat Pernyataan Hasil Inventarisasi BMN
- Surat Pernyataan Pelaksanaan Inventarisasi BMN
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test activity ID confirmed working from previous iterations
TEST_ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"
NON_EXISTENT_ACTIVITY_ID = "00000000-0000-0000-0000-000000000000"


class TestRHIPDF:
    """Test RHI (Rekapitulasi Hasil Inventarisasi) PDF endpoint"""
    
    def test_rhi_pdf_returns_valid_pdf(self):
        """RHI endpoint returns valid PDF with 200 status"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        
        # Verify reasonable size (PDF should be more than just headers)
        assert len(response.content) > 1000, f"PDF seems too small: {len(response.content)} bytes"
        
        print(f"✓ RHI PDF: {len(response.content)} bytes, valid PDF header")
    
    def test_rhi_pdf_404_for_nonexistent_activity(self):
        """RHI endpoint returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{NON_EXISTENT_ACTIVITY_ID}/rhi-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ RHI PDF returns 404 for non-existent activity")


class TestBAHIPDF:
    """Test BAHI (Berita Acara Hasil Inventarisasi) PDF endpoint"""
    
    def test_bahi_pdf_returns_valid_pdf(self):
        """BAHI endpoint returns valid PDF with 200 status"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/bahi-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        
        # BAHI is comprehensive, should be larger
        assert len(response.content) > 2000, f"PDF seems too small: {len(response.content)} bytes"
        
        print(f"✓ BAHI PDF: {len(response.content)} bytes, valid PDF header")
    
    def test_bahi_pdf_404_for_nonexistent_activity(self):
        """BAHI endpoint returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{NON_EXISTENT_ACTIVITY_ID}/bahi-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ BAHI PDF returns 404 for non-existent activity")


class TestSPHasilPDF:
    """Test Surat Pernyataan Hasil Inventarisasi BMN PDF endpoint"""
    
    def test_sp_hasil_pdf_returns_valid_pdf(self):
        """SP Hasil endpoint returns valid PDF with 200 status"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-hasil-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        
        assert len(response.content) > 1000, f"PDF seems too small: {len(response.content)} bytes"
        
        print(f"✓ SP Hasil PDF: {len(response.content)} bytes, valid PDF header")
    
    def test_sp_hasil_pdf_404_for_nonexistent_activity(self):
        """SP Hasil endpoint returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{NON_EXISTENT_ACTIVITY_ID}/sp-hasil-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ SP Hasil PDF returns 404 for non-existent activity")


class TestSPPelaksanaanPDF:
    """Test Surat Pernyataan Pelaksanaan Inventarisasi BMN PDF endpoint"""
    
    def test_sp_pelaksanaan_pdf_returns_valid_pdf(self):
        """SP Pelaksanaan endpoint returns valid PDF with 200 status"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-pelaksanaan-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        
        assert len(response.content) > 1000, f"PDF seems too small: {len(response.content)} bytes"
        
        print(f"✓ SP Pelaksanaan PDF: {len(response.content)} bytes, valid PDF header")
    
    def test_sp_pelaksanaan_pdf_404_for_nonexistent_activity(self):
        """SP Pelaksanaan endpoint returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{NON_EXISTENT_ACTIVITY_ID}/sp-pelaksanaan-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ SP Pelaksanaan PDF returns 404 for non-existent activity")


class TestExistingReports:
    """Test that existing report endpoints still work (Dokumen Pendukung Lainnya)"""
    
    def test_berita_acara_pdf_still_works(self):
        """Existing BA Tidak Ditemukan endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/berita-acara-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        print(f"✓ BA Tidak Ditemukan PDF still works: {len(response.content)} bytes")
    
    def test_sptjm_pdf_still_works(self):
        """Existing SPTJM endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sptjm-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        print(f"✓ SPTJM PDF still works: {len(response.content)} bytes")
    
    def test_surat_koreksi_pdf_still_works(self):
        """Existing Surat Koreksi endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/surat-koreksi-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF', "Response doesn't start with PDF header"
        print(f"✓ Surat Koreksi PDF still works: {len(response.content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
