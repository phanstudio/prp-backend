import cloudinary
import cloudinary.uploader
from core.settings import settings
from PIL import Image
import io
import asyncio
import hashlib
import re

THUMBNAIL="thumbnail" #"templates/thumbnails"
THUMBNAIL_SIZE=512

cloudinary.config(
    cloud_name=settings.cloud_name,
    api_key=settings.cloud_api_key,
    api_secret=settings.cloud_api_secret,
    secure=True
)

# with multiple cns we can have it be modular were we can change easily 
# also for deleting we can just delete the whole service
# we will be using different cns services and logging it but we will not store locally

# --- Image processing (threaded) ---
def _process_image_sync(file_bytes, max_size=2048, to_webp=True):
    img = Image.open(io.BytesIO(file_bytes))
    
    # Only convert if not already RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Calculate new size once
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    
    img_format = "WEBP" if to_webp else "JPEG"
    extension = "webp" if to_webp else "jpg"

    buffer = io.BytesIO()
    # Use method="fastest" for WebP, remove optimize for JPEG
    if to_webp:
        img.save(buffer, format=img_format, quality=75, method=0)  # method=0 is fastest
    else:
        img.save(buffer, format=img_format, quality=75, optimize=False)
    
    buffer.seek(0)
    return buffer, extension

async def process_image(file_bytes, max_size=2048, to_webp=True):
    return await asyncio.to_thread(_process_image_sync, file_bytes, max_size, to_webp)

# def _upload_sync(file_bytes, folder, extension, public_id=None):
#     upload_params = {
#         "folder": folder,
#         "resource_type": "image",
#         "format": extension,
#         "overwrite": False,
#         "invalidate": False,
#         "eager": [],  # Skip eager transformations
#         "notification_url": None,  # Skip webhook
#         "async": False,  # Ensure synchronous (default, but explicit)
#     }
    
#     if public_id:
#         upload_params["public_id"] = public_id
#         upload_params["unique_filename"] = False
    
#     return cloudinary.uploader.upload(file_bytes, **upload_params)

# async def upload_image(file_obj, folder: str = "templates", max_size=2048):
#     file_bytes = await file_obj.read()
#     buffer, extension = await process_image(file_bytes, max_size=max_size)
    
#     file_hash = hashlib.md5(buffer.getvalue()).hexdigest()[:12]
#     public_id = f"{file_hash}"
    
#     res = await asyncio.to_thread(_upload_sync, buffer, folder, extension, public_id)
#     return res["secure_url"], res["public_id"]

async def upload_image(file_obj, folder: str = "templates", max_size=2048):
    file_bytes = await file_obj.read()

    # keep your PIL preprocessing
    buffer, _ = await process_image(file_bytes, max_size=max_size)

    # DO NOT generate a custom hash public_id anymore
    # DO NOT override Cloudinary auto-naming

    res = await asyncio.to_thread(
        cloudinary.uploader.upload,
        buffer,
        folder=folder,
        resource_type="image",
        # let Cloudinary determine the final format/extension
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    return res["secure_url"], res["public_id"]

async def delete_images(public_id: str, thumbnail_p_id: str):
    loop = asyncio.get_running_loop()
    result = await asyncio.gather(
        loop.run_in_executor(None, cloudinary.uploader.destroy, public_id),
        loop.run_in_executor(None, cloudinary.uploader.destroy, thumbnail_p_id),
    )
    return result

async def update_image(cloudinary_public_id, file, folder="templates", max_size=2048):
    # Delete old image if exists
    if cloudinary_public_id:
        try:
            cloudinary.uploader.destroy(cloudinary_public_id)
        except Exception as e:
            # logging.warning(f"Failed to delete old image: {str(e)}")
            print(f"Failed to delete old image: {str(e)}")
    return await upload_image(file, folder, max_size)

async def update_images(template_url, template_public_id, thumbnail_public_id, thumbnail_file):
    # call update_image directly since we only have one coroutine
    thumb_url, thumb_id = await update_image(
        thumbnail_public_id,
        thumbnail_file,
        folder=THUMBNAIL,
        max_size=THUMBNAIL_SIZE
    )

    # return unpacked values
    return template_url, template_public_id, thumb_url, thumb_id

async def upload_images(template_file, thumbnail_file):
    url, thumb = await asyncio.gather(
        upload_image(template_file, folder="templates"),
        upload_image(thumbnail_file, folder= THUMBNAIL, max_size=THUMBNAIL_SIZE)
    )
    return *url, *thumb

# async def upload_image_to_cloudinary(file: UploadFile, folder: str = "templates"):
#     """Upload image and thumbnail to Cloudinary"""
#     try:
#     except Exception as e:
#         logging.error(f"Error uploading to Cloudinary: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to upload image"
#         )


def get_public_id(url):
    match = re.search(r"/upload/(?:v\d+/)?(.+)\.\w+$", url)
    return match.group(1) if match else None
