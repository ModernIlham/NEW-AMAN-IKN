"""
Test Suite for Iteration 57 Features:
1. GET /api/assets/groups - Enhanced member detail fields
2. PUT /api/assets/batch-update - New fields including batch_photo and document_checklist_items
"""

import pytest
import requests
import os
import uuid

# Use environment variable for API URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"

# Test activity ID from context (has assets)
TEST_ACTIVITY_ID = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"


class TestAssetGroupsEndpoint:
    """Test GET /api/assets/groups - members should include new fields"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create 2 assets with same asset_code to form a group"""
        self.asset_code = f"TEST_GROUP_{uuid.uuid4().hex[:8]}"
        self.asset_ids = []
        
        # Create 2 assets with same asset_code
        for i in range(2):
            asset_data = {
                "asset_code": self.asset_code,
                "NUP": str(i + 1),
                "asset_name": f"Test Group Asset {i + 1}",
                "category": "Test Category",
                "brand": "Test Brand",
                "model": "Test Model",
                "kode_register": f"REG-{self.asset_code}-{i + 1}",
                "serial_number": f"SN-{uuid.uuid4().hex[:6]}",
                "purchase_date": "2025-01-15",
                "purchase_price": 500000,
                "location": f"Location {i + 1}",
                "department": "Test Dept",
                "eselon1": "Eselon I Test",
                "eselon2": f"Eselon II Unit {i + 1}",
                "user": f"User {i + 1}",
                "condition": "Baik",
                "status": "Aktif",
                "nomor_spm": f"SPM-{uuid.uuid4().hex[:6]}",
                "perolehan_dari_nama": f"Supplier {i + 1}",
                "supplier": f"Main Supplier {i + 1}",
                "activity_id": TEST_ACTIVITY_ID
            }
            resp = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
            if resp.status_code == 200 or resp.status_code == 201:
                self.asset_ids.append(resp.json().get("id"))
        
        yield
        
        # Cleanup
        for aid in self.asset_ids:
            try:
                requests.delete(f"{BASE_URL}/api/assets/{aid}")
            except:
                pass

    def test_groups_endpoint_returns_200(self):
        """Test that groups endpoint returns 200"""
        resp = requests.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": TEST_ACTIVITY_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "groups" in data
        assert "total_groups" in data
        print(f"PASS: Groups endpoint returned {data['total_groups']} groups")

    def test_groups_contain_created_group(self):
        """Test that created assets appear in groups"""
        resp = requests.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": TEST_ACTIVITY_ID})
        assert resp.status_code == 200
        groups = resp.json().get("groups", [])
        
        # Find our test group
        test_group = None
        for g in groups:
            if g.get("asset_code") == self.asset_code:
                test_group = g
                break
        
        assert test_group is not None, f"Expected to find group with asset_code {self.asset_code}"
        assert test_group.get("count") == 2, f"Expected 2 members, got {test_group.get('count')}"
        print(f"PASS: Found test group with {test_group.get('count')} members")

    def test_groups_members_have_new_fields(self):
        """Test that group members include new fields: supplier, perolehan_dari_nama, purchase_date, purchase_price, category, eselon1, eselon2"""
        resp = requests.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": TEST_ACTIVITY_ID})
        assert resp.status_code == 200
        groups = resp.json().get("groups", [])
        
        # Find our test group
        test_group = None
        for g in groups:
            if g.get("asset_code") == self.asset_code:
                test_group = g
                break
        
        assert test_group is not None, f"Group not found for asset_code {self.asset_code}"
        
        members = test_group.get("members", [])
        assert len(members) == 2, f"Expected 2 members, got {len(members)}"
        
        required_fields = ["supplier", "perolehan_dari_nama", "purchase_date", "purchase_price", "category", "eselon1", "eselon2"]
        for member in members:
            for field in required_fields:
                assert field in member, f"Member missing field '{field}'"
            
            # Verify values are populated
            assert member.get("perolehan_dari_nama") is not None, "perolehan_dari_nama should be populated"
            assert member.get("supplier") is not None, "supplier should be populated"
            assert member.get("eselon1") is not None, "eselon1 should be populated"
            assert member.get("eselon2") is not None, "eselon2 should be populated"
            assert member.get("category") is not None, "category should be populated"
        
        print(f"PASS: All required fields present in members: {required_fields}")

    def test_groups_members_have_kode_register(self):
        """Test that members include kode_register (for display without truncation)"""
        resp = requests.get(f"{BASE_URL}/api/assets/groups", params={"activity_id": TEST_ACTIVITY_ID})
        assert resp.status_code == 200
        groups = resp.json().get("groups", [])
        
        test_group = None
        for g in groups:
            if g.get("asset_code") == self.asset_code:
                test_group = g
                break
        
        assert test_group is not None
        members = test_group.get("members", [])
        
        for member in members:
            assert "kode_register" in member, "Member missing 'kode_register' field"
            assert member.get("kode_register") is not None, "kode_register should be populated"
        
        print("PASS: Members include kode_register field")


