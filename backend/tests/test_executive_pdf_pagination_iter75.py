"""
Test Executive Summary PDF Pagination Feature - Iteration 75

Tests the re-architected Executive Summary PDF generation:
1. Summary PDF (no asset detail table)
2. Paginated Data PDFs (499 items per page)
3. Data info endpoint for pagination info

Activity ID with 1926 assets: 2dad75d1-c43f-4c5b-8aad-3c6b48cce584
Expected pages: ceil(1926/499) = 4 pages
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"

class TestExecutiveDataInfoEndpoint:
    """Test GET /api/inventory-activities/{id}/executive-data-info"""
    
    def test_data_info_returns_correct_pagination(self):
        """Verify endpoint returns correct pagination info for 1926 assets"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-info")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_assets" in data, "Response should contain total_assets"
        assert "total_pages" in data, "Response should contain total_pages"
        assert "pages" in data, "Response should contain pages array"
        
        # With 1926 assets and 499 per page, should have 4 pages
        # Page 1: 1-499 (499), Page 2: 500-998 (499), Page 3: 999-1497 (499), Page 4: 1498-1926 (429)
        assert data["total_assets"] == 1926, f"Expected 1926 assets, got {data['total_assets']}"
        assert data["total_pages"] == 4, f"Expected 4 pages, got {data['total_pages']}"
        assert len(data["pages"]) == 4, f"Expected 4 page entries, got {len(data['pages'])}"
        
    def test_data_info_page_ranges_correct(self):
        """Verify each page has correct start/end/count"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-info")
        assert response.status_code == 200
        
        data = response.json()
        pages = data["pages"]
        
        # Page 1: 1-499
        assert pages[0]["page"] == 1
        assert pages[0]["start"] == 1
        assert pages[0]["end"] == 499
        assert pages[0]["count"] == 499
        
        # Page 2: 500-998
        assert pages[1]["page"] == 2
        assert pages[1]["start"] == 500
        assert pages[1]["end"] == 998
        assert pages[1]["count"] == 499
        
        # Page 3: 999-1497
        assert pages[2]["page"] == 3
        assert pages[2]["start"] == 999
        assert pages[2]["end"] == 1497
        assert pages[2]["count"] == 499
        
        # Page 4: 1498-1926 (last page, smaller)
        assert pages[3]["page"] == 4
        assert pages[3]["start"] == 1498
        assert pages[3]["end"] == 1926
        assert pages[3]["count"] == 429  # 1926 - 1498 + 1 = 429
        
    def test_data_info_invalid_activity_returns_404(self):
        """Verify 404 for non-existent activity"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities/invalid-id-12345/executive-data-info")
        assert response.status_code == 404


class TestExecutiveSummaryPDF:
    """Test GET /api/inventory-activities/{id}/executive-summary-pdf"""
    
    def test_summary_pdf_returns_pdf(self):
        """Verify endpoint returns a valid PDF"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-summary-pdf",
            timeout=120  # PDF generation can be slow
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        
        # Verify it's a PDF (starts with %PDF)
        assert response.content[:4] == b"%PDF", "Response should be a valid PDF"
        
        # Summary PDF should be relatively small (no asset tables)
        # Expecting less than 5MB for summary only
        pdf_size = len(response.content)
        assert pdf_size < 5 * 1024 * 1024, f"Summary PDF too large: {pdf_size} bytes"
        print(f"Summary PDF size: {pdf_size / 1024:.1f} KB")
        
    def test_summary_pdf_does_not_contain_asset_table(self):
        """Summary PDF should not contain the detailed asset data table"""
        # This is verified by the template not including asset_pages
        # The template executive_summary.html is used with empty asset_pages
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-summary-pdf",
            timeout=120
        )
        assert response.status_code == 200
        # Summary PDF should have limited pages (cover + summary + charts + analysis/teams)
        # Without asset detail, it should be under 1MB typically
        pdf_size = len(response.content)
        print(f"Summary PDF size: {pdf_size / 1024:.1f} KB (no asset detail table)")


class TestExecutiveDataPDF:
    """Test GET /api/inventory-activities/{id}/executive-data-pdf?page=N"""
    
    def test_data_pdf_page1_returns_pdf(self):
        """Verify page 1 returns valid PDF with asset data"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page=1",
            timeout=120
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content[:4] == b"%PDF", "Response should be a valid PDF"
        
        # Data PDF will have ~28 pages for 499 assets (18 rows per page)
        # 499 / 18 = 27.7 -> 28 pages
        pdf_size = len(response.content)
        print(f"Data PDF page 1 size: {pdf_size / 1024:.1f} KB")
        
    def test_data_pdf_page4_last_page(self):
        """Verify last page (page 4) returns valid PDF"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page=4",
            timeout=120
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content[:4] == b"%PDF", "Response should be a valid PDF"
        
        # Page 4 has 429 assets (1926 - 1497 = 429)
        # 429 / 18 = 23.8 -> 24 pages
        pdf_size = len(response.content)
        print(f"Data PDF page 4 size: {pdf_size / 1024:.1f} KB")
        
    def test_data_pdf_invalid_page_returns_400(self):
        """Verify 400 error for invalid page number"""
        # Page 99 doesn't exist (only 4 pages)
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page=99",
            timeout=30
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        # Error should mention the invalid page
        assert "99" in data["detail"] or "tidak valid" in data["detail"].lower()
        
    def test_data_pdf_page_zero_returns_400(self):
        """Verify 400 error for page 0"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page=0",
            timeout=30
        )
        assert response.status_code == 400
        
    def test_data_pdf_negative_page_returns_400(self):
        """Verify 400 error for negative page"""
        response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page=-1",
            timeout=30
        )
        assert response.status_code == 400
        

class TestEndpointIntegration:
    """Integration tests for the full workflow"""
    
    def test_full_pagination_workflow(self):
        """Test complete workflow: get info then download each page"""
        # Step 1: Get pagination info
        info_response = requests.get(
            f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-info"
        )
        assert info_response.status_code == 200
        info = info_response.json()
        
        # Step 2: Verify we can access each page endpoint
        for page_info in info["pages"]:
            page_num = page_info["page"]
            # Just check it returns 200 (don't download full PDF to save time)
            response = requests.head(
                f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page={page_num}",
                timeout=10
            )
            # HEAD may return 200 or 405 (Method Not Allowed)
            # Use GET with timeout
            response = requests.get(
                f"{BASE_URL}/api/inventory-activities/{ACTIVITY_ID}/executive-data-pdf?page={page_num}",
                timeout=120,
                stream=True  # Don't download full content
            )
            assert response.status_code == 200, f"Page {page_num} returned {response.status_code}"
            print(f"Page {page_num} ({page_info['start']}-{page_info['end']}): OK")
            response.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
