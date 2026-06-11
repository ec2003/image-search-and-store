from dataclasses import dataclass
from io import BytesIO

from django.conf import settings


CONTENT_TYPES_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class ImageInfo:
    content_type: str
    width: int
    height: int


def inspect_image(content: bytes) -> ImageInfo:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            content_type = CONTENT_TYPES_BY_FORMAT.get(image.format or "")
            if content_type not in settings.IMAGE_ALLOWED_CONTENT_TYPES:
                raise ValueError("Unsupported image format.")
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise ValueError("Uploaded object is not a readable image.") from exc

    return ImageInfo(content_type=content_type, width=width, height=height)


def create_thumbnail(content: bytes, *, max_size: tuple[int, int] = (512, 512)) -> bytes:
    from PIL import Image

    with Image.open(BytesIO(content)) as image:
        image.thumbnail(max_size)
        output = BytesIO()
        image.convert("RGB").save(output, format="WEBP", quality=82)
        return output.getvalue()
