# app/routes.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from . import schemas, crud, database, cloud, models
from core import auth
from core.settings import settings
from datetime import datetime, timezone
import json
from pydantic import ValidationError
from fastapi import Form, status
from typing import List, Optional
import asyncio
from core.scripts.analysis import start_time, calculate_time
import random
import string

router = APIRouter()

def generate_username(email: str, length: int = 4, email_length: int = 5) -> str:
    """Generate a username from email prefix + random digits."""
    base = email.split("@")[0][:email_length]
    random_suffix = ''.join(random.choices(string.ascii_lowercase+string.digits, k=length))
    return f"{base}{random_suffix}"

async def generate_unique_username(db: AsyncSession, email: str, email_length: int = 5, length: int = 7) -> str:
    """Generate a username and ensure it's unique in the database."""
    while True:
        username = generate_username(email, length, email_length)
        existing = await crud.get_user_by_username(db, username)
        if not existing:
            return username

# --- User endpoints --- #
@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
async def register(user_in: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    print(user_in.email)
    existing = await crud.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if not user_in.username:
        user_in.username = await generate_unique_username(db, user_in.email)
    return await crud.create_user(db, user_in)

@router.post("/login")
async def login(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    db_user = await crud.get_user_by_email(db, user.email)
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth.create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/auth/me", response_model=schemas.UserOut)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

def parse_text_elements(text_elements: str = Form(...)) -> List[schemas.TextElement]:
    try:
        parsed = json.loads(text_elements)
        for i in parsed:
            i["id"] = float(i["id"])
        return [schemas.TextElement(**t) for t in parsed]
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid text_elements JSON: {e}")

# --- Cloudinary signed upload endpoint --- #
@router.post("/cloudinary/sign", response_model=schemas.CloudinarySignResponse)
async def sign_cloudinary_upload(
    sign_request: schemas.CloudinarySignRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
):
    try:
        payload = cloud.generate_signed_upload_data(
            user_id=current_user.id,
            folder=sign_request.folder,
            resource_type=sign_request.resource_type,
            upload_preset=sign_request.upload_preset or settings.cloud_signed_upload_preset,
            allowed_formats=sign_request.allowed_formats,
            max_file_size=sign_request.max_file_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sign upload: {e}")

    return payload


# --- Template endpoints --- #
@router.post("/templates", response_model=schemas.TemplateCreateOut, status_code=status.HTTP_201_CREATED) # ✅
async def create_template(
    name: str = Form(...),
    description: str = Form(None),
    tag: Optional[str] = Form(None),
    text_elements: List[schemas.TextElement] = Depends(parse_text_elements),
    file: Optional[UploadFile] = File(None),
    file2: Optional[UploadFile] = File(None),  # second file
    image_url: Optional[str] = Form(None),
    image_public_id: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    thumbnail_public_id: Optional[str] = Form(None),
    current_user = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db),
):
    tmpl_in = schemas.TemplateCreate(name=name, description=description, text_elements=text_elements, tag=tag)

    if file and file2:
        upload_task = asyncio.create_task(cloud.upload_images(file, file2))
        try:
            image_url, image_public_id, thumbnail_url, thumbnail_public_id = await upload_task
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image upload failed: {e}")
    elif image_url and image_public_id and thumbnail_url and thumbnail_public_id:
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide either both files ('file', 'file2') for backend upload, "
                "or Cloudinary values ('image_url', 'image_public_id', 'thumbnail_url', 'thumbnail_public_id')."
            ),
        )

    try:
        return await crud.create_template(db, tmpl_in, owner_id=current_user.id, image_url=image_url, 
                thumbnail_url=thumbnail_url, image_public_id=image_public_id, thumbnail_public_id=thumbnail_public_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.get("/templates", response_model=List[schemas.TemplateOut])
async def list_templates(search: Optional[str] = None, skip: int = 0, limit: int = 10, db: AsyncSession = Depends(database.get_db)):
    return await crud.list_templates(db, skip=skip, limit=limit, search=search)

@router.get("/templates/{template_id}", response_model=schemas.TemplateOut)
async def get_template(template_id: int, db: AsyncSession = Depends(database.get_db)):
    tmpl = await crud.get_template(db, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl

@router.put("/templates/{template_id}", status_code=status.HTTP_206_PARTIAL_CONTENT)
async def update_template(
    template_id: int,
    name: Optional[str] = Form(...),
    description: Optional[str] = Form(None),
    tag: Optional[str] = Form(None),
    text_elements: Optional[List[schemas.TextElement]] = Depends(parse_text_elements),
    file: Optional[UploadFile] = File(None),
    file2: Optional[UploadFile] = File(None),
    thumbnail_url: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    image_public_id: Optional[str] = Form(None),
    thumbnail_public_id: Optional[str] = Form(None),
    current_user=Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db),
):
    # Initialize update_data with the basic fields
    update_data = schemas.TemplateCreate(
        name=name, 
        description=description, 
        text_elements=text_elements, 
        tag=tag
    ).model_dump()
    
    # If new image(s) uploaded -> update with stable public_id(s)
    if file or file2:
        if not image_public_id or not thumbnail_public_id:
            raise HTTPException(
                status_code=400,
                detail="For file updates, provide image_public_id and thumbnail_public_id.",
            )

        try:
            if file and file2:
                image_task = asyncio.create_task(
                    cloud.update_image(image_public_id, file, folder="templates")
                )
                thumb_task = asyncio.create_task(
                    cloud.update_image(
                        thumbnail_public_id,
                        file2,
                        folder=cloud.THUMBNAIL,
                        max_size=cloud.THUMBNAIL_SIZE,
                    )
                )
                (new_image_url, _), (new_thumb_url, new_thumb_id) = await asyncio.gather(image_task, thumb_task)
                update_data.update({
                    "image_url": new_image_url,
                    "thumbnail_url": new_thumb_url,
                    "image_public_id": image_public_id,
                    "thumbnail_public_id": new_thumb_id,
                })
            elif file:
                new_image_url, _ = await cloud.update_image(image_public_id, file, folder="templates")
                update_data.update({
                    "image_url": new_image_url,
                    "image_public_id": image_public_id,
                })
                if thumbnail_url and thumbnail_public_id:
                    update_data.update({
                        "thumbnail_url": thumbnail_url,
                        "thumbnail_public_id": thumbnail_public_id,
                    })
            else:
                thumb_url, thumb_id = await cloud.update_images(
                    image_url, image_public_id, thumbnail_public_id, file2
                )
                update_data.update({
                    "image_url": image_url,
                    "thumbnail_url": thumb_url,
                    "image_public_id": image_public_id,
                    "thumbnail_public_id": thumb_id,
                })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image upload failed: {e}")
    elif any([thumbnail_url, image_url, image_public_id, thumbnail_public_id]):
        if not all([thumbnail_url, image_url, image_public_id, thumbnail_public_id]):
            raise HTTPException(
                status_code=400,
                detail="Provide all of image_url, image_public_id, thumbnail_url, thumbnail_public_id.",
            )
        update_data.update(
            {
                "image_url": image_url,
                "thumbnail_url": thumbnail_url,
                "image_public_id": image_public_id,
                "thumbnail_public_id": thumbnail_public_id,
            }
        )

    result = await crud.update_template(db, template_id, update_data, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Template not found or not permitted")
    
    return {"message": "Template updated successfully"}

@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user = Depends(auth.get_current_active_user),
    db: AsyncSession = Depends(database.get_db),
):
    # fetch template first
    template: models.Template = await crud.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # delete DB entry
    result = await crud.delete_template(db, template_id, current_user)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Template not found or not permitted")

    # delete images (non-blocking)
    await cloud.delete_images(template.image_public_id, template.thumbnail_public_id)

    return


# --- Variants --- #
@router.post("/variants", response_model=schemas.VariantOut, status_code=status.HTTP_201_CREATED) # ✅
async def create_variant(
    file: Optional[UploadFile] = File(None),
    source_id: int = Form(...),
    text_elements: List[schemas.TextElement] = Depends(parse_text_elements),
    thumbnail_url: Optional[str] = Form(None),
    thumbnail_public_id: Optional[str] = Form(None),
    current_user = Depends(auth.get_current_active_user), 
    db: AsyncSession = Depends(database.get_db)
):
    st = start_time()
    variant_in = schemas.VariantCreate(text_elements=text_elements, source_id=source_id)

    if file:
        upload_task = asyncio.create_task(cloud.upload_image(file, cloud.THUMBNAIL, cloud.THUMBNAIL_SIZE))
        try:
            thumbnail_url, thumbnail_public_id = await upload_task
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image upload failed: {e}")
    elif not (thumbnail_url and thumbnail_public_id):
        raise HTTPException(
            status_code=400,
            detail="Provide either 'file' or both 'thumbnail_url' and 'thumbnail_public_id'.",
        )

    try:
        result = await crud.create_variant(db, thumbnail_url, thumbnail_public_id,
            owner_id=current_user.id, variant_in=variant_in)
        print(calculate_time(st))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.get("/templates/{template_id}/variants", response_model=List[schemas.VariantOut])
async def list_variants(template_id: int, skip: int = 0, limit: int = 10, db: AsyncSession = Depends(database.get_db)):
    return await crud.list_variants_for_template(db, template_id, skip=skip, limit=limit)

# Health check
@router.get("/health") # ✅
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

@router.get("/alive-api")
async def check_alive():
    """
    Cron health-check endpoint.
    Returns "OK" if the cron secret is valid.
    """
    return {"status": "OK"}

@router.get("/")
async def root():
    return {"message": "Prp meme API", "status": "online"}
