"""Tests for the final JSON-to-PDF searchable-fact boundary."""

from pathlib import Path

import pymupdf

from app.candidate_generation import (
    CandidateDatasetPlan,
    load_candidate_dataset_plan,
    load_candidate_profiles,
)
from app.cv_ingestion import build_readable_cv_filename_from_metadata
from app.cv_rendering import (
    ExtractedCvDocument,
    build_cv_render_jobs,
    render_cv_job,
    validate_cv_pdf_collection,
    validate_profile_against_pdf_text,
)
from app.schemas import CandidateProfile


_BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_PLAN_PATH = _BACKEND_DIRECTORY / "app" / "dataset" / "candidate_dataset_plan.json"


def test_committed_pdf_collection_preserves_all_facts_and_scenarios() -> None:
    """The final 30 PDFs preserve every rendered fact and demo scenario."""

    data_directory = _resolve_committed_data_directory()
    plan = load_candidate_dataset_plan(_PLAN_PATH)
    profiles = load_candidate_profiles(
        data_directory / "candidate_profiles" / "candidate_profiles.json"
    )

    report = validate_cv_pdf_collection(
        plan,
        profiles,
        pdf_directory=data_directory / "cv_pdfs",
    )

    assert report.is_valid
    assert report.actual_pdf_count == 30
    assert report.validated_pdf_count == 30
    assert report.validated_fact_count == report.expected_fact_count
    assert report.expected_fact_count > 2000
    assert report.validated_scenario_count == 11


def test_real_rendered_pdf_passes_single_profile_validation(
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """A real Jinja and WeasyPrint output passes the fact validator."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    jobs = build_cv_render_jobs(
        [profile],
        images_directory=tmp_path / "images",
        html_preview_directory=tmp_path / "html",
        pdf_directory=tmp_path / "pdfs",
    )
    render_cv_job(jobs[0], keep_html=False)

    report = validate_cv_pdf_collection(
        _single_profile_plan(profile),
        [profile],
        pdf_directory=tmp_path / "pdfs",
    )

    assert report.is_valid
    assert report.validated_pdf_count == 1
    assert report.validated_fact_count == report.expected_fact_count


def test_validation_reports_missing_searchable_facts(
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """A text PDF with only identity data fails the complete fact contract."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    pdf_path = tmp_path / "candidate_001.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "candidate_001 Eleni Markou")
        document.save(pdf_path)

    with pymupdf.open(pdf_path) as document:
        text = "\n".join(page.get_text("text", sort=True) for page in document)
        page_count = document.page_count

    result = validate_profile_against_pdf_text(
        profile,
        ExtractedCvDocument(
            candidate_id=profile.candidate_id,
            path=pdf_path,
            page_count=page_count,
            text=text,
        ),
    )

    assert not result.is_valid
    assert result.validated_fact_count < result.expected_fact_count
    assert any("professional title" in issue for issue in result.missing_facts)
    assert any("skill Python" in issue for issue in result.missing_facts)


def test_collection_reports_missing_and_unexpected_pdf_names(
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """The collection boundary rejects gaps and stale PDF artifacts."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    pdf_directory = tmp_path / "pdfs"
    pdf_directory.mkdir()
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf_directory / "candidate_999.pdf")

    report = validate_cv_pdf_collection(
        _single_profile_plan(profile),
        [profile],
        pdf_directory=pdf_directory,
    )

    assert not report.is_valid
    assert report.missing_pdf_names == (
        build_readable_cv_filename_from_metadata(
            candidate_name=profile.full_name,
            professional_title=profile.professional_title,
            source_label=profile.candidate_id,
        ),
    )
    assert report.unexpected_pdf_names == ("candidate_999.pdf",)


def _resolve_committed_data_directory() -> Path:
    """Resolve shared data in Docker and direct host test layouts."""

    candidates = (
        _BACKEND_DIRECTORY / "data",
        _BACKEND_DIRECTORY.parent / "data",
    )
    for candidate in candidates:
        if (
            candidate
            / "candidate_profiles"
            / "candidate_profiles.json"
        ).is_file():
            return candidate

    checked_paths = ", ".join(str(path) for path in candidates)
    raise AssertionError(
        "Committed candidate data was not found. "
        f"Checked: {checked_paths}."
    )


def _single_profile_plan(profile: CandidateProfile) -> CandidateDatasetPlan:
    """Create the smallest valid plan for isolated collection tests."""

    return CandidateDatasetPlan.model_validate(
        {
            "dataset_version": 1,
            "candidate_count": 1,
            "purpose": "Validate one rendered fictional candidate CV.",
            "fictional_data_policy": {"all_data_is_fictional": True},
            "generation_rules": {"render_visible_pdf_text": True},
            "distributions": {
                "profession": {profile.profession.value: 1},
            },
            "search_scenarios": [
                {
                    "scenario_id": "single_python_candidate",
                    "question": "Which candidate has Python experience?",
                    "expected_candidate_ids": [profile.candidate_id],
                    "required_evidence": ["Python"],
                    "answer_behavior": "Return the candidate with PDF evidence.",
                }
            ],
            "candidates": [
                {
                    "candidate_id": profile.candidate_id,
                    "full_name": profile.full_name,
                    "professional_title": profile.professional_title,
                    "profession": profile.profession.value,
                    "seniority": profile.seniority.value,
                    "country": profile.contact.country,
                    "city": profile.contact.city,
                    "languages": [
                        language.model_dump(mode="json")
                        for language in profile.languages
                    ],
                    "required_skills": [
                        skill.name for skill in profile.skills
                    ],
                    "certification": None,
                    "leadership_team_size": 5,
                    "required_education": None,
                    "required_project": None,
                    "known_facts": [
                        "Has professional Python experience.",
                        "Has a visible employment history.",
                        "Has visible contact information.",
                    ],
                    "demo_tags": ["single_profile"],
                }
            ],
        }
    )
