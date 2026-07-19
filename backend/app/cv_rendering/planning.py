"""Prepare deterministic jobs for candidate CV rendering.

This module is intentionally independent from Jinja and WeasyPrint.  It proves
that the validated profile collection can be selected, measured, and mapped to
stable portrait, HTML-preview, and PDF paths before any visual rendering starts.
"""

from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

from app.cv_ingestion.naming import (
    CvDocumentNamingError,
    build_readable_cv_filename_from_metadata,
)
from app.cv_rendering.models import CvProfileMetrics, CvRenderJob
from app.schemas import CandidateProfile


# Portrait generation may initially produce PNG files, but WP4 will normalize
# every accepted asset to one predictable format before the final PDF batch.
NORMALIZED_PORTRAIT_EXTENSION = ".webp"


class CvRenderingPlanError(ValueError):
    """Raised when profiles cannot be mapped to a valid rendering plan."""


def measure_candidate_profile(profile: CandidateProfile) -> CvProfileMetrics:
    """Return deterministic size measurements for one validated profile.

    ``total_text_characters`` is an approximation based on all string values in
    the profile.  It is useful for locating boundary cases, but the generated
    PDF remains the final authority for page count and overflow decisions.
    """

    serialized_profile = profile.model_dump(mode="json")

    return CvProfileMetrics(
        total_text_characters=_count_text_characters(serialized_profile),
        work_entries=len(profile.work_experience),
        work_highlights=sum(
            len(experience.highlights)
            for experience in profile.work_experience
        ),
        education_entries=len(profile.education),
        skill_entries=len(profile.skills),
        language_entries=len(profile.languages),
        certification_entries=len(profile.certifications),
        project_entries=len(profile.projects),
    )


def build_cv_render_jobs(
    profiles: Sequence[CandidateProfile],
    *,
    images_directory: Path,
    pdf_directory: Path,
    html_preview_directory: Path,
    portrait_candidate_ids: Collection[str] | None = None,
) -> list[CvRenderJob]:
    """Map every validated profile to stable rendering artifact paths.

    Jobs are always returned in candidate-ID order.  Duplicate IDs are rejected
    defensively even though the WP3 collection validator already checks them.
    """

    ordered_profiles = sorted(
        profiles,
        key=lambda profile: profile.candidate_id,
    )
    candidate_ids = [profile.candidate_id for profile in ordered_profiles]

    if len(candidate_ids) != len(set(candidate_ids)):
        raise CvRenderingPlanError(
            "Candidate profiles must have unique candidate IDs before "
            "CV rendering."
        )

    planned_ids = (
        set(candidate_ids)
        if portrait_candidate_ids is None
        else set(portrait_candidate_ids)
    )
    unknown_planned_ids = planned_ids.difference(candidate_ids)
    if unknown_planned_ids:
        raise CvRenderingPlanError(
            "Portrait plan contains unknown candidate IDs: "
            f"{', '.join(sorted(unknown_planned_ids))}."
        )

    jobs: list[CvRenderJob] = []
    for profile in ordered_profiles:
        try:
            pdf_filename = build_readable_cv_filename_from_metadata(
                candidate_name=profile.full_name,
                professional_title=profile.professional_title,
                source_label=profile.candidate_id,
            )
        except CvDocumentNamingError as error:
            raise CvRenderingPlanError(str(error)) from error

        jobs.append(
            CvRenderJob(
                profile=profile,
                portrait_path=(
                    images_directory
                    / f"{profile.candidate_id}{NORMALIZED_PORTRAIT_EXTENSION}"
                ),
                portrait_planned=profile.candidate_id in planned_ids,
                pdf_path=pdf_directory / pdf_filename,
                html_preview_path=(
                    html_preview_directory / f"{profile.candidate_id}.html"
                ),
                metrics=measure_candidate_profile(profile),
            )
        )

    _validate_unique_pdf_paths(jobs)
    return jobs


def select_cv_render_jobs(
    jobs: Sequence[CvRenderJob],
    *,
    candidate_id: str | None,
    count: int | None,
    start_from: str | None,
    select_all: bool,
) -> list[CvRenderJob]:
    """Select one candidate, a bounded sequence, or the complete collection."""

    selected_modes = sum(
        mode_selected
        for mode_selected in (
            candidate_id is not None,
            count is not None,
            select_all,
        )
    )
    if selected_modes != 1:
        raise CvRenderingPlanError(
            "Choose exactly one of candidate_id, count, or select_all."
        )

    if candidate_id is not None and start_from is not None:
        raise CvRenderingPlanError(
            "start_from cannot be combined with candidate_id."
        )

    ordered_jobs = sorted(jobs, key=lambda job: job.candidate_id)
    jobs_by_id = {job.candidate_id: job for job in ordered_jobs}

    if candidate_id is not None:
        try:
            return [jobs_by_id[candidate_id]]
        except KeyError as error:
            raise CvRenderingPlanError(
                f"Unknown candidate ID: {candidate_id}."
            ) from error

    start_index = 0
    if start_from is not None:
        try:
            start_job = jobs_by_id[start_from]
        except KeyError as error:
            raise CvRenderingPlanError(
                f"Unknown start candidate ID: {start_from}."
            ) from error

        start_index = ordered_jobs.index(start_job)

    remaining_jobs = ordered_jobs[start_index:]

    if select_all:
        return remaining_jobs

    assert count is not None
    if count < 1:
        raise CvRenderingPlanError("count must be at least 1.")

    selected_jobs = remaining_jobs[:count]
    if len(selected_jobs) < count:
        raise CvRenderingPlanError(
            f"Requested {count} CVs, but only {len(remaining_jobs)} remain "
            "from the selected starting point."
        )

    return selected_jobs


def find_profile_boundaries(
    jobs: Sequence[CvRenderJob],
) -> tuple[CvRenderJob, CvRenderJob]:
    """Return the shortest and densest jobs by approximate text volume."""

    if not jobs:
        raise CvRenderingPlanError(
            "At least one candidate profile is required for CV rendering."
        )

    shortest = min(
        jobs,
        key=lambda job: (
            job.metrics.total_text_characters,
            job.candidate_id,
        ),
    )
    densest = max(
        jobs,
        key=lambda job: (
            job.metrics.total_text_characters,
            job.candidate_id,
        ),
    )

    return shortest, densest


def _count_text_characters(value: Any) -> int:
    """Recursively count string characters in a serialized profile value."""

    if isinstance(value, str):
        return len(value)

    if isinstance(value, dict):
        return sum(
            _count_text_characters(nested_value)
            for nested_value in value.values()
        )

    if isinstance(value, list):
        return sum(_count_text_characters(item) for item in value)

    return 0


def _validate_unique_pdf_paths(jobs: Sequence[CvRenderJob]) -> None:
    """Reject profiles that collapse to the same readable PDF filename."""

    jobs_by_path: dict[str, CvRenderJob] = {}
    for job in jobs:
        normalized_path = job.pdf_path.as_posix().casefold()
        existing_job = jobs_by_path.get(normalized_path)
        if existing_job is not None:
            raise CvRenderingPlanError(
                "Readable CV filenames must be unique. "
                f"{existing_job.candidate_id} and {job.candidate_id} both map "
                f"to {job.pdf_path.name}."
            )
        jobs_by_path[normalized_path] = job
