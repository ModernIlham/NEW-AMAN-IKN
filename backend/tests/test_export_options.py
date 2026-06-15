"""
Test Export Dropdown Changes - iteration 27
Tests:
1. Backend: GET /api/inventory-activities/{id}/executive-summary-pdf returns valid 3-page PDF
2. Backend: GET /api/inventory-activities/{id}/executive-summary-html returns HTML with real asset data
3. Backend: PDF table CSS has table-layout:fixed and word-wrap:break-word
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_ACTIVITY_ID = "ce16f46a-e90d-477b-a900-e9a77eecc7d9"

class TestExecutiveSummaryPDF:
    """Test executive summary PDF generation"""
    
    def test_pdf_endpoint_returns_valid_pdf(self):
        """Test PDF endpoint returns valid PDF with correct headers"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-pdf"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        assert 'application/pdf' in response.headers.get('Content-Type', ''), "Should return PDF content type"
        
        # Check PDF header and footer
        content = response.content
        assert content[:5] == b'%PDF-', "PDF should start with %PDF-"
        assert b'%%EOF' in content[-100:], "PDF should end with %%EOF"
        
        # Check PDF size (should be substantial for 3 pages)
        pdf_size_kb = len(content) / 1024
        assert pdf_size_kb > 100, f"PDF should be > 100KB for 3 pages, got {pdf_size_kb:.1f}KB"
        print(f"PDF size: {pdf_size_kb:.1f}KB - PASS")
    
    def test_pdf_endpoint_invalid_activity_returns_404(self):
        """Test invalid activity ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/invalid-id-12345/executive-summary-pdf"
        )
        assert response.status_code == 404, f"Expected 404 for invalid ID, got {response.status_code}"


class TestExecutiveSummaryHTML:
    """Test executive summary HTML preview"""
    
    def test_html_endpoint_returns_valid_html(self):
        """Test HTML preview endpoint returns valid HTML with all sections"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        assert 'text/html' in response.headers.get('Content-Type', ''), "Should return HTML content type"
        
        html = response.text
        
        # Check for 3 main sections
        assert 'cover-page' in html, "HTML should contain cover-page section"
        assert 'exec-page' in html, "HTML should contain exec-page (executive summary) section"
        assert 'data-page' in html, "HTML should contain data-page (landscape table) section"
        
        # Check for preview mode separators
        assert 'separator' in html, "HTML preview should contain separator elements between pages"
        
        print("HTML contains all 3 page sections - PASS")
    
    def test_html_contains_real_asset_data(self):
        """Test HTML contains real asset data (4 assets expected)"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html"
        )
        assert response.status_code == 200
        
        html = response.text
        
        # Check for data-table with rows (should have header + 4 data rows)
        # Count <tr> tags in data-page section
        row_count = html.count('<tr>')
        # At least 5 rows expected: header + 4 assets (or more if totals row)
        assert row_count >= 5, f"Expected at least 5 table rows (1 header + 4 assets), got {row_count}"
        
        print(f"HTML contains {row_count} table rows - PASS")
    
    def test_html_table_css_has_wrapping_styles(self):
        """Test HTML contains table-layout:fixed and word-wrap:break-word in CSS"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}/executive-summary-html"
        )
        assert response.status_code == 200
        
        html = response.text
        
        # Check for table wrapping CSS
        assert 'table-layout: fixed' in html or 'table-layout:fixed' in html, \
            "CSS should contain table-layout: fixed for column wrapping"
        
        assert 'word-wrap: break-word' in html or 'word-wrap:break-word' in html, \
            "CSS should contain word-wrap: break-word for text wrapping"
        
        assert 'overflow-wrap: break-word' in html or 'overflow-wrap:break-word' in html, \
            "CSS should contain overflow-wrap: break-word for text wrapping"
        
        print("HTML table CSS has proper wrapping styles - PASS")
    
    def test_html_endpoint_invalid_activity_returns_404(self):
        """Test invalid activity ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/invalid-id-12345/executive-summary-html"
        )
        assert response.status_code == 404, f"Expected 404 for invalid ID, got {response.status_code}"


class TestActivityAssetsExist:
    """Verify test activity has the expected assets"""
    
    def test_activity_exists(self):
        """Test activity exists and is accessible"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{TEST_ACTIVITY_ID}"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('id') == TEST_ACTIVITY_ID, "Activity ID should match"
        print(f"Activity: {data.get('nama_kegiatan')} - PASS")
    
    def test_activity_has_4_assets(self):
        """Test activity has 4 assets for the PDF/HTML"""
        response = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": TEST_ACTIVITY_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        total = data.get('total', 0)
        assert total == 4, f"Expected 4 assets, got {total}"
        print(f"Activity has {total} assets - PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
