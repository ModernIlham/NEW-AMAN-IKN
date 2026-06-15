"""
Test DBHI PDF Reports - LKPP 85/2025 Phase 2
Tests all 6 DBHI (Daftar Barang Hasil Inventarisasi) PDF report endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"

class TestDBHIPDFReports:
    """Test DBHI PDF report generation endpoints"""
    
    def test_dbhi_kondisi_baik_returns_pdf(self):
        """Test kondisi-baik DBHI PDF endpoint returns 200 with PDF content"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/kondisi-baik")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ kondisi-baik PDF: {len(response.content)} bytes")
    
    def test_dbhi_kondisi_rusak_ringan_returns_pdf(self):
        """Test kondisi-rusak-ringan DBHI PDF endpoint returns 200 with PDF content"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/kondisi-rusak-ringan")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ kondisi-rusak-ringan PDF: {len(response.content)} bytes")
    
    def test_dbhi_kondisi_rusak_berat_returns_pdf(self):
        """Test kondisi-rusak-berat DBHI PDF endpoint returns 200 with PDF content"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/kondisi-rusak-berat")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ kondisi-rusak-berat PDF: {len(response.content)} bytes")
    
    def test_dbhi_berlebih_returns_pdf(self):
        """Test berlebih DBHI PDF endpoint returns 200 with PDF content
        This type has extra columns: Keterangan Berlebih, Asal Usul, Tindak Lanjut
        """
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/berlebih")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ berlebih PDF: {len(response.content)} bytes")
    
    def test_dbhi_tidak_ditemukan_returns_pdf(self):
        """Test tidak-ditemukan DBHI PDF endpoint returns 200 with PDF content
        This type has extra columns: Klasifikasi, Sub Klasifikasi, Uraian, Tindak Lanjut
        """
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/tidak-ditemukan")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ tidak-ditemukan PDF: {len(response.content)} bytes")
    
    def test_dbhi_sengketa_returns_pdf(self):
        """Test sengketa DBHI PDF endpoint returns 200 with PDF content
        This type has extra columns: No. Perkara, Pihak Bersengketa, Keterangan Sengketa
        """
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/sengketa")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"✓ sengketa PDF: {len(response.content)} bytes")
    
    def test_invalid_dbhi_type_returns_400(self):
        """Test that invalid DBHI type returns 400 error"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/invalid-type")
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got {response.status_code}"
        # Verify error message mentions valid types
        data = response.json()
        assert "detail" in data, "Error response should have detail field"
        assert "tidak valid" in data["detail"].lower() or "invalid" in data["detail"].lower(), "Error should indicate invalid type"
        print("✓ Invalid DBHI type correctly returns 400")
    
    def test_nonexistent_activity_returns_404(self):
        """Test that non-existent activity ID returns 404"""
        fake_activity_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{fake_activity_id}/dbhi/kondisi-baik")
        
        assert response.status_code == 404, f"Expected 404 for non-existent activity, got {response.status_code}"
        print("✓ Non-existent activity correctly returns 404")


class TestDBHIPDFContentValidation:
    """Validate PDF content starts with correct PDF header"""
    
    def test_pdf_valid_format(self):
        """Verify that PDF content is valid (starts with %PDF)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/dbhi/kondisi-baik")
        
        assert response.status_code == 200
        # PDF files start with %PDF magic bytes
        assert response.content[:4] == b'%PDF', "PDF content should start with %PDF header"
        print("✓ PDF has valid %PDF header")


class TestRekapitulasiDBHICounts:
    """Test that rekapitulasi endpoint returns correct counts for DBHI buttons"""
    
    def test_rekapitulasi_returns_condition_breakdown(self):
        """Verify rekapitulasi returns data needed for DBHI button counts"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/rekapitulasi")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check ditemukan breakdown exists
        assert "ditemukan" in data, "Should have ditemukan data"
        ditemukan = data["ditemukan"]
        assert "kondisi_baik" in ditemukan, "Should have kondisi_baik breakdown"
        assert "kondisi_rusak_ringan" in ditemukan, "Should have kondisi_rusak_ringan breakdown"
        assert "kondisi_rusak_berat" in ditemukan, "Should have kondisi_rusak_berat breakdown"
        
        # Check berlebih exists
        assert "berlebih" in data, "Should have berlebih data"
        assert "count" in data["berlebih"], "Berlebih should have count"
        
        # Check tidak_ditemukan exists
        assert "tidak_ditemukan" in data, "Should have tidak_ditemukan data"
        assert "count" in data["tidak_ditemukan"], "Tidak ditemukan should have count"
        
        # Check sengketa exists
        assert "sengketa" in data, "Should have sengketa data"
        assert "count" in data["sengketa"], "Sengketa should have count"
        
        print(f"✓ Rekapitulasi breakdown: kondisi_baik={ditemukan.get('kondisi_baik', {}).get('count', 0)}, "
              f"rusak_ringan={ditemukan.get('kondisi_rusak_ringan', {}).get('count', 0)}, "
              f"rusak_berat={ditemukan.get('kondisi_rusak_berat', {}).get('count', 0)}, "
              f"berlebih={data['berlebih'].get('count', 0)}, "
              f"tidak_ditemukan={data['tidak_ditemukan'].get('count', 0)}, "
              f"sengketa={data['sengketa'].get('count', 0)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
