"""Collection-wide verification for the generated candidate dataset.

Generation validates one candidate at a time. Before rendering PDFs, this
module performs the complementary dataset-level checks: completeness, plan
compliance, distributions, uniqueness, and the curated demo scenarios.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

from app.schemas import CandidateProfile

from .compliance import validate_profile_against_slot
from .models import CandidateDatasetPlan, SearchScenario
from .uniqueness import find_profile_uniqueness_problems


# Unsupported scenarios intentionally expect no matching candidates. Their
# forbidden phrases make the absence check explicit instead of trying to infer
# every possible synonym from a natural-language question.
_UNSUPPORTED_SCENARIO_PHRASES: dict[str, tuple[str, ...]] = {
    "unsupported_security_clearance": ("security clearance",),
}


@dataclass(frozen=True, slots=True)
class CandidateDatasetValidationReport:
    """Structured result returned by the final dataset validator."""

    expected_profile_count: int
    actual_profile_count: int
    compliant_profile_count: int
    total_scenario_count: int
    validated_scenario_count: int
    uniqueness_problem_count: int
    distribution_problem_count: int
    issues: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return True only when every collection-wide check passed."""

        return not self.issues


def validate_candidate_dataset(
    plan: CandidateDatasetPlan,
    profiles: Sequence[CandidateProfile],
) -> CandidateDatasetValidationReport:
    """Validate one persisted profile collection against its controlled plan.

    The function deliberately returns all discovered problems together. A
    complete report is more useful than repeatedly fixing one issue at a time,
    especially after an expensive LLM generation run.
    """

    issues: list[str] = []
    expected_ids = [slot.candidate_id for slot in plan.candidates]
    actual_ids = [profile.candidate_id for profile in profiles]

    if len(profiles) != plan.candidate_count:
        issues.append(
            "Profile count mismatch: expected "
            f"{plan.candidate_count}, received {len(profiles)}."
        )

    duplicate_ids = [
        candidate_id
        for candidate_id, count in Counter(actual_ids).items()
        if count > 1
    ]
    if duplicate_ids:
        issues.append(
            "Duplicate candidate IDs: "
            f"{', '.join(sorted(duplicate_ids))}."
        )

    missing_ids = [
        candidate_id
        for candidate_id in expected_ids
        if candidate_id not in actual_ids
    ]
    if missing_ids:
        issues.append(
            f"Missing candidate IDs: {', '.join(missing_ids)}."
        )

    unexpected_ids = [
        candidate_id
        for candidate_id in actual_ids
        if candidate_id not in expected_ids
    ]
    if unexpected_ids:
        issues.append(
            "Unexpected candidate IDs: "
            f"{', '.join(sorted(set(unexpected_ids)))}."
        )

    if actual_ids != expected_ids and not duplicate_ids:
        issues.append(
            "Candidate profiles must be stored in the same deterministic "
            "candidate-ID order as the dataset plan."
        )

    profiles_by_id = {
        profile.candidate_id: profile
        for profile in profiles
    }

    compliant_profile_count = 0
    for slot in plan.candidates:
        profile = profiles_by_id.get(slot.candidate_id)
        if profile is None:
            continue

        compliance_problems = validate_profile_against_slot(profile, slot)
        if compliance_problems:
            issues.extend(
                f"{slot.candidate_id}: {problem}"
                for problem in compliance_problems
            )
        else:
            compliant_profile_count += 1

    uniqueness_issues = _validate_collection_uniqueness(profiles)
    issues.extend(uniqueness_issues)

    distribution_issues = _validate_distributions(plan, profiles)
    issues.extend(distribution_issues)

    validated_scenario_count, scenario_issues = _validate_search_scenarios(
        plan.search_scenarios,
        profiles_by_id,
        profiles,
    )
    issues.extend(scenario_issues)

    return CandidateDatasetValidationReport(
        expected_profile_count=plan.candidate_count,
        actual_profile_count=len(profiles),
        compliant_profile_count=compliant_profile_count,
        total_scenario_count=len(plan.search_scenarios),
        validated_scenario_count=validated_scenario_count,
        uniqueness_problem_count=len(uniqueness_issues),
        distribution_problem_count=len(distribution_issues),
        issues=tuple(issues),
    )


def _validate_collection_uniqueness(
    profiles: Sequence[CandidateProfile],
) -> list[str]:
    """Run the same exact duplicate checks used during generation."""

    issues: list[str] = []
    accepted_profiles: list[CandidateProfile] = []

    for profile in profiles:
        problems = find_profile_uniqueness_problems(
            profile,
            accepted_profiles,
        )
        issues.extend(
            f"{profile.candidate_id}: {problem}"
            for problem in problems
        )
        accepted_profiles.append(profile)

    return issues


