"""Tests for deterministic CV rendering plans and profile measurements."""

from pathlib import Path

import pytest

from app.cv_rendering import (
    CvRenderingPlanError,
    build_cv_render_jobs,
    find_profile_boundaries,
    measure_candidate_profile,
    select_cv_render_jobs,
)
from app.schemas import CandidateProfile


def _candidate_with_id(
    payload: dict,
    *,
    candidate_id: str,
    full_name: str,
    summary_suffix: str = "",
) -> CandidateProfile:
    """Create one independently validated profile for planning tests."""

    copied_payload = CandidateProfile.model_validate(payload).model_dump(
        mode="json"
    )
    copied_payload["candidate_id"] = candidate_id
    copied_payload["full_name"] = full_name
    copied_payload["contact"]["email"] = (
        f"{candidate_id}@example.com"
    )
    copied_payload["summary"] = (
        f"{copied_payload['summary']} {summary_suffix}"
    ).strip()

    return CandidateProfile.model_validate(copied_payload)


def test_build_jobs_uses_stable_candidate_paths_and_order(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Candidate IDs link profiles, portraits, previews, and PDFs."""

    candidate_002 = _candidate_with_id(
        valid_candidate_payload,
        candidate_id="candidate_002",
        full_name="Taylor Reed",
    )
    candidate_001 = _candidate_with_id(
        valid_candidate_payload,
        candidate_id="candidate_001",
        full_name="Alex Morgan",
    )

    jobs = build_cv_render_jobs(
        [candidate_002, candidate_001],
        images_directory=tmp_path / "images",
        pdf_directory=tmp_path / "pdfs",
        html_preview_directory=tmp_path / "html",
    )

    assert [job.candidate_id for job in jobs] == [
        "candidate_001",
        "candidate_002",
    ]
    assert jobs[0].portrait_path.name == "candidate_001.webp"
    assert jobs[0].pdf_path.name == "candidate_001.pdf"
    assert jobs[0].html_preview_path.name == "candidate_001.html"


def test_profile_metrics_capture_rendering_density(
    valid_candidate_payload: dict,
) -> None:
    """Measurements count the sections that affect document length."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)

    metrics = measure_candidate_profile(profile)

    assert metrics.total_text_characters > len(profile.summary)
    assert metrics.work_entries == 1
    assert metrics.work_highlights == 1
    assert metrics.education_entries == 1
    assert metrics.skill_entries == 3
    assert metrics.language_entries == 2


def test_selection_supports_candidate_count_and_starting_point(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """The future renderer can safely test one profile or a small batch."""

    profiles = [
        _candidate_with_id(
            valid_candidate_payload,
            candidate_id=f"candidate_{index:03d}",
            full_name=f"Candidate {index}",
        )
        for index in range(1, 4)
    ]
    jobs = build_cv_render_jobs(
        profiles,
        images_directory=tmp_path / "images",
        pdf_directory=tmp_path / "pdfs",
        html_preview_directory=tmp_path / "html",
    )

    selected = select_cv_render_jobs(
        jobs,
        candidate_id=None,
        count=2,
        start_from="candidate_002",
        select_all=False,
    )

    assert [job.candidate_id for job in selected] == [
        "candidate_002",
        "candidate_003",
    ]


def test_selection_rejects_unknown_candidate(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Developer selection errors fail before any files are written."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    jobs = build_cv_render_jobs(
        [profile],
        images_directory=tmp_path / "images",
        pdf_directory=tmp_path / "pdfs",
        html_preview_directory=tmp_path / "html",
    )

    with pytest.raises(CvRenderingPlanError, match="Unknown candidate ID"):
        select_cv_render_jobs(
            jobs,
            candidate_id="candidate_999",
            count=None,
            start_from=None,
            select_all=False,
        )


def test_boundary_profiles_use_approximate_text_volume(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """The shortest and densest profiles are deterministic sample choices."""

    short_profile = _candidate_with_id(
        valid_candidate_payload,
        candidate_id="candidate_001",
        full_name="Short Profile",
    )
    dense_profile = _candidate_with_id(
        valid_candidate_payload,
        candidate_id="candidate_002",
        full_name="Dense Profile",
        summary_suffix=(
            "Additional detailed delivery evidence for print-layout testing. "
            * 4
        ),
    )
    jobs = build_cv_render_jobs(
        [dense_profile, short_profile],
        images_directory=tmp_path / "images",
        pdf_directory=tmp_path / "pdfs",
        html_preview_directory=tmp_path / "html",
    )

    shortest, densest = find_profile_boundaries(jobs)

    assert shortest.candidate_id == "candidate_001"
    assert densest.candidate_id == "candidate_002"
