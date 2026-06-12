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
    """
    رفع ملف (صورة أو فيديو) إلى Cloudinary.
    يرجع dict فيه:
      - url:        رابط الملف
      - public_id:  معرّف Cloudinary (للحذف لاحقاً)
      - resource_type: 'image' أو 'video'
    أو None لو فشل الرفع.
    """
    try:
        ext = file_storage.filename.rsplit('.', 1)[-1].lower()
        resource_type = "video" if ext in VIDEO_EXTENSIONS else "image"

        result = cloudinary.uploader.upload(
            file_storage,
            folder        = folder,
            resource_type = resource_type,
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
    """حذف ملف من Cloudinary"""
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception as e:
        print(f"Cloudinary delete error: {e}")
