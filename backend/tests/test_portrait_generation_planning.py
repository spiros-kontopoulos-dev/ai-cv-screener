"""Tests for deterministic portrait prompts and generation plans."""

from pathlib import Path

import pytest

from app.portrait_generation import (
    PortraitGenerationPlanError,
    build_portrait_generation_jobs,
    build_portrait_prompt,
    select_portrait_generation_jobs,
)
from app.schemas import CandidateProfile


def test_portrait_prompt_is_fictional_professional_and_avoids_caption_layouts(
    valid_candidate_payload: dict,
) -> None:
    """The prompt excludes identity text and rejects document-style overlays."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)

    prompt = build_portrait_prompt(profile)

    # Identity values are intentionally kept out of the image prompt because
    # image models may render them as nameplates or lower-third captions.
    assert "Alex Morgan" not in prompt
    assert "Senior Python Backend Engineer" not in prompt
    assert "Athens, Greece" not in prompt

    assert "completely fictional adult professional" in prompt
    assert "Output only the portrait photograph itself" in prompt
    assert "photograph must fill the entire canvas from edge to edge" in prompt
    assert "Do not create a CV, resume, profile card, ID card" in prompt
    assert "lower third, caption strip, banner, footer" in prompt
    assert "Do not include any text, letters, words, captions, names" in prompt
    assert "Return only the uninterrupted photograph" in prompt
    assert "Do not depict or imitate any real person" in prompt


def test_portrait_jobs_use_stable_webp_paths_and_ordering(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Candidate IDs provide deterministic prompt-to-image mapping."""

    second_payload = {
        **valid_candidate_payload,
        "candidate_id": "candidate_002",
        "full_name": "Jordan Lee",
        "contact": {
            **valid_candidate_payload["contact"],
            "email": "jordan.lee@example.com",
        },
    }
    profiles = [
        CandidateProfile.model_validate(second_payload),
        CandidateProfile.model_validate(valid_candidate_payload),
    ]

    jobs = build_portrait_generation_jobs(
        profiles,
        images_directory=tmp_path / "images",
    )

    assert [job.candidate_id for job in jobs] == [
        "candidate_001",
        "candidate_002",
    ]
    assert jobs[0].output_path.name == "candidate_001.webp"
    assert jobs[1].output_path.name == "candidate_002.webp"


def test_portrait_job_selection_supports_resume_batches(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """A count can begin from one later stable candidate ID."""

    profiles = []
    for number in range(1, 4):
        payload = {
            **valid_candidate_payload,
            "candidate_id": f"candidate_{number:03d}",
            "full_name": f"Candidate Number {number}",
            "contact": {
                **valid_candidate_payload["contact"],
                "email": f"candidate{number}@example.com",
            },
        }
        profiles.append(CandidateProfile.model_validate(payload))

    jobs = build_portrait_generation_jobs(
        profiles,
        images_directory=tmp_path / "images",
    )

    selected = select_portrait_generation_jobs(
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


def test_portrait_selection_rejects_unknown_candidate(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Selection errors identify invalid stable candidate IDs."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    jobs = build_portrait_generation_jobs(
        [profile],
        images_directory=tmp_path / "images",
    )

    with pytest.raises(PortraitGenerationPlanError, match="candidate_999"):
        select_portrait_generation_jobs(
            jobs,
            candidate_id="candidate_999",
            count=None,
            start_from=None,
            select_all=False,
        )


def test_portrait_jobs_include_only_coverage_plan_candidates(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """The generation queue excludes intentionally photo-free candidates."""

    second_payload = {
        **valid_candidate_payload,
        "candidate_id": "candidate_002",
        "full_name": "Jordan Lee",
        "contact": {
            **valid_candidate_payload["contact"],
            "email": "jordan.lee@example.com",
        },
    }
    profiles = [
        CandidateProfile.model_validate(valid_candidate_payload),
        CandidateProfile.model_validate(second_payload),
    ]

    jobs = build_portrait_generation_jobs(
        profiles,
        images_directory=tmp_path / "images",
        portrait_candidate_ids={"candidate_002"},
    )

    assert [job.candidate_id for job in jobs] == ["candidate_002"]
