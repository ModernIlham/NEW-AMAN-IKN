"""
Test Executive Summary PDF - Backend API Tests
Tests the new executive summary PDF report endpoint
"""
import pytest
import requests
import os
from PyPDF2 import PdfReader
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestExecutiveSummaryPDF:
    """Executive Summary PDF endpoint tests"""
    
    @pytest.fixture
    def activity_with_assets(self):
        """Get an activity that has assets for testing"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        
        # Find an activity with assets
        for activity in activities:
            if activity.get('total_assets', 0) > 0:
                return activity['id']
        
        pytest.skip("No activity with assets found for testing")
    
    @pytest.fixture
    def small_activity(self):
        """Get an activity with fewer assets for faster testing"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200
        activities = response.json()
        
        # Find an activity with fewer assets (< 20)
        for activity in activities:
            asset_count = activity.get('total_assets', 0)
            if 0 < asset_count < 20:
                return activity['id']
        
        # If no small activity found, return first with assets
        for activity in activities:
            if activity.get('total_assets', 0) > 0:
                return activity['id']
        
        pytest.skip("No activity with assets found for testing")

    def test_endpoint_returns_200(self, activity_with_assets):
        """Test that the endpoint returns 200 for valid activity"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{activity_with_assets}/executive-summary-pdf",
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/inventory-activities/{activity_id}/executive-summary-pdf returns 200")
    
    def test_returns_valid_pdf(self, small_activity):
        """Test that the response is a valid PDF file"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{small_activity}/executive-summary-pdf"
        )
        assert response.status_code == 200
        
        # Check content type
        assert 'application/pdf' in response.headers.get('Content-Type', ''), \
            f"Expected application/pdf, got {response.headers.get('Content-Type')}"
        
        # Check PDF magic bytes
        pdf_content = response.content
        assert pdf_content[:4] == b'%PDF', "Response is not a valid PDF file"
        
        print("✓ Response is a valid PDF file (Content-Type: application/pdf, starts with %PDF)")
    
    def test_pdf_has_correct_structure(self, small_activity):
        """Test that the PDF has exactly 3+ pages with correct orientation:
        - Page 1: Portrait (Cover)
        - Page 2: Portrait (Executive Summary)
        - Page 3+: Landscape (Data Table)
        """
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{small_activity}/executive-summary-pdf"
        )
        assert response.status_code == 200
        
        # Parse PDF
        pdf_buffer = io.BytesIO(response.content)
        reader = PdfReader(pdf_buffer)
        
        # Check minimum pages (at least 3 for Cover + Summary + Data)
        total_pages = len(reader.pages)
        assert total_pages >= 3, f"Expected at least 3 pages, got {total_pages}"
        print(f"✓ PDF has {total_pages} pages (minimum 3 required)")
        
        # Check Page 1: Portrait A4 (Cover)
        page1 = reader.pages[0]
        width1 = float(page1.mediabox.width)
        height1 = float(page1.mediabox.height)
        assert width1 < height1, f"Page 1 should be Portrait but got width={width1:.0f}, height={height1:.0f}"
        print(f"✓ Page 1: Portrait ({width1:.0f}x{height1:.0f}pt) - Cover Page")
        
        # Check Page 2: Portrait A4 (Executive Summary)
        page2 = reader.pages[1]
        width2 = float(page2.mediabox.width)
        height2 = float(page2.mediabox.height)
        assert width2 < height2, f"Page 2 should be Portrait but got width={width2:.0f}, height={height2:.0f}"
        print(f"✓ Page 2: Portrait ({width2:.0f}x{height2:.0f}pt) - Executive Summary")
        
        # Check Page 3: Landscape A4 (Data Table)
        page3 = reader.pages[2]
        width3 = float(page3.mediabox.width)
        height3 = float(page3.mediabox.height)
        assert width3 > height3, f"Page 3 should be Landscape but got width={width3:.0f}, height={height3:.0f}"
        print(f"✓ Page 3: Landscape ({width3:.0f}x{height3:.0f}pt) - Data Table")
        
        # All additional pages should also be Landscape (Data Table continuation)
        for i in range(3, min(total_pages, 10)):  # Check up to page 10
            page = reader.pages[i]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            assert width > height, f"Page {i+1} should be Landscape"
        
        if total_pages > 3:
            print(f"✓ Pages 3-{total_pages}: All Landscape (Data Table continuation)")
    
    def test_invalid_activity_returns_404(self):
        """Test that invalid activity ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/invalid-activity-id-12345/executive-summary-pdf"
        )
        assert response.status_code == 404, f"Expected 404 for invalid activity, got {response.status_code}"
        print("✓ Invalid activity ID returns 404")
    
    def test_content_disposition_header(self, small_activity):
        """Test that the PDF has correct Content-Disposition header for download"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{small_activity}/executive-summary-pdf"
        )
        assert response.status_code == 200
        
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp, f"Expected 'attachment' in Content-Disposition, got: {content_disp}"
        assert 'Executive_Summary' in content_disp, f"Expected 'Executive_Summary' in filename, got: {content_disp}"
        assert '.pdf' in content_disp, f"Expected '.pdf' in filename, got: {content_disp}"
        
        print(f"✓ Content-Disposition header: {content_disp}")


class TestReportSettingsLogo:
    """Test that report settings logo is used"""
    
    def test_report_settings_exists(self):
        """Test that report_settings endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/report-settings")
        assert response.status_code == 200
        
        data = response.json()
        assert 'type' in data, "report_settings should have 'type' field"
        print("✓ GET /api/report-settings returns valid data")
    
    def test_logo_url_in_settings(self):
        """Test that logo_url exists in report settings"""
        response = requests.get(f"{BASE_URL}/api/report-settings")
        assert response.status_code == 200
        
        data = response.json()
        logo_url = data.get('logo_url', '')
        
        if logo_url:
            # Check it's a valid data URL
            assert logo_url.startswith('data:image/'), f"logo_url should be a data URL, got: {logo_url[:50]}..."
            print("✓ logo_url is present and is a valid data URL (base64 encoded image)")
        else:
            print("⚠ logo_url is empty (no logo uploaded)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
