"""CLI tests for candidate-aware CV retrieval inspection."""

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CandidateAwareCvRetriever,
    CandidateCvRetrievalQuery,
    CandidateRetrievalConfig,
    CvEvidenceScore,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
)
from app.scripts.inspect_candidate_cv_retrieval import run_cli


class FakeAssistedRetriever:
    def retrieve(self, query):
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
        sources = (
            RawCvRetrievalSource(
                candidate_id="candidate_002",
                candidate_name="Jonas Keller",
                professional_title="Python Backend Engineer",
                document_id="document_002",
                document_hash="a" * 64,
                source_filename="jonas-keller-cv.pdf",
                source_path="/app/data/cv_pdfs/jonas-keller-cv.pdf",
                section_name="professional_summary",
                page_numbers=(1,),
                chunk_index=1,
                chunking_version="cv-sections-v1",
            ),
            RawCvRetrievalSource(
                candidate_id="candidate_002",
                candidate_name="Jonas Keller",
                professional_title="Python Backend Engineer",
                document_id="document_002",
                document_hash="a" * 64,
                source_filename="jonas-keller-cv.pdf",
                source_path="/app/data/cv_pdfs/jonas-keller-cv.pdf",
                section_name="skills_and_languages",
                page_numbers=(2,),
                chunk_index=4,
                chunking_version="cv-sections-v1",
            ),
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
                    chunk_id="chunk_backend",
                    distance=0.3,
                    text="Python backend engineer building Django services.",
                    source=sources[0],
                    score=CvEvidenceScore(
                        semantic_score=0.7,
                        lexical_score=0.5,
                        numeric_score=0.0,
                        combined_score=0.64,
                        matched_terms=("backend", "engineer"),
                        matched_phrases=(),
                        matched_numeric_values=(),
                        contextual_numeric_match=False,
                    ),
                ),
                ScoredCvEvidenceHit(
                    rank=2,
                    raw_rank=20,
                    chunk_id="chunk_language",
                    distance=0.5,
                    text="PROGRAMMING LANGUAGES German Native Python.",
                    source=sources[1],
                    score=CvEvidenceScore(
                        semantic_score=0.5,
                        lexical_score=0.5,
                        numeric_score=0.0,
                        combined_score=0.5,
                        matched_terms=("german", "native"),
                        matched_phrases=(),
                        matched_numeric_values=(),
                        contextual_numeric_match=False,
                        matched_term_evidence=(
                            "german+native=german native",
                        ),
                    ),
                ),
            ),
        )


def _retriever() -> CandidateAwareCvRetriever:
    return CandidateAwareCvRetriever(
        CandidateRetrievalConfig(),
        assisted_retriever=FakeAssistedRetriever(),
    )


def test_cli_prints_candidate_coverage_and_separate_source_evidence(capsys) -> None:
    status = run_cli(
        [
            "--query",
            "Find a native German backend engineer.",
            "--candidate-limit",
            "5",
            "--evidence-limit",
            "3",
        ],
        retriever=_retriever(),
    )
    output = capsys.readouterr().out

    assert status == 0
    assert "CANDIDATE-AWARE CV RETRIEVAL INSPECTION" in output
    assert "Grouped candidates: 1" in output
    assert "german native [relation]" in output
    assert "backend engineer [phrase]" in output
    assert "candidate=candidate_002" in output
    assert "matched_conditions=2/2" in output
    assert "complete=True" in output
    assert "chunk_backend" in output
    assert "chunk_language" in output
    assert "professional_summary" in output
    assert "skills_and_languages" in output


def test_cli_rejects_invalid_display_and_preview_limits(capsys) -> None:
    display_status = run_cli(
        ["--query", "Python", "--display-limit", "0"],
        retriever=_retriever(),
    )
    display_error = capsys.readouterr().err
    preview_status = run_cli(
        ["--query", "Python", "--preview-characters", "-1"],
        retriever=_retriever(),
    )
    preview_error = capsys.readouterr().err

    assert display_status == 2
    assert "must be positive" in display_error
    assert preview_status == 2
    assert "cannot be negative" in preview_error
