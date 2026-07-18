"""Tests for bounded portrait retries and normalized persistence."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.portrait_generation import (
    PortraitGenerationFailed,
    PortraitProviderError,
    build_portrait_generation_jobs,
    generate_portrait_with_retries,
)
from app.schemas import CandidateProfile


def _image_bytes() -> bytes:
    image = Image.effect_noise((700, 700), 50).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _SequenceProvider:
    """Return configured failures or byte payloads in order."""

    def __init__(self, responses: list[bytes | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def generate(self, prompt: str, *, candidate_id: str) -> bytes:
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


def _job(
    tmp_path: Path,
    valid_candidate_payload: dict,
):
    profile = CandidateProfile.model_validate(valid_candidate_payload)
    return build_portrait_generation_jobs(
        [profile],
        images_directory=tmp_path / "images",
    )[0]


def test_generation_retries_provider_failure_then_saves_webp(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """A transient API error shares one bounded retry budget."""

    provider = _SequenceProvider(
        [
            PortraitProviderError("temporary", retryable=True),
            _image_bytes(),
        ]
    )

    result = generate_portrait_with_retries(
        _job(tmp_path, valid_candidate_payload),
        provider=provider,
        max_retries=2,
        normalized_size=512,
        webp_quality=88,
    )

    assert result.attempts == 2
    assert result.output_path.is_file()
    assert result.metadata.format == "WEBP"


def test_generation_stops_on_non_retryable_provider_failure(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Permanent provider errors do not consume unnecessary requests."""

    provider = _SequenceProvider(
        [PortraitProviderError("rejected", retryable=False)]
    )

    with pytest.raises(PortraitGenerationFailed) as captured:
        generate_portrait_with_retries(
            _job(tmp_path, valid_candidate_payload),
            provider=provider,
            max_retries=2,
            normalized_size=512,
            webp_quality=88,
        )

    assert captured.value.attempts == 1
    assert provider.calls == 1
