"""Regression tests for robust recruiter-query understanding."""

import pytest

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CvEvidenceScore,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
    build_candidate_conditions,
    rank_candidates,
    score_evidence_text,
)


@pytest.mark.parametrize(
    "question, expected_terms",
    [
        (
            "Who knows Python, FastAPI, and PostgreSQL?",
            ("python", "fastapi", "postgresql"),
        ),
        (
            "Find people skilled in Python, FastAPI, and PostgreSQL.",
            ("python", "fastapi", "postgresql"),
        ),
        (
            "Which candidate combines PyTorch, NLP, and vector databases?",
            ("pytorch", "nlp", "vector", "database"),
        ),
    ],
)
def test_conversational_scaffolding_never_becomes_evidence(
    question: str,
    expected_terms: tuple[str, ...],
) -> None:
    features = analyze_recruiter_question(question)

    assert features.lexical_terms == expected_terms
    labels = [
        condition.label for condition in build_candidate_conditions(features)
    ]
    assert labels == list(expected_terms)


@pytest.mark.parametrize(
    "question",
    [
        "Who has a Bachelor of Science in Software Engineering?",
        "Who holds a BSc in Software Engineering?",
        "Which candidates earned a BS in Software Engineering?",
        "Which CVs show a Bachelor of Science focused on Software Engineering?",
    ],
)
def test_bachelor_science_aliases_create_one_education_condition(
    question: str,
) -> None:
    features = analyze_recruiter_question(question)
    conditions = build_candidate_conditions(features)

    assert len(features.education_constraints) == 1
    assert [(condition.kind, condition.label) for condition in conditions] == [
        ("education", "bachelor of science in software engineering")
    ]


