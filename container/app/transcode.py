"""Image sniffing and webp -> JPEG conversion for l3."""

from __future__ import annotations

from pathlib import Path

IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "heic": "image/heic",
    "avif": "image/avif",
}

_EXT_ALIASES = {"jpeg": "jpg", "jpe": "jpg"}


class TranscodeFailed(Exception):
    """Pillow could not decode or re-encode the downloaded image."""


def magic_head(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            return handle.read(12)
    except OSError:
        return b""


def is_webp(head: bytes) -> bool:
    return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def to_jpeg(source: Path, dest: Path) -> None:
    from PIL import Image

    try:
        with Image.open(source) as image:
            image.convert("RGB").save(dest, "JPEG", quality=90)
    except Exception as exc:  # noqa: BLE001 - Pillow surfaces many types
        raise TranscodeFailed("图片转码失败") from exc


def normal_image_ext(declared: str, head: bytes) -> str:
    ext = _EXT_ALIASES.get(declared, declared)
    if ext in IMAGE_TYPES:
        return ext
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if is_webp(head):
        return "webp"
    return "jpg"
