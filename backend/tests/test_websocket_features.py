"""
Test WebSocket features for real-time notifications
Features tested:
1. WebSocket connection and online_users message on connect
2. Ping/pong heartbeat
3. Multi-user connection with online user count
4. Disconnect updates for remaining users
5. Asset CRUD triggers real-time notifications
"""
import pytest
import asyncio
import json
import websockets
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://asset-crud-auth.preview.emergentagent.com').rstrip('/')
WS_URL = BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://')

# Test data
TEST_ACTIVITY_ID = "test-ws-activity-123"
TEST_USER_1 = {"user_id": "user1", "user_name": "User One"}
TEST_USER_2 = {"user_id": "user2", "user_name": "User Two"}

class TestWebSocketConnection:
    """Test WebSocket basic connection"""
    
    @pytest.mark.asyncio
    async def test_ws_connect_receives_online_users(self):
        """Feature 1: Connect to WebSocket and receive online_users message"""
        ws_endpoint = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_1['user_id']}&user_name={TEST_USER_1['user_name']}"
        
        try:
            async with websockets.connect(ws_endpoint, close_timeout=5) as ws:
                # Should receive online_users message on connect
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                
                assert data["type"] == "online_users", f"Expected type 'online_users', got '{data.get('type')}'"
                assert "users" in data, "Response should contain 'users' field"
                assert "count" in data, "Response should contain 'count' field"
                assert data["count"] >= 1, "Count should be at least 1 (the connected user)"
                
                print(f"✅ Feature 1 PASSED: Connected and received online_users: {data}")
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")


