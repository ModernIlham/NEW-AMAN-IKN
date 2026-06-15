#!/usr/bin/env python3
"""
Targeted BUGFIX testing - since PATCH works without auth, we can test the actual bugfix functionality
"""

import asyncio
import aiohttp
import json
import base64
import time
import logging
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend URL
BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

class TargetedBugfixTester:
    def __init__(self):
        self.session = None
        self.test_activity_id = None

    async def setup(self):
        """Initialize session"""
        self.session = aiohttp.ClientSession()
        await self.get_test_activity()

    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()

    async def get_test_activity(self):
        """Get an existing activity for testing"""
        # Get existing assets to find an activity_id
        async with self.session.get(f"{API_URL}/assets?page_size=1") as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("items", [])
                if assets:
                    self.test_activity_id = assets[0].get("activity_id")
                    logger.info(f"Using existing activity: {self.test_activity_id}")

    def create_test_image_base64(self, color="red", size=100):
        """Create a simple test image in base64 format"""
        colors = {
            "red": (255, 0, 0),
            "green": (0, 255, 0), 
            "blue": (0, 0, 255),
        }
        
        img = Image.new('RGB', (size, size), colors.get(color, (255, 0, 0)))
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_bytes = buffer.getvalue()
        
        return f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('ascii')}"

    async def test_part_a_thumbnail_bugfix(self):
        """Test Part A: thumbnail_index only PATCH (the main bugfix)"""
        logger.info("\n🎯 PART A: Testing thumbnail_index only PATCH...")
        
        results = []
        
        if not self.test_activity_id:
            logger.error("❌ No activity ID available for testing")
            return results

        # Create asset with multiple photos
        photo_a = self.create_test_image_base64("red", 100)
        photo_b = self.create_test_image_base64("green", 100)
        photo_c = self.create_test_image_base64("blue", 100)
        
        asset_data = {
            "asset_code": f"BUGFIX-A1-{int(time.time())}",
            "NUP": f"NUP-A1-{int(time.time())}",
            "asset_name": "Bugfix Test Asset - Thumbnail",
            "category": "Test Category",
            "activity_id": self.test_activity_id,
            "photos": [photo_a, photo_b, photo_c],
            "thumbnail_index": 0
        }
        
        # Create asset
        async with self.session.post(f"{API_URL}/assets", json=asset_data) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                
                logger.info(f"✅ Created test asset: {asset_id}")
                
                # Record initial state
                initial_photo = asset.get("photo")
                initial_thumbnail = asset.get("thumbnail")
                initial_gallery_thumbnail = asset.get("gallery_thumbnail")
                initial_thumbnail_index = asset.get("thumbnail_index", 0)
                
                logger.info(f"Initial state:")
                logger.info(f"  thumbnail_index: {initial_thumbnail_index}")
                logger.info(f"  photo length: {len(initial_photo) if initial_photo else 0}")
                logger.info(f"  thumbnail length: {len(initial_thumbnail) if initial_thumbnail else 0}")
                logger.info(f"  gallery_thumbnail length: {len(initial_gallery_thumbnail) if initial_gallery_thumbnail else 0}")
                
                # Test 1: PATCH with only thumbnail_index (no photos, no photo_ops)
                logger.info("\n📸 Test 1: PATCH with only thumbnail_index=2...")
                
                patch_data = {"thumbnail_index": 2}
                headers = {"If-Match": str(asset.get("version", 1))}
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=headers) as patch_resp:
                    if patch_resp.status == 200:
                        updated_asset = await patch_resp.json()
                        
                        # Check changes
                        new_photo = updated_asset.get("photo")
                        new_thumbnail = updated_asset.get("thumbnail")
                        new_gallery_thumbnail = updated_asset.get("gallery_thumbnail")
                        new_thumbnail_index = updated_asset.get("thumbnail_index")
                        
                        logger.info(f"After PATCH:")
                        logger.info(f"  thumbnail_index: {new_thumbnail_index}")
                        logger.info(f"  photo length: {len(new_photo) if new_photo else 0}")
                        logger.info(f"  thumbnail length: {len(new_thumbnail) if new_thumbnail else 0}")
                        logger.info(f"  gallery_thumbnail length: {len(new_gallery_thumbnail) if new_gallery_thumbnail else 0}")
                        
                        # Verify thumbnail_index updated
                        if new_thumbnail_index == 2:
                            logger.info("✅ thumbnail_index correctly updated to 2")
                            results.append("A1-thumbnail-index-updated")
                        else:
                            logger.error(f"❌ thumbnail_index not updated: expected 2, got {new_thumbnail_index}")
                        
                        # Verify photo changed (should now be photo C - index 2)
                        if new_photo and new_photo != initial_photo:
                            logger.info("✅ photo field changed (now shows different photo)")
                            results.append("A1-photo-changed")
                            
                            # Check if it's actually photo C (blue)
                            if new_photo == photo_c:
                                logger.info("✅ photo field correctly shows photo C (blue)")
                                results.append("A1-photo-correct")
                        else:
                            logger.error("❌ photo field not changed")
                        
                        # Verify thumbnail regenerated
                        if new_thumbnail and new_thumbnail != initial_thumbnail:
                            logger.info("✅ thumbnail regenerated")
                            results.append("A1-thumbnail-regenerated")
                        else:
                            logger.error("❌ thumbnail not regenerated")
                        
                        # Verify gallery_thumbnail regenerated
                        if new_gallery_thumbnail and new_gallery_thumbnail != initial_gallery_thumbnail:
                            logger.info("✅ gallery_thumbnail regenerated")
                            results.append("A1-gallery-thumbnail-regenerated")
                        else:
                            logger.error("❌ gallery_thumbnail not regenerated")
                        
                    else:
                        error = await patch_resp.text()
                        logger.error(f"❌ PATCH failed: {patch_resp.status} - {error}")
                
                # Test 2: Edge case - asset with no photos
                logger.info("\n📸 Test 2: Creating asset with no photos...")
                
                asset_no_photos = {
                    "asset_code": f"BUGFIX-A2-{int(time.time())}",
                    "NUP": f"NUP-A2-{int(time.time())}",
                    "asset_name": "Bugfix Test Asset - No Photos",
                    "category": "Test Category",
                    "activity_id": self.test_activity_id,
                    "photos": []
                }
                
                async with self.session.post(f"{API_URL}/assets", json=asset_no_photos) as resp2:
                    if resp2.status == 200:
                        asset2 = await resp2.json()
                        asset2_id = asset2["id"]
                        
                        # Try PATCH thumbnail_index on asset with no photos
                        patch_data2 = {"thumbnail_index": 1}
                        headers2 = {"If-Match": str(asset2.get("version", 1))}
                        
                        async with self.session.patch(f"{API_URL}/assets/{asset2_id}", 
                                                    json=patch_data2, headers=headers2) as patch_resp2:
                            if patch_resp2.status == 200:
                                updated_asset2 = await patch_resp2.json()
                                
                                # Should coerce to 0 and not crash
                                final_index = updated_asset2.get("thumbnail_index")
                                if final_index == 0:
                                    logger.info("✅ thumbnail_index coerced to 0 for asset with no photos")
                                    results.append("A2-no-photos-handled")
                                else:
                                    logger.error(f"❌ thumbnail_index not coerced: {final_index}")
                            else:
                                logger.error(f"❌ PATCH failed on no-photos asset: {patch_resp2.status}")
                
            else:
                error = await resp.text()
                logger.error(f"❌ Asset creation failed: {resp.status} - {error}")
        
        return results

    async def test_part_b_audit_headers(self):
        """Test Part B: Audit headers functionality"""
        logger.info("\n🎯 PART B: Testing audit headers...")
        
        results = []
        
        if not self.test_activity_id:
            logger.error("❌ No activity ID available for testing")
            return results

        # Create a test asset
        asset_data = {
            "asset_code": f"BUGFIX-B1-{int(time.time())}",
            "NUP": f"NUP-B1-{int(time.time())}",
            "asset_name": "Bugfix Test Asset - Audit",
            "category": "Test Category",
            "activity_id": self.test_activity_id
        }
        
        # Test 1: Create asset with audit headers
        logger.info("👤 Test 1: Creating asset with X-Audit-User headers...")
        
        headers = {
            "X-Audit-User": "Budi Santoso",
            "X-Audit-User-Id": "budi-uuid-123"
        }
        
        async with self.session.post(f"{API_URL}/assets", json=asset_data, headers=headers) as resp:
            if resp.status == 200:
                asset = await resp.json()
                asset_id = asset["id"]
                
                logger.info("✅ Asset created with audit headers")
                results.append("B1-create-with-audit-headers")
                
                # Check audit logs
                await asyncio.sleep(1)  # Give time for audit log to be written
                
                async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp:
                    if audit_resp.status == 200:
                        audit_data = await audit_resp.json()
                        logs = audit_data.get("logs", [])
                        
                        # Find the create log for this asset
                        create_log = None
                        for log in logs:
                            if (log.get("action") == "create" and 
                                log.get("asset_id") == asset_id):
                                create_log = log
                                break
                        
                        if create_log:
                            username = create_log.get("username", "")
                            logger.info(f"Create audit log username: '{username}'")
                            
                            if username == "Budi Santoso":
                                logger.info("✅ Audit log shows correct username: Budi Santoso")
                                results.append("B1-audit-log-correct-username")
                            else:
                                logger.error(f"❌ Audit log username incorrect: expected 'Budi Santoso', got '{username}'")
                        else:
                            logger.error("❌ No create audit log found for asset")
                    else:
                        logger.error(f"❌ Failed to get audit logs: {audit_resp.status}")
                
                # Test 2: PATCH asset with audit headers
                logger.info("👤 Test 2: PATCH asset with X-Audit-User headers...")
                
                patch_data = {"asset_name": "Updated Asset Name for Audit Test"}
                patch_headers = {
                    "If-Match": str(asset.get("version", 1)),
                    "X-Audit-User": "Siti Nurhaliza",
                    "X-Audit-User-Id": "siti-uuid-456"
                }
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data, headers=patch_headers) as patch_resp:
                    if patch_resp.status == 200:
                        logger.info("✅ PATCH with audit headers successful")
                        results.append("B2-patch-with-audit-headers")
                        
                        # Check audit logs again
                        await asyncio.sleep(1)
                        
                        async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp2:
                            if audit_resp2.status == 200:
                                audit_data2 = await audit_resp2.json()
                                logs2 = audit_data2.get("logs", [])
                                
                                # Find the update log
                                update_log = None
                                for log in logs2:
                                    if (log.get("action") == "update" and 
                                        log.get("asset_id") == asset_id):
                                        update_log = log
                                        break
                                
                                if update_log:
                                    username = update_log.get("username", "")
                                    logger.info(f"Update audit log username: '{username}'")
                                    
                                    if username == "Siti Nurhaliza":
                                        logger.info("✅ Update audit log shows correct username: Siti Nurhaliza")
                                        results.append("B2-audit-log-correct-username")
                                    else:
                                        logger.error(f"❌ Update audit log username incorrect: expected 'Siti Nurhaliza', got '{username}'")
                                else:
                                    logger.error("❌ No update audit log found for asset")
                    else:
                        logger.error(f"❌ PATCH with audit headers failed: {patch_resp.status}")
                
                # Test 3: PATCH without audit headers (should show 'unknown')
                logger.info("👤 Test 3: PATCH without audit headers...")
                
                patch_data3 = {"notes": "Test without audit headers"}
                patch_headers3 = {"If-Match": str(asset.get("version", 1) + 1)}  # No audit headers
                
                async with self.session.patch(f"{API_URL}/assets/{asset_id}", 
                                            json=patch_data3, headers=patch_headers3) as patch_resp3:
                    if patch_resp3.status == 200:
                        logger.info("✅ PATCH without audit headers successful")
                        results.append("B3-patch-without-audit-headers")
                        
                        # Check audit logs
                        await asyncio.sleep(1)
                        
                        async with self.session.get(f"{API_URL}/audit-logs?asset_id={asset_id}") as audit_resp3:
                            if audit_resp3.status == 200:
                                audit_data3 = await audit_resp3.json()
                                logs3 = audit_data3.get("logs", [])
                                
                                # Find the most recent log (should be 'unknown')
                                if logs3:
                                    recent_log = logs3[0]  # Most recent first
                                    username = recent_log.get("username", "")
                                    
                                    if username in ["unknown", ""]:
                                        logger.info("✅ Audit log without headers shows 'unknown' username")
                                        results.append("B3-audit-log-unknown")
                                    else:
                                        logger.error(f"❌ Audit log without headers incorrect: {username}")
            else:
                error = await resp.text()
                logger.error(f"❌ Asset creation failed: {resp.status} - {error}")
        
        return results

    async def run_all_tests(self):
        """Run all targeted tests"""
        logger.info("🚀 Starting targeted BUGFIX testing...")
        
        try:
            await self.setup()
            
            # Run test parts
            part_a_results = await self.test_part_a_thumbnail_bugfix()
            part_b_results = await self.test_part_b_audit_headers()
            
            # Summary
            total_passed = len(part_a_results) + len(part_b_results)
            
            logger.info(f"\n📊 TARGETED TEST RESULTS:")
            logger.info(f"Part A (Thumbnail bugfix): {len(part_a_results)} tests passed")
            logger.info(f"Part B (Audit headers): {len(part_b_results)} tests passed")
            logger.info(f"TOTAL: {total_passed} tests passed")
            
            logger.info(f"\nPart A results: {part_a_results}")
            logger.info(f"Part B results: {part_b_results}")
            
            return {
                "total_passed": total_passed,
                "part_a": part_a_results,
                "part_b": part_b_results
            }
            
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            raise
        finally:
            await self.cleanup()

async def main():
    """Main test execution"""
    tester = TargetedBugfixTester()
    results = await tester.run_all_tests()
    return results

if __name__ == "__main__":
    asyncio.run(main())