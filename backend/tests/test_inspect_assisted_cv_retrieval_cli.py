"""CLI tests for exact-condition-assisted CV retrieval inspection."""

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CvEvidenceScore,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
)
from app.scripts.inspect_assisted_cv_retrieval import run_cli


class FakeRetriever:
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
        source = RawCvRetrievalSource(
            candidate_id="candidate_006",
            candidate_name="Noor Example",
            professional_title="Backend Engineer",
            document_id="document_abc",
            document_hash="a" * 64,
            source_filename="noor-example-cv.pdf",
            source_path="/app/data/cv_pdfs/noor-example-cv.pdf",
            section_name="experience",
            page_numbers=(1,),
            chunk_index=2,
            chunking_version="cv-sections-v1",
        )
        return AssistedCvRetrievalResult(
            raw_result=raw,
            query_features=analyze_recruiter_question(query.text),
            scanned_record_count=184,
            duplicates_removed=1,
            supplemental_hit_count=1,
            hits=(
                ScoredCvEvidenceHit(
                    rank=1,
                    raw_rank=None,
                    chunk_id="chunk_exact",
                    distance=None,
                    text="Team leadership: managed 8 people.",
                    source=source,
                    score=CvEvidenceScore(
                        semantic_score=0.0,
                        lexical_score=1.0,
                        numeric_score=1.0,
                        combined_score=0.6,
                        matched_terms=("manage", "engineer"),
                        matched_phrases=(),
                        matched_numeric_values=("8",),
                        contextual_numeric_match=True,
                        matched_term_evidence=(
                            "manage=managed",
                            "engineer=people",
                        ),
                        matched_numeric_contexts=(
                            "team leadership managed 8 people",
                        ),
                    ),
                    supplemental_exact_hit=True,
                ),
            ),
        )


def test_cli_prints_score_components_and_exact_scan_origin(capsys) -> None:
    exit_code = run_cli(
        [
            "--query",
            "Who managed exactly eight engineers?",
            "--display-limit",
            "5",
        ],
        retriever=FakeRetriever(),
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ASSISTED CV RETRIEVAL INSPECTION" in output
    assert "Collection records scanned: 184" in output
    assert "Numeric constraints: 8" in output
    assert "origin=exact-scan" in output
    assert "numeric=1.0000" in output
    assert "matched_text=manage=managed, engineer=people" in output
    assert "numeric_context=team leadership managed 8 people" in output
    assert "contextual_numeric=True" in output
    assert "managed 8 people" in output


def test_cli_rejects_invalid_display_and_preview_limits(capsys) -> None:
    display_status = run_cli(
        ["--query", "Python", "--display-limit", "0"],
        retriever=FakeRetriever(),
    )
    display_error = capsys.readouterr().err
    preview_status = run_cli(
        ["--query", "Python", "--preview-characters", "-1"],
        retriever=FakeRetriever(),
    )
    preview_error = capsys.readouterr().err

    assert display_status == 2
    assert "must be positive" in display_error
    assert preview_status == 2
    assert "cannot be negative" in preview_error
