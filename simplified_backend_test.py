#!/usr/bin/env python3
"""
Simplified Backend testing for BUGFIX round focusing on the specific issues that can be tested
without full admin authentication.

This test will focus on:
1. Testing existing assets for thumbnail functionality (if any exist)
2. Testing audit log structure and content
3. Testing basic API functionality
"""

import asyncio
import aiohttp
import json
import base64
import uuid
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend URL from frontend/.env
BASE_URL = "https://asset-crud-auth.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

class SimplifiedBugfixTester:
    def __init__(self):
        self.session = None

    async def setup(self):
        """Initialize session"""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()

    async def test_backend_health(self):
        """Test basic backend functionality"""
        logger.info("🏥 Testing backend health...")
        
        results = []
        
        # Test categories endpoint
        async with self.session.get(f"{API_URL}/categories") as resp:
            if resp.status == 200:
                logger.info("✅ Categories endpoint working")
                results.append("categories-working")
            else:
                logger.error(f"❌ Categories endpoint failed: {resp.status}")
        
        # Test inventory classifications
        async with self.session.get(f"{API_URL}/inventory-classifications") as resp:
            if resp.status == 200:
                data = await resp.json()
                if "inventory_statuses" in data:
                    logger.info("✅ Inventory classifications endpoint working")
                    results.append("inventory-classifications-working")
                else:
                    logger.error("❌ Inventory classifications missing expected data")
            else:
                logger.error(f"❌ Inventory classifications failed: {resp.status}")
        
        return results

    async def test_existing_assets_structure(self):
        """Test existing assets for proper structure and thumbnail fields"""
        logger.info("📋 Testing existing assets structure...")
        
        results = []
        
        # Get existing assets
        async with self.session.get(f"{API_URL}/assets?page_size=10") as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("items", [])
                
                logger.info(f"Found {len(assets)} existing assets")
                
                if assets:
                    # Check first asset structure
                    asset = assets[0]
                    asset_id = asset.get("id")
                    
                    # Check for required fields from bugfix
                    required_fields = ["thumbnail_index", "photo", "thumbnail", "gallery_thumbnail", "version"]
                    missing_fields = []
                    
                    for field in required_fields:
                        if field not in asset:
                            missing_fields.append(field)
                    
                    if not missing_fields:
                        logger.info("✅ Asset structure contains all required fields")
                        results.append("asset-structure-complete")
                    else:
                        logger.error(f"❌ Asset missing fields: {missing_fields}")
                    
                    # Check thumbnail_index field specifically
                    if "thumbnail_index" in asset:
                        thumbnail_index = asset.get("thumbnail_index")
                        logger.info(f"✅ thumbnail_index field present: {thumbnail_index}")
                        results.append("thumbnail-index-field-present")
                    
                    # Check version field for OCC
                    if "version" in asset:
                        version = asset.get("version")
                        logger.info(f"✅ version field present: {version}")
                        results.append("version-field-present")
                    
                    # Get detailed asset to check full structure
                    async with self.session.get(f"{API_URL}/assets/{asset_id}") as detail_resp:
                        if detail_resp.status == 200:
                            detailed_asset = await detail_resp.json()
                            
                            # Check photos array
                            photos = detailed_asset.get("photos", [])
                            logger.info(f"Asset has {len(photos)} photos")
                            
                            if len(photos) > 1:
                                logger.info("✅ Asset has multiple photos (good for thumbnail testing)")
                                results.append("multi-photo-asset-available")
                            
                            results.append("asset-detail-accessible")
                        else:
                            logger.error(f"❌ Could not get asset details: {detail_resp.status}")
                else:
                    logger.info("ℹ️ No existing assets found")
            else:
                logger.error(f"❌ Could not get assets: {resp.status}")
        
        return results

    async def test_audit_logs_structure(self):
        """Test audit logs for proper structure and username field"""
        logger.info("📝 Testing audit logs structure...")
        
        results = []
        
        # Get existing audit logs
        async with self.session.get(f"{API_URL}/audit-logs?page_size=10") as resp:
            if resp.status == 200:
                data = await resp.json()
                logs = data.get("logs", [])
                
                logger.info(f"Found {len(logs)} existing audit logs")
                
                if logs:
                    # Check first log structure
                    log = logs[0]
                    
                    # Check for required fields
                    required_fields = ["username", "action", "asset_id", "timestamp"]
                    missing_fields = []
                    
                    for field in required_fields:
                        if field not in log:
                            missing_fields.append(field)
                    
                    if not missing_fields:
                        logger.info("✅ Audit log structure contains all required fields")
                        results.append("audit-log-structure-complete")
                    else:
                        logger.error(f"❌ Audit log missing fields: {missing_fields}")
                    
                    # Check username field specifically (this is what the bugfix addresses)
                    username = log.get("username", "")
                    logger.info(f"Audit log username: '{username}'")
                    
                    if username and username != "unknown":
                        logger.info("✅ Audit log has proper username (not 'unknown')")
                        results.append("audit-log-proper-username")
                    elif username == "unknown":
                        logger.info("⚠️ Audit log shows 'unknown' username (this is what bugfix addresses)")
                        results.append("audit-log-unknown-username-found")
                    else:
                        logger.info("ℹ️ Audit log has empty username")
                    
                    # Check for different username patterns
                    usernames = set()
                    for log in logs[:5]:  # Check first 5 logs
                        usernames.add(log.get("username", ""))
                    
                    logger.info(f"Found usernames in logs: {list(usernames)}")
                    
                    if len(usernames) > 1:
                        logger.info("✅ Multiple different usernames found in audit logs")
                        results.append("audit-log-multiple-usernames")
                    
                    results.append("audit-logs-accessible")
                else:
                    logger.info("ℹ️ No existing audit logs found")
            else:
                logger.error(f"❌ Could not get audit logs: {resp.status}")
        
        return results

    async def test_patch_without_auth(self):
        """Test PATCH endpoint behavior without authentication (should fail gracefully)"""
        logger.info("🔒 Testing PATCH endpoint without authentication...")
        
        results = []
        
        # Get an existing asset ID
        async with self.session.get(f"{API_URL}/assets?page_size=1") as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("items", [])
                
                if assets:
                    asset_id = assets[0]["id"]
                    
                    # Try PATCH without authentication
                    patch_data = {"thumbnail_index": 1}
                    
                    async with self.session.patch(f"{API_URL}/assets/{asset_id}", json=patch_data) as patch_resp:
                        if patch_resp.status == 401:
                            logger.info("✅ PATCH correctly requires authentication (401)")
                            results.append("patch-requires-auth")
                        elif patch_resp.status == 403:
                            logger.info("✅ PATCH correctly forbidden without auth (403)")
                            results.append("patch-requires-auth")
                        else:
                            logger.error(f"❌ PATCH unexpected status without auth: {patch_resp.status}")
                            error_text = await patch_resp.text()
                            logger.error(f"Response: {error_text}")
        
        return results

    async def test_thumbnail_index_field_validation(self):
        """Test that thumbnail_index field is properly handled in API responses"""
        logger.info("🖼️ Testing thumbnail_index field validation...")
        
        results = []
        
        # Get assets and check thumbnail_index values
        async with self.session.get(f"{API_URL}/assets?page_size=20") as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("items", [])
                
                thumbnail_indices = []
                for asset in assets:
                    if "thumbnail_index" in asset:
                        thumbnail_indices.append(asset["thumbnail_index"])
                
                if thumbnail_indices:
                    logger.info(f"Found thumbnail_index values: {thumbnail_indices[:10]}")
                    
                    # Check if values are reasonable (should be >= 0)
                    valid_indices = [idx for idx in thumbnail_indices if isinstance(idx, int) and idx >= 0]
                    
                    if len(valid_indices) == len(thumbnail_indices):
                        logger.info("✅ All thumbnail_index values are valid integers >= 0")
                        results.append("thumbnail-index-values-valid")
                    else:
                        logger.error(f"❌ Some thumbnail_index values are invalid")
                    
                    # Check for variety in values (indicates the field is being used)
                    unique_values = set(thumbnail_indices)
                    if len(unique_values) > 1:
                        logger.info(f"✅ thumbnail_index has variety: {unique_values}")
                        results.append("thumbnail-index-variety")
                    else:
                        logger.info(f"ℹ️ thumbnail_index all same value: {unique_values}")
                
                results.append("thumbnail-index-field-tested")
        
        return results

    async def run_all_tests(self):
        """Run all simplified tests"""
        logger.info("🚀 Starting simplified BUGFIX round backend testing...")
        
        try:
            await self.setup()
            
            # Run all test parts
            health_results = await self.test_backend_health()
            asset_results = await self.test_existing_assets_structure()
            audit_results = await self.test_audit_logs_structure()
            patch_results = await self.test_patch_without_auth()
            thumbnail_results = await self.test_thumbnail_index_field_validation()
            
            # Summary
            all_results = health_results + asset_results + audit_results + patch_results + thumbnail_results
            total_tests = len(all_results)
            
            logger.info(f"\n📊 SIMPLIFIED TEST RESULTS:")
            logger.info(f"Backend Health: {len(health_results)} tests")
            logger.info(f"Asset Structure: {len(asset_results)} tests")
            logger.info(f"Audit Logs: {len(audit_results)} tests")
            logger.info(f"PATCH Security: {len(patch_results)} tests")
            logger.info(f"Thumbnail Fields: {len(thumbnail_results)} tests")
            logger.info(f"TOTAL: {total_tests} tests completed")
            
            logger.info(f"\nPassed tests: {all_results}")
            
            # Analysis for the bugfix
            logger.info(f"\n🔍 BUGFIX ANALYSIS:")
            
            if "thumbnail-index-field-present" in all_results:
                logger.info("✅ thumbnail_index field is present in assets (Part A infrastructure)")
            
            if "version-field-present" in all_results:
                logger.info("✅ version field is present for OCC (Part B regression)")
            
            if "audit-log-structure-complete" in all_results:
                logger.info("✅ Audit log structure is complete (Part B infrastructure)")
            
            if "audit-log-unknown-username-found" in all_results:
                logger.info("⚠️ Found 'unknown' usernames in audit logs (confirms Part B bug exists)")
            elif "audit-log-proper-username" in all_results:
                logger.info("✅ Found proper usernames in audit logs (Part B may be fixed)")
            
            if "patch-requires-auth" in all_results:
                logger.info("✅ PATCH endpoints properly secured")
            
            return {
                "total_tests": total_tests,
                "results": all_results,
                "health": health_results,
                "assets": asset_results,
                "audit": audit_results,
                "patch": patch_results,
                "thumbnail": thumbnail_results
            }
            
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            raise
        finally:
            await self.cleanup()

async def main():
    """Main test execution"""
    tester = SimplifiedBugfixTester()
    results = await tester.run_all_tests()
    
    return results

if __name__ == "__main__":
    asyncio.run(main())