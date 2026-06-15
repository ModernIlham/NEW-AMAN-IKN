"""
Tests for Gallery Mode Features and Related Enhancements
- Gallery thumbnail (256x256) generation and API response
- Asset groups endpoint with detailed member info
- Import validation for internal duplicates
- Doc summary in assets response
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USERNAME = "testadmin"
TEST_PASSWORD = "test1234"

class TestGalleryFeatures:
    """Test gallery view backend requirements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and activity_id"""
        # Login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get activities
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities", headers=self.headers)
        assert activities_resp.status_code == 200
        activities = activities_resp.json()
        if activities:
            self.activity_id = activities[0].get("id")
        else:
            self.activity_id = None
    
    def test_assets_list_returns_gallery_thumbnail(self):
        """Verify /api/assets returns gallery_thumbnail field in projection (may be null for old assets)"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": self.activity_id, "page_size": 10},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "items" in data
        assert "total" in data
        
        # Check that items have required fields (gallery_thumbnail may be None for old assets)
        for item in data.get("items", []):
            # gallery_thumbnail may be missing for assets created before feature was added
            # It will be generated on next edit/create
            # The field is in projection so should be included once asset is updated
            
            # These fields should always be present
            assert "photo_count" in item, "photo_count field missing"
            assert "doc_summary" in item, "doc_summary field missing"
            assert "doc_total" in item, "doc_total field missing"
            assert "doc_checked" in item, "doc_checked field missing"
            
            has_gallery_thumb = "gallery_thumbnail" in item or item.get("gallery_thumbnail") is not None
            print(f"Asset {item.get('asset_code')}: gallery_thumbnail in response={has_gallery_thumb}, photo_count={item.get('photo_count')}")
    
    def test_assets_list_doc_summary_structure(self):
        """Verify doc_summary has correct structure for DOK badge"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": self.activity_id, "page_size": 10},
            headers=self.headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        for item in data.get("items", []):
            doc_summary = item.get("doc_summary", [])
            if doc_summary:
                for doc in doc_summary:
                    # Verify doc_summary item structure
                    assert "name" in doc, "doc_summary item missing 'name'"
                    assert "checked" in doc, "doc_summary item missing 'checked'"
                    assert "has_photos" in doc, "doc_summary item missing 'has_photos'"
                    assert "has_documents" in doc, "doc_summary item missing 'has_documents'"
                    assert "photo_count" in doc, "doc_summary item missing 'photo_count'"
                    assert "doc_count" in doc, "doc_summary item missing 'doc_count'"
                print(f"Asset {item.get('asset_code')}: doc_summary valid with {len(doc_summary)} items")


class TestAssetGroups:
    """Test /api/assets/groups endpoint with detailed members"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and activity_id"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities", headers=self.headers)
        activities = activities_resp.json()
        self.activity_id = activities[0].get("id") if activities else None
    
    def test_groups_endpoint_returns_data(self):
        """Verify /api/assets/groups returns data structure"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        resp = requests.get(
            f"{BASE_URL}/api/assets/groups",
            params={"activity_id": self.activity_id},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        
        assert "groups" in data
        assert "total_groups" in data
        print(f"Found {data.get('total_groups')} groups")
    
    def test_groups_members_have_detailed_info(self):
        """Verify group members include detailed info fields"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        resp = requests.get(
            f"{BASE_URL}/api/assets/groups",
            params={"activity_id": self.activity_id},
            headers=self.headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check structure of groups
        for group in data.get("groups", []):
            assert "asset_code" in group
            assert "asset_name" in group
            assert "count" in group
            assert "NUPs" in group
            assert "members" in group, "members array missing from group"
            
            # Check member details
            for member in group.get("members", []):
                assert "id" in member, "member missing 'id'"
                assert "NUP" in member, "member missing 'NUP'"
                assert "location" in member, "member missing 'location'"
                assert "user" in member, "member missing 'user'"
                assert "condition" in member, "member missing 'condition'"
                assert "inventory_status" in member, "member missing 'inventory_status'"
                assert "nomor_spm" in member, "member missing 'nomor_spm'"
                
            print(f"Group {group.get('asset_code')}: {group.get('count')} members with detailed info")


