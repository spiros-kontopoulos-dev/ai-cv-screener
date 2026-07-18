"""Deterministic experience calculation and profile normalization.

The LLM is good at creating realistic roles and descriptions, but it is not a
reliable date-arithmetic engine. This module therefore owns the numerical link
between employment dates and ``years_of_experience``.

For slots with an explicit experience fact, the plan remains authoritative and
normal compliance checks verify the generated dates. For every other slot,
Python derives the total from the union of non-overlapping work intervals and
updates skill-year values that would otherwise exceed the derived career total.
"""

import re
from collections.abc import Sequence

from app.schemas import CandidateProfile, SeniorityLevel

from .models import CandidateGenerationSlot


# The dataset is prepared in July 2026. Current roles are measured through this
# month so repeated runs produce the same deterministic result.
LATEST_ALLOWED_YEAR_MONTH = "2026-07"
LATEST_ALLOWED_YEAR = 2026

# Several controlled known facts lock an exact total, for example:
# "Has 8 years of backend experience."
_EXPERIENCE_FACT_PATTERN = re.compile(
    r"\bhas\s+(?P<years>\d+(?:\.\d+)?)\s+years\b",
    flags=re.IGNORECASE,
)


class CandidateExperienceNormalizationError(ValueError):
    """Raised when a generated timeline conflicts with the slot seniority."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


def extract_locked_experience_years(
    slot: CandidateGenerationSlot,
) -> float | None:
    """Return the exact experience total required by a known fact, if any."""

    for known_fact in slot.known_facts:
        match = _EXPERIENCE_FACT_PATTERN.search(known_fact)
        if match is not None:
            return float(match.group("years"))

    return None


def calculate_non_overlapping_employment_months(
    profile: CandidateProfile,
) -> int:
    """Return the union of all employment intervals in whole months.

    Adjacent ranges are joined and overlapping roles are counted only once.
    This avoids inflating experience when a candidate held a part-time or
    advisory role alongside their main position.
    """

    latest_month = year_month_to_index(LATEST_ALLOWED_YEAR_MONTH)
    intervals = sorted(
        (
            year_month_to_index(role.start_date),
            (
                year_month_to_index(role.end_date)
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


def calculate_employment_years(profile: CandidateProfile) -> float:
    """Calculate visible career duration rounded to one decimal place."""

    covered_months = calculate_non_overlapping_employment_months(profile)
    return round(covered_months / 12, 1)


def normalize_profile_experience(
    profile: CandidateProfile,
    slot: CandidateGenerationSlot,
) -> CandidateProfile:
    """Derive experience for unlocked slots and return a validated profile.

    The model's numeric total is treated as provisional unless the dataset plan
    explicitly locks it. Skill durations above the derived total are capped at
    the career duration because a skill cannot predate the candidate's career.
    The reconstructed ``CandidateProfile`` is validated again so downstream
    code never receives an internally inconsistent object.
    """

    if extract_locked_experience_years(slot) is not None:
        return profile

    calculated_years = calculate_employment_years(profile)
    seniority_problem = _find_seniority_timeline_problem(
        slot.seniority,
        calculated_years,
    )
    if seniority_problem is not None:
        raise CandidateExperienceNormalizationError([seniority_problem])

    profile_payload = profile.model_dump(mode="python")
    profile_payload["years_of_experience"] = calculated_years

    normalized_skills: list[dict] = []
    for skill in profile.skills:
        skill_payload = skill.model_dump(mode="python")
        skill_years = skill.years_of_experience

        if skill_years is not None and skill_years > calculated_years:
            skill_payload["years_of_experience"] = calculated_years

        normalized_skills.append(skill_payload)

    profile_payload["skills"] = normalized_skills
    return CandidateProfile.model_validate(profile_payload)


def year_month_to_index(value: str) -> int:
    """Convert ``YYYY-MM`` into an integer for interval arithmetic."""

    year_text, month_text = value.split("-", maxsplit=1)
    return int(year_text) * 12 + int(month_text) - 1


def _find_seniority_timeline_problem(
    seniority: SeniorityLevel,
    calculated_years: float,
) -> str | None:
    """Return an actionable problem when dates contradict fixed seniority."""

    if seniority == SeniorityLevel.JUNIOR and calculated_years > 4:
        return (
            "The work timeline covers approximately "
            f"{calculated_years:.1f} years, which is too long for the locked "
            "junior seniority. Shorten the employment dates to four years or "
            "less."
        )

    if seniority == SeniorityLevel.MID and not 2 <= calculated_years <= 10:
        return (
            "The work timeline covers approximately "
            f"{calculated_years:.1f} years, but the locked mid seniority "
            "requires between 2 and 10 years. Adjust the employment dates."
        )

    if seniority == SeniorityLevel.SENIOR and calculated_years < 5:
        return (
            "The work timeline covers approximately "
            f"{calculated_years:.1f} years, but the locked senior seniority "
            "requires at least 5 years. Extend the employment dates."
        )

    return None
