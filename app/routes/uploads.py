from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
import uuid
from datetime import datetime

from app.config import get_settings
from app.middleware.auth import get_current_user_id

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    entity_type: str = Form(default="general"),
    entity_id: Optional[str] = Form(default=None),
    clerk_user_id: str = Depends(get_current_user_id),
):
    settings = get_settings()
    if not settings.ENABLE_FIREBASE_STORAGE:
        raise HTTPException(status_code=503, detail="Image upload is disabled")

    if file.size and file.size > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_IMAGE_SIZE_MB}MB",
        )

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    ext = content_type.split("/")[-1] if "/" in content_type else "jpg"
    filename = f"{entity_type}/{clerk_user_id}/{uuid.uuid4()}.{ext}"

    try:
        # Firebase Storage upload placeholder
        # When Firebase Admin is set up:
        # bucket = storage.bucket(settings.FIREBASE_STORAGE_BUCKET)
        # blob = bucket.blob(filename)
        # blob.upload_from_file(file.file, content_type=content_type)
        # blob.make_public()
        # url = blob.public_url

        url = f"https://{settings.FIREBASE_STORAGE_BUCKET}/{filename}"

        return {
            "url": url,
            "filename": filename,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
