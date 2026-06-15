
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Activity-based Workflow for Inventory System
Tests for iteration 5: Activity Selection Page, Create Activity with uploads, Asset filtering by activity_id
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = TEST_ADMIN_PASSWORD

class TestHealthAndAuth:
    """Test health check and authentication"""
    
    def test_health_check(self):
        """API should be running"""
        r = requests.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print(f"✓ Health check passed: {data['message']}")
    
    def test_login_success(self):
        """Login with valid credentials should return token"""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == TEST_USERNAME
        print(f"✓ Login success: {data['user']['name']}")
    
    def test_login_invalid_credentials(self):
        """Login with invalid credentials should return 401"""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wrong",
            "password": "wrong"
        })
        assert r.status_code == 401
        print("✓ Invalid credentials rejected with 401")


class TestInventoryActivities:
    """Test inventory activities CRUD and workflow"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        })
        return r.json()["access_token"]
    
    def test_get_activities_list(self):
        """GET /inventory-activities should return list with stats"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} activities")
        
        # Check each activity has required fields
        if data:
            act = data[0]
            assert "id" in act
            assert "nomor_surat" in act
            assert "nama_kegiatan" in act
            assert "total_assets" in act
            assert "total_value" in act
            print(f"✓ Activity has stats: {act['nama_kegiatan']} ({act['total_assets']} assets, Rp {act['total_value']:,.0f})")
    
    def test_create_activity_basic(self):
        """POST /inventory-activities should create activity"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "nomor_surat": f"TEST/{unique_id}/2024",
            "nama_kegiatan": f"Test Activity {unique_id}",
            "deskripsi": "Created by automated test",
            "tanggal_mulai": "2024-01-01",
            "tanggal_selesai": "2024-12-31",
            "penanggung_jawab": "Test User",
            "asset_ids": [],
            "photos": [],
            "documents": []
        }
        r = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["nomor_surat"] == payload["nomor_surat"]
        assert data["nama_kegiatan"] == payload["nama_kegiatan"]
        assert "id" in data
        print(f"✓ Created activity: {data['nama_kegiatan']} (id: {data['id'][:8]}...)")
        
        # Cleanup - delete the test activity
        del_r = requests.delete(f"{BASE_URL}/api/inventory-activities/{data['id']}")
        assert del_r.status_code == 200
        print("✓ Cleaned up test activity")
    
    def test_create_activity_with_photos(self):
        """Create activity with photo uploads"""
        unique_id = str(uuid.uuid4())[:8]
        # Small base64 image for testing (1x1 red pixel PNG)
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        
        payload = {
            "nomor_surat": f"PHOTO/{unique_id}/2024",
            "nama_kegiatan": f"Activity with Photo {unique_id}",
            "deskripsi": "Testing photo upload",
            "tanggal_mulai": "2024-01-01",
            "tanggal_selesai": "",
            "penanggung_jawab": "Tester",
            "asset_ids": [],
            "photos": [test_image, test_image],  # 2 photos
            "documents": []
        }
        r = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("photos", [])) == 2
        print(f"✓ Created activity with {len(data['photos'])} photos")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/inventory-activities/{data['id']}")
    
    def test_create_activity_with_documents(self):
        """Create activity with document uploads"""
        unique_id = str(uuid.uuid4())[:8]
        # Minimal PDF base64
        test_doc = {
            "name": "test_document.pdf",
            "data": "data:application/pdf;base64,JVBERi0xLjEKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvUmVzb3VyY2VzIDw8ID4+IC9NZWRpYUJveCBbMCAwIDYxMiA3OTJdID4+CmVuZG9iagp4cmVmCjAgNAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA1NyAwMDAwMCBuIAowMDAwMDAwMTE0IDAwMDAwIG4gCnRyYWlsZXIKPDwgL1Jvb3QgMSAwIFIgL1NpemUgNCA+PgpzdGFydHhyZWYKMjE2CiUlRU9G"
        }
        
        payload = {
            "nomor_surat": f"DOC/{unique_id}/2024",
            "nama_kegiatan": f"Activity with Document {unique_id}",
            "deskripsi": "Testing document upload",
            "tanggal_mulai": "2024-01-01",
            "tanggal_selesai": "",
            "penanggung_jawab": "Tester",
            "asset_ids": [],
            "photos": [],
            "documents": [test_doc]
        }
        r = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("documents", [])) == 1
        assert data["documents"][0]["name"] == "test_document.pdf"
        print(f"✓ Created activity with {len(data['documents'])} document(s): {data['documents'][0]['name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/inventory-activities/{data['id']}")
    
    def test_duplicate_nomor_surat_rejected(self):
        """Duplicate nomor_surat should be rejected"""
        # Get existing activity
        r = requests.get(f"{BASE_URL}/api/inventory-activities")
        activities = r.json()
        if not activities:
            pytest.skip("No existing activities to test duplicate")
        
        existing_nomor = activities[0]["nomor_surat"]
        
        payload = {
            "nomor_surat": existing_nomor,  # Duplicate
            "nama_kegiatan": "Duplicate Test",
            "deskripsi": "",
            "tanggal_mulai": "",
            "tanggal_selesai": "",
            "penanggung_jawab": "",
            "asset_ids": [],
            "photos": [],
            "documents": []
        }
        r = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        assert r.status_code == 400
        assert "sudah digunakan" in r.json()["detail"]
        print(f"✓ Duplicate nomor_surat '{existing_nomor}' correctly rejected")
    
    def test_delete_activity(self):
        """DELETE /inventory-activities/:id should delete activity"""
        # Create one to delete
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "nomor_surat": f"DEL/{unique_id}/2024",
            "nama_kegiatan": f"To Delete {unique_id}",
            "deskripsi": "",
            "tanggal_mulai": "",
            "tanggal_selesai": "",
            "penanggung_jawab": "",
            "asset_ids": [],
            "photos": [],
            "documents": []
        }
        create_r = requests.post(f"{BASE_URL}/api/inventory-activities", json=payload)
        activity_id = create_r.json()["id"]
        
        # Delete it
        del_r = requests.delete(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert del_r.status_code == 200
        
        # Verify it's gone
        get_r = requests.get(f"{BASE_URL}/api/inventory-activities/{activity_id}")
        assert get_r.status_code == 404
        print("✓ Activity deleted and verified gone")


class TestAssetActivityFiltering:
    """Test assets filtering by activity_id"""
    
    def test_get_assets_by_activity(self):
        """GET /assets?activity_id=xxx should filter by activity"""
        # Get an activity with assets
        r = requests.get(f"{BASE_URL}/api/inventory-activities")
        activities = r.json()
        
        # Find activity with assets
        activity_with_assets = None
        for act in activities:
            if act.get("total_assets", 0) > 0:
                activity_with_assets = act
                break
        
        if not activity_with_assets:
            pytest.skip("No activity with assets to test filtering")
        
        activity_id = activity_with_assets["id"]
        expected_count = activity_with_assets["total_assets"]
        
        # Get assets filtered by activity
        r = requests.get(f"{BASE_URL}/api/assets?activity_id={activity_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == expected_count
        print(f"✓ Activity '{activity_with_assets['nama_kegiatan']}' has {data['total']} assets (expected {expected_count})")
        
        # Verify all assets have correct activity_id
        for asset in data["items"]:
            assert asset.get("activity_id") == activity_id
        print(f"✓ All {len(data['items'])} assets have correct activity_id")
    
    def test_assets_stats_by_activity(self):
        """GET /assets/stats?activity_id=xxx should return stats for activity"""
        r = requests.get(f"{BASE_URL}/api/inventory-activities")
        activities = r.json()
        
        activity_with_assets = None
        for act in activities:
            if act.get("total_assets", 0) > 0:
                activity_with_assets = act
                break
        
        if not activity_with_assets:
            pytest.skip("No activity with assets")
        
        activity_id = activity_with_assets["id"]
        
        r = requests.get(f"{BASE_URL}/api/assets/stats?activity_id={activity_id}")
        assert r.status_code == 200
        data = r.json()
        assert "total_assets" in data
        assert "total_value" in data
        print(f"✓ Stats for activity: {data['total_assets']} assets, Rp {data['total_value']:,.0f}")


class TestAssetPhotoLimit:
    """Test photo upload limit is 6"""
    
    def test_create_asset_with_6_photos(self):
        """Create asset with exactly 6 photos should work"""
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        unique_code = f"60{str(uuid.uuid4())[:8].replace('-', '')[:8]}"  # 10 digit code
        
        payload = {
            "asset_code": unique_code,
            "asset_name": "Test Asset with 6 Photos",
            "category": "Elektronik",
            "photos": [test_image] * 6,  # 6 photos
            "NUP": "",
            "brand": "",
            "model": "",
            "kode_register": "",
            "serial_number": "",
            "purchase_date": "",
            "purchase_price": "",
            "location": "",
            "department": "",
            "user": "",
            "condition": "Baik",
            "status": "Aktif",
            "nomor_spm": "",
            "perolehan_dari_nama": "",
            "nomor_kontrak": "",
            "nomor_bukti_perolehan": "",
            "supplier": "",
            "notes": "",
            "document_checklist": []
        }
        
        r = requests.post(f"{BASE_URL}/api/assets", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("photos", [])) == 6
        print("✓ Created asset with 6 photos")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/assets/{data['id']}")


class TestAssetCardPrint:
    """Test KTP-sized card printing"""
    
    def test_print_single_card(self):
        """GET /assets/:id/card should return PDF"""
        # Get an asset
        r = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=1")
        assets = r.json()["items"]
        if not assets:
            pytest.skip("No assets to test card print")
        
        asset_id = assets[0]["id"]
        
        r = requests.get(f"{BASE_URL}/api/assets/{asset_id}/card")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert len(r.content) > 0
        print(f"✓ Single card PDF generated: {len(r.content)} bytes")
    
    def test_print_bulk_cards(self):
        """POST /assets/cards/bulk should return PDF with multiple cards"""
        # Get a few assets
        r = requests.get(f"{BASE_URL}/api/assets?page=1&page_size=3")
        assets = r.json()["items"]
        if len(assets) < 2:
            pytest.skip("Need at least 2 assets for bulk print test")
        
        asset_ids = [a["id"] for a in assets[:3]]
        
        r = requests.post(f"{BASE_URL}/api/assets/cards/bulk", json=asset_ids)
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/pdf"
        assert len(r.content) > 0
        print(f"✓ Bulk cards PDF generated for {len(asset_ids)} assets: {len(r.content)} bytes")


class TestDocumentChecklist:
    """Test document checklist with file upload preview"""
    
    def test_asset_with_document_checklist(self):
        """Create asset with document checklist items"""
        unique_code = f"DC{str(uuid.uuid4())[:8].replace('-', '')[:8]}"
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        
        payload = {
            "asset_code": unique_code,
            "asset_name": "Asset with Document Checklist",
            "category": "Elektronik",
            "photos": [],
            "document_checklist": [
                {
                    "name": "STNK",
                    "checked": True,
                    "notes": "Test note",
                    "photos": [test_image],
                    "documents": []
                },
                {
                    "name": "BPKB",
                    "checked": False,
                    "notes": ""
                }
            ],
            "NUP": "",
            "brand": "",
            "model": "",
            "kode_register": "",
            "serial_number": "",
            "purchase_date": "",
            "purchase_price": "",
            "location": "",
            "department": "",
            "user": "",
            "condition": "Baik",
            "status": "Aktif",
            "nomor_spm": "",
            "perolehan_dari_nama": "",
            "nomor_kontrak": "",
            "nomor_bukti_perolehan": "",
            "supplier": "",
            "notes": ""
        }
        
        r = requests.post(f"{BASE_URL}/api/assets", json=payload)
        assert r.status_code == 200
        data = r.json()
        
        # Verify checklist
        checklist = data.get("document_checklist", [])
        assert len(checklist) == 2
        assert checklist[0]["name"] == "STNK"
        assert checklist[0]["checked"] == True
        print(f"✓ Created asset with {len(checklist)} checklist items")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/assets/{data['id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
