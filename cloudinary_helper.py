import cloudinary
import cloudinary.uploader
from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

cloudinary.config(
    cloud_name = CLOUDINARY_CLOUD_NAME,
    api_key    = CLOUDINARY_API_KEY,
    api_secret = CLOUDINARY_API_SECRET,
    secure     = True
)

VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def upload_file(file_storage, folder="uploads"):
    try:
        filename = file_storage.filename or ""
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ""
        resource_type = "video" if ext in VIDEO_EXTENSIONS else "image"

        # Read file bytes — works on all hosting platforms including Render
        file_bytes = file_storage.read()
        if not file_bytes:
            print("Cloudinary: empty file")
            return None

        result = cloudinary.uploader.upload(
            file_bytes,
            folder        = folder,
            resource_type = resource_type,
            use_filename  = True,
            unique_filename = True,
        )
        return {
            "url":           result["secure_url"],
            "public_id":     result["public_id"],
            "resource_type": resource_type,
        }
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


def delete_file(public_id, resource_type="image"):
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception as e:
        print(f"Cloudinary delete error: {e}")
