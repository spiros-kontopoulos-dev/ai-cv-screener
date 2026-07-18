"""Tests for portrait decoding, normalization, and collection validation."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.portrait_generation import (
    PortraitImageError,
    inspect_portrait_image,
    normalize_portrait_image,
    validate_portrait_collection,
)
from app.schemas import CandidateProfile


def _gradient_image_bytes(
    *,
    size: tuple[int, int] = (900, 700),
    format_name: str = "PNG",
) -> bytes:
    """Return deterministic non-uniform image bytes for processing tests."""

    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(size[1]):
        for x in range(size[0]):
            pixels[x, y] = (
                x % 256,
                y % 256,
                (x + y) % 256,
            )

    buffer = BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()


def test_normalization_creates_square_rgb_webp(tmp_path: Path) -> None:
    """Provider image formats are normalized to one deterministic contract."""

    output_path = tmp_path / "candidate_001.webp"

    metadata = normalize_portrait_image(
        _gradient_image_bytes(),
        output_path=output_path,
        normalized_size=512,
        webp_quality=88,
    )

    assert metadata.path == output_path
    assert metadata.width == 512
    assert metadata.height == 512
    assert metadata.format == "WEBP"
    assert metadata.size_bytes > 0

    inspected = inspect_portrait_image(
        output_path,
        expected_size=512,
    )
    assert inspected.width == 512


def test_normalization_rejects_unreadable_bytes(tmp_path: Path) -> None:
    """Invalid provider output never replaces a portrait asset."""

    output_path = tmp_path / "candidate_001.webp"

    with pytest.raises(PortraitImageError, match="readable image"):
        normalize_portrait_image(
            b"not an image",
            output_path=output_path,
            normalized_size=512,
            webp_quality=88,
        )

    assert not output_path.exists()


def test_collection_validation_reports_missing_and_unexpected_images(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Profile-image mapping must be complete and contain no wrong assets."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    images_directory = tmp_path / "images"
    images_directory.mkdir()
    (images_directory / "candidate_999.jpg").write_bytes(
        _gradient_image_bytes(format_name="JPEG")
    )

    result = validate_portrait_collection(
        [profile],
        images_directory=images_directory,
        expected_size=512,
    )

    assert result.is_valid is False
    assert result.missing_candidate_ids == ("candidate_001",)
    assert result.unexpected_files == ("candidate_999.jpg",)
