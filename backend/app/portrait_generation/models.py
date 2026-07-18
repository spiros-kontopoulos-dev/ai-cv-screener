"""Typed models for fictional candidate portrait generation."""

from dataclasses import dataclass
from pathlib import Path

from app.schemas import CandidateProfile


@dataclass(frozen=True, slots=True)
class PortraitGenerationJob:
    """One deterministic portrait request and its normalized output path."""

    profile: CandidateProfile
    output_path: Path
    prompt: str

    @property
    def candidate_id(self) -> str:
        """Return the stable candidate identifier used by every artifact."""

        return self.profile.candidate_id

    @property
    def portrait_exists(self) -> bool:
        """Return whether the normalized WebP portrait already exists."""

        return self.output_path.is_file()


@dataclass(frozen=True, slots=True)
class PortraitImageMetadata:
    """Verified properties of one normalized portrait file."""

    path: Path
    width: int
    height: int
    mode: str
    format: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class PortraitGenerationResult:
    """Successful generation details for one candidate portrait."""

    candidate_id: str
    output_path: Path
    attempts: int
    metadata: PortraitImageMetadata


@dataclass(frozen=True, slots=True)
class PortraitCollectionValidation:
    """Collection-level profile-to-portrait validation summary."""

    expected_count: int
    valid_count: int
    missing_candidate_ids: tuple[str, ...]
    invalid_portraits: tuple[str, ...]
    unexpected_files: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return whether the complete portrait collection is usable."""

        return not (
            self.missing_candidate_ids
            or self.invalid_portraits
            or self.unexpected_files
        ) and self.valid_count == self.expected_count
