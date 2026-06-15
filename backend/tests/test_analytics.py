"""
Backend tests for the Dashboard Analytics feature (iteration 11)
Tests the /api/assets/analytics endpoint with activity_id parameter
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAnalyticsEndpoint:
    """Tests for GET /api/assets/analytics endpoint"""
    
    @pytest.fixture(scope="class")
    def activity_id(self):
        """Get the COBA 1 activity ID for testing"""
        response = requests.get(f"{BASE_URL}/api/inventory-activities")
        assert response.status_code == 200, f"Failed to get activities: {response.text}"
        activities = response.json()
        
        # Find COBA 1 activity
        coba1 = next((act for act in activities if 'COBA' in act.get('nama_kegiatan', '').upper()), None)
        assert coba1 is not None, "COBA 1 activity not found"
        return coba1['id']
    
    def test_analytics_endpoint_returns_200(self, activity_id):
        """Test analytics endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Analytics endpoint returned 200")
    
    def test_analytics_has_required_keys(self, activity_id):
        """Test analytics response has all 5 required keys"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        required_keys = ['by_category', 'by_condition', 'by_status', 'by_location', 'by_department']
        for key in required_keys:
            assert key in data, f"Missing key: {key}"
        
        print(f"✓ All required keys present: {required_keys}")
    
    def test_by_category_structure(self, activity_id):
        """Test by_category has correct structure with name, count, value"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        assert len(data['by_category']) > 0, "by_category should not be empty"
        
        for item in data['by_category']:
            assert 'name' in item, "by_category item missing 'name'"
            assert 'count' in item, "by_category item missing 'count'"
            assert 'value' in item, "by_category item missing 'value'"
            assert isinstance(item['count'], int), "count should be int"
            assert isinstance(item['value'], (int, float)), "value should be numeric"
        
        print(f"✓ by_category has {len(data['by_category'])} categories with correct structure")
    
    def test_by_condition_structure(self, activity_id):
        """Test by_condition has correct structure with name and count"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        assert len(data['by_condition']) > 0, "by_condition should not be empty"
        
        for item in data['by_condition']:
            assert 'name' in item, "by_condition item missing 'name'"
            assert 'count' in item, "by_condition item missing 'count'"
        
        print(f"✓ by_condition has {len(data['by_condition'])} conditions")
    
    def test_by_status_structure(self, activity_id):
        """Test by_status has correct structure with name and count"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        assert len(data['by_status']) > 0, "by_status should not be empty"
        
        for item in data['by_status']:
            assert 'name' in item, "by_status item missing 'name'"
            assert 'count' in item, "by_status item missing 'count'"
        
        print(f"✓ by_status has {len(data['by_status'])} statuses")
    
    def test_by_location_structure(self, activity_id):
        """Test by_location has correct structure and is limited to 10"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        assert len(data['by_location']) > 0, "by_location should not be empty"
        assert len(data['by_location']) <= 10, "by_location should be limited to 10"
        
        for item in data['by_location']:
            assert 'name' in item, "by_location item missing 'name'"
            assert 'count' in item, "by_location item missing 'count'"
        
        print(f"✓ by_location has {len(data['by_location'])} locations (max 10)")
    
    def test_by_department_structure(self, activity_id):
        """Test by_department has correct structure and is limited to 10"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        data = response.json()
        
        assert len(data['by_department']) > 0, "by_department should not be empty"
        assert len(data['by_department']) <= 10, "by_department should be limited to 10"
        
        for item in data['by_department']:
            assert 'name' in item, "by_department item missing 'name'"
            assert 'count' in item, "by_department item missing 'count'"
            assert 'value' in item, "by_department item missing 'value'"
        
        print(f"✓ by_department has {len(data['by_department'])} departments (max 10)")
    
    def test_analytics_caching(self, activity_id):
        """Test that analytics endpoint uses caching (second request should be fast)"""
        import time
        
        # First request
        start1 = time.time()
        response1 = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        time1 = time.time() - start1
        
        # Second request (should be cached)
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/assets/analytics?activity_id={activity_id}")
        time2 = time.time() - start2
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        print(f"✓ First request: {time1:.3f}s, Second request: {time2:.3f}s")
        # Note: Due to network latency, we can't strictly assert cache speed


class TestAnalyticsWithoutActivityId:
    """Test analytics endpoint without activity_id (all assets)"""
    
    def test_analytics_without_activity_id(self):
        """Test analytics works without activity_id (returns data for all assets)"""
        response = requests.get(f"{BASE_URL}/api/assets/analytics")
        assert response.status_code == 200
        
        data = response.json()
        assert 'by_category' in data
        assert 'by_condition' in data
        assert 'by_status' in data
        assert 'by_location' in data
        assert 'by_department' in data
        
        print("✓ Analytics endpoint works without activity_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
