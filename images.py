"""Safe handling of the optional outfit image upload."""
import io
import uuid
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from ..config import settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def process_upload(file: Optional[UploadFile]) -> Optional[Tuple[bytes, str]]:
    """Validate + normalise an uploaded image.

    Returns (jpeg_bytes, public_url) or None when no file was sent.
    The image is re-encoded as JPEG (max 1024px) which strips EXIF data and
    guarantees the stored file really is an image.
    """
    if file is None or not file.filename:
        return None

    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not data:
        return None
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image is too large (max 5 MB).")

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise HTTPException(400, "Only JPG, PNG or WEBP images are allowed.")
            img = img.convert("RGB")
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(400, "The uploaded file is not a valid image.")

    jpeg = buf.getvalue()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (settings.UPLOAD_DIR / name).write_bytes(jpeg)
    return jpeg, f"/static/uploads/{name}"
