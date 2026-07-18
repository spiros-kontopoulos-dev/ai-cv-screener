"""Bounded portrait provider retries and normalized image persistence."""

from typing import Protocol

from .client import PortraitProviderError
from .images import PortraitImageError, normalize_portrait_image
from .models import PortraitGenerationJob, PortraitGenerationResult


class PortraitImageProvider(Protocol):
    """Small provider contract used by orchestration and deterministic tests."""

    def generate(self, prompt: str, *, candidate_id: str) -> bytes:
        """Generate raw image bytes for one fictional portrait."""

        ...


class PortraitGenerationFailed(RuntimeError):
    """Raised after a non-retryable error or exhausted retry budget."""

    def __init__(
        self,
        *,
        candidate_id: str,
        attempts: int,
        reason: str,
    ) -> None:
        self.candidate_id = candidate_id
        self.attempts = attempts
        self.reason = reason
        super().__init__(
            f"{candidate_id} failed after {attempts} attempt(s): {reason}"
        )


def generate_portrait_with_retries(
    job: PortraitGenerationJob,
    *,
    provider: PortraitImageProvider,
    max_retries: int,
    normalized_size: int,
    webp_quality: int,
) -> PortraitGenerationResult:
    """Generate and normalize one portrait within a fixed retry budget."""

    total_attempts = max_retries + 1

    for attempt_number in range(1, total_attempts + 1):
        try:
            image_bytes = provider.generate(
                job.prompt,
                candidate_id=job.candidate_id,
            )
            metadata = normalize_portrait_image(
                image_bytes,
                output_path=job.output_path,
                normalized_size=normalized_size,
                webp_quality=webp_quality,
            )
        except PortraitProviderError as error:
            if not error.retryable or attempt_number == total_attempts:
                raise PortraitGenerationFailed(
                    candidate_id=job.candidate_id,
                    attempts=attempt_number,
                    reason=str(error),
                ) from error
            continue
        except PortraitImageError as error:
            if attempt_number == total_attempts:
                raise PortraitGenerationFailed(
                    candidate_id=job.candidate_id,
                    attempts=attempt_number,
                    reason=str(error),
                ) from error
            continue

        return PortraitGenerationResult(
            candidate_id=job.candidate_id,
            output_path=job.output_path,
            attempts=attempt_number,
            metadata=metadata,
        )

    raise RuntimeError("Portrait generation ended without a result.")
