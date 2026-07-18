"""Tests for complete portrait collection validation reporting."""

from io import BytesIO
from pathlib import Path

from PIL import Image

from app.candidate_generation.persistence import save_candidate_profiles
from app.core.config import Settings
from app.portrait_generation import normalize_portrait_image
from app.schemas import CandidateProfile
from app.scripts.validate_candidate_portraits import run_cli


def _image_bytes() -> bytes:
    image = Image.effect_noise((700, 700), 50).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_validation_passes_for_complete_normalized_collection(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """One valid WebP per profile produces a passing report."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    images_directory = tmp_path / "images"
    save_candidate_profiles(profiles_path, [profile])
    normalize_portrait_image(
        _image_bytes(),
        output_path=images_directory / "candidate_001.webp",
        normalized_size=512,
        webp_quality=88,
    )

    status = run_cli(
        settings=Settings(
            candidate_profiles_output_path=profiles_path,
            candidate_images_directory=images_directory,
            portrait_normalized_size=512,
        )
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "Valid portraits: 1" in captured.out
    assert "Result: PASS" in captured.out


def test_validation_fails_for_missing_portrait(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Missing candidate assets produce a clear failing report."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])

    status = run_cli(
        settings=Settings(
            candidate_profiles_output_path=profiles_path,
            candidate_images_directory=tmp_path / "images",
        )
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "candidate_001" in captured.out
    assert "Result: FAIL" in captured.out
