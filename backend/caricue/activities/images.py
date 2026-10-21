"""Validation and re-encoding of uploaded question images.

Nothing the browser sends is trusted: the bytes must decode as a real JPEG,
PNG or WebP, the pixel count is bounded before the image is loaded, EXIF
(which can carry GPS positions) is dropped, and the picture is re-encoded at a
sensible size. What gets stored is Pillow's output, never the original upload.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

#: Refuses decompression bombs before pixels are decoded.
MAX_SOURCE_PIXELS = 40_000_000


class ImageRejected(ValueError):
    """The upload is not an acceptable image. The message is safe to show."""


@dataclass
class ProcessedImage:
    content: ContentFile
    extension: str


def process_upload(upload) -> ProcessedImage:
    limits = settings.CARICUE
    max_bytes = limits["MAX_IMAGE_BYTES"]
    max_edge = limits["MAX_IMAGE_EDGE_PX"]

    if upload.size > max_bytes:
        raise ImageRejected(
            f"That image is too large (limit {max_bytes // (1024 * 1024)} MB)."
        )

    raw = upload.read()
    try:
        probe = Image.open(io.BytesIO(raw))
        probe.verify()  # structural check; the image must be reopened after
        image = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageRejected("That file is not a readable image.") from exc

    source_format = (image.format or "").upper()
    if source_format not in ALLOWED_FORMATS:
        raise ImageRejected("Use a JPEG, PNG or WebP image.")
    if image.width * image.height > MAX_SOURCE_PIXELS:
        raise ImageRejected("That image has too many pixels. Please shrink it first.")

    try:
        image.load()
        image = ImageOps.exif_transpose(image)
    except (OSError, SyntaxError, ValueError) as exc:
        raise ImageRejected("That file is not a readable image.") from exc

    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    if source_format == "PNG" or (has_alpha and source_format != "WEBP"):
        image.save(buffer, format="PNG", optimize=True)
        extension = ".png"
    elif source_format == "WEBP":
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(buffer, format="WEBP", quality=85)
        extension = ".webp"
    else:
        image.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)
        extension = ".jpg"

    return ProcessedImage(content=ContentFile(buffer.getvalue()), extension=extension)
