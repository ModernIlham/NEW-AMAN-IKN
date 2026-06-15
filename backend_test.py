#!/usr/bin/env python3
"""
Backend testing for BUGFIX round: thumbnail not updating on cover-only change + audit user 'Unknown' in WS/audit log + mobile FAB scroll

Test scope:
- Part A: Cover-only thumbnail refresh (PATCH with only thumbnail_index)
- Part B: Audit user identity in audit log & WebSocket
- Part C: General smoke tests (POST, Idempotency-Key, WS)
"""

import asyncio
import aiohttp
import json
import base64
import uuid
import time
import websockets
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend URL from frontend/.env
BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"
WS_URL = f"wss://multi-user-stability.preview.emergentagent.com/ws"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "pending_user_lom58sdp@test.com"
ADMIN_PASSWORD = "Test1234"

class BugfixTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.admin_user_id = None
        self.test_activity_id = None
        self.test_assets = []
        self.ws_connection = None
        self.ws_messages = []

    async def setup(self):
        """Initialize session and authenticate"""
        self.session = aiohttp.ClientSession()
        await self.authenticate()
        await self.create_test_activity()

    async def cleanup(self):
        """Clean up resources"""
        if self.ws_connection:
            await self.ws_connection.close()
        if self.session:
            await self.session.close()

    async def authenticate(self):
        """Authenticate as admin user"""
        logger.info("🔐 Authenticating admin user...")
        
        # Try OTP flow to get first admin (bootstrap)
        timestamp = int(time.time())
        
        # Step 1: Request OTP for new user
        otp_request = {
            'username': f'test_admin_{timestamp}',
            'password': 'TestAdmin123',
            'name': 'Test Admin',
            'email': f'test_{timestamp}@test.com'
        }
        
        async with self.session.post(f"{API_URL}/auth/request-otp", json=otp_request) as resp:
            if resp.status == 200:
                logger.info("✅ OTP request successful")
                
                # Get OTP from backend logs (in real scenario, would be from email)
                await asyncio.sleep(1)  # Give time for log to be written
                
                # For testing, we'll try common test OTPs or check if there's a debug mode
                test_otps = ['123456', '000000', 'test123']
                
                for test_otp in test_otps:
                    verify_request = {
                        'email': otp_request['email'],
                        'otp': test_otp
                    }
                    
                    async with self.session.post(f"{API_URL}/auth/verify-otp", json=verify_request) as verify_resp:
                        if verify_resp.status == 200:
                            verify_data = await verify_resp.json()
                            if verify_data.get('access_token'):
                                self.auth_token = verify_data["access_token"]
                                self.admin_user_id = verify_data["user"]["id"]
                                logger.info(f"✅ OTP verification successful with {test_otp}")
                                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                                return
                
                # If OTP verification fails, try to get OTP from logs
                logger.info("⚠️ Standard OTPs failed, checking logs for actual OTP...")
                
                # Read the actual OTP from logs
                import subprocess
                try:
                    log_output = subprocess.check_output(
                        ["tail", "-n", "20", "/var/log/supervisor/backend.err.log"], 
                        text=True
                    )
                    
                    # Look for OTP in logs
                    for line in log_output.split('\n'):
                        if f"OTP email sent to {otp_request['email']}" in line:
                            actual_otp = line.split(': ')[-1].strip()
                            logger.info(f"Found OTP in logs: {actual_otp[:8]}...")
                            
                            verify_request = {
                                'email': otp_request['email'],
                                'otp': actual_otp
                            }
                            
                            async with self.session.post(f"{API_URL}/auth/verify-otp", json=verify_request) as verify_resp:
                                if verify_resp.status == 200:
                                    verify_data = await verify_resp.json()
                                    if verify_data.get('access_token'):
                                        self.auth_token = verify_data["access_token"]
                                        self.admin_user_id = verify_data["user"]["id"]
                                        logger.info("✅ OTP verification successful with actual OTP")
                                        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                                        return
                                    else:
                                        logger.info("⚠️ OTP verification successful but user is inactive (NEW FEATURE)")
                                        break
                            break
                except Exception as e:
                    logger.error(f"Failed to read logs: {e}")
        
        # If all authentication methods fail, we can't proceed with full testing
        # But we can still test some endpoints that don't require authentication
        logger.error("❌ Could not authenticate admin user")
        raise Exception("Authentication failed - cannot proceed with full testing")

    async def create_test_activity(self):
        """Create a test activity for our assets"""
        logger.info("📋 Creating test activity...")
        
        activity_data = {
            "nama_kegiatan": f"BUGFIX Test Activity {int(time.time())}",
            "kode_satker": "123456",
            "nama_satker": "Test Satker",
            "nomor_surat": f"TEST-{int(time.time())}",
            "tanggal_surat": datetime.now().isoformat()[:10]
        }
        
        async with self.session.post(f"{API_URL}/inventory-activities", json=activity_data) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.test_activity_id = data["id"]
                logger.info(f"✅ Test activity created: {self.test_activity_id}")
            else:
                error = await resp.text()
                raise Exception(f"Failed to create test activity: {error}")

    def create_test_image_base64(self, color="red", size=100):
        """Create a simple test image in base64 format"""
        # Create a simple colored square image
        from PIL import Image
        import io
        
        # Create image with different colors for visual distinction
        colors = {
            "red": (255, 0, 0),
            "green": (0, 255, 0), 
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "purple": (255, 0, 255)
        }
        
        img = Image.new('RGB', (size, size), colors.get(color, (255, 0, 0)))
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_bytes = buffer.getvalue()
        
        return f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('ascii')}"

    async def test_part_a_cover_only_thumbnail_refresh(self):
        """Test Part A: Cover-only thumbnail refresh"""
        logger.info("\n🎯 PART A: Testing cover-only thumbnail refresh...")
        
        results = []
        
        # Test A1: Create asset with 3 different photos, then change thumbnail_index only
        logger.info("📸 A1: Testing thumbnail_index change with existing photos...")
        
        # Create 3 visually distinct images
        photo_a = self.create_test_image_base64("red", 100)
        photo_b = self.create_test_image_base64("green", 100)
        photo_c = self.create_test_image_base64("blue", 100)
        
        asset_data = {
            "asset_code": f"TEST-A1-{int(time.time())}",
            "NUP": f"NUP-A1-{int(time.time())}",
            "asset_name": "Test Asset A1 - Three Photos",
            "category": "Laptop",
            "activity_id": self.test_activity_id,
            "photos": [photo_a, photo_b, photo_c],
            "thumbnail_index": 0
        }
        
        # Create asset
        async with self.session.post(f"{API_URL}/assets", json=asset_data) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                self.test_assets.append(asset_id)
                
                # Record initial state
                initial_photo = asset.get("photo")
                initial_thumbnail = asset.get("thumbnail")
                initial_gallery_thumbnail = asset.get("gallery_thumbnail")
                initial_thumbnail_index = asset.get("thumbnail_index")
                
                logger.info(f"✅ Asset created with thumbnail_index={initial_thumbnail_index}")
                logger.info(f"   Initial photo length: {len(initial_photo) if initial_photo else 0}")
                logger.info(f"   Initial thumbnail length: {len(initial_thumbnail) if initial_thumbnail else 0}")
                
                # PATCH with only thumbnail_index (no photos, no photo_ops)
                patch_data = {"thumbnail_index": 2}
                headers = {"If-Match": str(asset["version"])}
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        updated_asset = await patch_resp.json()
                        
                        # Verify changes
                        new_photo = updated_asset.get("photo")
                        new_thumbnail = updated_asset.get("thumbnail")
                        new_gallery_thumbnail = updated_asset.get("gallery_thumbnail")
                        new_thumbnail_index = updated_asset.get("thumbnail_index")
                        
                        # Check thumbnail_index updated
                        if new_thumbnail_index == 2:
                            logger.info("✅ thumbnail_index correctly updated to 2")
                            results.append("A1-index-updated")
                        else:
                            logger.error(f"❌ thumbnail_index not updated: expected 2, got {new_thumbnail_index}")
                        
                        # Check photo changed (should now be photo C)
                        if new_photo and new_photo != initial_photo:
                            logger.info("✅ photo field changed (now shows photo C)")
                            results.append("A1-photo-changed")
                        else:
                            logger.error("❌ photo field not changed")
                        
                        # Check thumbnail regenerated
                        if new_thumbnail and new_thumbnail != initial_thumbnail:
                            logger.info("✅ thumbnail regenerated")
                            results.append("A1-thumbnail-regenerated")
                        else:
                            logger.error("❌ thumbnail not regenerated")
                        
                        # Check gallery_thumbnail regenerated
                        if new_gallery_thumbnail and new_gallery_thumbnail != initial_gallery_thumbnail:
                            logger.info("✅ gallery_thumbnail regenerated")
                            results.append("A1-gallery-thumbnail-regenerated")
                        else:
                            logger.error("❌ gallery_thumbnail not regenerated")
                            
                    else:
                        error = await patch_resp.text()
                        logger.error(f"❌ PATCH failed: {error}")
            else:
                error = await resp.text()
                logger.error(f"❌ Asset creation failed: {error}")
        
        # Test A2: Edge case - asset with no photos
        logger.info("📸 A2: Testing thumbnail_index change with no photos...")
        
        asset_data_no_photos = {
            "asset_code": f"TEST-A2-{int(time.time())}",
            "NUP": f"NUP-A2-{int(time.time())}",
            "asset_name": "Test Asset A2 - No Photos",
            "category": "Laptop",
            "activity_id": self.test_activity_id,
            "photos": []
        }
        
        async with self.session.post(f"{API_URL}/assets", json=asset_data_no_photos) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                self.test_assets.append(asset_id)
                
                # Try to PATCH thumbnail_index on asset with no photos
                patch_data = {"thumbnail_index": 1}
                headers = {"If-Match": str(asset["version"])}
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        updated_asset = await patch_resp.json()
                        
                        # Should coerce to 0 and not crash
                        if updated_asset.get("thumbnail_index") == 0:
                            logger.info("✅ thumbnail_index coerced to 0 for asset with no photos")
                            results.append("A2-no-photos-handled")
                        else:
                            logger.error(f"❌ thumbnail_index not coerced: {updated_asset.get('thumbnail_index')}")
                    else:
                        logger.error(f"❌ PATCH failed on no-photos asset: {await patch_resp.text()}")
        
        # Test A3: Regression - photo_ops path still works
        logger.info("📸 A3: Testing photo_ops regression...")
        
        asset_data_ops = {
            "asset_code": f"TEST-A3-{int(time.time())}",
            "NUP": f"NUP-A3-{int(time.time())}",
            "asset_name": "Test Asset A3 - Photo Ops",
            "category": "Laptop",
            "activity_id": self.test_activity_id,
            "photos": [photo_a, photo_b]
        }
        
        async with self.session.post(f"{API_URL}/assets", json=asset_data_ops) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                self.test_assets.append(asset_id)
                
                # PATCH with photo_ops (reorder and set thumbnail_index)
                patch_data = {
                    "photo_ops": {
                        "keep": [1, 0],  # Reorder: second photo first
                        "add": [],
                        "thumbnail_index": 0
                    }
                }
                headers = {"If-Match": str(asset["version"])}
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        updated_asset = await patch_resp.json()
                        
                        # Check that cover photo matches reordered photos[0]
                        new_photos = updated_asset.get("photos", [])
                        new_photo = updated_asset.get("photo")
                        
                        if len(new_photos) >= 1 and new_photo == new_photos[0]:
                            logger.info("✅ photo_ops regression test passed - cover matches reordered photos[0]")
                            results.append("A3-photo-ops-working")
                        else:
                            logger.error("❌ photo_ops regression failed")
                    else:
                        logger.error(f"❌ photo_ops PATCH failed: {await patch_resp.text()}")
        
        logger.info(f"📊 Part A Results: {len(results)}/6 tests passed")
        return results

    async def test_part_b_audit_user_identity(self):
        """Test Part B: Audit user identity in audit log & WebSocket"""
        logger.info("\n🎯 PART B: Testing audit user identity...")
        
        results = []
        
        # Create a test asset first
        asset_data = {
            "asset_code": f"TEST-B1-{int(time.time())}",
            "NUP": f"NUP-B1-{int(time.time())}",
            "asset_name": "Test Asset B1 - Audit Test",
            "category": "Laptop",
            "activity_id": self.test_activity_id
        }
        
        async with self.session.post(f"{API_URL}/assets", json=asset_data) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                self.test_assets.append(asset_id)
                
                # Test B1: PATCH with audit headers
                logger.info("👤 B1: Testing PATCH with X-Audit-User headers...")
                
                patch_data = {"asset_name": "Updated Asset Name for Audit Test"}
                headers = {
                    "If-Match": str(asset["version"]),
                    "X-Audit-User": "Budi Santoso",
                    "X-Audit-User-Id": "budi-uuid-123"
                }
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        logger.info("✅ PATCH with audit headers successful")
                        
                        # Check audit logs
                        await asyncio.sleep(1)  # Give time for audit log to be written
                        
                        async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp:
                            if audit_resp.status == 200:
                                audit_data = await audit_resp.json()
                                logs = audit_data.get("logs", [])
                                
                                # Find the most recent update log
                                update_log = None
                                for log in logs:
                                    if log.get("action") == "update" and log.get("asset_id") == asset_id:
                                        update_log = log
                                        break
                                
                                if update_log and update_log.get("username") == "Budi Santoso":
                                    logger.info("✅ Audit log shows correct username: Budi Santoso")
                                    results.append("B1-audit-log-username")
                                else:
                                    logger.error(f"❌ Audit log username incorrect: {update_log.get('username') if update_log else 'No log found'}")
                            else:
                                logger.error(f"❌ Failed to get audit logs: {await audit_resp.text()}")
                    else:
                        logger.error(f"❌ PATCH with audit headers failed: {await patch_resp.text()}")
                
                # Test B2: WebSocket broadcast with audit user
                logger.info("🔌 B2: Testing WebSocket broadcast with audit user...")
                
                try:
                    # Connect to WebSocket
                    ws_uri = f"{WS_URL}?token={self.auth_token}&activity_id={self.test_activity_id}"
                    self.ws_connection = await websockets.connect(ws_uri)
                    logger.info("✅ WebSocket connected")
                    
                    # Start listening for messages
                    async def listen_for_messages():
                        try:
                            async for message in self.ws_connection:
                                data = json.loads(message)
                                self.ws_messages.append(data)
                                logger.info(f"📨 WS Message: {data.get('type', 'unknown')}")
                        except websockets.exceptions.ConnectionClosed:
                            pass
                    
                    # Start listening in background
                    listen_task = asyncio.create_task(listen_for_messages())
                    
                    # Wait a moment for connection to stabilize
                    await asyncio.sleep(1)
                    
                    # Perform another PATCH to trigger WebSocket event
                    patch_data = {"notes": f"WebSocket test update {int(time.time())}"}
                    headers = {
                        "If-Match": str(asset["version"] + 1),  # Incremented from previous PATCH
                        "X-Audit-User": "Budi Santoso",
                        "X-Audit-User-Id": "budi-uuid-123"
                    }
                    
                    async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                                json=patch_data, headers=headers) as patch_resp:
                        if patch_resp.status == 200:
                            logger.info("✅ Second PATCH successful")
                            
                            # Wait for WebSocket message
                            await asyncio.sleep(2)
                            
                            # Check for asset_updated message with correct user
                            asset_updated_msg = None
                            for msg in self.ws_messages:
                                if msg.get("type") == "asset_updated" and msg.get("data", {}).get("id") == asset_id:
                                    asset_updated_msg = msg
                                    break
                            
                            if asset_updated_msg and asset_updated_msg.get("user") == "Budi Santoso":
                                logger.info("✅ WebSocket asset_updated message contains correct user: Budi Santoso")
                                results.append("B2-websocket-user")
                            else:
                                logger.error(f"❌ WebSocket message user incorrect: {asset_updated_msg.get('user') if asset_updated_msg else 'No message found'}")
                        else:
                            logger.error(f"❌ Second PATCH failed: {await patch_resp.text()}")
                    
                    # Cancel listening task
                    listen_task.cancel()
                    
                except Exception as e:
                    logger.error(f"❌ WebSocket test failed: {e}")
                
                # Test B3: Regression - PATCH without audit headers
                logger.info("👤 B3: Testing PATCH without X-Audit-User headers...")
                
                patch_data = {"notes": "Test without audit headers"}
                headers = {"If-Match": str(asset["version"] + 2)}  # No audit headers
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        logger.info("✅ PATCH without audit headers successful")
                        
                        # Check audit logs show "unknown"
                        await asyncio.sleep(1)
                        
                        async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp:
                            if audit_resp.status == 200:
                                audit_data = await audit_resp.json()
                                logs = audit_data.get("logs", [])
                                
                                # Find the most recent log (should be "unknown")
                                if logs and logs[0].get("username") in ["unknown", ""]:
                                    logger.info("✅ Audit log without headers shows 'unknown' username")
                                    results.append("B3-no-headers-unknown")
                                else:
                                    logger.error(f"❌ Audit log without headers incorrect: {logs[0].get('username') if logs else 'No logs'}")
                            else:
                                logger.error(f"❌ Failed to get audit logs: {await audit_resp.text()}")
                    else:
                        logger.error(f"❌ PATCH without audit headers failed: {await patch_resp.text()}")
                
                # Test B4: Regression - OCC still enforced
                logger.info("🔒 B4: Testing OCC regression...")
                
                # Try PATCH with stale If-Match
                patch_data = {"notes": "Should fail with stale version"}
                headers = {
                    "If-Match": "1",  # Stale version
                    "X-Audit-User": "Test User"
                }
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 409:
                        logger.info("✅ OCC regression test passed - stale If-Match rejected with 409")
                        results.append("B4-occ-working")
                    else:
                        logger.error(f"❌ OCC regression failed - expected 409, got {patch_resp.status}")
        
        logger.info(f"📊 Part B Results: {len(results)}/4 tests passed")
        return results

    async def test_part_c_general_smoke(self):
        """Test Part C: General smoke tests"""
        logger.info("\n🎯 PART C: Testing general smoke tests...")
        
        results = []
        
        # Test C1: POST /api/assets with audit headers
        logger.info("📝 C1: Testing POST /api/assets with audit headers...")
        
        asset_data = {
            "asset_code": f"TEST-C1-{int(time.time())}",
            "NUP": f"NUP-C1-{int(time.time())}",
            "asset_name": "Test Asset C1 - POST with Audit",
            "category": "Laptop",
            "activity_id": self.test_activity_id
        }
        
        headers = {
            "X-Audit-User": "Create Test User",
            "X-Audit-User-Id": "create-test-123"
        }
        
        async with self.session.post(f"{API_URL}/assets", json=asset_data, headers=headers) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                self.test_assets.append(asset_id)
                logger.info("✅ POST /api/assets with audit headers successful")
                results.append("C1-post-with-audit")
                
                # Check audit log
                await asyncio.sleep(1)
                async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp:
                    if audit_resp.status == 200:
                        audit_data = await audit_resp.json()
                        logs = audit_data.get("logs", [])
                        
                        if logs and logs[0].get("username") == "Create Test User":
                            logger.info("✅ POST audit log shows correct username")
                            results.append("C1-post-audit-log")
            else:
                logger.error(f"❌ POST with audit headers failed: {await resp.text()}")
        
        # Test C2: Idempotency-Key functionality
        logger.info("🔑 C2: Testing Idempotency-Key functionality...")
        
        idempotency_key = f"test-key-{uuid.uuid4()}"
        asset_data = {
            "asset_code": f"TEST-C2-{int(time.time())}",
            "NUP": f"NUP-C2-{int(time.time())}",
            "asset_name": "Test Asset C2 - Idempotency",
            "category": "Laptop",
            "activity_id": self.test_activity_id
        }
        
        headers = {"Idempotency-Key": idempotency_key}
        
        # First request
        async with self.session.post(f"{API_URL}/assets", json=asset_data, headers=headers) as resp:
            if resp.status == 200:
                first_asset = await resp.json()
                first_asset_id = first_asset["id"]
                self.test_assets.append(first_asset_id)
                
                # Second request with same key
                async with self.session.post(f"{API_URL}/assets", json=asset_data, headers=headers) as resp2:
                    if resp2.status == 200:
                        second_asset = await resp2.json()
                        
                        if first_asset_id == second_asset["id"]:
                            logger.info("✅ Idempotency-Key working - same asset ID returned")
                            results.append("C2-idempotency-working")
                        else:
                            logger.error("❌ Idempotency-Key failed - different asset IDs")
                    else:
                        logger.error(f"❌ Second idempotent request failed: {await resp2.text()}")
            else:
                logger.error(f"❌ First idempotent request failed: {await resp.text()}")
        
        # Test C3: WebSocket asset_updated fires on PATCH
        logger.info("🔌 C3: Testing WebSocket asset_updated on PATCH...")
        
        if self.test_assets:
            test_asset_id = self.test_assets[0]
            
            # Get current asset version
            async with self.session.get(f"{API_URL}/assets/{test_asset_id}") as resp:
                if resp.status == 200:
                    asset = await resp.json()
                    
                    # Clear previous WS messages
                    self.ws_messages.clear()
                    
                    # Perform PATCH
                    patch_data = {"notes": f"WebSocket test {int(time.time())}"}
                    headers = {"If-Match": str(asset["version"])}
                    
                    async with self.session.patch(f"{API_URL}/assets/{test_asset_id}", 
                                                json=patch_data, headers=headers) as patch_resp:
                        if patch_resp.status == 200:
                            # Wait for WebSocket message
                            await asyncio.sleep(2)
                            
                            # Check for asset_updated message
                            asset_updated_found = any(
                                msg.get("type") == "asset_updated" and 
                                msg.get("data", {}).get("id") == test_asset_id
                                for msg in self.ws_messages
                            )
                            
                            if asset_updated_found:
                                logger.info("✅ WebSocket asset_updated fired on PATCH")
                                results.append("C3-websocket-updated")
                            else:
                                logger.error("❌ WebSocket asset_updated not received")
                        else:
                            logger.error(f"❌ PATCH for WebSocket test failed: {await patch_resp.text()}")
        
        logger.info(f"📊 Part C Results: {len(results)}/4 tests passed")
        return results

    async def run_all_tests(self):
        """Run all bugfix tests"""
        logger.info("🚀 Starting BUGFIX round backend testing...")
        
        try:
            await self.setup()
            
            # Run all test parts
            part_a_results = await self.test_part_a_cover_only_thumbnail_refresh()
            part_b_results = await self.test_part_b_audit_user_identity()
            part_c_results = await self.test_part_c_general_smoke()
            
            # Summary
            total_tests = 6 + 4 + 4  # Part A + Part B + Part C
            total_passed = len(part_a_results) + len(part_b_results) + len(part_c_results)
            
            logger.info(f"\n📊 FINAL RESULTS:")
            logger.info(f"Part A (Cover-only thumbnail): {len(part_a_results)}/6 tests passed")
            logger.info(f"Part B (Audit user identity): {len(part_b_results)}/4 tests passed")
            logger.info(f"Part C (General smoke): {len(part_c_results)}/4 tests passed")
            logger.info(f"TOTAL: {total_passed}/{total_tests} tests passed ({total_passed/total_tests*100:.1f}%)")
            
            # Detailed results
            all_results = part_a_results + part_b_results + part_c_results
            logger.info(f"\nPassed tests: {all_results}")
            
            return {
                "total_tests": total_tests,
                "total_passed": total_passed,
                "part_a": part_a_results,
                "part_b": part_b_results,
                "part_c": part_c_results,
                "success_rate": total_passed/total_tests
            }
            
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            raise
        finally:
            await self.cleanup()

async def main():
    """Main test execution"""
    tester = BugfixTester()
    results = await tester.run_all_tests()
    
    # Return results for test_result.md update
    return results

if __name__ == "__main__":
    # Install required packages if not available
    try:
        import aiohttp
        import websockets
        from PIL import Image
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Installing required packages...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp", "websockets", "Pillow"])
        import aiohttp
        import websockets
        from PIL import Image
    
    asyncio.run(main())