
# --- centralised test credentials (avoid hardcoded secrets) ---
import os, sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME  # noqa: E402
"""
Test Suite for Batch Edit 'Kosongkan' (Clear) Feature - Iteration 61
Tests the new clear functionality in batch edit panel:
- __clear__ sentinel value for text/dropdown fields
- clear_photos flag to remove all photos
- clear_document_checklist flag to clear all docs
- Mixed updates (some fields set, some cleared)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBatchClearFeature:
    """Tests for batch update clear functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data - login and create test assets in existing activity"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.user = login_resp.json()
        self.session.headers.update({
            "X-User-Id": self.user.get("id", ""),
            "X-User-Name": self.user.get("username", "admin"),
            "X-Session-Id": str(uuid.uuid4())
        })

        # Use existing test activity (from iteration 60)
        self.activity_id = "2dad75d1-c43f-4c5b-8aad-3c6b48cce584"

        # Create 5 test assets with data to clear
        self.asset_ids = []
        for i in range(5):
            asset_resp = self.session.post(f"{BASE_URL}/api/assets", json={
                "activity_id": self.activity_id,
                "asset_code": f"CLEAR-{i:03d}",
                "asset_name": f"Test Asset Clear {i}",
                "category": "Laptop",
                "location": f"Room {i}",
                "brand": f"Brand {i}",
                "model": f"Model {i}",
                "condition": "Baik",
                "inventory_status": "Ditemukan",
                "stiker_status": "Belum Terpasang",
                "eselon1": "Eselon1-Test",
                "eselon2": "Eselon2-A",
                "nomor_spm": f"SPM-{i}",
                "supplier": f"Supplier {i}",
                "photos": [f"data:image/png;base64,TEST{i}"],
                "document_checklist": [
                    {"name": "KIB", "checked": True, "photos": [], "documents": []},
                    {"name": "BAST", "checked": False, "photos": [], "documents": []}
                ]
            })
            assert asset_resp.status_code in [200, 201], f"Asset creation failed: {asset_resp.text}"
            self.asset_ids.append(asset_resp.json().get("id"))

        yield

        # Cleanup: Delete test assets only (keep activity)
        for aid in self.asset_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/assets/{aid}")
            except:
                pass

    def test_clear_text_field_brand(self):
        """Test clearing brand field using __clear__ sentinel"""
        # Batch update brand with __clear__
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {"brand": "__clear__"}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"
        result = resp.json()
        assert result.get("updated") == 2 or result.get("count") == 2 or "success" in str(result).lower()

        # Verify brand is now empty string
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("brand") == "", f"Brand should be empty but got: {asset.get('brand')}"

    def test_clear_text_field_location(self):
        """Test clearing location field using __clear__ sentinel"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {"location": "__clear__"}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify location is now empty string
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("location") == "", f"Location should be empty but got: {asset.get('location')}"

    def test_clear_dropdown_field_condition(self):
        """Test clearing condition dropdown field using __clear__ sentinel"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {"condition": "__clear__"}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify condition is now empty string
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("condition") == "", f"Condition should be empty but got: {asset.get('condition')}"

    def test_clear_photos(self):
        """Test clearing all photos using clear_photos flag"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[2:4],
            "updates": {"clear_photos": True}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify photos are cleared
        for aid in self.asset_ids[2:4]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            photos = asset.get("photos", [])
            assert photos == [] or photos is None or len(photos) == 0, f"Photos should be empty but got: {photos}"

    def test_clear_document_checklist(self):
        """Test clearing all documents using clear_document_checklist flag"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": [self.asset_ids[4]],
            "updates": {"clear_document_checklist": True}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify document_checklist is cleared
        asset_resp = self.session.get(f"{BASE_URL}/api/assets/{self.asset_ids[4]}")
        assert asset_resp.status_code == 200
        asset = asset_resp.json()
        doc_checklist = asset.get("document_checklist", [])
        assert doc_checklist == [] or doc_checklist is None or len(doc_checklist) == 0, f"Doc checklist should be empty but got: {doc_checklist}"

    def test_mixed_update_set_and_clear(self):
        """Test mixed updates: some fields set to value, some cleared"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:3],
            "updates": {
                "location": "New Location Set",  # Set new value
                "brand": "__clear__",  # Clear field
                "model": "__clear__",  # Clear field
                "supplier": "New Supplier"  # Set new value
            }
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify mixed updates
        for aid in self.asset_ids[:3]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("location") == "New Location Set", "Location should be 'New Location Set'"
            assert asset.get("brand") == "", "Brand should be empty"
            assert asset.get("model") == "", "Model should be empty"
            assert asset.get("supplier") == "New Supplier", "Supplier should be 'New Supplier'"

    def test_reject_empty_updates(self):
        """Test that batch update rejects when no valid updates provided"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:1],
            "updates": {}
        })
        assert resp.status_code == 400, f"Should reject empty updates, got: {resp.status_code}"

    def test_clear_eselon_fields(self):
        """Test clearing eselon1 and eselon2 fields"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {
                "eselon1": "__clear__",
                "eselon2": "__clear__"
            }
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify eselon fields are cleared
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("eselon1") == "", f"Eselon1 should be empty but got: {asset.get('eselon1')}"
            assert asset.get("eselon2") == "", f"Eselon2 should be empty but got: {asset.get('eselon2')}"

    def test_clear_inventory_status_and_stiker_status(self):
        """Test clearing inventory_status and stiker_status dropdown fields"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {
                "inventory_status": "__clear__",
                "stiker_status": "__clear__"
            }
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify dropdown fields are cleared
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("inventory_status") == "", "Inventory status should be empty"
            assert asset.get("stiker_status") == "", "Stiker status should be empty"

    def test_clear_nomor_spm(self):
        """Test clearing nomor_spm field"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": self.asset_ids[:2],
            "updates": {"nomor_spm": "__clear__"}
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify nomor_spm is cleared
        for aid in self.asset_ids[:2]:
            asset_resp = self.session.get(f"{BASE_URL}/api/assets/{aid}")
            assert asset_resp.status_code == 200
            asset = asset_resp.json()
            assert asset.get("nomor_spm") == "", f"Nomor SPM should be empty but got: {asset.get('nomor_spm')}"

    def test_clear_photos_and_set_other_field(self):
        """Test clearing photos while setting another field"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": [self.asset_ids[0]],
            "updates": {
                "clear_photos": True,
                "location": "Updated After Clear"
            }
        })
        assert resp.status_code == 200, f"Batch update failed: {resp.text}"

        # Verify photos cleared and location updated
        asset_resp = self.session.get(f"{BASE_URL}/api/assets/{self.asset_ids[0]}")
        assert asset_resp.status_code == 200
        asset = asset_resp.json()
        photos = asset.get("photos", [])
        assert photos == [] or len(photos) == 0, "Photos should be empty"
        assert asset.get("location") == "Updated After Clear", "Location should be updated"


class TestBatchClearValidation:
    """Tests for validation and edge cases"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login only"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": TEST_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.user = login_resp.json()
        self.session.headers.update({
            "X-User-Id": self.user.get("id", ""),
            "X-User-Name": self.user.get("username", "admin"),
            "X-Session-Id": str(uuid.uuid4())
        })

    def test_reject_empty_asset_ids(self):
        """Test that batch update rejects empty asset_ids"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": [],
            "updates": {"brand": "__clear__"}
        })
        assert resp.status_code == 400, f"Should reject empty asset_ids, got: {resp.status_code}"

    def test_reject_no_updates(self):
        """Test that batch update rejects when updates is empty"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": ["some-fake-id"],
            "updates": {}
        })
        assert resp.status_code == 400, f"Should reject empty updates, got: {resp.status_code}"

    def test_reject_only_none_values(self):
        """Test that batch update rejects when all updates are None"""
        resp = self.session.put(f"{BASE_URL}/api/assets/batch-update", json={
            "asset_ids": ["some-fake-id"],
            "updates": {"brand": None, "location": None}
        })
        assert resp.status_code == 400, f"Should reject all-None updates, got: {resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