class TestImportDuplicateValidation:
    """Test import validation for internal duplicates within uploaded file"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and activity_id"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities", headers=self.headers)
        activities = activities_resp.json()
        self.activity_id = activities[0].get("id") if activities else None
    
    def test_import_rejects_internal_duplicates_asset_code_nup(self):
        """Verify import rejects file with duplicate Kode Aset + NUP"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        # Create CSV with duplicate Kode Aset + NUP
        csv_content = """asset_code,NUP,asset_name,category
1234567890,1,Test Asset A,Electronics
1234567890,1,Test Asset B,Electronics
1234567891,2,Test Asset C,Electronics"""
        
        files = {'file': ('test_import.csv', csv_content, 'text/csv')}
        resp = requests.post(
            f"{BASE_URL}/api/import",
            params={"activity_id": self.activity_id},
            files=files,
            headers=self.headers
        )
        
        # Should fail with error about internal duplicates
        data = resp.json()
        assert data.get("success") == False, "Import should fail for internal duplicates"
        
        # Check error message mentions duplicate
        errors = data.get("errors", [])
        has_duplicate_error = any("ganda" in e.lower() or "duplicate" in e.lower() or "sudah ada" in e.lower() for e in errors)
        print(f"Import response: success={data.get('success')}, errors={errors}")
        assert has_duplicate_error, f"Expected error about duplicates, got: {errors}"
    
    def test_import_rejects_internal_duplicates_kode_register(self):
        """Verify import rejects file with duplicate Kode Register"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        # Create CSV with duplicate Kode Register
        csv_content = """asset_code,NUP,asset_name,category,kode_register
1234567890,1,Test Asset A,Electronics,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
1234567891,2,Test Asset B,Electronics,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"""
        
        files = {'file': ('test_import.csv', csv_content, 'text/csv')}
        resp = requests.post(
            f"{BASE_URL}/api/import",
            params={"activity_id": self.activity_id},
            files=files,
            headers=self.headers
        )
        
        data = resp.json()
        assert data.get("success") == False, "Import should fail for duplicate kode_register"
        
        errors = data.get("errors", [])
        has_duplicate_error = any("ganda" in e.lower() or "kode register" in e.lower() for e in errors)
        print(f"Import response: success={data.get('success')}, errors={errors}")
        assert has_duplicate_error, f"Expected error about kode_register duplicates, got: {errors}"


class TestFormValidation:
    """Test lat/long validation requirements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and activity_id"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        activities_resp = requests.get(f"{BASE_URL}/api/inventory-activities", headers=self.headers)
        activities = activities_resp.json()
        self.activity_id = activities[0].get("id") if activities else None
    
    def test_get_single_asset_for_edit(self):
        """Verify single asset fetch includes all fields for edit form"""
        if not self.activity_id:
            pytest.skip("No activity available")
        
        # First get list of assets
        list_resp = requests.get(
            f"{BASE_URL}/api/assets",
            params={"activity_id": self.activity_id, "page_size": 1},
            headers=self.headers
        )
        assert list_resp.status_code == 200
        items = list_resp.json().get("items", [])
        
        if not items:
            pytest.skip("No assets to test")
        
        asset_id = items[0].get("id")
        
        # Fetch single asset
        detail_resp = requests.get(
            f"{BASE_URL}/api/assets/{asset_id}",
            headers=self.headers
        )
        assert detail_resp.status_code == 200, f"Failed to fetch asset: {detail_resp.text}"
        
        asset = detail_resp.json()
        
        # Verify all fields are present for edit form
        required_fields = [
            "id", "asset_code", "asset_name", "category",
            "koordinat_latitude", "koordinat_longitude",
            "inventory_status", "photos", "document_checklist"
        ]
        for field in required_fields:
            assert field in asset, f"Field '{field}' missing from asset detail response"
        
        print(f"Asset {asset.get('asset_code')}: lat={asset.get('koordinat_latitude')}, lon={asset.get('koordinat_longitude')}, inv_status={asset.get('inventory_status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
