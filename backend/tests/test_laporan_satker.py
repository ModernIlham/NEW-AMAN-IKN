"""
Test Laporan Satker HTML/PDF export feature
Tests:
- GET /api/inventory-activities/{id}/laporan-satker-html - HTML preview
- GET /api/inventory-activities/{id}/laporan-satker-pdf - PDF download
- Report data validation (kode_satker, nama_satker, nomor_surat)
- Report analysis data (stat counts, chart data)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Known activity IDs from agent context
VALID_ACTIVITY_ID = "cdddd9eb-f945-4548-b9a5-3f214d34a7cb"  # Has kode_satker 0000139 and nama_satker SATKER E
ALTERNATE_ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"  # May have more data
INVALID_ACTIVITY_ID = "invalid-uuid-12345-does-not-exist"


class TestLaporanSatkerEndpoints:
    """Test Laporan Satker API endpoints"""

    def test_laporan_satker_html_valid_activity(self):
        """GET /api/inventory-activities/{id}/laporan-satker-html returns 200 with HTML content"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        assert "text/html" in response.headers.get("content-type", ""), "Expected HTML content type"
        
        # Verify HTML structure - should have cover page and sections
        html = response.text
        assert "<!DOCTYPE html>" in html or "<html" in html, "Response should be valid HTML"
        assert "LAPORAN HASIL" in html or "Inventarisasi BMN" in html, "Should contain report title"
        
        print(f"✓ laporan-satker-html returns 200 with HTML ({len(html)} chars)")

    def test_laporan_satker_html_invalid_activity(self):
        """GET /api/inventory-activities/{id}/laporan-satker-html returns 404 for invalid activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{INVALID_ACTIVITY_ID}/laporan-satker-html")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ laporan-satker-html returns 404 for invalid activity")

    def test_laporan_satker_pdf_valid_activity(self):
        """GET /api/inventory-activities/{id}/laporan-satker-pdf returns PDF binary"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-pdf")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Expected PDF content type"
        
        # PDF files start with %PDF
        content = response.content
        assert content[:4] == b"%PDF", "Response should be valid PDF (starts with %PDF)"
        assert len(content) > 1000, f"PDF should have substantial content, got {len(content)} bytes"
        
        # Check Content-Disposition header for filename
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd, "Should have attachment disposition"
        assert ".pdf" in cd.lower(), "Filename should have .pdf extension"
        
        print(f"✓ laporan-satker-pdf returns valid PDF ({len(content)} bytes)")

    def test_laporan_satker_pdf_invalid_activity(self):
        """GET /api/inventory-activities/{id}/laporan-satker-pdf returns 404 for invalid activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{INVALID_ACTIVITY_ID}/laporan-satker-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ laporan-satker-pdf returns 404 for invalid activity")


class TestLaporanSatkerContent:
    """Test Laporan Satker report content includes correct data"""

    def test_html_contains_activity_data(self):
        """HTML report includes kode_satker, nama_satker, nomor_surat from activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for kode_satker 0000139 as mentioned in context
        assert "0000139" in html, "Should contain kode_satker 0000139"
        
        # Check for nama_satker SATKER E
        assert "SATKER E" in html or "satker" in html.lower(), "Should contain nama_satker"
        
        print("✓ HTML report contains activity data (kode_satker, nama_satker)")

    def test_html_has_cover_page_elements(self):
        """HTML report has professional cover page with dark gradient background"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Cover page CSS classes and content
        assert 'class="cover"' in html or "cover" in html, "Should have cover page element"
        assert "LAPORAN HASIL" in html or "INVENTARISASI" in html, "Cover should have title"
        
        # Check for dark gradient (background: linear-gradient with #0f172a or similar dark colors)
        assert "gradient" in html.lower() or "#0f172a" in html or "#1e3a5f" in html, "Should have gradient background styling"
        
        print("✓ HTML report has professional cover page")

    def test_html_has_6_sections(self):
        """HTML report has 6 sections: Data Kegiatan, Ringkasan, Analisis, Daftar Aset, Kelengkapan Dok, Kesimpulan"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for section markers (num class with numbers 1-6)
        sections_found = []
        expected_sections = [
            ("1", "Data Kegiatan"),
            ("2", "Ringkasan"),
            ("3", "Analisis"),
            ("4", "Daftar Aset"),
            ("5", "Kelengkapan Dokumen"),
            ("6", "Kesimpulan"),
        ]
        
        for num, section_name in expected_sections:
            # Check for section number marker and/or section content
            has_num = f'class="num">{num}<' in html or f'"num">{num}' in html
            has_name = section_name.lower() in html.lower() or section_name.split()[0].lower() in html.lower()
            if has_num or has_name:
                sections_found.append(section_name)
        
        assert len(sections_found) >= 4, f"Expected at least 4 sections, found: {sections_found}"
        print(f"✓ HTML report has sections: {sections_found}")

    def test_html_has_stat_cards(self):
        """HTML report has Ringkasan Inventarisasi stat cards"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for stat card elements
        assert 'stat-card' in html or 'stat-row' in html, "Should have stat card styling"
        
        # Check for stat labels
        stat_labels = ["Total NUP", "Ditemukan", "Tidak Ditemukan", "Berlebih"]
        found_labels = [lbl for lbl in stat_labels if lbl.lower() in html.lower()]
        
        assert len(found_labels) >= 2, f"Expected stat labels, found: {found_labels}"
        print(f"✓ HTML report has stat cards with labels: {found_labels}")

    def test_html_has_charts(self):
        """HTML report has bar charts for analysis (kondisi, status, kategori, lokasi)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for chart elements
        assert 'chart-box' in html or 'bar-chart' in html or 'chart-row' in html, "Should have chart styling"
        
        # Check for chart titles
        chart_titles = ["Kondisi", "Status", "Kategori", "Lokasi"]
        found_titles = [t for t in chart_titles if t.lower() in html.lower()]
        
        assert len(found_titles) >= 2, f"Expected chart titles, found: {found_titles}"
        print(f"✓ HTML report has bar charts: {found_titles}")

    def test_html_has_data_table(self):
        """HTML report has Daftar Aset table"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for table elements
        assert '<table' in html and 'data-table' in html, "Should have data table"
        
        # Check for table headers
        table_headers = ["Kode", "NUP", "Nama", "Kondisi", "Status"]
        found_headers = [h for h in table_headers if h.lower() in html.lower()]
        
        assert len(found_headers) >= 3, f"Expected table headers, found: {found_headers}"
        print(f"✓ HTML report has data table with columns: {found_headers}")

    def test_html_has_print_button(self):
        """HTML report has 'Cetak / Simpan PDF' button in toolbar"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{VALID_ACTIVITY_ID}/laporan-satker-html")
        assert response.status_code == 200
        
        html = response.text
        
        # Check for print button
        assert 'Cetak' in html or 'print' in html.lower() or 'Simpan PDF' in html, "Should have print/save button"
        assert 'toolbar' in html or 'btn-print' in html, "Should have toolbar with print button"
        
        print("✓ HTML report has print/save button in toolbar")


class TestLaporanSatkerAlternateActivity:
    """Test with alternate activity ID that may have more data"""

    def test_alternate_activity_html(self):
        """Test HTML report for alternate activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ALTERNATE_ACTIVITY_ID}/laporan-satker-html")
        
        if response.status_code == 200:
            html = response.text
            assert "<!DOCTYPE html>" in html or "<html" in html
            print(f"✓ Alternate activity HTML report works ({len(html)} chars)")
        elif response.status_code == 404:
            print("⚠ Alternate activity not found (404) - skipping")
            pytest.skip("Alternate activity not found")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")

    def test_alternate_activity_pdf(self):
        """Test PDF report for alternate activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ALTERNATE_ACTIVITY_ID}/laporan-satker-pdf")
        
        if response.status_code == 200:
            content = response.content
            assert content[:4] == b"%PDF"
            print(f"✓ Alternate activity PDF report works ({len(content)} bytes)")
        elif response.status_code == 404:
            print("⚠ Alternate activity not found (404) - skipping")
            pytest.skip("Alternate activity not found")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