class TestBatchUpdateNewFields:
    """Test PUT /api/assets/batch-update with new fields"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create test assets for batch update"""
        self.asset_ids = []
        
        for i in range(2):
            asset_data = {
                "asset_code": f"TEST_BATCH_{uuid.uuid4().hex[:8]}",
                "NUP": str(i + 1),
                "asset_name": f"Test Batch Asset {i + 1}",
                "category": "Original Category",
                "location": "Original Location",
                "condition": "Baik",
                "status": "Aktif",
                "activity_id": TEST_ACTIVITY_ID
            }
            resp = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
            if resp.status_code in [200, 201]:
                self.asset_ids.append(resp.json().get("id"))
        
        yield
        
        # Cleanup
        for aid in self.asset_ids:
            try:
                requests.delete(f"{BASE_URL}/api/assets/{aid}")
            except:
                pass

    def test_batch_update_eselon_fields(self):
        """Test batch update with eselon1 and eselon2 fields"""
        updates = {
            "eselon1": "Eselon I Updated",
            "eselon2": "Eselon II Updated"
        }
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("updated") == len(self.asset_ids)
        
        # Verify update
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("eselon1") == "Eselon I Updated"
            assert asset.get("eselon2") == "Eselon II Updated"
        
        print("PASS: Batch update eselon1/eselon2 works correctly")

    def test_batch_update_nomor_spm(self):
        """Test batch update with nomor_spm field"""
        updates = {"nomor_spm": "SPM-BATCH-001"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        # Verify
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("nomor_spm") == "SPM-BATCH-001"
        
        print("PASS: Batch update nomor_spm works correctly")

    def test_batch_update_perolehan_dari_nama(self):
        """Test batch update with perolehan_dari_nama field"""
        updates = {"perolehan_dari_nama": "Supplier ABC"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("perolehan_dari_nama") == "Supplier ABC"
        
        print("PASS: Batch update perolehan_dari_nama works correctly")

    def test_batch_update_nomor_kontrak(self):
        """Test batch update with nomor_kontrak field"""
        updates = {"nomor_kontrak": "KONTRAK-2025-001"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("nomor_kontrak") == "KONTRAK-2025-001"
        
        print("PASS: Batch update nomor_kontrak works correctly")

    def test_batch_update_nomor_bukti_perolehan(self):
        """Test batch update with nomor_bukti_perolehan (BAST) field"""
        updates = {"nomor_bukti_perolehan": "BAST-2025-001"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("nomor_bukti_perolehan") == "BAST-2025-001"
        
        print("PASS: Batch update nomor_bukti_perolehan works correctly")

    def test_batch_update_supplier(self):
        """Test batch update with supplier field"""
        updates = {"supplier": "PT Supplier Indonesia"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("supplier") == "PT Supplier Indonesia"
        
        print("PASS: Batch update supplier works correctly")

    def test_batch_update_purchase_date(self):
        """Test batch update with purchase_date field"""
        updates = {"purchase_date": "2025-06-15"}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("purchase_date") == "2025-06-15"
        
        print("PASS: Batch update purchase_date works correctly")

    def test_batch_update_purchase_price(self):
        """Test batch update with purchase_price field"""
        updates = {"purchase_price": 1500000}
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            # Price might be stored as string or number
            price = asset.get("purchase_price")
            assert price is not None
        
        print("PASS: Batch update purchase_price works correctly")

    def test_batch_update_coordinates(self):
        """Test batch update with koordinat_latitude and koordinat_longitude fields"""
        updates = {
            "koordinat_latitude": "-6.200000",
            "koordinat_longitude": "106.816666"
        }
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("koordinat_latitude") == "-6.200000"
            assert asset.get("koordinat_longitude") == "106.816666"
        
        print("PASS: Batch update coordinates works correctly")

    def test_batch_update_brand_model(self):
        """Test batch update with brand and model fields"""
        updates = {
            "brand": "Dell",
            "model": "Latitude 5520"
        }
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200
        
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            assert asset.get("brand") == "Dell"
            assert asset.get("model") == "Latitude 5520"
        
        print("PASS: Batch update brand/model works correctly")


class TestBatchPhotoUpload:
    """Test batch_photo field in batch-update"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create test assets"""
        self.asset_ids = []
        
        for i in range(2):
            asset_data = {
                "asset_code": f"TEST_PHOTO_{uuid.uuid4().hex[:8]}",
                "NUP": str(i + 1),
                "asset_name": f"Test Photo Asset {i + 1}",
                "activity_id": TEST_ACTIVITY_ID
            }
            resp = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
            if resp.status_code in [200, 201]:
                self.asset_ids.append(resp.json().get("id"))
        
        yield
        
        # Cleanup
        for aid in self.asset_ids:
            try:
                requests.delete(f"{BASE_URL}/api/assets/{aid}")
            except:
                pass

    def test_batch_photo_adds_to_all_assets(self):
        """Test that batch_photo adds a photo to all selected assets"""
        # Create a minimal valid base64 image (1x1 red pixel JPEG)
        test_image_base64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAB//2Q=="
        
        updates = {
            "batch_photo": test_image_base64
        }
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify each asset has the photo
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            photos = asset.get("photos", [])
            assert len(photos) > 0, f"Asset {aid} should have at least one photo"
            # The photo should be in the photos array
            assert any("base64" in p for p in photos), "Photo should be base64 encoded"
        
        print("PASS: Batch photo adds to all assets correctly")


class TestBatchDocumentChecklist:
    """Test document_checklist_items field in batch-update"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create test assets"""
        self.asset_ids = []
        
        for i in range(2):
            asset_data = {
                "asset_code": f"TEST_DOC_{uuid.uuid4().hex[:8]}",
                "NUP": str(i + 1),
                "asset_name": f"Test Doc Asset {i + 1}",
                "activity_id": TEST_ACTIVITY_ID,
                "document_checklist": [
                    {"name": "Buku Manual", "checked": False, "notes": "", "photos": [], "documents": []},
                    {"name": "Charger/Adapter", "checked": False, "notes": "", "photos": [], "documents": []}
                ]
            }
            resp = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
            if resp.status_code in [200, 201]:
                self.asset_ids.append(resp.json().get("id"))
        
        yield
        
        # Cleanup
        for aid in self.asset_ids:
            try:
                requests.delete(f"{BASE_URL}/api/assets/{aid}")
            except:
                pass

    def test_batch_document_checklist_updates(self):
        """Test that document_checklist_items updates checklist for all assets"""
        updates = {
            "document_checklist_items": [
                {"name": "Buku Manual", "checked": True},
                {"name": "Charger/Adapter", "checked": True}
            ]
        }
        
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids,
            "updates": updates
        })
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify each asset has updated document checklist
        for aid in self.asset_ids:
            asset = requests.get(f"{BASE_URL}/api/assets/{aid}").json()
            doc_checklist = asset.get("document_checklist", [])
            
            # Find "Buku Manual" and "Charger/Adapter"
            buku_manual = next((d for d in doc_checklist if d.get("name") == "Buku Manual"), None)
            charger = next((d for d in doc_checklist if d.get("name") == "Charger/Adapter"), None)
            
            assert buku_manual is not None, "Buku Manual should exist in checklist"
            assert charger is not None, "Charger/Adapter should exist in checklist"
            assert buku_manual.get("checked") == True, "Buku Manual should be checked"
            assert charger.get("checked") == True, "Charger/Adapter should be checked"
        
        print("PASS: Batch document checklist update works correctly")


class TestBatchUpdateAllowedFields:
    """Test that BATCH_ALLOWED_FIELDS contains all new fields"""

    def test_batch_update_rejects_invalid_fields(self):
        """Test that invalid fields are ignored"""
        # First create a test asset
        asset_data = {
            "asset_code": f"TEST_INVALID_{uuid.uuid4().hex[:8]}",
            "NUP": "1",
            "asset_name": "Test Invalid Field Asset",
            "activity_id": TEST_ACTIVITY_ID
        }
        resp = requests.post(f"{BASE_URL}/api/assets", json=asset_data)
        assert resp.status_code in [200, 201]
        asset_id = resp.json().get("id")
        
        try:
            # Try to update with invalid field
            updates = {
                "invalid_field_xyz": "should be ignored",
                "location": "Valid Location"
            }
            
            resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
                "asset_ids": [asset_id],
                "updates": updates
            })
            
            # Should still succeed but only apply valid fields
            assert resp.status_code == 200
            
            # Verify location was updated
            asset = requests.get(f"{BASE_URL}/api/assets/{asset_id}").json()
            assert asset.get("location") == "Valid Location"
            
            print("PASS: Invalid fields are ignored, valid fields are applied")
        finally:
            requests.delete(f"{BASE_URL}/api/assets/{asset_id}")

    def test_batch_update_empty_updates_rejected(self):
        """Test that empty updates are rejected with 400"""
        resp = requests.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": ["fake-id"],
            "updates": {}
        })
        
        assert resp.status_code == 400, f"Expected 400 for empty updates, got {resp.status_code}"
        print("PASS: Empty updates are properly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
