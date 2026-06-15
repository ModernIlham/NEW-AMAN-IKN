import asyncio
import os
import base64
import io
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image as PILImage

# Setup environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

if not MONGO_URL or not DB_NAME:
    print("❌ Error: MONGO_URL or DB_NAME not found in .env")
    exit(1)

# Helper for thumbnail generation
def create_thumbnail(image_data: str) -> str:
    """Generate a small thumbnail from base64 image"""
    if not image_data:
        return None
    
    try:
        # Check if it's a data URL
        if "base64," in image_data:
            header, encoded = image_data.split("base64,", 1)
        else:
            header = "data:image/jpeg;base64"
            encoded = image_data

        # Decode
        image_bytes = base64.b64decode(encoded)
        img = PILImage.open(io.BytesIO(image_bytes))
        
        # Resize to max 100x100
        img.thumbnail((100, 100))
        
        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)
        
        # Encode back to base64
        thumb_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"{header}base64,{thumb_base64}"
    except Exception as e:
        print(f"⚠️ Thumbnail generation error: {e}")
        return None

async def migrate():
    print(f"🔌 Connecting to MongoDB: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🔍 Scanning assets...")
    assets = await db.assets.find({}).to_list(None)
    
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    for asset in assets:
        asset_id = asset.get('id')
        name = asset.get('asset_name', 'Unknown')
        photo = asset.get('photo')
        thumbnail = asset.get('thumbnail')
        
        if not photo:
            skipped_count += 1
            continue
            
        if thumbnail:
            # Already has thumbnail
            skipped_count += 1
            continue
            
        print(f"🖼️ Generating thumbnail for: {name} ({asset_id})...")
        
        new_thumbnail = create_thumbnail(photo)
        
        if new_thumbnail:
            await db.assets.update_one(
                {"id": asset_id},
                {"$set": {"thumbnail": new_thumbnail}}
            )
            updated_count += 1
        else:
            error_count += 1
            print(f"❌ Failed to generate thumbnail for {name}")

    print("\n" + "="*30)
    print("✅ Migration Complete")
    print(f"Total Assets: {len(assets)}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print("="*30)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
