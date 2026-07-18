"""Deterministic checks between a generated profile and its plan slot.

Pydantic validates the general CandidateProfile contract. These checks validate
that the profile also satisfies the *specific* controlled slot that produced
it, for example the required name, skill combination, language proficiency,
or leadership team size.
"""

import re

from app.schemas import CandidateProfile

from .models import CandidateGenerationSlot


# The assignment is being prepared in July 2026. Generated timelines must not
# contain future employment, education, project, or certification dates.
LATEST_ALLOWED_YEAR_MONTH = "2026-07"
LATEST_ALLOWED_YEAR = 2026

# CVs commonly round experience to a whole year. A one-year tolerance keeps
# the check practical while still rejecting clear contradictions between the
# declared total and the employment timeline.
EXPERIENCE_TOLERANCE_YEARS = 1.0

# Several known facts explicitly lock the total experience value. The pattern
# captures sentences such as "Has 8 years of backend experience."
_EXPERIENCE_FACT_PATTERN = re.compile(
    r"\bhas\s+(?P<years>\d+(?:\.\d+)?)\s+years\b",
    flags=re.IGNORECASE,
)


def validate_profile_against_slot(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
) -> list[str]:
    """Return every deterministic mismatch between a profile and its slot.

    Returning a list instead of raising on the first problem gives the retry
    prompt complete, actionable feedback and usually avoids extra API calls.
    """

    problems: list[str] = []

    _check_exact_identity(profile, slot, problems)
    _check_required_skills(profile, slot, problems)
    _check_required_languages(profile, slot, problems)
    _check_certification(profile, slot, problems)
    _check_leadership(profile, slot, problems)
    _check_education(profile, slot, problems)
    _check_project(profile, slot, problems)
    _check_explicit_experience_fact(profile, slot, problems)
    _check_experience_duration(profile, problems)
    _check_ordering_and_future_dates(profile, problems)

    return problems


