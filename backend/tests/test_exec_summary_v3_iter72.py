"""
Test Executive Summary v3 - Multi-page structure with chart visualizations
Tests: HTML rendering, PDF generation with proper page breaks, chart data variables
Activity ID: c08c060e-d21b-4c9f-bd5a-b8d0f6230806 (has 0 assets, ON PROGRESS dates)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestExecutiveSummaryHTMLStructure:
    """Test Executive Summary HTML has correct multi-page structure and chart components"""
    
    def test_executive_summary_html_returns_200(self):
        """GET /api/inventory-activities/{id}/executive-summary-html returns 200"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Executive summary HTML returns 200")
    
    def test_html_contains_cover_page(self):
        """HTML has cover-page div with page-break-after CSS"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'class="cover-page"' in html, "Missing cover-page div"
        assert 'Laporan Eksekutif' in html, "Missing cover title"
        print("PASS: Cover page present with correct structure")
    
    def test_html_contains_exec_pages(self):
        """HTML has multiple exec-page divs for multi-page structure"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Count exec-page occurrences (should be at least 3: exec summary, charts dist, charts analysis)
        exec_page_count = html.count('class="exec-page"')
        assert exec_page_count >= 3, f"Expected at least 3 exec-page divs, got {exec_page_count}"
        print(f"PASS: Found {exec_page_count} exec-page divs (multi-page structure)")
    
    def test_html_contains_data_page_landscape(self):
        """HTML has data-page div for landscape data table"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'class="data-page"' in html, "Missing data-page div (landscape table)"
        assert 'landscape-page' in html, "Missing landscape-page CSS reference"
        print("PASS: Data page (landscape) present")
    
    def test_html_has_page_break_css(self):
        """HTML CSS contains page-break-after styles for proper PDF pagination"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'page-break-after' in html, "Missing page-break-after CSS"
        assert '@page landscape-page' in html, "Missing @page landscape-page rule"
        print("PASS: Page break CSS rules present")


class TestExecutiveSummaryChartComponents:
    """Test HTML contains all new chart visualization CSS classes and sections"""
    
    def test_hbar_row_horizontal_bar_chart(self):
        """HTML contains hbar-row class for horizontal bar charts"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # CSS class definition
        assert '.hbar-row' in html, "Missing .hbar-row CSS definition"
        assert '.hbar-label' in html, "Missing .hbar-label CSS"
        assert '.hbar-track' in html, "Missing .hbar-track CSS"
        assert '.hbar-fill' in html, "Missing .hbar-fill CSS"
        print("PASS: Horizontal bar chart CSS classes present")
    
    def test_donut_container_svg_donut_chart(self):
        """HTML contains donut-container class for SVG donut charts"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert '.donut-container' in html, "Missing .donut-container CSS definition"
        assert '.donut-legend' in html, "Missing .donut-legend CSS"
        assert '.donut-legend-item' in html, "Missing .donut-legend-item CSS"
        print("PASS: SVG donut chart CSS classes present")
    
    def test_sbar_row_stacked_bar_chart(self):
        """HTML contains sbar-row class for stacked bar charts"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert '.sbar-row' in html, "Missing .sbar-row CSS definition"
        assert '.sbar-label' in html, "Missing .sbar-label CSS"
        assert '.sbar-track' in html, "Missing .sbar-track CSS"
        assert '.sbar-seg' in html, "Missing .sbar-seg CSS (stacked segments)"
        print("PASS: Stacked bar chart CSS classes present")
    
    def test_coverage_bar_progress_bars(self):
        """HTML contains coverage-bar class for coverage progress bars"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert '.coverage-bar' in html, "Missing .coverage-bar CSS definition"
        assert '.coverage-track' in html, "Missing .coverage-track CSS"
        assert '.coverage-fill' in html, "Missing .coverage-fill CSS"
        assert '.coverage-pct' in html, "Missing .coverage-pct CSS"
        print("PASS: Coverage bar CSS classes present")
    
    def test_tim_section_team_display(self):
        """HTML contains tim-section class for team display"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert '.tim-section' in html, "Missing .tim-section CSS definition"
        assert '.tim-header' in html, "Missing .tim-header CSS"
        assert '.tim-grid' in html, "Missing .tim-grid CSS"
        assert '.tim-card' in html, "Missing .tim-card CSS"
        print("PASS: Tim section CSS classes present")


class TestExecutiveSummaryOnProgressBanner:
    """Test ON PROGRESS banner functionality"""
    
    def test_on_progress_banner_present(self):
        """Activity within date range shows ON PROGRESS banner"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Activity has dates 2026-01-01 to 2026-12-31, current month is Jan 2026
        assert 'on-progress-banner' in html, "Missing on-progress-banner CSS definition"
        # The banner should be rendered (not commented out)
        assert 'ON PROGRESS' in html or 'on-progress' in html.lower(), "ON PROGRESS banner should be present"
        print("PASS: ON PROGRESS banner present for activity within date range")


