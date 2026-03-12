from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Union, Literal
from datetime import datetime
# from pydantic_extra_types.color import Color

# c = Color('ff00ff')


# class Model(BaseModel):
#     color: Color

# Text element schema (not a DB model)
class TextElement(BaseModel):
    id: Optional[float] = None # unnessesary since its no being auto gen
    text: str
    x: float
    y: float
    font_size: int = Field(default=14, ge=8, le=101)
    color: str = Field(default="#000000")
    rotation: float = Field(default=0.0, ge=-180, le=180)
    font_family: str = "Arial"
    width: Optional[float] = 100
    height: Optional[float] = 50

    outline_color: Optional[str] = Field(default="#000000")
    outline_size: Optional[int] = Field(default=1, ge=-1, le=31)

    text_align: Optional[str] = None
    font_weight: Optional[Union[str, float]] = None
    font_style: Optional[str] = None
    underline: Optional[bool] = False
    linethrough: Optional[bool] = False
    effect_type: Optional[str] = None

    # Shadow properties
    shadow_color: Optional[str] = Field(default="#000000")
    shadow_blur: Optional[float] = None
    shadow_offset_x: Optional[float] = None
    shadow_offset_y: Optional[float] = None
    shadow_opacity: Optional[float] = None

# --- Users --- #
class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(min_length=6)

class User(UserBase):
    id: int
    is_superuser: bool
    is_staff: bool

    class Config:
        from_attributes = True

class UserOut(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    is_staff: bool

    model_config = ConfigDict(from_attributes=True)

# class UserUpdate(BaseModel):
#     email: Optional[EmailStr] = None
#     is_active: Optional[bool] = None
#     is_staff: Optional[bool] = None
#     password: Optional[str] = Field(None, min_length=6)

# class UserResponse(UserBase):
#     id: int
#     is_superuser: bool
#     created_at: datetime

#     class Config:
#         from_attributes = True


# --- Templates --- #
class TemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    text_elements: List[TextElement]
    tag: Optional[str] = None

class TemplateCreate(TemplateBase):
    pass

class TemplateOut(TemplateBase): # might be toomuch info because we have most of the info already in the frontend the only info we don't have is the image url
    id: int
    image_url: str
    thumbnail_url: str
    owner_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class TemplateCreateOut(TemplateBase):
    id: int
    image_url: str
    thumbnail_url: str
    owner_id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class Template(TemplateBase):
    id: int
    image_url: str
    thumbnail_url: str
    owner_id: int

    class Config:
        from_attributes = True

# --- Variant --- #
class VariantBase(BaseModel):
    text_elements: List[TextElement]

class VariantCreate(VariantBase):
    source_id: int  # which template this variant is derived from

class VariantOut(VariantBase):
    id: int
    owner_id: int
    source_id: int
    thumbnail_url:str

    model_config = ConfigDict(from_attributes=True)


class CloudinarySignRequest(BaseModel):
    folder: Literal["templates", "thumbnail", "variants"] = "templates"
    resource_type: Literal["image"] = "image"
    upload_preset: Optional[str] = None
    allowed_formats: Optional[List[str]] = None
    max_file_size: Optional[int] = Field(default=None, gt=0)
    eager: Optional[bool] = False      # ✅ frontend just passes true for thumbnail


class CloudinarySignResponse(BaseModel):
    timestamp: int
    signature: str
    api_key: str
    cloud_name: str
    folder: str
    resource_type: str
    upload_preset: Optional[str] = None
    allowed_formats: Optional[List[str]] = None
    max_file_size: Optional[int] = None
    expires_in: int
    upload_url: str
    eager: Optional[str] = None        # ✅ the serialized transform string
    # eager_async: Optional[str] = None        # ✅ the serialized transform string


# class TemplateBase(BaseModel):
#     name: str = Field(min_length=1, max_length=200)
#     description: Optional[str] = None

# class TemplateCreate(TemplateBase):
#     pass

# class TemplateUpdate(BaseModel):
#     name: Optional[str] = Field(None, min_length=1, max_length=200)
#     description: Optional[str] = None
#     text_elements: Optional[List[TextElement]] = None

# class TemplateResponse(TemplateBase):
#     id: int
#     image_url: Optional[str]
#     thumbnail_url: Optional[str]
#     text_elements: List[TextElement]
#     owner_id: int
#     created_at: datetime
#     updated_at: datetime

#     class Config:
#         from_attributes = True

# class Token(BaseModel):
#     access_token: str
#     token_type: str

# class TokenData(BaseModel):
#     email: Optional[str] = None

