"""Small immutable models used by the portrait pipeline.

They describe planned work, saved image metadata, generation results, and the
final collection validation report without mixing those values with provider or
filesystem logic.
"""

from dataclasses import dataclass
from pathlib import Path

from app.schemas import CandidateProfile


@dataclass(frozen=True, slots=True)
class PortraitGenerationJob:
    """One candidate profile, appearance plan, and destination image path."""

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
    """Verified format, dimensions, colour mode, and file size for one portrait."""

    path: Path
    width: int
    height: int
    mode: str
    format: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class PortraitGenerationResult:
    """One completed or skipped portrait job and its attempt count."""

    candidate_id: str
    output_path: Path
    attempts: int
    metadata: PortraitImageMetadata


@dataclass(frozen=True, slots=True)
class PortraitCollectionValidation:
    """Collection report for missing, invalid, or unexpected portrait files."""

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
