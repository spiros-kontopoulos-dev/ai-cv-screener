"""CLI tests for WP6 broad raw retrieval inspection."""

from app.cv_retrieval import (
    CvRawRetrievalError,
    RawCvRetrievalHit,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
)
from app.scripts.inspect_raw_cv_retrieval import run_cli


class FakeRetriever:
    """Return a complete typed result without model or Chroma dependencies."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[RawCvRetrievalQuery] = []

    def retrieve(self, query: RawCvRetrievalQuery) -> RawCvRetrievalResult:
        self.queries.append(query)
        if self.error:
            raise self.error
        source = RawCvRetrievalSource(
            candidate_id="candidate_001",
            candidate_name="Jane Example",
            professional_title="Backend Engineer",
            document_id="document_abc123",
            document_hash="a" * 64,
            source_filename="jane-example-backend-engineer-cv.pdf",
            source_path="/app/data/cv_pdfs/jane-example-backend-engineer-cv.pdf",
            section_name="experience",
            page_numbers=(1, 2),
            chunk_index=3,
            chunking_version="cv-sections-v1",
        )
        return RawCvRetrievalResult(
            query=query,
            requested_result_limit=query.result_limit or 50,
            collection_name="cv_chunks",
            collection_record_count=184,
            distance_metric="cosine",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            embedding_dimension=384,
            hits=(
                RawCvRetrievalHit(
                    rank=1,
                    chunk_id="chunk_1",
                    distance=0.123456,
                    text="Built Python and FastAPI services for hiring teams.",
                    source=source,
                ),
            ),
        )


def test_cli_prints_broad_typed_source_trace(capsys) -> None:
    """Inspection output exposes every source identity needed by later WP6 work."""

    retriever = FakeRetriever()
    exit_code = run_cli(
        [
            "--query",
            "Who knows Python?",
            "--result-limit",
            "30",
            "--preview-characters",
            "80",
        ],
        retriever=retriever,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert retriever.queries == [
        RawCvRetrievalQuery("Who knows Python?", result_limit=30)
    ]
    assert "RAW CV RETRIEVAL INSPECTION" in output
    assert "Collection records: 184" in output
    assert "Embedding dimension: 384" in output
    assert "Candidates represented: 1" in output
    assert "candidate=candidate_001" in output
    assert "pages=1-2" in output
    assert "file=jane-example-backend-engineer-cv.pdf" in output
    assert "hash=aaaaaaaaaaaa" in output
    assert "Built Python and FastAPI services" in output


def test_cli_accepts_top_k_alias_and_multiple_queries(capsys) -> None:
    """The developer command can inspect several questions in one model session."""

    retriever = FakeRetriever()
    exit_code = run_cli(
        [
            "--query",
            "Python",
            "--query",
            "German backend engineer",
            "--top-k",
            "12",
            "--preview-characters",
            "0",
        ],
        retriever=retriever,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert len(retriever.queries) == 2
    assert all(query.result_limit == 12 for query in retriever.queries)
    assert output.count("QUERY:") == 2
    assert "Built Python" not in output


def test_cli_reports_invalid_preview_and_retrieval_failure(capsys) -> None:
    """Invalid arguments and retrieval errors produce shell-friendly failures."""

    invalid_status = run_cli(
        ["--query", "Python", "--preview-characters", "-1"],
        retriever=FakeRetriever(),
    )
    invalid_error = capsys.readouterr().err
    retrieval_status = run_cli(
        ["--query", "Python"],
        retriever=FakeRetriever(error=CvRawRetrievalError("index unavailable")),
    )
    retrieval_error = capsys.readouterr().err

    assert invalid_status == 2
    assert "cannot be negative" in invalid_error
    assert retrieval_status == 2
    assert "index unavailable" in retrieval_error
