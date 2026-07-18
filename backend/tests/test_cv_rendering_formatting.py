"""Tests for human-readable values used by the Jinja CV template."""

import pytest

from app.cv_rendering import (
    CvFormattingError,
    candidate_initials,
    format_education_year_range,
    format_skill_years,
    format_work_date_range,
    format_year_month,
    format_years_of_experience,
    group_skills,
)
from app.schemas import CandidateProfile


def test_date_helpers_render_cv_friendly_ranges() -> None:
    """Machine-friendly dates become concise, readable CV labels."""

    assert format_year_month("2023-01") == "Jan 2023"
    assert format_work_date_range("2021-04", None) == (
        "Apr 2021 - Present"
    )
    assert format_work_date_range("2018-07", "2021-03") == (
        "Jul 2018 - Mar 2021"
    )
    assert format_education_year_range(2010, 2014) == "2010 - 2014"


def test_invalid_year_month_raises_domain_error() -> None:
    """Template helpers fail clearly if an invalid value bypasses schema checks."""

    with pytest.raises(CvFormattingError, match="Expected a YYYY-MM date"):
        format_year_month("January 2024")


def test_experience_and_initials_are_compact() -> None:
    """Header and skill labels avoid unnecessary decimal noise."""

    assert format_years_of_experience(8.0) == "8 years"
    assert format_years_of_experience(1.0) == "1 year"
    assert format_years_of_experience(4.5) == "4.5 years"
    assert format_skill_years(7.0) == "7y"
    assert format_skill_years(None) is None
    assert candidate_initials("Alex Morgan") == "AM"
    assert candidate_initials("Sofia Maria Petrou") == "SM"


def test_skills_are_grouped_without_losing_validated_objects(
    valid_candidate_payload: dict,
) -> None:
    """Category grouping preserves source order and skill evidence."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)

    groups = group_skills(profile.skills)

    assert [group["label"] for group in groups] == [
        "Programming Languages",
        "Frameworks",
        "Databases",
    ]
    assert groups[0]["skills"][0].name == "Python"
