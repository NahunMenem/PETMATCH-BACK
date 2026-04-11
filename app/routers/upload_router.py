import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from ..config import settings
from ..auth import get_current_user
from .. import models

router = APIRouter(prefix="/upload", tags=["upload"])

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10


@router.post("/photo")
async def upload_photo(
    photo: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
):
    if photo.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Solo se permiten imágenes JPG, PNG o WebP",
        )

    contents = await photo.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"La imagen no puede superar {MAX_SIZE_MB}MB",
        )

    result = cloudinary.uploader.upload(
        contents,
        folder="petmatch/pets",
        transformation=[
            {"width": 800, "height": 800, "crop": "limit"},
            {"quality": "auto"},
        ],
    )
    return {"url": result["secure_url"]}