def test_education_condition_binds_field_to_requested_degree() -> None:
    result = _assisted_result(
        "Who has a Bachelor of Science in Software Engineering?",
        (
            _hit(
                rank=1,
                candidate_id="candidate_match",
                candidate_name="Matching Candidate",
                professional_title="Software Engineer",
                section_name="education",
                text=(
                    "Bachelor of Science in Software Engineering "
                    "Example University 2020 - 2024"
                ),
                matched_terms=("bachelor", "science", "software", "engineering"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_cross_degree",
                candidate_name="Cross Degree Candidate",
                professional_title="Backend Engineer",
                section_name="education",
                text=(
                    "Master of Science in Software Engineering "
                    "Bachelor of Science in Computer Science"
                ),
                matched_terms=("bachelor", "science", "software", "engineering"),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=4)
    matching = next(
        item for item in ranked.candidates if item.candidate_id == "candidate_match"
    )
    cross_degree = next(
        item
        for item in ranked.candidates
        if item.candidate_id == "candidate_cross_degree"
    )

    assert matching.complete_condition_coverage is True
    assert len(matching.evidence) == 1
    assert cross_degree.matched_condition_count == 0


@pytest.mark.parametrize(
    "question, expected_relation",
    [
        (
            "Who works in backend engineering and has German as a native language?",
            ("german", "native"),
        ),
        (
            "Show a backend developer whose mother tongue is German.",
            ("german", "native"),
        ),
        (
            "Show a data engineer using Spark whose mother tongue is Spanish.",
            ("spanish", "native"),
        ),
    ],
)
def test_language_idioms_preserve_language_and_proficiency(
    question: str,
    expected_relation: tuple[str, str],
) -> None:
    features = analyze_recruiter_question(question)

    assert [relation.terms for relation in features.text_relations] == [
        expected_relation
    ]


def test_professional_experience_is_not_a_language_relation() -> None:
    features = analyze_recruiter_question(
        "Who has over five years of professional experience?"
    )

    assert features.text_relations == ()
    assert len(features.numeric_constraints) == 1
    assert features.numeric_constraints[0].operator == "gt"


def test_plus_suffix_means_at_least_for_experience_duration() -> None:
    features = analyze_recruiter_question(
        "Which candidates have 6+ years in their career?"
    )

    assert len(features.numeric_constraints) == 1
    constraint = features.numeric_constraints[0]
    assert constraint.operator == "gte"
    assert constraint.relation == "experience_duration"


def test_candidate_id_number_does_not_satisfy_experience_duration() -> None:
    features = analyze_recruiter_question(
        "Who has more than 5 years of working experience?"
    )
    score = score_evidence_text(
        "Junior UX Designer · 2 years experience · candidate_030",
        features,
    )

    assert score.numeric_score == 0.0
    assert score.contextual_numeric_match is False


def test_general_engineering_query_becomes_source_aware_role() -> None:
    features = analyze_recruiter_question("Who knows engineering?")

    conditions = build_candidate_conditions(features)
    assert [(item.kind, item.label) for item in conditions] == [
        ("role", "engineering")
    ]


def test_frontend_background_becomes_source_aware_role() -> None:
    features = analyze_recruiter_question(
        "Who has a frontend background related to accessibility?"
    )

    conditions = build_candidate_conditions(features)
    assert [(item.kind, item.label) for item in conditions] == [
        ("role", "frontend"),
        ("term", "accessibility"),
    ]


def test_comparison_scaffolding_does_not_change_candidate_conditions() -> None:
    features = analyze_recruiter_question(
        "Evaluate Aino Korhonen versus Lukas Gruber for a cloud data engineer position."
    )
    conditions = build_candidate_conditions(
        features,
        candidate_names=("Aino Korhonen", "Lukas Gruber", "Javier Molina"),
    )

    assert [(condition.kind, condition.label) for condition in conditions] == [
        ("identity", "explicitly requested candidate"),
        ("phrase", "data engineer"),
        ("term", "cloud"),
    ]


def test_morphological_capability_alias_requires_self_described_evidence() -> None:
    result = _assisted_result(
        "Who knows accessibility in frontend development?",
        (
            _hit(
                rank=1,
                candidate_id="candidate_frontend",
                candidate_name="Frontend Candidate",
                professional_title="Frontend Engineer",
                section_name="professional_summary",
                text="Frontend Engineer building accessible component systems.",
                matched_terms=("frontend", "development", "accessibility"),
                matched_term_evidence=("accessibility=accessible",),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_incidental",
                candidate_name="Incidental Candidate",
                professional_title="Frontend Engineer",
                section_name="experience",
                text=(
                    "Frontend Engineer who converted one screen into an "
                    "accessible view."
                ),
                matched_terms=("frontend", "development", "accessibility"),
                matched_term_evidence=("accessibility=accessible",),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=3)
    declared = next(
        item
        for item in ranked.candidates
        if item.candidate_id == "candidate_frontend"
    )
    incidental = next(
        item
        for item in ranked.candidates
        if item.candidate_id == "candidate_incidental"
    )

    assert declared.complete_condition_coverage is True
    assert incidental.complete_condition_coverage is False


def _assisted_result(
    question: str,
    hits: tuple[ScoredCvEvidenceHit, ...],
) -> AssistedCvRetrievalResult:
    raw = RawCvRetrievalResult(
        query=RawCvRetrievalQuery(text=question, result_limit=100),
        requested_result_limit=100,
        collection_name="cv_chunks",
        collection_record_count=184,
        distance_metric="cosine",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension=384,
        hits=(),
    )
    return AssistedCvRetrievalResult(
        raw_result=raw,
        query_features=analyze_recruiter_question(question),
        scanned_record_count=184,
        duplicates_removed=0,
        supplemental_hit_count=0,
        hits=hits,
    )


def _hit(
    *,
    rank: int,
    candidate_id: str,
    candidate_name: str,
    professional_title: str,
    section_name: str,
    text: str,
    matched_terms: tuple[str, ...],
    matched_term_evidence: tuple[str, ...] = (),
) -> ScoredCvEvidenceHit:
    return ScoredCvEvidenceHit(
        rank=rank,
        raw_rank=rank,
        chunk_id=f"chunk_{candidate_id}_{rank}",
        distance=0.2,
        text=text,
        source=RawCvRetrievalSource(
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            professional_title=professional_title,
            document_id=f"document_{candidate_id}",
            document_hash=(candidate_id[-1] * 64),
            source_filename=f"{candidate_id}.pdf",
            source_path=f"/app/data/cv_pdfs/{candidate_id}.pdf",
            section_name=section_name,
            page_numbers=(1,),
            chunk_index=rank,
            chunking_version="cv-sections-v1",
        ),
        score=CvEvidenceScore(
            semantic_score=0.8,
            lexical_score=1.0,
            numeric_score=0.0,
            combined_score=0.86,
            matched_terms=matched_terms,
            matched_phrases=(),
            matched_numeric_values=(),
            contextual_numeric_match=False,
            matched_term_evidence=matched_term_evidence,
            matched_numeric_contexts=(),
        ),
        supplemental_exact_hit=False,
    )
