import os
import uuid
from pathlib import Path

import aiofiles
from cryptography.fernet import Fernet


ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
EXTENSION_TO_CONTENT_TYPE = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


def validate_upload(content_type: str, file_size: int) -> str:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Type de fichier non autorise. Utilisez PDF, JPEG ou PNG.")
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError("Fichier trop volumineux (max 5 Mo).")
    return ALLOWED_CONTENT_TYPES[content_type]


def build_fernet(fernet_key: str) -> Fernet:
    try:
        return Fernet(fernet_key.encode())
    except Exception as exc:
        raise ValueError("FERNET_KEY invalide. Generez une cle Fernet valide.") from exc


async def encrypt_and_store_file(
    raw_bytes: bytes,
    content_type: str,
    fernet: Fernet,
    storage_dir: str = "storage/encrypted-results",
) -> str:
    extension = validate_upload(content_type=content_type, file_size=len(raw_bytes))

    encrypted_bytes = fernet.encrypt(raw_bytes)

    # Check if Cloudinary is configured
    from app.config import settings
    if settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret:
        import io
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True
        )

        file_name = f"{uuid.uuid4().hex}{extension}.enc"
        upload_stream = io.BytesIO(encrypted_bytes)

        # Upload to Cloudinary as raw resource type
        res = cloudinary.uploader.upload(
            upload_stream,
            resource_type="raw",
            public_id=f"encrypted-results/{file_name}"
        )
        return res["secure_url"]

    # Fallback to local storage
    os.makedirs(storage_dir, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{extension}.enc"
    output_path = Path(storage_dir) / file_name

    async with aiofiles.open(output_path, "wb") as f:
        await f.write(encrypted_bytes)

    return str(output_path)


def infer_original_extension_from_encrypted_path(encrypted_path: str) -> str:
    # Clean URL path components if present
    clean_path = encrypted_path.split("?")[0].split("#")[0]
    filename = clean_path.split("/")[-1]
    suffixes = Path(filename).suffixes
    if len(suffixes) >= 2 and suffixes[-1] == ".enc":
        return suffixes[-2]
    return ".bin"


def infer_content_type_from_encrypted_path(encrypted_path: str) -> str:
    extension = infer_original_extension_from_encrypted_path(encrypted_path)
    return EXTENSION_TO_CONTENT_TYPE.get(extension.lower(), "application/octet-stream")


def decrypt_file_from_path(encrypted_path: str, fernet: Fernet) -> bytes:
    if encrypted_path.startswith("http://") or encrypted_path.startswith("https://"):
        import httpx
        with httpx.Client() as client:
            resp = client.get(encrypted_path)
            if resp.status_code != 200:
                raise FileNotFoundError("Fichier chiffre introuvable sur Cloudinary")
            encrypted_bytes = resp.content
    else:
        path = Path(encrypted_path)
        if not path.exists():
            raise FileNotFoundError("Fichier chiffre introuvable")
        encrypted_bytes = path.read_bytes()

    return fernet.decrypt(encrypted_bytes)

