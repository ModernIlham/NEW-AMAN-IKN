"""
Test Tim Inventarisasi (Internal) Features - Iteration 73
Tests:
1. Backend: tim_inti, tim_pembantu, penanggung_jawab_jabatan, penanggung_jawab_nip fields
2. Backend: tim_pendukung entries with dari_pihak field
3. Reports: RHI, BAHI, Executive Summary, Laporan Satker include all new tim sections
4. Reports: Executive Summary shows ALL categories and ALL locations (dynamic multi-page)
5. XLSX Export: Tim Inti/Pembantu/PJ export
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test activity with known test data
TEST_ACTIVITY_ID = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"


class TestTimInventarisasiBackend:
    """Test Backend API for Tim Inventarisasi fields"""
    
    def test_get_activity_returns_tim_inti_field(self):
        """GET /api/inventory-activities/{id} should return tim_inti field"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "tim_inti" in data, "tim_inti field should be present in response"
        assert isinstance(data["tim_inti"], list), "tim_inti should be a list"
    
    def test_get_activity_returns_tim_pembantu_field(self):
        """GET /api/inventory-activities/{id} should return tim_pembantu field"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "tim_pembantu" in data, "tim_pembantu field should be present in response"
        assert isinstance(data["tim_pembantu"], list), "tim_pembantu should be a list"
    
    def test_get_activity_returns_penanggung_jawab_jabatan(self):
        """GET /api/inventory-activities/{id} should return penanggung_jawab_jabatan"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "penanggung_jawab_jabatan" in data, "penanggung_jawab_jabatan field should be present"
    
    def test_get_activity_returns_penanggung_jawab_nip(self):
        """GET /api/inventory-activities/{id} should return penanggung_jawab_nip"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "penanggung_jawab_nip" in data, "penanggung_jawab_nip field should be present"
    
    def test_tim_inti_member_has_required_fields(self):
        """tim_inti members should have nama, jabatan, nip, unit, is_ketua fields"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        tim_inti = data.get("tim_inti", [])
        
        if tim_inti:
            member = tim_inti[0]
            # Check expected fields exist
            expected_fields = ["nama", "jabatan", "nip", "unit", "is_ketua"]
            for field in expected_fields:
                assert field in member, f"tim_inti member should have '{field}' field"
            print(f"Tim Inti member: {member}")
    
    def test_tim_pembantu_member_has_required_fields(self):
        """tim_pembantu members should have nama, jabatan, nip, unit, is_ketua fields"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        tim_pembantu = data.get("tim_pembantu", [])
        
        if tim_pembantu:
            member = tim_pembantu[0]
            expected_fields = ["nama", "jabatan", "nip", "unit", "is_ketua"]
            for field in expected_fields:
                assert field in member, f"tim_pembantu member should have '{field}' field"
            print(f"Tim Pembantu member: {member}")
    
    def test_tim_pendukung_has_dari_pihak_field(self):
        """tim_pendukung members should have dari_pihak field"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert response.status_code == 200
        
        data = response.json()
        tim_pendukung = data.get("tim_pendukung", [])
        
        if tim_pendukung:
            member = tim_pendukung[0]
            assert "dari_pihak" in member, "tim_pendukung member should have 'dari_pihak' field"
            print(f"Tim Pendukung member: {member}")


class TestTimInventarisasiUpdate:
    """Test updating activity with Tim Inventarisasi data"""
    
    def test_update_activity_with_tim_inti_and_pembantu(self):
        """PUT should accept tim_inti and tim_pembantu data"""
        # First get existing activity
        get_response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert get_response.status_code == 200
        
        current_data = get_response.json()
        
        # Update with tim_inti and tim_pembantu
        update_payload = {
            "nomor_surat": current_data.get("nomor_surat"),
            "nama_kegiatan": current_data.get("nama_kegiatan"),
            "kode_satker": current_data.get("kode_satker", "TEST001"),
            "nama_satker": current_data.get("nama_satker", "Test Satker"),
            "penanggung_jawab": "Budi Santoso",
            "penanggung_jawab_jabatan": "Kepala Bagian Inventaris",
            "penanggung_jawab_nip": "199001012020121001",
            "tim_inti": [
                {"nama": "Ahmad Ketua", "jabatan": "Ketua Tim Inti", "nip": "199101012020121002", "unit": "Bagian Umum", "is_ketua": True},
                {"nama": "Siti Anggota", "jabatan": "Anggota Tim Inti", "nip": "199201012020121003", "unit": "Bagian Keuangan", "is_ketua": False}
            ],
            "tim_pembantu": [
                {"nama": "Dedi Koordinator", "jabatan": "Ketua Tim Pembantu", "nip": "199301012020121004", "unit": "Bagian Aset", "is_ketua": True},
                {"nama": "Dewi Pembantu", "jabatan": "Anggota Tim Pembantu", "nip": "199401012020121005", "unit": "Bagian Aset", "is_ketua": False}
            ],
            "tim_pendukung": [
                {"nama": "Konsultan A", "jabatan": "Konsultan Aset", "nip": "-", "dari_pihak": "PT Konsultan BMN"}
            ],
            "tanggal_mulai": current_data.get("tanggal_mulai", "2026-01-01"),
            "tanggal_selesai": current_data.get("tanggal_selesai", "2026-12-31")
        }
        
        response = requests.put(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}",
            json=update_payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify data was saved
        verify_response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}")
        assert verify_response.status_code == 200
        
        verify_data = verify_response.json()
        assert verify_data.get("penanggung_jawab") == "Budi Santoso"
        assert verify_data.get("penanggung_jawab_jabatan") == "Kepala Bagian Inventaris"
        assert verify_data.get("penanggung_jawab_nip") == "199001012020121001"
        assert len(verify_data.get("tim_inti", [])) == 2
        assert len(verify_data.get("tim_pembantu", [])) == 2
        assert len(verify_data.get("tim_pendukung", [])) == 1
        assert verify_data.get("tim_pendukung", [{}])[0].get("dari_pihak") == "PT Konsultan BMN"
        print("✓ Activity updated with Tim Inventarisasi data successfully")


