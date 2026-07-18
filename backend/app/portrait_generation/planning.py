"""Build and select deterministic candidate portrait-generation jobs."""

from collections.abc import Collection, Sequence
from pathlib import Path

from app.schemas import CandidateProfile

from .models import PortraitGenerationJob
from .prompting import build_portrait_prompt


NORMALIZED_PORTRAIT_EXTENSION = ".webp"


class PortraitGenerationPlanError(ValueError):
    """Raised when portrait paths or CLI selection are inconsistent."""


def build_portrait_generation_jobs(
    profiles: Sequence[CandidateProfile],
    *,
    images_directory: Path,
    portrait_candidate_ids: Collection[str] | None = None,
) -> list[PortraitGenerationJob]:
    """Map validated profiles to prompts and stable WebP output paths."""

    ordered_profiles = sorted(
        profiles,
        key=lambda profile: profile.candidate_id,
    )
    candidate_ids = [profile.candidate_id for profile in ordered_profiles]

    if len(candidate_ids) != len(set(candidate_ids)):
        raise PortraitGenerationPlanError(
            "Candidate profiles contain duplicate candidate IDs."
        )

    planned_ids = (
        set(candidate_ids)
        if portrait_candidate_ids is None
        else set(portrait_candidate_ids)
    )
    unknown_ids = planned_ids.difference(candidate_ids)
    if unknown_ids:
        raise PortraitGenerationPlanError(
            "Portrait plan contains unknown candidate IDs: "
            f"{', '.join(sorted(unknown_ids))}."
        )

    return [
        PortraitGenerationJob(
            profile=profile,
            output_path=(
                images_directory
                / f"{profile.candidate_id}{NORMALIZED_PORTRAIT_EXTENSION}"
            ),
            prompt=build_portrait_prompt(profile),
        )
        for profile in ordered_profiles
        if profile.candidate_id in planned_ids
    ]


def select_portrait_generation_jobs(
    jobs: Sequence[PortraitGenerationJob],
    *,
    candidate_id: str | None,
    count: int | None,
    start_from: str | None,
    select_all: bool,
) -> list[PortraitGenerationJob]:
    """Select one planned portrait, a bounded batch, or all planned portraits."""

    selected_modes = sum(
        mode_selected
        for mode_selected in (
            candidate_id is not None,
            count is not None,
            select_all,
        )
    )
    if selected_modes != 1:
        raise PortraitGenerationPlanError(
            "Choose exactly one of candidate_id, count, or select_all."
        )

    if candidate_id is not None and start_from is not None:
        raise PortraitGenerationPlanError(
            "start_from cannot be combined with candidate_id."
        )

    ordered_jobs = sorted(jobs, key=lambda job: job.candidate_id)
    jobs_by_id = {job.candidate_id: job for job in ordered_jobs}

    if candidate_id is not None:
        try:
            return [jobs_by_id[candidate_id]]
        except KeyError as error:
            raise PortraitGenerationPlanError(
                f"Candidate ID is not selected by the portrait plan: {candidate_id}."
            ) from error

    start_index = 0
    if start_from is not None:
        try:
            start_job = jobs_by_id[start_from]
        except KeyError as error:
            raise PortraitGenerationPlanError(
                "Start candidate ID is not selected by the portrait plan: "
                f"{start_from}."
            ) from error

        start_index = ordered_jobs.index(start_job)

    remaining_jobs = ordered_jobs[start_index:]

    if select_all:
        return remaining_jobs

    assert count is not None
    if count < 1:
        raise PortraitGenerationPlanError("count must be at least 1.")

    selected_jobs = remaining_jobs[:count]
    if len(selected_jobs) < count:
        raise PortraitGenerationPlanError(
            f"Requested {count} portraits, but only {len(remaining_jobs)} "
            "remain from the selected starting point."
        )

    return selected_jobs