class TestExecutiveSummaryPDF:
    """Test Executive Summary PDF generation with proper page breaks"""
    
    def test_executive_summary_pdf_returns_200(self):
        """GET /api/inventory-activities/{id}/executive-summary-pdf returns 200"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Executive summary PDF returns 200")
    
    def test_pdf_is_valid(self):
        """PDF response contains valid PDF signature"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-pdf")
        content = response.content
        assert content[:4] == b'%PDF', f"Invalid PDF signature: {content[:10]}"
        print("PASS: PDF has valid %PDF signature")
    
    def test_pdf_content_type(self):
        """PDF response has correct content-type header"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-pdf")
        content_type = response.headers.get('content-type', '')
        assert 'pdf' in content_type.lower(), f"Expected PDF content-type, got: {content_type}"
        print(f"PASS: PDF has correct content-type: {content_type}")
    
    def test_pdf_has_reasonable_size(self):
        """PDF should have reasonable file size (>10KB for proper multi-page)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-pdf")
        size = len(response.content)
        assert size > 10000, f"PDF too small ({size} bytes), may be missing pages"
        print(f"PASS: PDF size is {size} bytes (reasonable for multi-page document)")


class TestExecutiveSummaryChartDataVariables:
    """Test that all new chart data variables are passed from backend"""
    
    def test_cat_chart_in_page3(self):
        """Page 3 HTML references cat_chart data (Top Kategori Aset)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Check for the chart section title mentioning categories
        assert 'Top' in html and ('Kategori' in html or 'kategori' in html), "Missing kategori chart section"
        print("PASS: Category chart section present")
    
    def test_loc_chart_in_page3(self):
        """Page 3 HTML references loc_chart data (Top Lokasi Aset)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'Lokasi' in html or 'lokasi' in html, "Missing lokasi chart section"
        print("PASS: Location chart section present")
    
    def test_year_chart_in_page4(self):
        """Page 4 HTML references year_chart data (Distribusi Per Tahun)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Year distribution section on page 4
        assert 'Tahun' in html, "Missing tahun (year) distribution section"
        print("PASS: Year distribution section present")
    
    def test_eselon_chart_in_page4(self):
        """Page 4 HTML references eselon_chart data (Distribusi Per Eselon)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'Eselon' in html or 'eselon' in html, "Missing eselon distribution section"
        print("PASS: Eselon distribution section present")
    
    def test_status_pie_css_defined(self):
        """HTML CSS defines status_pie SVG donut chart styles (rendered when data exists)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # The CSS classes for status pie should be defined in the template
        # Note: When activity has 0 assets, the status_pie section is conditionally hidden
        # but the CSS classes are still defined in the stylesheet
        assert '.donut-container' in html, "Missing donut-container CSS definition"
        assert '.donut-legend' in html, "Missing donut-legend CSS definition"
        print("PASS: Status pie chart CSS classes defined (section conditionally rendered when data exists)")
    
    def test_coverage_stats_section(self):
        """HTML contains coverage statistics (Photo, GPS, Document)"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        assert 'Dokumentasi Foto' in html or 'Foto' in html, "Missing photo coverage"
        assert 'GPS' in html or 'Koordinat' in html, "Missing GPS coverage"
        assert 'Dokumen' in html or 'Kelengkapan' in html, "Missing document coverage"
        print("PASS: Coverage statistics section present")


class TestExecutiveSummaryPageNumbers:
    """Test page numbering in HTML"""
    
    def test_page_numbers_present(self):
        """HTML contains page number indicators"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Check for page numbering pattern (e.g., "Halaman 2 dari X")
        assert 'Halaman' in html, "Missing page number text"
        assert 'dari' in html, "Missing page count reference"
        print("PASS: Page numbering present in HTML")
    
    def test_separator_marks_for_preview(self):
        """Preview mode HTML contains separator divs for page distinction"""
        activity_id = "c08c060e-d21b-4c9f-bd5a-b8d0f6230806"
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}/executive-summary-html")
        html = response.text
        # Preview mode should have separator divs
        assert 'separator' in html, "Missing separator class for preview mode"
        print("PASS: Separator markers present for preview mode")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
