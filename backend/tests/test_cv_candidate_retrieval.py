"""Tests for candidate-aware retrieval orchestration and limits."""

import pytest

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CandidateAwareCvRetriever,
    CandidateCvRetrievalQuery,
    CandidateRetrievalConfig,
    CvCandidateRetrievalError,
    CvEvidenceScore,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
)


class FakeAssistedRetriever:
    def retrieve(self, query):
        source = RawCvRetrievalSource(
            candidate_id="candidate_001",
            candidate_name="Eleni Markou",
            professional_title="Senior Python Backend Engineer",
            document_id="document_001",
            document_hash="a" * 64,
            source_filename="eleni-markou-cv.pdf",
            source_path="/app/data/cv_pdfs/eleni-markou-cv.pdf",
            section_name="professional_summary",
            page_numbers=(1,),
            chunk_index=1,
            chunking_version="cv-sections-v1",
        )
        raw = RawCvRetrievalResult(
            query=query,
            requested_result_limit=query.result_limit or 50,
            collection_name="cv_chunks",
            collection_record_count=184,
            distance_metric="cosine",
            embedding_model="test-model",
            embedding_dimension=384,
            hits=(),
        )
        return AssistedCvRetrievalResult(
            raw_result=raw,
            query_features=analyze_recruiter_question(query.text),
            scanned_record_count=184,
            duplicates_removed=0,
            supplemental_hit_count=0,
            hits=(
                ScoredCvEvidenceHit(
                    rank=1,
                    raw_rank=1,
                    chunk_id="chunk_001",
                    distance=0.2,
                    text="Senior Python backend engineer.",
                    source=source,
                    score=CvEvidenceScore(
                        semantic_score=0.8,
                        lexical_score=1.0,
                        numeric_score=0.0,
                        combined_score=0.86,
                        matched_terms=("python",),
                        matched_phrases=(),
                        matched_numeric_values=(),
                        contextual_numeric_match=False,
                    ),
                ),
            ),
        )


class BrokenAssistedRetriever:
    def retrieve(self, query):
        raise ValueError("broken candidate evidence")


def test_candidate_retriever_resolves_limits_and_preserves_query() -> None:
    retriever = CandidateAwareCvRetriever(
        CandidateRetrievalConfig(
            default_candidate_limit=5,
            max_candidate_limit=20,
            default_evidence_limit=3,
            max_evidence_limit=6,
        ),
        assisted_retriever=FakeAssistedRetriever(),
    )

    result = retriever.retrieve(
        CandidateCvRetrievalQuery(
            "  Python   candidates  ",
            candidate_limit=4,
            semantic_result_limit=40,
            evidence_limit=2,
        )
    )

    assert result.assisted_result.raw_result.query.text == "Python candidates"
    assert result.assisted_result.raw_result.requested_result_limit == 40
    assert result.requested_candidate_limit == 4
    assert result.evidence_per_candidate_limit == 2
    assert result.candidates[0].candidate_id == "candidate_001"


def test_candidate_retriever_rejects_limits_above_configured_caps() -> None:
    retriever = CandidateAwareCvRetriever(
        CandidateRetrievalConfig(
            default_candidate_limit=5,
            max_candidate_limit=10,
            default_evidence_limit=3,
            max_evidence_limit=4,
        ),
        assisted_retriever=FakeAssistedRetriever(),
    )

    with pytest.raises(CvCandidateRetrievalError, match="between 1 and 10"):
        retriever.retrieve(
            CandidateCvRetrievalQuery("Python", candidate_limit=11)
        )
    with pytest.raises(CvCandidateRetrievalError, match="between 1 and 4"):
        retriever.retrieve(
            CandidateCvRetrievalQuery("Python", evidence_limit=5)
        )


def test_candidate_retriever_wraps_invalid_grouped_evidence() -> None:
    retriever = CandidateAwareCvRetriever(
        CandidateRetrievalConfig(),
        assisted_retriever=BrokenAssistedRetriever(),
    )

    with pytest.raises(CvCandidateRetrievalError, match="broken candidate"):
        retriever.retrieve(CandidateCvRetrievalQuery("Python"))
