"""Tests for the controlled synthetic-candidate dataset specification."""

import json
from collections import Counter
from pathlib import Path

from app.schemas import (
    LanguageProficiency,
    ProfessionCategory,
    SeniorityLevel,
)


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def _load_plan() -> dict:
    """Load the committed JSON plan used by the future LLM generator."""

    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def test_plan_contains_30_unique_candidate_slots() -> None:
    """The plan should define the complete candidate set exactly once."""

    plan = _load_plan()
    candidates = plan["candidates"]
    candidate_ids = [candidate["candidate_id"] for candidate in candidates]
    names = [candidate["full_name"].casefold() for candidate in candidates]

    expected_ids = [f"candidate_{number:03d}" for number in range(1, 31)]

    assert plan["candidate_count"] == 30
    assert len(candidates) == 30
    assert candidate_ids == expected_ids
    assert len(set(candidate_ids)) == 30
    assert len(set(names)) == 30


def test_declared_distributions_match_candidate_slots() -> None:
    """The summary quotas must stay synchronized with the slot definitions."""

    plan = _load_plan()
    candidates = plan["candidates"]
    distributions = plan["distributions"]

    profession_counts = Counter(
        candidate["profession"] for candidate in candidates
    )
    seniority_counts = Counter(
        candidate["seniority"] for candidate in candidates
    )
    country_counts = Counter(candidate["country"] for candidate in candidates)
    language_counts = Counter(
        language["name"]
        for candidate in candidates
        for language in candidate["languages"]
    )

    assert dict(sorted(profession_counts.items())) == distributions["profession"]
    assert dict(sorted(seniority_counts.items())) == distributions["seniority"]
    assert dict(sorted(country_counts.items())) == distributions["country"]
    assert dict(sorted(language_counts.items())) == distributions["language_mentions"]

    assert sum(candidate["certification"] is not None for candidate in candidates) == (
        distributions["candidates_with_certifications"]
    )
    assert sum(
        candidate["leadership_team_size"] is not None for candidate in candidates
    ) == distributions["candidates_with_leadership"]
    assert sum(
        candidate["required_project"] is not None for candidate in candidates
    ) == distributions["candidates_with_required_projects"]
    assert sum(len(candidate["languages"]) >= 3 for candidate in candidates) == (
        distributions["candidates_with_three_or_more_languages"]
    )


def test_every_candidate_has_generation_constraints_and_known_facts() -> None:
    """Each slot must provide enough controlled evidence for generation."""

    plan = _load_plan()

    for candidate in plan["candidates"]:
        assert len(candidate["required_skills"]) >= 5
        assert len(candidate["known_facts"]) >= 3
        assert candidate["languages"]
        assert any(
            language["name"] == "English"
            and language["proficiency"] in {"native", "fluent", "professional"}
            for language in candidate["languages"]
        )

        if candidate["leadership_team_size"] is not None:
            assert candidate["leadership_team_size"] >= 1


def test_search_scenarios_reference_valid_candidates() -> None:
    """Known demo questions must point only to defined candidate slots."""

    plan = _load_plan()
    valid_ids = {
        candidate["candidate_id"] for candidate in plan["candidates"]
    }
    scenario_ids = [
        scenario["scenario_id"] for scenario in plan["search_scenarios"]
    ]

    assert len(scenario_ids) == len(set(scenario_ids))

    for scenario in plan["search_scenarios"]:
        assert set(scenario["expected_candidate_ids"]).issubset(valid_ids)
        assert scenario["question"].strip()
        assert scenario["answer_behavior"].strip()

    unsupported = next(
        scenario
        for scenario in plan["search_scenarios"]
        if scenario["scenario_id"] == "unsupported_security_clearance"
    )
    assert unsupported["expected_candidate_ids"] == []


def test_fictional_data_and_pdf_grounding_rules_are_locked() -> None:
    """The specification must prevent real data and JSON-based RAG shortcuts."""

    policy = _load_plan()["fictional_data_policy"]

    assert all(policy.values())


def test_plan_uses_only_schema_controlled_values() -> None:
    """The dataset plan must stay compatible with the candidate schema."""

    plan = _load_plan()
    valid_professions = {value.value for value in ProfessionCategory}
    valid_seniority = {value.value for value in SeniorityLevel}
    valid_proficiency = {value.value for value in LanguageProficiency}

    for candidate in plan["candidates"]:
        assert candidate["profession"] in valid_professions
        assert candidate["seniority"] in valid_seniority
        assert len(candidate["required_skills"]) == len(
            {skill.casefold() for skill in candidate["required_skills"]}
        )
        assert len(candidate["languages"]) == len(
            {language["name"].casefold() for language in candidate["languages"]}
        )
        assert all(
            language["proficiency"] in valid_proficiency
            for language in candidate["languages"]
        )
