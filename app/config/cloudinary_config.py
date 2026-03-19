import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Cloudinary configuration from .env file
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

# Validate that credentials are set
if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    print("⚠️ WARNING: Cloudinary credentials not found in .env file!")
    print("Please create a .env file with CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET")
else:
    # Configure Cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    print("✅ Cloudinary configured successfully")

def upload_media(file_path_or_bytes, folder="properties", resource_type="auto"):
    """
    Upload media to Cloudinary
    
    Args:
        file_path_or_bytes: File path or bytes object
        folder: Folder name in Cloudinary
        resource_type: 'image', 'video', or 'auto'
    
    Returns:
        dict: Upload result with 'public_id', 'secure_url', etc.
    """
    try:
        result = cloudinary.uploader.upload(
            file_path_or_bytes,
            folder=folder,
            resource_type=resource_type
        )
        return {
            'success': True,
            'public_id': result['public_id'],
            'url': result['secure_url'],
            'resource_type': result['resource_type'],
            'format': result['format'],
            'bytes': result['bytes']
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def delete_media(public_id, resource_type="image"):
    """
    Delete media from Cloudinary
    
    Args:
        public_id: Cloudinary public ID
        resource_type: 'image' or 'video'
    
    Returns:
        dict: Deletion result
    """
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return {
            'success': result['result'] == 'ok',
            'result': result
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def generate_thumbnail(public_id):
    """
    Generate thumbnail URL for videos
    
    Args:
        public_id: Cloudinary public ID of the video
    
    Returns:
        str: Thumbnail URL
    """
    return cloudinary.CloudinaryImage(public_id).build_url(
        resource_type="video",
        format="jpg",
        start_offset="0"
    )
