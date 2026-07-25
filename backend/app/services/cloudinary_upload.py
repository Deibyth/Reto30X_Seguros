"""CloudinaryUploadService — Upload audio files to Cloudinary for persistent storage.

Uses the CLOUDINARY_URL environment variable or explicit credentials.
Fails gracefully — never raises, always returns None on error.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy import so missing package doesn't crash unrelated code
_cloudinary_available = False
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api

    _cloudinary_available = True
except ImportError:
    logger.warning("cloudinary package not installed — audio uploads disabled")


def _parse_cloudinary_url(url: str) -> tuple[str, str, str, str] | None:
    """Parse ``cloudinary://api_key:api_secret@cloud_name`` into components.

    Returns ``(cloud_name, api_key, api_secret, cloudinary_url)`` or None.
    """
    match = re.match(
        r"^cloudinary://([^:]+):([^@]+)@(.+)$",
        url,
    )
    if not match:
        return None
    api_key, api_secret, cloud_name = match.groups()
    # Strip trailing slash or path if present
    cloud_name = cloud_name.split("/")[0]
    return cloud_name, api_key, api_secret, url


class CloudinaryUploadService:
    """Uploads local audio files to Cloudinary.

    Usage:
        service = CloudinaryUploadService()
        url = await service.upload_audio("/path/to/file.mp3", "public_id")
        # url -> "https://res.cloudinary.com/..." or None
    """

    def __init__(self, cloudinary_url: str | None = None) -> None:
        self._enabled = False
        if not _cloudinary_available:
            logger.warning("CloudinaryUploadService: cloudinary package not available")
            return

        # Priority: explicit URL > CLOUDINARY_URL env var
        url = cloudinary_url or os.environ.get("CLOUDINARY_URL", "")
        if not url:
            logger.info("CloudinaryUploadService: no CLOUDINARY_URL — disabled")
            return

        parsed = _parse_cloudinary_url(url)
        if not parsed:
            logger.warning("CloudinaryUploadService: invalid CLOUDINARY_URL format")
            return

        cloud_name, api_key, api_secret, _ = parsed
        try:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True,
            )
            # Set env var so cloudinary core can also pick it up
            os.environ.setdefault("CLOUDINARY_URL", url)
            self._enabled = True
            logger.info(
                "CloudinaryUploadService initialized (cloud_name=%s)", cloud_name
            )
        except Exception as exc:
            logger.warning("CloudinaryUploadService: failed to configure: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def upload_audio(
        self,
        local_path: str | Path,
        public_id: str,
        resource_type: str = "auto",
    ) -> str | None:
        """Upload a local audio file to Cloudinary.

        Parameters
        ----------
        local_path : str | Path
            Path to the local audio file.
        public_id : str
            Cloudinary public ID (e.g. the MD5 hash of the text).
        resource_type : str
            Cloudinary resource type — ``"auto"`` (default, auto-detects),
            ``"video"`` (works for audio), ``"image"``, or ``"raw"``.

        Returns
        -------
        str | None
            Secure Cloudinary URL, or None on failure.
        """
        if not self._enabled:
            return None

        local_path = Path(local_path)
        if not local_path.exists():
            logger.warning("Cloudinary upload skipped — file not found: %s", local_path)
            return None

        try:
            result = cloudinary.uploader.upload(
                str(local_path),
                public_id=public_id,
                resource_type=resource_type,
                overwrite=True,
            )
            secure_url: str | None = result.get("secure_url")
            if secure_url:
                logger.info(
                    "Cloudinary upload OK: %s -> %s (bytes=%s)",
                    public_id,
                    secure_url,
                    result.get("bytes"),
                )
                return secure_url

            logger.warning("Cloudinary upload OK but no secure_url in response")
            return None
        except Exception as exc:
            logger.warning("Cloudinary upload failed for %s: %s", public_id, exc)
            return None
