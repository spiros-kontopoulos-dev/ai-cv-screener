"""Presentation helpers for CV template rendering.

The validated candidate schema deliberately stores predictable machine-friendly
values such as ``2023-01`` and ``backend_engineering``.  This module converts
those values into concise human-readable labels without changing the source
profile or duplicating business validation.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from app.schemas import Skill


_SKILL_CATEGORY_LABELS = {
    "programming_language": "Programming Languages",
    "framework": "Frameworks",
    "database": "Databases",
    "cloud": "Cloud",
    "devops": "DevOps & Delivery",
    "data_ai": "Data & AI",
    "testing": "Testing",
    "design": "Design",
    "product": "Product",
    "other": "Other",
}

_LANGUAGE_PROFICIENCY_LABELS = {
    "native": "Native",
    "fluent": "Fluent",
    "professional": "Professional",
    "intermediate": "Intermediate",
    "basic": "Basic",
}

_SENIORITY_LABELS = {
    "junior": "Junior",
    "mid": "Mid-level",
    "senior": "Senior",
}


class CvFormattingError(ValueError):
    """Raised when a validated-looking display value cannot be formatted."""


def format_year_month(value: str) -> str:
    """Convert a validated ``YYYY-MM`` value into ``Mon YYYY`` text."""

    try:
        parsed_value = datetime.strptime(value, "%Y-%m")
    except ValueError as error:
        raise CvFormattingError(
            f"Expected a YYYY-MM date for CV rendering, received {value!r}."
        ) from error

    return parsed_value.strftime("%b %Y")


def format_work_date_range(start_date: str, end_date: str | None) -> str:
    """Format one employment range, using ``Present`` for current roles."""

    rendered_end = format_year_month(end_date) if end_date else "Present"
    return f"{format_year_month(start_date)} - {rendered_end}"


def format_education_year_range(
    start_year: int,
    end_year: int | None,
) -> str:
    """Format one education year range, supporting ongoing programmes."""

    rendered_end = str(end_year) if end_year is not None else "Present"
    return f"{start_year} - {rendered_end}"


def format_years_of_experience(value: float) -> str:
    """Render whole and half-year experience values without trailing zeros."""

    numeric_value = float(value)
    normalized_value = (
        int(numeric_value) if numeric_value.is_integer() else numeric_value
    )
    unit = "year" if numeric_value == 1 else "years"
    return f"{normalized_value:g} {unit}"


def format_skill_years(value: float | None) -> str | None:
    """Return a compact skill-duration label when the value is available."""

    if value is None:
        return None

    numeric_value = float(value)
    normalized_value = (
        int(numeric_value) if numeric_value.is_integer() else numeric_value
    )
    return f"{normalized_value:g}y"


def humanize_identifier(value: str) -> str:
    """Turn a snake-case identifier into a title-cased display label."""

    return value.replace("_", " ").title()


def format_seniority(value: str) -> str:
    """Return the controlled seniority label used in the document header."""

    return _SENIORITY_LABELS.get(value, humanize_identifier(value))


def format_language_proficiency(value: str) -> str:
    """Return a concise spoken-language proficiency label."""

    return _LANGUAGE_PROFICIENCY_LABELS.get(
        value,
        humanize_identifier(value),
    )


def candidate_initials(full_name: str) -> str:
    """Return at most two initials for the temporary portrait placeholder."""

    name_parts = [part for part in full_name.split() if part]
    if not name_parts:
        return "CV"

    return "".join(part[0].upper() for part in name_parts[:2])


def group_skills(skills: Iterable[Skill]) -> list[dict[str, object]]:
    """Group skills by controlled category while preserving input order.

    A plain dictionary payload keeps the Jinja template simple.  Skills remain
    real ``Skill`` objects so the template can access their validated fields.
    """

    grouped_skills: dict[str, list[Skill]] = defaultdict(list)
    category_order: list[str] = []

    for skill in skills:
        category_value = skill.category.value
        if category_value not in grouped_skills:
            category_order.append(category_value)
        grouped_skills[category_value].append(skill)

    return [
        {
            "label": _SKILL_CATEGORY_LABELS.get(
                category,
                humanize_identifier(category),
            ),
            "skills": grouped_skills[category],
        }
        for category in category_order
    ]
