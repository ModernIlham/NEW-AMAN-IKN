"""
Test Audit Log Feature (Riwayat Perubahan)
Tests for:
- POST /api/assets creates audit entry
- PUT /api/assets/{id} creates audit entry with change tracking
- DELETE /api/assets/{id} creates audit entry
- GET /api/audit-logs?activity_id=xxx returns filtered logs
- GET /api/audit-logs?asset_id=xxx returns per-asset logs
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuditLogs:
    """Test audit log functionality"""
    
    # Store test data for cleanup
    test_asset_id = None
    test_asset_code = None
    test_activity_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        # Get a valid activity_id by listing inventory activities
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200, f"Failed to get activities: {response.text}"
        activities = response.json()
        assert len(activities) > 0, "No activities found - need at least one activity"
        # Use COBA 1 activity
        for act in activities:
            if "COBA 1" in act.get("nama_kegiatan", ""):
                TestAuditLogs.test_activity_id = act["id"]
                break
        if not TestAuditLogs.test_activity_id:
            TestAuditLogs.test_activity_id = activities[0]["id"]
        yield
    
    def test_01_create_asset_creates_audit_entry(self):
        """POST /api/assets creates audit entry - create an asset with X-Audit-User header"""
        # Create a unique asset code
        timestamp = int(time.time())
        asset_code = f"TEST-AUDIT-{timestamp}"
        TestAuditLogs.test_asset_code = asset_code
        
        payload = {
            "asset_code": asset_code,
            "NUP": "001",
            "asset_name": "Test Asset for Audit Log",
            "category": "Peralatan dan Mesin",
            "activity_id": TestAuditLogs.test_activity_id
        }
        
        headers = {"X-Audit-User": "testuser"}
        response = requests.post(f"{BASE_URL}/api/assets", json=payload, headers=headers)
        
        assert response.status_code == 200, f"Failed to create asset: {response.text}"
        data = response.json()
        TestAuditLogs.test_asset_id = data.get("id")
        assert TestAuditLogs.test_asset_id, "Asset ID not returned"
        print(f"✓ Asset created: {asset_code}, ID: {TestAuditLogs.test_asset_id}")
        
    def test_02_verify_create_audit_entry(self):
        """Verify GET /api/audit-logs returns the create entry"""
        # Small delay to ensure audit log is written
        time.sleep(0.5)
        
        # Check audit logs for the activity
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": TestAuditLogs.test_activity_id, "page_size": 50}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        
        assert "logs" in data, "Response missing 'logs' key"
        assert "total" in data, "Response missing 'total' key"
        
        logs = data["logs"]
        # Find our create entry
        create_entries = [l for l in logs if l.get("action") == "create" and l.get("asset_code") == TestAuditLogs.test_asset_code]
        assert len(create_entries) > 0, f"No create audit entry found for asset {TestAuditLogs.test_asset_code}"
        
        entry = create_entries[0]
        assert entry.get("username") == "testuser", f"Wrong username: {entry.get('username')}"
        assert entry.get("asset_id") == TestAuditLogs.test_asset_id, "Wrong asset_id"
        print(f"✓ Create audit entry verified: {entry}")
        
    def test_03_update_asset_creates_audit_entry_with_changes(self):
        """PUT /api/assets/{id} creates audit entry with change tracking"""
        # First get the current asset data
        response = requests.get(f"{BASE_URL}/api/assets/{TestAuditLogs.test_asset_id}")
        assert response.status_code == 200, f"Failed to get asset: {response.text}"
        current_data = response.json()
        
        # Update the asset with changes
        updated_data = {
            "asset_code": current_data["asset_code"],
            "NUP": current_data["NUP"],
            "asset_name": "Updated Asset Name for Audit",
            "category": current_data["category"],
            "location": "Test Location",
            "department": "Test Department",
            "activity_id": TestAuditLogs.test_activity_id
        }
        
        headers = {"X-Audit-User": "testuser_update"}
        response = requests.put(
            f"{BASE_URL}/api/assets/{TestAuditLogs.test_asset_id}",
            json=updated_data,
            headers=headers
        )
        assert response.status_code == 200, f"Failed to update asset: {response.text}"
        print("✓ Asset updated with new name, location, department")
        
    def test_04_verify_update_audit_entry_with_changes(self):
        """Verify update audit entry shows what fields changed"""
        time.sleep(0.5)
        
        # Check audit logs for the activity
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": TestAuditLogs.test_activity_id, "page_size": 50}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        
        logs = data["logs"]
        # Find update entries for our asset
        update_entries = [l for l in logs if l.get("action") == "update" and l.get("asset_id") == TestAuditLogs.test_asset_id]
        assert len(update_entries) > 0, f"No update audit entry found for asset {TestAuditLogs.test_asset_id}"
        
        entry = update_entries[0]
        assert entry.get("username") == "testuser_update", f"Wrong username: {entry.get('username')}"
        
        # Verify changes array shows what changed
        changes = entry.get("changes", [])
        assert len(changes) > 0, "No changes recorded in audit entry"
        
        # Check that we have the expected changed fields
        changed_fields = [c["field"] for c in changes]
        assert "asset_name" in changed_fields, "asset_name change not tracked"
        assert "location" in changed_fields, "location change not tracked"
        assert "department" in changed_fields, "department change not tracked"
        
        # Verify the change format
        name_change = next(c for c in changes if c["field"] == "asset_name")
        assert name_change["from"] == "Test Asset for Audit Log", f"Wrong 'from' value: {name_change['from']}"
        assert name_change["to"] == "Updated Asset Name for Audit", f"Wrong 'to' value: {name_change['to']}"
        
        print(f"✓ Update audit entry verified with changes: {changes}")
        
    def test_05_filter_audit_logs_by_asset_id(self):
        """GET /api/audit-logs?asset_id=xxx returns per-asset logs"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"asset_id": TestAuditLogs.test_asset_id}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        
        logs = data["logs"]
        # All logs should be for our asset
        for log in logs:
            assert log.get("asset_id") == TestAuditLogs.test_asset_id, f"Log has wrong asset_id: {log}"
        
        # Should have at least create and update entries
        actions = [l["action"] for l in logs]
        assert "create" in actions, "Missing create entry"
        assert "update" in actions, "Missing update entry"
        
        print(f"✓ Asset-filtered audit logs verified: {len(logs)} entries")
        
    def test_06_delete_asset_creates_audit_entry(self):
        """DELETE /api/assets/{id} creates audit entry"""
        headers = {"X-Audit-User": "testuser_delete"}
        response = requests.delete(
            f"{BASE_URL}/api/assets/{TestAuditLogs.test_asset_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Failed to delete asset: {response.text}"
        print("✓ Asset deleted")
        
    def test_07_verify_delete_audit_entry(self):
        """Verify delete audit entry was created"""
        time.sleep(0.5)
        
        # Check audit logs for the activity
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": TestAuditLogs.test_activity_id, "page_size": 50}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        
        logs = data["logs"]
        # Find delete entries for our asset
        delete_entries = [l for l in logs if l.get("action") == "delete" and l.get("asset_code") == TestAuditLogs.test_asset_code]
        assert len(delete_entries) > 0, f"No delete audit entry found for asset {TestAuditLogs.test_asset_code}"
        
        entry = delete_entries[0]
        assert entry.get("username") == "testuser_delete", f"Wrong username: {entry.get('username')}"
        print(f"✓ Delete audit entry verified: {entry}")
        
    def test_08_audit_log_pagination(self):
        """Test audit log pagination"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": TestAuditLogs.test_activity_id, "page": 1, "page_size": 10}
        )
        assert response.status_code == 200, f"Failed to get audit logs: {response.text}"
        data = response.json()
        
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        
        assert data["page"] == 1
        assert data["page_size"] == 10
        
        print(f"✓ Audit log pagination verified: total={data['total']}, total_pages={data['total_pages']}")


class TestAuditLogRegressionAndEdgeCases:
    """Additional tests for audit log edge cases"""
    
    def test_audit_logs_empty_filters(self):
        """GET /api/audit-logs with no filters returns all logs"""
        response = requests.get(f"{BASE_URL}/api/audit-logs")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "logs" in data
        assert "total" in data
        print(f"✓ Audit logs without filters: {data['total']} total entries")
        
    def test_audit_logs_nonexistent_activity(self):
        """GET /api/audit-logs?activity_id=nonexistent returns empty"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            params={"activity_id": "nonexistent-id-12345"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["logs"] == []
        assert data["total"] == 0
        print("✓ Nonexistent activity returns empty logs")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
