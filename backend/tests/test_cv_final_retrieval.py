"""Tests for final support thresholds and prompt-ready evidence budgets."""

import pytest

from app.cv_retrieval import (
    CandidateCvRetrievalQuery,
    CvCandidateRetrievalError,
    CvFinalRetrievalError,
    FinalCvRetrievalQuery,
    FinalCvRetriever,
    FinalRetrievalConfig,
)
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class FakeCandidateRetriever:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def retrieve(self, query):
        self.queries.append(query)
        return self.result


class BrokenCandidateRetriever:
    def retrieve(self, query):
        raise CvCandidateRetrievalError("broken final candidate pool")


def test_complete_candidates_are_preferred_and_partial_rows_are_removed() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_complete",
                "Complete Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.85,
                coverage_score=1.0,
            ),
            CandidateSpec(
                "candidate_partial",
                "Partial Candidate",
                "Backend Engineer",
                matched_count=1,
                candidate_score=0.55,
                coverage_score=0.5,
            ),
        )
    )

    result = finalize_for_test(candidate_result)

    assert result.outcome == "supported"
    assert [candidate.candidate_id for candidate in result.candidates] == [
        "candidate_complete"
    ]
    assert result.candidates[0].support_level == "complete"


def test_high_confidence_partial_candidates_are_used_only_as_fallback() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_partial",
                "Partial Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.52,
                coverage_score=2 / 3,
            ),
        ),
        condition_labels=("python", "postgresql", "fastapi"),
    )

    result = finalize_for_test(candidate_result)

    assert result.outcome == "partial"
    assert result.candidates[0].support_level == "partial"
    assert "partial matches" in result.support_message


def test_zero_and_low_coverage_results_become_unsupported() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_noise",
                "Noise Candidate",
                "Platform Engineer",
                matched_count=1,
                candidate_score=0.28,
                coverage_score=1 / 3,
            ),
        ),
        question="Who holds government security clearance?",
        condition_labels=("government", "security", "clearance"),
    )

    result = finalize_for_test(candidate_result)

    assert result.outcome == "unsupported"
    assert result.candidates == ()
    assert "CANDIDATES: none" in result.context_text


def test_global_chunk_budget_and_per_candidate_budget_are_enforced() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_001",
                "First Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.90,
                coverage_score=1.0,
                evidence_texts=("Evidence one.", "Evidence two.", "Evidence three."),
            ),
            CandidateSpec(
                "candidate_002",
                "Second Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.85,
                coverage_score=1.0,
                evidence_texts=("Evidence four.", "Evidence five."),
            ),
        )
    )
    config = FinalRetrievalConfig(
        evidence_per_candidate_limit=2,
        max_total_evidence_chunks=3,
    )

    result = finalize_for_test(candidate_result, config=config)

    assert result.evidence_chunk_count == 3
    assert len(result.candidates[0].evidence) == 2
    assert len(result.candidates[1].evidence) == 1
    assert result.budget_exhausted is True


def test_context_budget_truncates_evidence_but_preserves_source_metadata() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_001",
                "Budget Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.90,
                coverage_score=1.0,
                evidence_texts=("A" * 3000,),
            ),
        )
    )
    config = FinalRetrievalConfig(
        max_context_characters=900,
        max_evidence_text_characters=700,
    )

    result = finalize_for_test(candidate_result, config=config)

    assert result.context_character_count <= 900
    assert "candidate_001-cv.pdf" in result.context_text
    assert "chunk_candidate_001_1" in result.context_text
    assert result.candidates[0].evidence[0].text.endswith("...")


def test_prompt_context_keeps_candidates_and_sources_separate() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_001",
                "Alpha Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.90,
                coverage_score=1.0,
            ),
            CandidateSpec(
                "candidate_002",
                "Beta Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.88,
                coverage_score=1.0,
            ),
        )
    )

    result = finalize_for_test(candidate_result)

    assert "CANDIDATE 1: Alpha Candidate" in result.context_text
    assert "CANDIDATE 2: Beta Candidate" in result.context_text
    assert "candidate_001-cv.pdf" in result.context_text
    assert "candidate_002-cv.pdf" in result.context_text
    assert all(
        evidence.source.candidate_id == candidate.candidate_id
        for candidate in result.candidates
        for evidence in candidate.evidence
    )


def test_final_retriever_requests_a_broad_candidate_pool_and_resolves_limit() -> None:
    candidate_result = build_candidate_result(
        (
            CandidateSpec(
                "candidate_001",
                "Candidate",
                "Python Engineer",
                matched_count=2,
                candidate_score=0.90,
                coverage_score=1.0,
            ),
        )
    )
    fake = FakeCandidateRetriever(candidate_result)
    retriever = FinalCvRetriever(
        FinalRetrievalConfig(
            candidate_pool_limit=12,
            candidate_evidence_pool_limit=4,
        ),
        candidate_retriever=fake,
    )

    result = retriever.retrieve(
        FinalCvRetrievalQuery(
            "  Python and PostgreSQL  ",
            candidate_limit=3,
            semantic_result_limit=60,
        )
    )

    assert result.requested_candidate_limit == 3
    assert fake.queries == [
        CandidateCvRetrievalQuery(
            "Python and PostgreSQL",
            candidate_limit=12,
            semantic_result_limit=60,
            evidence_limit=4,
        )
    ]


def test_final_retriever_validates_configuration_and_wraps_candidate_errors() -> None:
    with pytest.raises(ValueError, match="cover the maximum"):
        FinalRetrievalConfig(
            max_candidate_limit=10,
            candidate_pool_limit=5,
        )
    with pytest.raises(ValueError, match="Partial score threshold"):
        FinalRetrievalConfig(
            complete_min_candidate_score=0.3,
            partial_min_candidate_score=0.4,
        )

    retriever = FinalCvRetriever(
        FinalRetrievalConfig(),
        candidate_retriever=BrokenCandidateRetriever(),
    )
    with pytest.raises(CvFinalRetrievalError, match="broken final candidate"):
        retriever.retrieve(FinalCvRetrievalQuery("Python"))
