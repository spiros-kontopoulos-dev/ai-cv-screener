"""Deterministic checks between a generated profile and its plan slot.

Pydantic validates the general CandidateProfile contract. These checks validate
that the profile also satisfies the *specific* controlled slot that produced
it, for example the required name, skill combination, language proficiency,
or leadership team size.
"""

import re

from app.schemas import CandidateProfile

from .experience import (
    EXPERIENCE_TOLERANCE_YEARS,
    LATEST_ALLOWED_YEAR,
    LATEST_ALLOWED_YEAR_MONTH,
    calculate_employment_years,
    extract_locked_experience_years,
)
from .models import CandidateGenerationSlot


# Unlocked profiles must not repeat the provisional LLM total in their summary
# because Python derives the final value from employment dates after generation.
_SUMMARY_TOTAL_EXPERIENCE_PATTERN = re.compile(
    r"\b(?P<years>\d+(?:\.\d+)?)\+?\s+years?\s+of\s+experience\b",
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
    _check_experience_duration(profile, slot, problems)
    _check_summary_experience_statement(profile, slot, problems)
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

    expected_years = extract_locked_experience_years(slot)

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
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Check employment duration only when the plan locks an exact total.

    Unlocked totals are already normalized from the timeline by ``experience.py``
    before compliance runs. Locked totals remain plan-owned, so their generated
    dates must stay approximately consistent with the required value.
    """

    locked_years = extract_locked_experience_years(slot)
    if locked_years is None:
        return

    calculated_years = calculate_employment_years(profile)
    if abs(calculated_years - locked_years) > EXPERIENCE_TOLERANCE_YEARS:
        minimum_years = max(0.0, locked_years - EXPERIENCE_TOLERANCE_YEARS)
        maximum_years = locked_years + EXPERIENCE_TOLERANCE_YEARS
        problems.append(
            "The controlled experience total is "
            f"{locked_years:g} years, but the employment dates cover "
            f"approximately {calculated_years:.1f} non-overlapping years. "
            "Keep years_of_experience unchanged and adjust the work dates so "
            f"they cover between {minimum_years:.1f} and "
            f"{maximum_years:.1f} years."
        )


def _check_summary_experience_statement(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
    problems: list[str],
) -> None:
    """Prevent provisional unlocked totals from leaking into visible text."""

    summary_match = _SUMMARY_TOTAL_EXPERIENCE_PATTERN.search(profile.summary)
    if summary_match is None:
        return

    locked_years = extract_locked_experience_years(slot)
    stated_years = float(summary_match.group("years"))

    if locked_years is None:
        problems.append(
            "The summary must not state an exact phrase such as "
            f"'{stated_years:g} years of experience' because this slot has a "
            "Python-derived experience total. Use non-numeric wording such as "
            "'experienced mid-level backend engineer'."
        )
        return

    if stated_years != locked_years:
        problems.append(
            "The summary states "
            f"{stated_years:g} years of experience, but the controlled known "
            f"fact requires {locked_years:g}."
        )


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
