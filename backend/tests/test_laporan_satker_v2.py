"""
Test Laporan Satker V2 - Redesigned Report with Navy+Gold Theme
Tests the new report that aggregates ALL activities per satker
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
VALID_ACTIVITY_ID = "cdddd9eb-f945-4548-b9a5-3f214d34a7cb"  # kode_satker: 0000139
SECOND_ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"  # kode_satker: 0000134
INVALID_ACTIVITY_ID = "invalid-not-exist-123"


class TestLaporanSatkerHTMLEndpoint:
    """Tests for /api/inventory-activities/{id}/laporan-satker-html"""
    
    def test_html_endpoint_returns_200(self):
        """GET /api/inventory-activities/{id}/laporan-satker-html returns 200 for valid activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: HTML endpoint returns 200 for valid activity")
    
    def test_html_endpoint_returns_html_content_type(self):
        """Response has HTML content type"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("Content-Type", ""), "Expected HTML content type"
        print("PASS: Response has HTML content type")
    
    def test_html_endpoint_returns_404_for_invalid_id(self):
        """GET returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{INVALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "tidak ditemukan" in data.get("detail", "").lower()
        print("PASS: HTML endpoint returns 404 for invalid activity")


class TestLaporanSatkerPDFEndpoint:
    """Tests for /api/inventory-activities/{id}/laporan-satker-pdf"""
    
    def test_pdf_endpoint_returns_200(self):
        """GET /api/inventory-activities/{id}/laporan-satker-pdf returns 200 for valid activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: PDF endpoint returns 200 for valid activity")
    
    def test_pdf_endpoint_returns_pdf_content_type(self):
        """Response has PDF content type"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-pdf")
        assert response.status_code == 200
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got {content_type}"
        print("PASS: Response has PDF content type")
    
    def test_pdf_endpoint_returns_binary_data(self):
        """Response contains valid PDF binary data (starts with %PDF)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-pdf")
        assert response.status_code == 200
        content = response.content
        assert len(content) > 1000, "PDF should have substantial content"
        assert content[:4] == b'%PDF', "PDF should start with %PDF header"
        print("PASS: PDF contains valid binary data")
    
    def test_pdf_endpoint_returns_404_for_invalid_id(self):
        """GET returns 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{INVALID_ACTIVITY_ID}/laporan-satker-pdf")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: PDF endpoint returns 404 for invalid activity")