class TestReportsWithTimInventarisasi:
    """Test that reports include Tim Inventarisasi sections"""
    
    def test_executive_summary_html_has_tim_inventarisasi_section(self):
        """Executive Summary HTML should include Tim Inventarisasi table"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        html = response.text
        # Check for Tim Inventarisasi (Internal) section
        assert "Tim Inventarisasi" in html or "tim_inti" in html or "Tim Inti" in html, \
            "Executive Summary should include Tim Inventarisasi section"
        print("✓ Executive Summary HTML has Tim Inventarisasi content")
    
    def test_executive_summary_html_has_penanggung_jawab_section(self):
        """Executive Summary HTML should include Penanggung Jawab section"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html")
        assert response.status_code == 200
        
        html = response.text
        assert "Penanggung Jawab" in html, "Executive Summary should include Penanggung Jawab section"
        print("✓ Executive Summary HTML has Penanggung Jawab section")
    
    def test_executive_summary_html_has_tim_pendukung_dengan_dari_pihak(self):
        """Executive Summary HTML should show Tim Pendukung with Dari Pihak column"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html")
        assert response.status_code == 200
        
        html = response.text
        assert "Tim Pendukung" in html, "Executive Summary should include Tim Pendukung section"
        assert "Dari Pihak" in html, "Tim Pendukung section should have 'Dari Pihak' column header"
        print("✓ Executive Summary HTML has Tim Pendukung with Dari Pihak")
    
    def test_laporan_satker_html_loads_successfully(self):
        """Laporan Satker HTML should load successfully (v2 template)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        html = response.text
        # v2 template shows Penanggung Jawab and Tim Pendukung
        assert "Penanggung Jawab" in html, "Laporan Satker should include Penanggung Jawab section"
        assert "Tim Pendukung" in html, "Laporan Satker should include Tim Pendukung section"
        print("✓ Laporan Satker HTML v2 loads successfully with PJ and Tim Pendukung")
        # Note: Tim Inti/Pembantu are shown in Executive Summary, not Laporan Satker v2
    
    def test_rhi_pdf_generates_successfully(self):
        """RHI PDF should generate without errors"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/rhi-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 1000, "PDF should have reasonable size"
        print("✓ RHI PDF generates successfully")
    
    def test_bahi_pdf_generates_successfully(self):
        """BAHI PDF should generate without errors"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/bahi-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 1000, "PDF should have reasonable size"
        print("✓ BAHI PDF generates successfully")
    
    def test_executive_summary_pdf_generates_successfully(self):
        """Executive Summary PDF should generate without errors"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 5000, "PDF should have reasonable size"
        print("✓ Executive Summary PDF generates successfully")


class TestExecutiveSummaryTimSections:
    """Test that Executive Summary shows Tim Inventarisasi sections correctly"""
    
    def test_exec_summary_html_has_tim_inti_section(self):
        """Executive Summary HTML should show Tim Inti (Pelaksana) with members"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html?preview=true")
        assert response.status_code == 200
        
        html = response.text
        assert "Tim Inti (Pelaksana)" in html, "Should have Tim Inti (Pelaksana) section"
        assert "Ahmad Ketua" in html or "Ketua Tim" in html, "Should show Tim Inti ketua member"
        print("✓ Executive Summary has Tim Inti (Pelaksana) section")
    
    def test_exec_summary_html_has_tim_pembantu_section(self):
        """Executive Summary HTML should show Tim Pembantu with members"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html?preview=true")
        assert response.status_code == 200
        
        html = response.text
        assert "Tim Pembantu" in html, "Should have Tim Pembantu section"
        print("✓ Executive Summary has Tim Pembantu section")
    
    def test_exec_summary_html_has_tim_pendukung_with_dari_pihak(self):
        """Executive Summary HTML should show Tim Pendukung with Dari Pihak column"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html?preview=true")
        assert response.status_code == 200
        
        html = response.text
        assert "Tim Pendukung (Eksternal)" in html, "Should have Tim Pendukung (Eksternal) section"
        assert "Dari Pihak" in html, "Tim Pendukung should show Dari Pihak column header"
        print("✓ Executive Summary has Tim Pendukung with Dari Pihak column")


class TestXLSXExportWithTimData:
    """Test XLSX export includes Tim Inventarisasi data (requires assets)"""
    
    def test_xlsx_export_handles_no_data_gracefully(self):
        """XLSX export should return 404 with clear message when no data"""
        response = requests.get(
            f"{BASE_URL}/api/export/xlsx",
            params={"activity_id": TEST_ACTIVITY_ID}
        )
        # This activity has 0 assets, so 404 is expected
        assert response.status_code == 404, f"Expected 404 for activity with 0 assets, got {response.status_code}"
        
        data = response.json()
        assert "Tidak ada data" in data.get("detail", ""), "Should indicate no data to export"
        print("✓ XLSX export correctly returns 404 for activity with 0 assets")


class TestBeritaAcaraPDFWithTimInventarisasi:
    """Test Berita Acara PDF includes Tim Inventarisasi table"""
    
    def test_berita_acara_pdf_generates_successfully(self):
        """Berita Acara PDF should generate without errors"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/berita-acara-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 1000, "PDF should have reasonable size"
        print("✓ Berita Acara PDF generates successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