def _validate_distributions(
    plan: CandidateDatasetPlan,
    profiles: Sequence[CandidateProfile],
) -> list[str]:
    """Compare the generated collection with every planned distribution."""

    issues: list[str] = []
    actual_distributions: dict[str, Mapping[str, int] | int] = {
        "profession": Counter(
            profile.profession.value for profile in profiles
        ),
        "seniority": Counter(
            profile.seniority.value for profile in profiles
        ),
        "country": Counter(
            profile.contact.country for profile in profiles
        ),
        "language_mentions": Counter(
            language.name
            for profile in profiles
            for language in profile.languages
        ),
        "candidates_with_certifications": sum(
            bool(profile.certifications) for profile in profiles
        ),
        "candidates_with_leadership": sum(
            any(
                role.managed_team_size is not None
                for role in profile.work_experience
            )
            for profile in profiles
        ),
        "candidates_with_required_projects": sum(
            bool(profile.projects) for profile in profiles
        ),
        "candidates_with_three_or_more_languages": sum(
            len(profile.languages) >= 3 for profile in profiles
        ),
    }

    for distribution_name, expected_value in plan.distributions.items():
        actual_value = actual_distributions.get(distribution_name)
        if actual_value is None:
            issues.append(
                f"Unsupported distribution in plan: {distribution_name}."
            )
            continue

        if isinstance(expected_value, dict):
            normalized_actual = dict(actual_value)
            if normalized_actual != expected_value:
                issues.append(
                    f"Distribution {distribution_name!r} does not match "
                    f"the plan. Expected {expected_value}, received "
                    f"{normalized_actual}."
                )
        elif actual_value != expected_value:
            issues.append(
                f"Distribution {distribution_name!r} does not match the "
                f"plan. Expected {expected_value}, received {actual_value}."
            )

    return issues


def _validate_search_scenarios(
    scenarios: Sequence[SearchScenario],
    profiles_by_id: Mapping[str, CandidateProfile],
    profiles: Sequence[CandidateProfile],
) -> tuple[int, list[str]]:
    """Confirm that curated demo evidence is visible in generated profiles."""

    issues: list[str] = []
    validated_count = 0
    collection_text = _normalize_text(
        " ".join(_build_profile_evidence_parts(profile) for profile in profiles)
    )

    for scenario in scenarios:
        scenario_problems: list[str] = []

        if not scenario.expected_candidate_ids:
            forbidden_phrases = _UNSUPPORTED_SCENARIO_PHRASES.get(
                scenario.scenario_id,
                (),
            )
            for phrase in forbidden_phrases:
                if _normalize_text(phrase) in collection_text:
                    scenario_problems.append(
                        f"unsupported evidence {phrase!r} is present in the "
                        "generated collection."
                    )
        else:
            for candidate_id in scenario.expected_candidate_ids:
                profile = profiles_by_id.get(candidate_id)
                if profile is None:
                    scenario_problems.append(
                        f"expected candidate {candidate_id} is missing."
                    )
                    continue

                for evidence in scenario.required_evidence:
                    if not _profile_contains_evidence(profile, evidence):
                        scenario_problems.append(
                            f"{candidate_id} does not visibly contain required "
                            f"evidence {evidence!r}."
                        )

        if scenario_problems:
            issues.extend(
                f"Scenario {scenario.scenario_id!r}: {problem}"
                for problem in scenario_problems
            )
        else:
            validated_count += 1

    return validated_count, issues


def _profile_contains_evidence(
    profile: CandidateProfile,
    evidence: str,
) -> bool:
    """Match scenario evidence using normalized visible profile tokens.

    Scenario evidence is intentionally human-readable rather than a database
    query language. Requiring every normalized token allows equivalent visible
    forms such as ``German`` plus ``native`` or ``cloud data`` plus
    ``platforms`` without demanding one exact sentence.
    """

    evidence_tokens = set(_normalize_text(evidence).split())
    profile_tokens = set(
        _normalize_text(_build_profile_evidence_parts(profile)).split()
    )
    return evidence_tokens.issubset(profile_tokens)


def _build_profile_evidence_parts(profile: CandidateProfile) -> str:
    """Flatten every future PDF-visible field plus useful derived labels."""

    parts = [
        profile.candidate_id,
        profile.full_name,
        profile.professional_title,
        profile.profession.value,
        profile.profession.value.replace("_", " "),
        profile.seniority.value,
        str(profile.years_of_experience),
        profile.summary,
        profile.contact.city,
        profile.contact.country,
    ]

    for role in profile.work_experience:
        parts.extend(
            [
                role.job_title,
                role.company,
                role.location or "",
                *role.highlights,
                *role.technologies,
            ]
        )
        if role.managed_team_size is not None:
            team_size = role.managed_team_size
            parts.extend(
                [
                    f"managed team size {team_size}",
                    f"team size {team_size}",
                    f"managed {team_size} engineers",
                ]
            )

    for education in profile.education:
        parts.extend(
            [
                education.degree,
                education.field_of_study,
                education.institution,
                education.location or "",
            ]
        )

    for skill in profile.skills:
        parts.extend([skill.name, skill.category.value])

    for language in profile.languages:
        parts.extend(
            [
                language.name,
                language.proficiency.value,
                f"{language.name} {language.proficiency.value}",
            ]
        )

    if profile.certifications:
        parts.extend(["certification", "certifications"])
    for certification in profile.certifications:
        parts.extend(
            [
                certification.name,
                certification.issuer,
                str(certification.year),
            ]
        )

    for project in profile.projects:
        parts.extend(
            [
                project.name,
                project.description,
                *project.technologies,
                str(project.year) if project.year is not None else "",
            ]
        )

    return " ".join(parts)


def _normalize_text(value: str) -> str:
    """Normalize casing, punctuation, hyphens, and enum separators."""

    normalized = value.casefold().replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())