class TestWebSocketPingPong:
    """Test ping/pong heartbeat"""
    
    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Feature 2: Send ping, receive pong"""
        ws_endpoint = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_1['user_id']}&user_name={TEST_USER_1['user_name']}"
        
        try:
            async with websockets.connect(ws_endpoint, close_timeout=5) as ws:
                # First message is online_users
                initial_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                initial_data = json.loads(initial_msg)
                assert initial_data["type"] == "online_users"
                
                # Send ping
                await ws.send(json.dumps({"type": "ping"}))
                
                # Should receive pong
                pong_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                pong_data = json.loads(pong_msg)
                
                assert pong_data["type"] == "pong", f"Expected 'pong', got '{pong_data.get('type')}'"
                
                print(f"✅ Feature 2 PASSED: Sent ping, received pong: {pong_data}")
        except Exception as e:
            pytest.fail(f"Ping/pong test failed: {e}")


class TestMultiUserConnection:
    """Test multi-user WebSocket scenarios"""
    
    @pytest.mark.asyncio
    async def test_multi_user_connection(self):
        """Feature 3: Connect 2 users, verify both receive online_users with count=2"""
        ws_endpoint_1 = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_1['user_id']}&user_name={TEST_USER_1['user_name']}"
        ws_endpoint_2 = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_2['user_id']}&user_name={TEST_USER_2['user_name']}"
        
        try:
            async with websockets.connect(ws_endpoint_1, close_timeout=5) as ws1:
                # User 1 connects, receives online_users
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                data1 = json.loads(msg1)
                assert data1["type"] == "online_users"
                initial_count = data1["count"]
                print(f"User 1 connected, initial count: {initial_count}")
                
                async with websockets.connect(ws_endpoint_2, close_timeout=5) as ws2:
                    # User 2 connects
                    msg2 = await asyncio.wait_for(ws2.recv(), timeout=5.0)
                    data2 = json.loads(msg2)
                    assert data2["type"] == "online_users"
                    
                    # User 1 should also receive updated online_users
                    msg1_update = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                    data1_update = json.loads(msg1_update)
                    
                    # Both should have count >= 2 (could be more if other tests running)
                    assert data2["count"] >= 2, f"User 2 count should be >= 2, got {data2['count']}"
                    assert data1_update["count"] >= 2, f"User 1 updated count should be >= 2, got {data1_update['count']}"
                    
                    print(f"✅ Feature 3 PASSED: Multi-user connection works. User 1 count: {data1_update['count']}, User 2 count: {data2['count']}")
        except Exception as e:
            pytest.fail(f"Multi-user connection test failed: {e}")

    @pytest.mark.asyncio
    async def test_disconnect_updates_remaining_users(self):
        """Feature 4: Disconnect one user, remaining user gets updated online_users with reduced count"""
        ws_endpoint_1 = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_1['user_id']}&user_name={TEST_USER_1['user_name']}"
        ws_endpoint_2 = f"{WS_URL}/api/ws/{TEST_ACTIVITY_ID}?user_id={TEST_USER_2['user_id']}&user_name={TEST_USER_2['user_name']}"
        
        try:
            async with websockets.connect(ws_endpoint_1, close_timeout=5) as ws1:
                # User 1 connects
                await asyncio.wait_for(ws1.recv(), timeout=5.0)
                
                # User 2 connects
                ws2 = await websockets.connect(ws_endpoint_2, close_timeout=5)
                await asyncio.wait_for(ws2.recv(), timeout=5.0)  # User 2 initial
                
                # User 1 receives update about User 2
                msg_user2_joined = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                count_with_both = json.loads(msg_user2_joined)["count"]
                print(f"Count with both users: {count_with_both}")
                
                # User 2 disconnects
                await ws2.close()
                
                # User 1 should receive updated count (reduced by 1)
                msg_user2_left = await asyncio.wait_for(ws1.recv(), timeout=5.0)
                data_after_disconnect = json.loads(msg_user2_left)
                
                assert data_after_disconnect["type"] == "online_users"
                assert data_after_disconnect["count"] < count_with_both, "Count should decrease after disconnect"
                
                print(f"✅ Feature 4 PASSED: After user 2 disconnect, count reduced from {count_with_both} to {data_after_disconnect['count']}")
        except Exception as e:
            pytest.fail(f"Disconnect test failed: {e}")


class TestAssetChangeNotifications:
    """Test asset CRUD triggers real-time notifications"""
    
    def test_asset_crud_notification_flow(self):
        """Feature 5: Asset CRUD should be integrated with notify_asset_change in backend code"""
        # This is a code verification test - we verify the code structure
        # The actual notification is async and requires WebSocket listeners
        
        
        assets_path = "/app/backend/routes/assets.py"
        
        with open(assets_path, 'r') as f:
            content = f.read()
        
        # Check that notify_asset_change is imported
        assert "from routes.websocket import notify_asset_change" in content, \
            "notify_asset_change should be imported in assets.py"
        
        # Check that notify_asset_change is called in create, update, delete
        assert 'await notify_asset_change(asset.activity_id, "asset_created"' in content, \
            "create_asset should call notify_asset_change with 'asset_created'"
        
        assert 'await notify_asset_change(asset.activity_id, "asset_updated"' in content, \
            "update_asset should call notify_asset_change with 'asset_updated'"
        
        assert 'await notify_asset_change(asset_doc.get("activity_id", ""), "asset_deleted"' in content, \
            "delete_asset should call notify_asset_change with 'asset_deleted'"
        
        print("✅ Feature 5 PASSED: Asset CRUD routes correctly call notify_asset_change for real-time updates")


class TestWebSocketRouteConfiguration:
    """Verify WebSocket route is properly configured in server.py"""
    
    def test_ws_router_registered(self):
        """Verify ws_router is included in api_router"""
        server_path = "/app/backend/server.py"
        
        with open(server_path, 'r') as f:
            content = f.read()
        
        assert "from routes.websocket import ws_router" in content, \
            "ws_router should be imported from routes.websocket"
        
        assert "api_router.include_router(ws_router)" in content, \
            "ws_router should be included in api_router"
        
        print("✅ WebSocket router correctly registered in server.py")


class TestConnectionManager:
    """Verify ConnectionManager implementation"""
    
    def test_connection_manager_structure(self):
        """Verify ConnectionManager class has required methods"""
        ws_path = "/app/backend/routes/websocket.py"
        
        with open(ws_path, 'r') as f:
            content = f.read()
        
        required_methods = [
            "async def connect(",
            "def disconnect(",
            "def get_online_users(",
            "async def broadcast_online_users(",
            "async def broadcast("
        ]
        
        for method in required_methods:
            assert method in content, f"ConnectionManager should have method: {method}"
        
        # Verify notify_asset_change function exists
        assert "async def notify_asset_change(" in content, \
            "notify_asset_change function should exist"
        
        print("✅ ConnectionManager has all required methods")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
