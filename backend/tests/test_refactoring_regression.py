"""
Regression tests for major refactoring (iteration 28).
Tests all report PDF endpoints that were moved from server.py to routes/reports.py.
Also tests report-settings and inventory-classifications endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

# Test activity ID from previous iterations
TEST_ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"


class TestHealthAndBasics:
    """Test basic endpoints after refactoring"""
    
    def test_health_check(self):
        """Backend main health check endpoint"""
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        print("✓ Health check passed")
    
    def test_report_settings_get(self):
        """GET /api/report-settings returns type: global"""
        r = requests.get(f"{BASE_URL}/api/report-settings")
        assert r.status_code == 200
        data = r.json()
        assert data.get("type") == "global", f"Expected type='global', got {data.get('type')}"
        print(f"✓ Report settings GET passed - type={data.get('type')}")
    
    def test_report_settings_put(self):
        """PUT /api/report-settings updates settings"""
        test_data = {"nama_instansi": "Test Update Instansi", "tahun_anggaran": "2025"}
        r = requests.put(f"{BASE_URL}/api/report-settings", json=test_data)
        assert r.status_code == 200
        data = r.json()
        assert data.get("nama_instansi") == "Test Update Instansi"
        print("✓ Report settings PUT passed")
    
    def test_inventory_classifications(self):
        """GET /api/inventory-classifications returns correct fields"""
        r = requests.get(f"{BASE_URL}/api/inventory-classifications")
        assert r.status_code == 200
        data = r.json()
        # Must have these 5 fields (inventory_statuses instead of statuses as per actual response)
        required_fields = ["inventory_statuses", "klasifikasi", "sub_klasifikasi", "berlebih_info", "sengketa_info"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        print(f"✓ Inventory classifications passed - fields: {list(data.keys())}")


class TestRekapitulasiEndpoint:
    """Test rekapitulasi endpoint (now in routes/reports.py)"""
    
    def test_rekapitulasi_get(self):
        """GET /api/inventory-activities/{id}/rekapitulasi"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rekapitulasi")
        assert r.status_code == 200
        data = r.json()
        # Check required fields
        assert "total_bmn_diteliti" in data
        assert "ditemukan" in data
        assert "tidak_ditemukan" in data
        assert "berlebih" in data
        assert "sengketa" in data
        print(f"✓ Rekapitulasi passed - total={data.get('total_bmn_diteliti')}")
    
    def test_rekapitulasi_invalid_activity(self):
        """GET rekapitulasi with invalid ID returns 404"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/invalid-id-12345/rekapitulasi")
        assert r.status_code == 404
        print("✓ Rekapitulasi 404 for invalid ID passed")


class TestPDFEndpoints:
    """Test all PDF report endpoints that were moved to routes/reports.py"""
    
    def test_berita_acara_pdf(self):
        """GET /api/inventory-activities/{id}/berita-acara-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/berita-acara-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ Berita Acara PDF passed - size={len(r.content)} bytes")
    
    def test_sptjm_pdf(self):
        """GET /api/inventory-activities/{id}/sptjm-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sptjm-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ SPTJM PDF passed - size={len(r.content)} bytes")
    
    def test_surat_koreksi_pdf(self):
        """GET /api/inventory-activities/{id}/surat-koreksi-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/surat-koreksi-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ Surat Koreksi PDF passed - size={len(r.content)} bytes")
    
    def test_rhi_pdf(self):
        """GET /api/inventory-activities/{id}/rhi-pdf (Rekapitulasi Hasil Inventarisasi)"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ RHI PDF passed - size={len(r.content)} bytes")
    
    def test_bahi_pdf(self):
        """GET /api/inventory-activities/{id}/bahi-pdf (Berita Acara Hasil Inventarisasi)"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/bahi-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ BAHI PDF passed - size={len(r.content)} bytes")
    
    def test_sp_hasil_pdf(self):
        """GET /api/inventory-activities/{id}/sp-hasil-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-hasil-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ SP Hasil PDF passed - size={len(r.content)} bytes")
    
    def test_sp_pelaksanaan_pdf(self):
        """GET /api/inventory-activities/{id}/sp-pelaksanaan-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/sp-pelaksanaan-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ SP Pelaksanaan PDF passed - size={len(r.content)} bytes")
    
    def test_lhi_pdf(self):
        """GET /api/inventory-activities/{id}/lhi-pdf (Laporan Hasil Inventarisasi Lengkap)"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/lhi-pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ LHI PDF passed - size={len(r.content)} bytes")
    
    def test_executive_summary_pdf(self):
        """GET /api/inventory-activities/{id}/executive-summary-pdf"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        print(f"✓ Executive Summary PDF passed - size={len(r.content)} bytes")
    
    def test_executive_summary_html(self):
        """GET /api/inventory-activities/{id}/executive-summary-html"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert b"<!DOCTYPE html>" in r.content or b"<html" in r.content
        print(f"✓ Executive Summary HTML passed - size={len(r.content)} bytes")


class TestDBHIEndpoints:
    """Test DBHI (Daftar Barang Hasil Inventarisasi) PDF endpoints"""
    
    def test_dbhi_kondisi_baik(self):
        """GET /api/inventory-activities/{id}/dbhi/kondisi-baik"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/kondisi-baik")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Kondisi Baik passed - size={len(r.content)} bytes")
    
    def test_dbhi_kondisi_rusak_ringan(self):
        """GET /api/inventory-activities/{id}/dbhi/kondisi-rusak-ringan"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/kondisi-rusak-ringan")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Rusak Ringan passed - size={len(r.content)} bytes")
    
    def test_dbhi_kondisi_rusak_berat(self):
        """GET /api/inventory-activities/{id}/dbhi/kondisi-rusak-berat"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/kondisi-rusak-berat")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Rusak Berat passed - size={len(r.content)} bytes")
    
    def test_dbhi_berlebih(self):
        """GET /api/inventory-activities/{id}/dbhi/berlebih"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/berlebih")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Berlebih passed - size={len(r.content)} bytes")
    
    def test_dbhi_tidak_ditemukan(self):
        """GET /api/inventory-activities/{id}/dbhi/tidak-ditemukan"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/tidak-ditemukan")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Tidak Ditemukan passed - size={len(r.content)} bytes")
    
    def test_dbhi_sengketa(self):
        """GET /api/inventory-activities/{id}/dbhi/sengketa"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/sengketa")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        print(f"✓ DBHI Sengketa passed - size={len(r.content)} bytes")
    
    def test_dbhi_invalid_type(self):
        """GET /api/inventory-activities/{id}/dbhi/{invalid} returns 400"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/dbhi/invalid-type")
        assert r.status_code == 400
        print("✓ DBHI invalid type returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
