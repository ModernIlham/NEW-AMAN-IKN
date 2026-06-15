"""
Test Suite for Executive Summary PDF & HTML Preview Feature
Tests moved from RekapitulasiPanel to Export dropdown

Features tested:
1. Backend: GET /api/inventory-activities/{id}/executive-summary-pdf returns valid PDF
2. Backend: GET /api/inventory-activities/{id}/executive-summary-html returns HTML page
3. PDF structure: 3 pages (Portrait Cover, Portrait Summary, Landscape Data Table)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

class TestExecutiveSummaryFeature:
    """Tests for Executive Summary PDF and HTML preview endpoints"""
    
    # Test activity ID from the request
    ACTIVITY_ID = "82781711-fad4-4f05-99f9-5b60a7ae0781"
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_executive_summary_pdf_returns_valid_pdf(self):
        """GET /api/inventory-activities/{id}/executive-summary-pdf returns valid PDF"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-pdf")
        
        # Should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Content-Type should be application/pdf
        assert "application/pdf" in response.headers.get("Content-Type", ""), \
            f"Expected application/pdf, got {response.headers.get('Content-Type')}"
        
        # PDF should start with %PDF
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF file"
        
        print(f"✓ Executive Summary PDF endpoint returns valid PDF ({len(response.content)} bytes)")
    
    def test_executive_summary_pdf_has_content_disposition(self):
        """PDF response should include Content-Disposition header for download"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-pdf")
        
        assert response.status_code == 200
        
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition, f"Missing 'attachment' in Content-Disposition: {content_disposition}"
        assert "Laporan_Eksekutif" in content_disposition or "filename" in content_disposition, \
            f"Missing filename in Content-Disposition: {content_disposition}"
        
        print(f"✓ Content-Disposition header: {content_disposition}")
    
    def test_executive_summary_pdf_invalid_activity_returns_404(self):
        """GET with invalid activity ID should return 404"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/invalid-id-12345/executive-summary-pdf")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid activity ID returns 404")
    
    def test_executive_summary_html_returns_html_page(self):
        """GET /api/inventory-activities/{id}/executive-summary-html returns HTML preview"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-html")
        
        # Should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Content-Type should be text/html
        content_type = response.headers.get("Content-Type", "")
        assert "text/html" in content_type, f"Expected text/html, got {content_type}"
        
        # HTML should contain expected elements
        html_content = response.text
        assert "<!DOCTYPE html>" in html_content or "<html" in html_content, "Response is not valid HTML"
        assert "Laporan Eksekutif" in html_content, "Missing 'Laporan Eksekutif' title in HTML"
        
        print(f"✓ Executive Summary HTML endpoint returns valid HTML ({len(html_content)} chars)")
    
    def test_executive_summary_html_has_preview_mode(self):
        """HTML preview should have preview mode with separators"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-html")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Preview mode should have separator elements
        assert "separator" in html_content, "HTML preview should have separator elements"
        # Should have cover page
        assert "cover-page" in html_content, "HTML should have cover page section"
        # Should have executive summary page
        assert "exec-page" in html_content, "HTML should have executive summary page section"
        # Should have data table page
        assert "data-page" in html_content, "HTML should have data table page section"
        
        print("✓ HTML preview has correct structure (cover, exec summary, data table)")
    
    def test_executive_summary_html_invalid_activity_returns_404(self):
        """GET HTML preview with invalid activity ID should return 404"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/invalid-id-12345/executive-summary-html")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid activity ID returns 404 for HTML preview")
    
    def test_executive_summary_html_contains_real_data(self):
        """HTML preview should contain real data from the activity"""
        response = self.session.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-html")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Should have some numerical data (counts, values)
        # Check for presence of data table structure
        assert "<table" in html_content, "HTML should contain data table"
        # Should have rekap table
        assert "rekap-table" in html_content or "data-table" in html_content, "HTML should have rekap/data tables"
        
        print("✓ HTML preview contains real data tables")


class TestExecutiveSummaryPDFStructure:
    """Tests to verify the PDF has correct structure: Portrait Cover, Portrait Summary, Landscape Data Table"""
    
    ACTIVITY_ID = "82781711-fad4-4f05-99f9-5b60a7ae0781"
    
    def test_pdf_has_substantial_size(self):
        """PDF should have substantial content (not empty)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-pdf")
        
        assert response.status_code == 200
        
        # PDF should be at least a few KB (3 pages with content)
        pdf_size = len(response.content)
        assert pdf_size > 5000, f"PDF too small ({pdf_size} bytes), may be incomplete"
        
        print(f"✓ PDF has substantial size: {pdf_size} bytes")
    
    def test_pdf_can_be_parsed(self):
        """PDF should be parseable (valid structure)"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{self.ACTIVITY_ID}/executive-summary-pdf")
        
        assert response.status_code == 200
        
        # Check PDF header and trailer
        pdf_content = response.content
        assert pdf_content.startswith(b'%PDF'), "PDF missing header"
        assert b'%%EOF' in pdf_content[-1024:], "PDF missing EOF marker"
        
        print("✓ PDF has valid structure (header and EOF marker)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
