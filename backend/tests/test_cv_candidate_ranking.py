"""Tests for candidate grouping, condition coverage, and evidence balancing."""

import pytest

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CandidateCvRetrievalResult,
    CvEvidenceScore,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
    build_candidate_conditions,
    rank_candidates,
)


def test_conditions_collapse_language_and_role_relationships() -> None:
    features = analyze_recruiter_question(
        "Find a native German backend engineer."
    )

    conditions = build_candidate_conditions(
        features,
        candidate_names=("Jonas Keller", "Hannah Vogel"),
    )

    assert [(condition.kind, condition.label) for condition in conditions] == [
        ("relation", "german native"),
        ("phrase", "backend engineer"),
    ]


def test_candidate_modifier_becomes_source_aware_role_condition() -> None:
    features = analyze_recruiter_question(
        "Which frontend candidates have accessibility experience?"
    )

    conditions = build_candidate_conditions(features)

    assert [(condition.kind, condition.label) for condition in conditions] == [
        ("role", "frontend"),
        ("term", "accessibility"),
    ]


def test_standalone_role_condition_rejects_collaboration_mentions() -> None:
    result = _assisted_result(
        "Which frontend candidates have accessibility experience?",
        (
            _hit(
                rank=1,
                candidate_id="candidate_frontend",
                candidate_name="Frontend Candidate",
                professional_title="Junior Frontend Engineer",
                section_name="professional_summary",
                text=(
                    "Junior Frontend Engineer building accessible React "
                    "components and keyboard-friendly interfaces."
                ),
                semantic=0.70,
                lexical=1.0,
                matched_terms=("frontend", "accessibility"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_designer",
                candidate_name="Design Candidate",
                professional_title="Junior UX/UI Designer",
                section_name="experience",
                text=(
                    "Junior UX/UI Designer creating accessible flows and "
                    "collaborating with frontend developers on handoff."
                ),
                semantic=0.80,
                lexical=1.0,
                matched_terms=("frontend", "accessibility"),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=2)
    frontend = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_frontend"
    )
    designer = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_designer"
    )

    assert frontend.complete_condition_coverage is True
    assert designer.matched_condition_count == 1
    assert ranked.candidates[0].candidate_id == "candidate_frontend"


def test_compound_candidate_evidence_across_chunks_beats_partial_match() -> None:
    result = _assisted_result(
        "Find a native German backend engineer.",
        (
            _hit(
                rank=1,
                candidate_id="candidate_005",
                candidate_name="Marco Bellini",
                text="Highly relevant backend engineer building APIs.",
                semantic=0.92,
                lexical=0.50,
                matched_terms=("backend", "engineer"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_002",
                candidate_name="Jonas Keller",
                text="Python backend engineer building Django services.",
                semantic=0.72,
                lexical=0.50,
                matched_terms=("backend", "engineer"),
            ),
            _hit(
                rank=3,
                candidate_id="candidate_002",
                candidate_name="Jonas Keller",
                text="PROGRAMMING LANGUAGES German Native Python English Fluent",
                semantic=0.44,
                lexical=0.50,
                matched_terms=("german", "native"),
                matched_term_evidence=("german+native=german native",),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=3)

    assert ranked.candidates[0].candidate_id == "candidate_002"
    assert ranked.candidates[0].complete_condition_coverage is True
    assert ranked.candidates[0].matched_condition_count == 2
    assert len(ranked.candidates[0].evidence) == 2
    assert ranked.candidates[1].candidate_id == "candidate_005"
    assert ranked.candidates[1].coverage_score < 1.0


def test_repeated_verbose_chunks_do_not_inflate_candidate_score() -> None:
    hits = [
        _hit(
            rank=1,
            candidate_id="candidate_001",
            candidate_name="Verbose Candidate",
            text="Python backend delivery evidence one.",
            semantic=0.70,
            lexical=1.0,
            matched_terms=("python",),
        ),
        _hit(
            rank=2,
            candidate_id="candidate_002",
            candidate_name="Concise Candidate",
            text="Python backend delivery evidence.",
            semantic=0.70,
            lexical=1.0,
            matched_terms=("python",),
        ),
    ]
    hits.extend(
        _hit(
            rank=rank,
            candidate_id="candidate_001",
            candidate_name="Verbose Candidate",
            text=f"Additional Python evidence chunk {rank}.",
            semantic=0.60,
            lexical=1.0,
            matched_terms=("python",),
        )
        for rank in range(3, 8)
    )

    ranked = rank_candidates(
        _assisted_result("Python", tuple(hits)),
        candidate_limit=10,
        evidence_limit=2,
    )
    verbose = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_001"
    )
    concise = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_002"
    )

    assert verbose.candidate_score == pytest.approx(concise.candidate_score)
    assert verbose.total_candidate_hit_count == 6
    assert len(verbose.evidence) == 2
    assert concise.total_candidate_hit_count == 1


def test_evidence_selection_covers_distinct_conditions_before_filling() -> None:
    result = _assisted_result(
        "Python FastAPI PostgreSQL",
        (
            _hit(
                rank=1,
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                text="Python backend engineer with extensive delivery experience.",
                semantic=0.90,
                lexical=0.34,
                matched_terms=("python",),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                text="Technologies: FastAPI and PostgreSQL.",
                semantic=0.55,
                lexical=0.67,
                matched_terms=("fastapi", "postgresql"),
            ),
            _hit(
                rank=3,
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                text="More Python project details.",
                semantic=0.85,
                lexical=0.34,
                matched_terms=("python",),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=5, evidence_limit=2)
    candidate = ranked.candidates[0]

    assert candidate.complete_condition_coverage is True
    assert [item.hit.chunk_id for item in candidate.evidence] == [
        "chunk_candidate_001_2",
        "chunk_candidate_001_1",
    ]


def test_explicit_candidate_names_are_alternative_identity_matches() -> None:
    result = _assisted_result(
        "Compare Aino Korhonen and Lukas Gruber for a cloud data engineering role.",
        (
            _hit(
                rank=1,
                candidate_id="candidate_015",
                candidate_name="Aino Korhonen",
                text="Aino Korhonen Senior Data Engineer cloud data platforms.",
                semantic=0.70,
                lexical=0.75,
                matched_terms=("cloud", "data", "engineering"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_018",
                candidate_name="Lukas Gruber",
                text="Lukas Gruber Cloud Data Engineer and platform specialist.",
                semantic=0.68,
                lexical=0.75,
                matched_terms=("cloud", "data", "engineering"),
            ),
            _hit(
                rank=3,
                candidate_id="candidate_016",
                candidate_name="Javier Molina",
                text="Cloud data engineering specialist.",
                semantic=0.80,
                lexical=0.75,
                matched_terms=("cloud", "data", "engineering"),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=2)
    identity = next(
        condition
        for condition in ranked.conditions
        if condition.kind == "identity"
    )
    top_ids = [candidate.candidate_id for candidate in ranked.candidates[:2]]

    assert identity.alternatives == ("aino korhonen", "lukas gruber")
    assert set(top_ids) == {"candidate_015", "candidate_018"}
    assert all(
        candidate.matched_conditions[0].condition.kind == "identity"
        for candidate in ranked.candidates[:2]
    )
    third = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_016"
    )
    assert not any(
        match.condition.kind == "identity"
        for match in third.matched_conditions
    )



def test_comparison_name_tokens_do_not_leak_into_skill_conditions() -> None:
    features = analyze_recruiter_question(
        "Compare Aino Korhonen and Lukas Gruber for a cloud data engineering role."
    )

    conditions = build_candidate_conditions(
        features,
        candidate_names=("Aino Korhonen", "Lukas Gruber", "Javier Molina"),
    )

    assert [(condition.kind, condition.label) for condition in conditions] == [
        ("identity", "explicitly requested candidate"),
        ("phrase", "data engineering"),
        ("term", "cloud"),
    ]
    assert all(condition.label != "luka" for condition in conditions)


def test_collaborating_with_a_role_does_not_make_it_the_candidate_role() -> None:
    result = _assisted_result(
        "Find a backend engineer.",
        (
            _hit(
                rank=1,
                candidate_id="candidate_frontend",
                candidate_name="Frontend Candidate",
                professional_title="Frontend Engineer",
                section_name="experience",
                text=(
                    "Frontend Engineer Jan 2025 - Present. Built React screens "
                    "and collaborated closely with backend engineers on APIs."
                ),
                semantic=0.90,
                lexical=1.0,
                matched_terms=("backend", "engineer"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_backend",
                candidate_name="Backend Candidate",
                professional_title="Python Backend Engineer",
                section_name="identity",
                text="Backend Candidate Python Backend Engineer",
                semantic=0.70,
                lexical=1.0,
                matched_terms=("backend", "engineer"),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=2)
    backend = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_backend"
    )
    frontend = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_frontend"
    )

    assert backend.complete_condition_coverage is True
    assert frontend.matched_condition_count == 0
    assert ranked.candidates[0].candidate_id == "candidate_backend"


def test_role_phrase_uses_title_prefix_not_substring_prefixes() -> None:
    result = _assisted_result(
        "Find a backend engineer.",
        (
            _hit(
                rank=1,
                candidate_id="candidate_domain",
                candidate_name="Domain Candidate",
                professional_title="Distributed Systems Engineer",
                section_name="identity",
                text=(
                    "Domain Candidate Senior Distributed Systems Engineer "
                    "Backend Engineering"
                ),
                semantic=0.70,
                lexical=1.0,
                matched_terms=("backend", "engineer"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_mentions",
                candidate_name="Mention Candidate",
                professional_title="QA Engineer",
                section_name="experience",
                text=(
                    "QA Engineer. Partnered with backend engineers to verify "
                    "REST API behavior."
                ),
                semantic=0.75,
                lexical=1.0,
                matched_terms=("backend", "engineer"),
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=2)
    domain = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_domain"
    )
    mention = next(
        candidate
        for candidate in ranked.candidates
        if candidate.candidate_id == "candidate_mentions"
    )

    assert domain.matched_condition_count == 1
    assert mention.matched_condition_count == 0

def test_exact_numeric_relation_outranks_unrelated_semantic_number() -> None:
    result = _assisted_result(
        "Who managed exactly eight engineers?",
        (
            _hit(
                rank=1,
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                text="Senior backend engineer with 8 years of experience.",
                semantic=0.80,
                lexical=1.0,
                matched_terms=("manage", "engineer"),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_006",
                candidate_name="Noor van Dijk",
                text="Team leadership: managed 8 people and led exactly 8 engineers.",
                semantic=0.0,
                lexical=1.0,
                numeric=1.0,
                matched_terms=("manage", "engineer"),
                matched_numbers=("8",),
                contextual_numeric=True,
            ),
        ),
    )

    ranked = rank_candidates(result, candidate_limit=10, evidence_limit=2)

    assert len(ranked.conditions) == 1
    assert ranked.conditions[0].kind == "numeric"
    assert ranked.candidates[0].candidate_id == "candidate_006"
    assert ranked.candidates[0].coverage_score == 1.0
    assert ranked.candidates[1].coverage_score == 0.0


def test_conflicting_candidate_identity_is_rejected() -> None:
    result = _assisted_result(
        "Python",
        (
            _hit(
                rank=1,
                candidate_id="candidate_001",
                candidate_name="First Name",
                text="Python evidence.",
                semantic=0.7,
                lexical=1.0,
                matched_terms=("python",),
            ),
            _hit(
                rank=2,
                candidate_id="candidate_001",
                candidate_name="Different Name",
                text="More Python evidence.",
                semantic=0.6,
                lexical=1.0,
                matched_terms=("python",),
            ),
        ),
    )

    with pytest.raises(ValueError, match="conflicting names"):
        rank_candidates(result, candidate_limit=10, evidence_limit=2)


def _assisted_result(
    question: str,
    hits: tuple[ScoredCvEvidenceHit, ...],
) -> AssistedCvRetrievalResult:
    query = RawCvRetrievalQuery(question)
    raw = RawCvRetrievalResult(
        query=query,
        requested_result_limit=50,
        collection_name="cv_chunks",
        collection_record_count=184,
        distance_metric="cosine",
        embedding_model="test-model",
        embedding_dimension=384,
        hits=(),
    )
    return AssistedCvRetrievalResult(
        raw_result=raw,
        query_features=analyze_recruiter_question(question),
        scanned_record_count=184,
        duplicates_removed=0,
        supplemental_hit_count=sum(hit.supplemental_exact_hit for hit in hits),
        hits=hits,
    )


def _hit(
    *,
    rank: int,
    candidate_id: str,
    candidate_name: str,
    text: str,
    professional_title: str = "Backend Engineer",
    section_name: str | None = None,
    semantic: float,
    lexical: float,
    numeric: float = 0.0,
    matched_terms: tuple[str, ...] = (),
    matched_numbers: tuple[str, ...] = (),
    matched_term_evidence: tuple[str, ...] = (),
    contextual_numeric: bool = False,
) -> ScoredCvEvidenceHit:
    combined = (
        (0.40 * semantic) + (0.20 * lexical) + (0.40 * numeric)
        if numeric or contextual_numeric
        else (0.70 * semantic) + (0.30 * lexical)
    )
    return ScoredCvEvidenceHit(
        rank=rank,
        raw_rank=rank,
        chunk_id=f"chunk_{candidate_id}_{rank}",
        distance=max(0.0, 1.0 - semantic),
        text=text,
        source=RawCvRetrievalSource(
            candidate_id=candidate_id,
            candidate_name=candidate_name,
            professional_title=professional_title,
            document_id=f"document_{candidate_id}",
            document_hash=(candidate_id[-1] * 64),
            source_filename=f"{candidate_id}.pdf",
            source_path=f"/app/data/cv_pdfs/{candidate_id}.pdf",
            section_name=(
                section_name
                if section_name is not None
                else ("experience" if rank % 2 else "skills_and_languages")
            ),
            page_numbers=(1 if rank % 2 else 2,),
            chunk_index=rank,
            chunking_version="cv-sections-v1",
        ),
        score=CvEvidenceScore(
            semantic_score=semantic,
            lexical_score=lexical,
            numeric_score=numeric,
            combined_score=min(1.0, combined),
            matched_terms=matched_terms,
            matched_phrases=(),
            matched_numeric_values=matched_numbers,
            contextual_numeric_match=contextual_numeric,
            matched_term_evidence=matched_term_evidence,
            matched_numeric_contexts=(
                ("managed 8 people",) if contextual_numeric else ()
            ),
        ),
        supplemental_exact_hit=False,
    )
