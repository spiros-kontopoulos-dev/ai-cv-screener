"""Tests for deterministic exact-condition CV evidence analysis."""

import pytest

from app.cv_retrieval import (
    analyze_recruiter_question,
    score_evidence_text,
    semantic_relevance_from_distance,
)


def test_question_analysis_extracts_typed_team_size_constraint() -> None:
    """The number is modelled as team headcount, not as a loose token."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers in a backend team?"
    )

    assert features.lexical_terms == ("manage", "engineer", "backend", "team")
    assert "backend team" in features.lexical_phrases
    assert len(features.numeric_constraints) == 1
    constraint = features.numeric_constraints[0]
    assert constraint.value == 8
    assert constraint.display_value == "8"
    assert constraint.operator == "eq"
    assert constraint.relation == "team_size"
    assert set(constraint.context_concepts) >= {"management", "workforce"}


def test_case_insensitive_lexical_scoring_covers_skills_and_professions() -> None:
    """Exact technologies and role wording contribute interpretable coverage."""

    features = analyze_recruiter_question(
        "Python FastAPI PostgreSQL backend engineer"
    )
    score = score_evidence_text(
        "Senior BACKEND Engineer building Python, FastAPI and PostgreSQL APIs.",
        features,
        semantic_score=0.5,
    )

    assert score.lexical_score == 1.0
    assert score.matched_terms == (
        "python",
        "fastapi",
        "postgresql",
        "backend",
        "engineer",
    )
    assert set(score.matched_term_evidence) == {
        "python",
        "fastapi",
        "postgresql",
        "backend",
        "engineer",
    }
    assert score.numeric_score == 0.0
    assert score.combined_score == pytest.approx(0.65)


@pytest.mark.parametrize(
    "evidence",
    [
        "Team leadership: managed 8 people across backend delivery.",
        "Managed eight engineers responsible for platform reliability.",
        "Led a team of exactly 8 developers.",
        "Supervised 8 staff members across two squads.",
        "Team size: 8 engineers, with direct delivery responsibility.",
        "Maintained 8 direct reports in the engineering organisation.",
    ],
)
def test_team_size_relation_accepts_general_positive_patterns(evidence: str) -> None:
    """Different credible headcount phrasings satisfy the same typed relation."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers?"
    )
    score = score_evidence_text(evidence, features)

    assert score.numeric_score == 1.0
    assert score.contextual_numeric_match is True
    assert score.matched_numeric_values == ("8",)
    assert score.matched_numeric_contexts


@pytest.mark.parametrize(
    "evidence",
    [
        "Senior engineer with 8 years of experience.",
        "Python 8y, PostgreSQL 7y and Docker 6y.",
        "Worked in backend engineering since 2018.",
        "Contact: +30 210 555 0188.",
        "Managed delivery projects for 8 years.",
        "Managed a platform team. Has 8 years of engineering experience.",
        "Managed 6 engineers and delivered 8 projects.",
        "Managed more than 8 engineers during a transformation programme.",
        "The organisation employed 8 engineers; this candidate was an individual contributor.",
    ],
)
def test_team_size_relation_rejects_unrelated_or_non_exact_numbers(
    evidence: str,
) -> None:
    """Durations, dates, phones and unrelated counts cannot become headcount."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers?"
    )
    score = score_evidence_text(evidence, features, semantic_score=0.9)

    assert score.numeric_score == 0.0
    assert score.contextual_numeric_match is False
    assert score.matched_numeric_values == ()
    assert score.matched_numeric_contexts == ()


def test_realistic_noor_evidence_beats_realistic_eleni_duration_pattern() -> None:
    """The live regression is protected without candidate-specific code."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers?"
    )
    noor_pattern = score_evidence_text(
        "Senior Distributed Systems Engineer Mar 2022 - Present. "
        "Team leadership: managed 8 people. Led a team of exactly 8 "
        "engineers responsible for event-driven backend services.",
        features,
        semantic_score=0.0,
    )
    eleni_pattern = score_evidence_text(
        "Senior Python backend engineer with 8 years of experience building "
        "and operating API-driven services, with a track record of managing "
        "delivery and improving reliability.",
        features,
        semantic_score=0.7,
    )

    assert noor_pattern.numeric_score == 1.0
    assert eleni_pattern.numeric_score == 0.0
    assert noor_pattern.combined_score > eleni_pattern.combined_score


def test_language_proficiency_requires_local_real_text() -> None:
    """Cloud-native wording cannot impersonate native-language proficiency."""

    features = analyze_recruiter_question(
        "Find a native German backend engineer."
    )
    summary = score_evidence_text(
        "Cloud-native backend engineer building distributed services.",
        features,
    )
    language = score_evidence_text(
        "PROGRAMMING LANGUAGES German Native Python 6.5y English Fluent",
        features,
    )

    assert len(features.text_relations) == 1
    assert features.text_relations[0].relation == "language_proficiency"
    assert features.text_relations[0].terms == ("german", "native")
    assert set(summary.matched_terms) == {"backend", "engineer"}
    assert all("native" not in match for match in summary.matched_term_evidence)
    assert set(language.matched_terms) >= {"german", "native"}
    assert "german+native=german native" in language.matched_term_evidence


def test_aliases_report_actual_evidence_tokens() -> None:
    """Transparent aliases show the text that genuinely supported the match."""

    features = analyze_recruiter_question("managed developers")
    score = score_evidence_text(
        "Led engineers responsible for API delivery.",
        features,
    )

    assert score.matched_terms == ("manage", "developer")
    assert "manage=led" in score.matched_term_evidence
    assert "developer=engineers" in score.matched_term_evidence


def test_hyphenated_education_phrase_matches_extracted_pdf_text() -> None:
    """PDF punctuation differences do not hide exact education terminology."""

    features = analyze_recruiter_question(
        "Who studied Human-Computer Interaction?"
    )
    score = score_evidence_text(
        "Master of Science in Human Computer Interaction",
        features,
    )

    assert features.lexical_terms == ("human", "computer", "interaction")
    assert "human computer interaction" in features.lexical_phrases
    assert score.lexical_score == 1.0
    assert "human computer interaction" in score.matched_phrases


def test_semantic_distance_normalization_supports_collection_metrics() -> None:
    """All supported Chroma distances become comparable larger-is-better values."""

    assert semantic_relevance_from_distance(0.25, "cosine") == 0.75
    assert semantic_relevance_from_distance(0.25, "ip") == 0.75
    assert semantic_relevance_from_distance(3.0, "l2") == 0.25
    assert semantic_relevance_from_distance(4.0, "cosine") == 0.0

    with pytest.raises(ValueError, match="Unsupported"):
        semantic_relevance_from_distance(0.1, "unknown")
