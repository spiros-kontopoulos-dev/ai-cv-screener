"""Immutable data passed through the CV rendering pipeline.

These models keep planning separate from rendering. A job contains one validated
profile and all of its stable artifact paths. A result contains the verified
HTML/PDF output details.
"""

from dataclasses import dataclass
from pathlib import Path

from app.schemas import CandidateProfile


@dataclass(frozen=True, slots=True)
class CvProfileMetrics:
    """Simple content measurements used to find short and dense CV examples."""

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
    """One validated profile and every path needed to render its CV."""

    profile: CandidateProfile
    portrait_path: Path
    portrait_planned: bool
    pdf_path: Path
    html_preview_path: Path
    metrics: CvProfileMetrics

    @property
    def candidate_id(self) -> str:
        """Expose the stable identifier carried through every pipeline stage."""

        return self.profile.candidate_id

    @property
    def portrait_exists(self) -> bool:
        """Return whether the expected normalized portrait is available."""

        return self.portrait_path.is_file()


@dataclass(frozen=True, slots=True)
class CvRenderResult:
    """Verified page count, text size, portrait state, and output paths for one CV."""

    candidate_id: str
    pdf_path: Path
    html_preview_path: Path | None
    page_count: int
    extracted_text_characters: int
    portrait_planned: bool
    used_placeholder_portrait: bool
