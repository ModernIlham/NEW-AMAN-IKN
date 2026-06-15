import base64
import io
from PIL import Image

# Mock the function from server.py to test it in isolation
def create_thumbnail(image_data):
    if not image_data:
        return None
    
    try:
        if "base64," in image_data:
            header, encoded = image_data.split("base64,", 1)
        else:
            header = "data:image/jpeg;base64"
            encoded = image_data

        image_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(image_bytes))
        
        img.thumbnail((100, 100))
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)
        
        thumb_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"{header}base64,{thumb_base64}"
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test
def test_thumbnail_generation():
    # Create a simple red image
    img = Image.new('RGB', (500, 500), color = 'red')
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    base64_str = f"data:image/jpeg;base64,{img_str}"
    
    print(f"Original size: {len(base64_str)} chars")
    
    thumbnail = create_thumbnail(base64_str)
    
    if thumbnail:
        print("Thumbnail generated successfully")
        print(f"Thumbnail size: {len(thumbnail)} chars")
        if len(thumbnail) < len(base64_str):
            print("PASS: Thumbnail is smaller than original")
        else:
            print("FAIL: Thumbnail is not smaller")
    else:
        print("FAIL: Thumbnail generation returned None")

if __name__ == "__main__":
    test_thumbnail_generation()