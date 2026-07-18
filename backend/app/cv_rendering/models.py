"""Typed planning contracts for deterministic CV rendering.

WP4 converts validated ``CandidateProfile`` objects into visual assets.  These
small immutable data classes describe the work that will be performed without
mixing filesystem planning with the later Jinja and WeasyPrint implementation.
"""

from dataclasses import dataclass
from pathlib import Path

from app.schemas import CandidateProfile


@dataclass(frozen=True, slots=True)
class CvProfileMetrics:
    """Approximate content-density measurements for one candidate profile.

    The metrics do not remove or rewrite candidate content.  They help us pick
    representative short and dense profiles for template testing and will later
    support conservative CSS density classes when a CV needs tighter spacing.
    """

    total_text_characters: int
    work_entries: int
    work_highlights: int
    education_entries: int
    skill_entries: int
    language_entries: int
    certification_entries: int
    project_entries: int


@dataclass(frozen=True, slots=True)
class CvRenderJob:
    """All deterministic paths and source data for rendering one CV."""

    profile: CandidateProfile
    portrait_path: Path
    pdf_path: Path
    html_preview_path: Path
    metrics: CvProfileMetrics

    @property
    def candidate_id(self) -> str:
        """Expose the stable identifier used by every generated artifact."""

        return self.profile.candidate_id

    @property
    def portrait_exists(self) -> bool:
        """Return whether the expected normalized portrait is available."""

        return self.portrait_path.is_file()


@dataclass(frozen=True, slots=True)
class CvRenderResult:
    """Verified output metadata for one rendered candidate CV."""

    candidate_id: str
    pdf_path: Path
    html_preview_path: Path | None
    page_count: int
    extracted_text_characters: int
    used_placeholder_portrait: bool