def _check_exact_identity(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Validate immutable identity and classification fields."""

    exact_fields = {
        "candidate_id": (profile.candidate_id, slot.candidate_id),
        "full_name": (profile.full_name, slot.full_name),
        "professional_title": (
            profile.professional_title,
            slot.professional_title,
        ),
        "profession": (profile.profession.value, slot.profession.value),
        "seniority": (profile.seniority.value, slot.seniority.value),
        "city": (profile.contact.city, slot.city),
        "country": (profile.contact.country, slot.country),
    }

    for field_name, (actual, expected) in exact_fields.items():
        if _normalize(actual) != _normalize(expected):
            problems.append(
                f"{field_name} must be {expected!r}; received {actual!r}."
            )


def _check_required_skills(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Ensure every planned skill exists and has visible supporting evidence."""

    generated_skill_names = {
        _normalize(skill.name) for skill in profile.skills
    }

    evidence_parts = [profile.summary]
    for role in profile.work_experience:
        evidence_parts.extend(role.highlights)
        evidence_parts.extend(role.technologies)
    for project in profile.projects:
        evidence_parts.append(project.description)
        evidence_parts.extend(project.technologies)

    evidence_text = _normalize(" ".join(evidence_parts))

    for required_skill in slot.required_skills:
        normalized_skill = _normalize(required_skill)

        if normalized_skill not in generated_skill_names:
            problems.append(
                f"Required skill {required_skill!r} is missing from skills."
            )
            continue

        if normalized_skill not in evidence_text:
            problems.append(
                f"Required skill {required_skill!r} needs visible evidence "
                "outside the skills list."
            )


def _check_required_languages(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Match each controlled language and its exact proficiency."""

    generated_languages = {
        _normalize(language.name): language.proficiency
        for language in profile.languages
    }

    for required_language in slot.languages:
        normalized_name = _normalize(required_language.name)
        generated_proficiency = generated_languages.get(normalized_name)

        if generated_proficiency is None:
            problems.append(
                f"Required language {required_language.name!r} is missing."
            )
        elif generated_proficiency != required_language.proficiency:
            problems.append(
                f"Language {required_language.name!r} must have proficiency "
                f"{required_language.proficiency.value!r}; received "
                f"{generated_proficiency.value!r}."
            )


def _check_certification(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Preserve the controlled certification distribution exactly."""

    if slot.certification is None:
        if profile.certifications:
            problems.append(
                "certifications must be empty because this slot has no "
                "required certification."
            )
        return

    required = slot.certification
    matching_certification = next(
        (
            certification
            for certification in profile.certifications
            if _normalize(certification.name) == _normalize(required.name)
            and _normalize(certification.issuer) == _normalize(required.issuer)
            and certification.year == required.year
        ),
        None,
    )

    if matching_certification is None:
        problems.append(
            "Required certification must appear exactly as "
            f"{required.name!r}, issued by {required.issuer!r} in "
            f"{required.year}."
        )


def _check_leadership(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Validate explicit people-leadership evidence and team size."""

    generated_team_sizes = [
        role.managed_team_size
        for role in profile.work_experience
        if role.managed_team_size is not None
    ]

    if slot.leadership_team_size is None:
        if generated_team_sizes:
            problems.append(
                "managed_team_size must be omitted because this slot has no "
                "leadership requirement."
            )
        return

    if slot.leadership_team_size not in generated_team_sizes:
        problems.append(
            "At least one work-experience entry must have "
            f"managed_team_size={slot.leadership_team_size}."
        )


def _check_education(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Find the exact education entry used by controlled retrieval tests."""

    if slot.required_education is None:
        return

    required = slot.required_education
    matching_education = next(
        (
            education
            for education in profile.education
            if _normalize(education.degree) == _normalize(required.degree)
            and _normalize(education.field_of_study)
            == _normalize(required.field_of_study)
            and _normalize(education.institution)
            == _normalize(required.institution)
        ),
        None,
    )

    if matching_education is None:
        problems.append(
            "Required education must appear exactly as "
            f"{required.degree!r} in {required.field_of_study!r} from "
            f"{required.institution!r}."
        )


def _check_project(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Preserve the controlled portfolio-project distribution."""

    if slot.required_project is None:
        if profile.projects:
            problems.append(
                "projects must be empty because this slot has no required "
                "portfolio project."
            )
        return

    required = slot.required_project
    matching_project = next(
        (
            project
            for project in profile.projects
            if _normalize(project.name) == _normalize(required.name)
        ),
        None,
    )

    if matching_project is None:
        problems.append(
            f"Required project {required.name!r} is missing."
        )
        return

    generated_technologies = {
        _normalize(technology)
        for technology in matching_project.technologies
    }
    missing_technologies = [
        technology
        for technology in required.technologies
        if _normalize(technology) not in generated_technologies
    ]

    if missing_technologies:
        problems.append(
            f"Project {required.name!r} is missing required technologies: "
            f"{', '.join(missing_technologies)}."
        )


def _check_explicit_experience_fact(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Enforce total years when a known fact states an exact value."""

    expected_years: float | None = None

    for known_fact in slot.known_facts:
        match = _EXPERIENCE_FACT_PATTERN.search(known_fact)
        if match is not None:
            expected_years = float(match.group("years"))
            break

    if (
        expected_years is not None
        and profile.years_of_experience != expected_years
    ):
        problems.append(
            "years_of_experience must be "
            f"{expected_years:g} based on the controlled known fact; "
            f"received {profile.years_of_experience:g}."
        )


def _check_experience_duration(
    profile: CandidateProfile,
    problems: list[str],
) -> None:
    """Compare declared experience with non-overlapping employment months.

    A schema-valid profile can still claim eight years of experience while its
    work history visibly spans ten years. The PDF would expose that conflict,
    so we calculate the union of all role date ranges and reject only material
    differences. Overlapping roles are merged rather than double-counted.
    """

    covered_months = _calculate_non_overlapping_employment_months(profile)
    calculated_years = covered_months / 12

    if (
        abs(calculated_years - profile.years_of_experience)
        > EXPERIENCE_TOLERANCE_YEARS
    ):
        problems.append(
            "years_of_experience is inconsistent with the visible work "
            f"history: declared {profile.years_of_experience:g}, but the "
            f"employment dates cover approximately {calculated_years:.1f} "
            "non-overlapping years."
        )


def _calculate_non_overlapping_employment_months(
    profile: CandidateProfile,
) -> int:
    """Return the union of every employment interval in whole months."""

    latest_month = _year_month_to_index(LATEST_ALLOWED_YEAR_MONTH)
    intervals = sorted(
        (
            _year_month_to_index(role.start_date),
            (
                _year_month_to_index(role.end_date)
                if role.end_date is not None
                else latest_month
            ),
        )
        for role in profile.work_experience
    )

    merged_intervals: list[tuple[int, int]] = []
    for start_month, end_month in intervals:
        if not merged_intervals or start_month > merged_intervals[-1][1] + 1:
            merged_intervals.append((start_month, end_month))
            continue

        previous_start, previous_end = merged_intervals[-1]
        merged_intervals[-1] = (
            previous_start,
            max(previous_end, end_month),
        )

    return sum(
        end_month - start_month + 1
        for start_month, end_month in merged_intervals
    )


def _year_month_to_index(value: str) -> int:
    """Convert ``YYYY-MM`` into an integer suitable for interval arithmetic."""

    year_text, month_text = value.split("-", maxsplit=1)
    return int(year_text) * 12 + int(month_text) - 1


def _check_ordering_and_future_dates(
    profile: CandidateProfile,
    problems: list[str],
) -> None:
    """Keep generated timelines deterministic and historically plausible."""

    work_start_dates = [
        role.start_date for role in profile.work_experience
    ]
    if work_start_dates != sorted(work_start_dates, reverse=True):
        problems.append("work_experience must be ordered newest first.")

    education_start_years = [
        education.start_year for education in profile.education
    ]
    if education_start_years != sorted(
        education_start_years,
        reverse=True,
    ):
        problems.append("education must be ordered newest first.")

    for role in profile.work_experience:
        if role.start_date > LATEST_ALLOWED_YEAR_MONTH:
            problems.append(
                f"Work start_date {role.start_date!r} is later than "
                f"{LATEST_ALLOWED_YEAR_MONTH}."
            )
        if (
            role.end_date is not None
            and role.end_date > LATEST_ALLOWED_YEAR_MONTH
        ):
            problems.append(
                f"Work end_date {role.end_date!r} is later than "
                f"{LATEST_ALLOWED_YEAR_MONTH}."
            )

    for education in profile.education:
        if education.start_year > LATEST_ALLOWED_YEAR:
            problems.append(
                f"Education start_year {education.start_year} is later than "
                f"{LATEST_ALLOWED_YEAR}."
            )
        if (
            education.end_year is not None
            and education.end_year > LATEST_ALLOWED_YEAR
        ):
            problems.append(
                f"Education end_year {education.end_year} is later than "
                f"{LATEST_ALLOWED_YEAR}."
            )

    for certification in profile.certifications:
        if certification.year > LATEST_ALLOWED_YEAR:
            problems.append(
                f"Certification year {certification.year} is later than "
                f"{LATEST_ALLOWED_YEAR}."
            )

    for project in profile.projects:
        if project.year is not None and project.year > LATEST_ALLOWED_YEAR:
            problems.append(
                f"Project year {project.year} is later than "
                f"{LATEST_ALLOWED_YEAR}."
            )


def _normalize(value: str) -> str:
    """Normalize controlled text for case-insensitive exact comparisons."""

    return " ".join(value.casefold().split())
