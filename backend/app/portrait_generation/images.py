"""Normalize and validate generated portrait image files."""

from io import BytesIO
from os import replace
from pathlib import Path

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

from .models import PortraitImageMetadata


class PortraitImageError(RuntimeError):
    """Raised when provider bytes cannot become a usable portrait asset."""


def normalize_portrait_image(
    image_bytes: bytes,
    *,
    output_path: Path,
    normalized_size: int,
    webp_quality: int,
) -> PortraitImageMetadata:
    """Decode, crop, resize, and atomically save one RGB WebP portrait."""

    if not image_bytes:
        raise PortraitImageError("Generated portrait image data is empty.")

    try:
        with Image.open(BytesIO(image_bytes)) as source_image:
            transposed = ImageOps.exif_transpose(source_image)
            if min(transposed.size) < 256:
                raise PortraitImageError(
                    "Generated portrait is smaller than 256 pixels."
                )

            rgb_image = transposed.convert("RGB")
            normalized = ImageOps.fit(
                rgb_image,
                (normalized_size, normalized_size),
                method=Image.Resampling.LANCZOS,
                # Slightly favour the upper half so a square crop is less
                # likely to cut off hair while keeping shoulders visible.
                centering=(0.5, 0.44),
            )
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise PortraitImageError(
            "Generated portrait data is not a readable image."
        ) from error

    _validate_visual_variation(normalized)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.stem}.tmp{output_path.suffix}"
    )

    try:
        normalized.save(
            temporary_path,
            format="WEBP",
            quality=webp_quality,
            method=6,
        )
        replace(temporary_path, output_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise PortraitImageError(
            f"Normalized portrait could not be written: {output_path}"
        ) from error

    return inspect_portrait_image(
        output_path,
        expected_size=normalized_size,
    )


def inspect_portrait_image(
    path: Path,
    *,
    expected_size: int,
) -> PortraitImageMetadata:
    """Open one saved portrait and verify its normalized contract."""

    if not path.is_file():
        raise PortraitImageError(f"Portrait file does not exist: {path}")

    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            image_format = image.format or ""
            mode = image.mode
            rgb_image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise PortraitImageError(
            f"Portrait file is not a readable image: {path}"
        ) from error

    if image_format.upper() != "WEBP":
        raise PortraitImageError(
            f"Portrait must be WebP, received {image_format or 'unknown'}: "
            f"{path}"
        )

    if (width, height) != (expected_size, expected_size):
        raise PortraitImageError(
            "Portrait dimensions must be "
            f"{expected_size}x{expected_size}, received {width}x{height}: "
            f"{path}"
        )

    _validate_visual_variation(rgb_image)

    return PortraitImageMetadata(
        path=path,
        width=width,
        height=height,
        mode=mode,
        format=image_format.upper(),
        size_bytes=path.stat().st_size,
    )


def _validate_visual_variation(image: Image.Image) -> None:
    """Reject blank or nearly uniform provider output before persistence."""

    statistics = ImageStat.Stat(image.resize((64, 64)))
    if sum(statistics.var) < 25:
        raise PortraitImageError(
            "Generated portrait is blank or has insufficient visual detail."
        )