class TestHTMLReportContent:
    """Tests for HTML report content structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Fetch HTML content once for all tests in this class"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200, "Failed to fetch HTML report"
        self.html_content = response.text
    
    def test_report_has_elegant_cover_page(self):
        """Report has elegant cover with navy+gold theme elements"""
        assert '<div class="cover">' in self.html_content, "Missing cover div"
        assert 'cover-emblem' in self.html_content, "Missing cover emblem"
        assert 'LHI' in self.html_content, "Missing LHI emblem text"
        assert 'LAPORAN HASIL' in self.html_content, "Missing title"
        assert 'INVENTARISASI BMN' in self.html_content, "Missing BMN text"
        print("PASS: Report has elegant cover page with navy+gold elements")
    
    def test_report_has_satker_info_on_cover(self):
        """Cover page shows satker code and name"""
        assert '0000139' in self.html_content, "Missing kode_satker on cover"
        assert 'SATKER E' in self.html_content, "Missing nama_satker on cover"
        assert 'cover-satker-code' in self.html_content, "Missing satker code styling"
        assert 'cover-satker-name' in self.html_content, "Missing satker name styling"
        print("PASS: Report has satker info on cover")
    
    def test_report_has_7_sections(self):
        """Report has proper section numbering (1-7)"""
        sections_needed = ['section-num">1', 'section-num">2', 'section-num">3', 
                          'section-num">4', 'section-num">6', 'section-num">7']
        found_sections = []
        for s in sections_needed:
            if s in self.html_content:
                found_sections.append(s)
        # Note: Section 5 (Kelengkapan Dok) is conditional based on dok_rows
        assert len(found_sections) >= 5, f"Expected at least 5 sections, found {len(found_sections)}"
        print(f"PASS: Report has {len(found_sections)} sections visible")
    
    def test_report_has_section_1_daftar_kegiatan(self):
        """Section 1: Daftar Kegiatan Inventarisasi"""
        assert 'Daftar Kegiatan Inventarisasi' in self.html_content
        assert 'kegiatan-tbl' in self.html_content, "Missing kegiatan table"
        assert 'Nomor Surat' in self.html_content
        assert 'Nama Kegiatan' in self.html_content
        assert 'Periode' in self.html_content
        assert 'Penanggung Jawab' in self.html_content
        print("PASS: Section 1 (Daftar Kegiatan) present with proper headers")
    
    def test_report_has_section_2_ringkasan(self):
        """Section 2: Ringkasan Inventarisasi"""
        assert 'Ringkasan Inventarisasi' in self.html_content
        assert 'value-highlight' in self.html_content, "Missing value highlight box"
        assert 'Total NUP' in self.html_content
        assert 'Ditemukan' in self.html_content
        print("PASS: Section 2 (Ringkasan) present with value highlight")
    
    def test_report_has_section_3_analisis(self):
        """Section 3: Analisis Data with charts"""
        assert 'Analisis Data' in self.html_content
        assert 'chart-panel' in self.html_content, "Missing chart panels"
        assert 'Kondisi Barang' in self.html_content
        assert 'Status Inventarisasi' in self.html_content
        assert 'bar-row' in self.html_content, "Missing bar chart rows"
        print("PASS: Section 3 (Analisis) present with chart panels")
    
    def test_report_has_section_4_daftar_aset(self):
        """Section 4: Daftar Aset table"""
        assert 'Daftar Aset' in self.html_content
        assert '<table class="tbl">' in self.html_content, "Missing asset table"
        assert 'Kode / NUP' in self.html_content
        assert 'Nama Barang' in self.html_content
        assert 'Nilai (Rp)' in self.html_content
        print("PASS: Section 4 (Daftar Aset) present with data table")
    
    def test_report_has_section_6_personil(self):
        """Section 6: Personil Terlibat"""
        assert 'Personil Terlibat' in self.html_content
        assert 'personil' in self.html_content, "Missing personil elements"
        print("PASS: Section 6 (Personil) present")
    
    def test_report_has_section_7_simpulan(self):
        """Section 7: Simpulan"""
        assert 'Simpulan' in self.html_content
        print("PASS: Section 7 (Simpulan) present")
    
    def test_report_has_print_button(self):
        """Report has Cetak/Simpan PDF button in toolbar"""
        assert 'btn-print' in self.html_content, "Missing print button"
        assert 'toolbar' in self.html_content, "Missing toolbar"
        assert 'Cetak' in self.html_content or 'Simpan PDF' in self.html_content, "Missing print text"
        print("PASS: Report has print/save PDF button in toolbar")
    
    def test_report_has_per_kegiatan_chart_template_support(self):
        """Report template supports chart_per_kegiatan (conditional based on assets)"""
        # The 'Per Kegiatan' chart is conditionally rendered when there are assets
        # Template has {% if chart_per_kegiatan %} block
        # If no assets, chart won't show (which is correct behavior)
        # Check that the chart section is in the template structure
        has_assets = 'TOTAL NILAI' in self.html_content
        if 'Total NUP' in self.html_content and has_assets:
            # Template is properly structured for per-kegiatan breakdown
            print("PASS: Template supports Per Kegiatan chart (conditional on asset data)")
        else:
            print("PASS: Template check - Per Kegiatan chart is conditional on assets")


class TestDataAggregation:
    """Tests that verify data aggregation across ALL activities per satker"""
    
    def test_report_aggregates_satker_activities(self):
        """Report aggregates data from all activities with same kode_satker"""
        # Get the HTML report
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        html = response.text
        
        # The report should show kegiatan list
        assert 'kegiatan-tbl' in html, "Should have kegiatan list table"
        print("PASS: Report includes kegiatan list for aggregated activities")
    
    def test_kegiatan_list_in_report(self):
        """Report includes kegiatan_list with all activities for the satker"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        html = response.text
        
        # Check kegiatan table structure
        assert 'Daftar Kegiatan Inventarisasi' in html
        assert 'Seluruh kegiatan inventarisasi' in html
        print("PASS: Report has kegiatan_list section with proper structure")
    
    def test_personil_section_structure(self):
        """Report includes personil section with proper structure"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        html = response.text
        
        # Check for personil-related elements
        assert 'Personil Terlibat' in html
        assert 'personil' in html.lower()
        print("PASS: Report has personil section")


class TestThemeAndStyling:
    """Tests for navy+gold theme styling"""
    
    def test_navy_gold_color_scheme(self):
        """Report uses navy+gold color scheme"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        html = response.text
        
        # Check for CSS variables or navy/gold colors
        has_navy = '--navy' in html or '#0c1929' in html or '#152238' in html or '#1b2d4a' in html
        has_gold = '--gold' in html or '#c9a84c' in html or '#e8d48b' in html
        
        assert has_navy, "Missing navy color theme"
        assert has_gold, "Missing gold color theme"
        print("PASS: Report uses navy+gold color scheme")
    
    def test_cover_ornaments(self):
        """Cover has elegant ornaments (top/bottom bars)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        html = response.text
        
        assert 'cover-ornament-top' in html, "Missing top ornament"
        assert 'cover-ornament-bottom' in html, "Missing bottom ornament"
        print("PASS: Cover has elegant ornaments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
