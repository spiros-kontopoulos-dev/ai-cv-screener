"""Deterministic experience calculation and profile normalization.

The LLM is good at creating realistic roles and descriptions, but it is not a
reliable date-arithmetic engine. This module therefore owns the numerical link
between employment dates and ``years_of_experience``.

For slots with an explicit experience fact, the plan remains authoritative. If
the generated dates materially disagree with that locked value, Python rebuilds
the role timeline deterministically while preserving role order and content.
For every other slot, Python derives the total from the union of non-overlapping
work intervals and updates skill-year values that would otherwise exceed the
derived career total.
"""

import math
import re
from collections.abc import Sequence

from app.schemas import CandidateProfile, SeniorityLevel

from .models import CandidateGenerationSlot


# The dataset is prepared in July 2026. Current roles are measured through this
# month so repeated runs produce the same deterministic result.
LATEST_ALLOWED_YEAR_MONTH = "2026-07"
LATEST_ALLOWED_YEAR = 2026

# Locked totals may be rounded in ordinary CV wording. When the visible work
# history falls outside this range, Python repairs the dates instead of asking
# the model to perform repeated calendar arithmetic.
EXPERIENCE_TOLERANCE_YEARS = 1.0

# Keep every rendered role long enough to look credible when a locked timeline
# must be rebuilt. If a very short total cannot support six months per role,
# the allocation automatically falls back to at least one month per role.
MINIMUM_ROLE_DURATION_MONTHS = 6

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
    """Normalize locked or unlocked experience and return a valid profile.

    Unlocked slots use Python-derived experience totals. Locked slots preserve
    the plan's exact total and repair only materially inconsistent work dates.
    Skill durations are capped at the authoritative total in both cases.
    """

    locked_years = extract_locked_experience_years(slot)
    if locked_years is not None:
        return _normalize_locked_profile_experience(
            profile,
            locked_years=locked_years,
        )

    calculated_years = calculate_employment_years(profile)
    seniority_problem = _find_seniority_timeline_problem(
        slot.seniority,
        calculated_years,
    )
    if seniority_problem is not None:
        raise CandidateExperienceNormalizationError([seniority_problem])

    return _rebuild_profile_with_experience(
        profile,
        authoritative_years=calculated_years,
    )


def year_month_to_index(value: str) -> int:
    """Convert ``YYYY-MM`` into an integer for interval arithmetic."""

    year_text, month_text = value.split("-", maxsplit=1)
    return int(year_text) * 12 + int(month_text) - 1


def index_to_year_month(value: int) -> str:
    """Convert a month index back into the canonical ``YYYY-MM`` format."""

    year, zero_based_month = divmod(value, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _normalize_locked_profile_experience(
    profile: CandidateProfile,
    *,
    locked_years: float,
) -> CandidateProfile:
    """Preserve a locked total and repair an overlong or short timeline.

    The LLM still chooses role names, employers, achievements, and technology
    evidence. Python owns only the deterministic date allocation when the
    visible calendar duration falls outside the accepted tolerance.
    """

    calculated_years = calculate_employment_years(profile)
    profile_payload = profile.model_dump(mode="python")

    if abs(calculated_years - locked_years) > EXPERIENCE_TOLERANCE_YEARS:
        target_months = max(1, round(locked_years * 12))
        role_months = _allocate_role_months(profile, target_months)
        profile_payload["work_experience"] = _rebuild_work_dates(
            profile,
            role_months,
        )

    # The controlled plan is authoritative even if the provider returned a
    # different provisional total.
    normalized = CandidateProfile.model_validate(profile_payload)
    return _rebuild_profile_with_experience(
        normalized,
        authoritative_years=locked_years,
    )


def _allocate_role_months(
    profile: CandidateProfile,
    target_months: int,
) -> list[int]:
    """Distribute a locked career duration across existing roles.

    The allocation preserves the model's relative role-duration pattern using
    proportional weights, applies a small realism floor, and then uses a
    largest-remainder pass so the final month total is exact.
    """

    role_count = len(profile.work_experience)
    minimum_months = (
        MINIMUM_ROLE_DURATION_MONTHS
        if target_months >= role_count * MINIMUM_ROLE_DURATION_MONTHS
        else 1
    )

    guaranteed_months = minimum_months * role_count
    remaining_months = target_months - guaranteed_months

    latest_month = year_month_to_index(LATEST_ALLOWED_YEAR_MONTH)
    original_durations = [
        max(
            1,
            (
                year_month_to_index(role.end_date)
                if role.end_date is not None
                else latest_month
            )
            - year_month_to_index(role.start_date)
            + 1,
        )
        for role in profile.work_experience
    ]
    total_original_duration = sum(original_durations)

    raw_extras = [
        remaining_months * duration / total_original_duration
        for duration in original_durations
    ]
    allocated_extras = [math.floor(value) for value in raw_extras]

    unallocated_months = remaining_months - sum(allocated_extras)
    remainder_order = sorted(
        range(role_count),
        key=lambda index: raw_extras[index] - allocated_extras[index],
        reverse=True,
    )

    for index in remainder_order[:unallocated_months]:
        allocated_extras[index] += 1

    return [
        minimum_months + extra
        for extra in allocated_extras
    ]


def _rebuild_work_dates(
    profile: CandidateProfile,
    role_months: Sequence[int],
) -> list[dict]:
    """Rebuild contiguous role dates backwards while preserving role order."""

    newest_role = profile.work_experience[0]
    cursor_end = (
        year_month_to_index(LATEST_ALLOWED_YEAR_MONTH)
        if newest_role.end_date is None
        else year_month_to_index(newest_role.end_date)
    )

    rebuilt_roles: list[dict] = []

    for index, (role, duration_months) in enumerate(
        zip(profile.work_experience, role_months, strict=True)
    ):
        start_month = cursor_end - duration_months + 1
        role_payload = role.model_dump(mode="python")
        role_payload["start_date"] = index_to_year_month(start_month)

        # Preserve the visible current-role marker only for the newest role.
        if index == 0 and newest_role.end_date is None:
            role_payload["end_date"] = None
        else:
            role_payload["end_date"] = index_to_year_month(cursor_end)

        rebuilt_roles.append(role_payload)
        cursor_end = start_month - 1

    return rebuilt_roles


def _rebuild_profile_with_experience(
    profile: CandidateProfile,
    *,
    authoritative_years: float,
) -> CandidateProfile:
    """Set the authoritative total and cap skill durations consistently."""

    profile_payload = profile.model_dump(mode="python")
    profile_payload["years_of_experience"] = authoritative_years

    normalized_skills: list[dict] = []
    for skill in profile.skills:
        skill_payload = skill.model_dump(mode="python")
        skill_years = skill.years_of_experience

        if skill_years is not None and skill_years > authoritative_years:
            skill_payload["years_of_experience"] = authoritative_years

        normalized_skills.append(skill_payload)

    profile_payload["skills"] = normalized_skills
    return CandidateProfile.model_validate(profile_payload)


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
