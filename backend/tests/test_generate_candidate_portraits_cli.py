"""Tests for the WP4 candidate portrait-generation command."""

from io import BytesIO
from pathlib import Path

from PIL import Image

from app.candidate_generation.persistence import save_candidate_profiles
from app.core.config import Settings
from app.schemas import CandidateProfile
from app.scripts.generate_candidate_portraits import run_cli


def _settings(tmp_path: Path, profiles_path: Path) -> Settings:
    return Settings(
        openai_api_key="test-key",
        candidate_profiles_output_path=profiles_path,
        candidate_images_directory=tmp_path / "images",
        portrait_normalized_size=512,
        portrait_webp_quality=88,
    )


def _image_bytes() -> bytes:
    image = Image.effect_noise((700, 700), 50).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, *, candidate_id: str) -> bytes:
        self.calls += 1
        return _image_bytes()


def test_dry_run_prints_prompt_plan_without_provider(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Dry-run mode does not require a key or create image files."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])
    settings = Settings(
        candidate_profiles_output_path=profiles_path,
        candidate_images_directory=tmp_path / "images",
    )

    status = run_cli(
        ["--all", "--dry-run", "--show-prompts"],
        settings=settings,
        provider_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("provider should not be created")
        ),
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "CANDIDATE PORTRAIT GENERATION DRY RUN" in captured.out
    assert "candidate_001.webp" in captured.out
    assert "completely fictional adult" in captured.out
    assert not (tmp_path / "images").exists()


def test_real_generation_saves_normalized_portrait_and_resume_skips_it(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """A valid existing WebP resumes without another provider request."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    profiles_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(profiles_path, [profile])
    settings = _settings(tmp_path, profiles_path)
    provider = _Provider()

    first_status = run_cli(
        ["--all"],
        settings=settings,
        provider_factory=lambda _: provider,
    )
    second_status = run_cli(
        ["--all"],
        settings=settings,
        provider_factory=lambda _: provider,
    )

    captured = capsys.readouterr()
    assert first_status == 0
    assert second_status == 0
    assert provider.calls == 1
    assert (tmp_path / "images" / "candidate_001.webp").is_file()
    assert "Skipped existing: 1" in captured.out
