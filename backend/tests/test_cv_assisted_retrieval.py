"""Tests for semantic retrieval assisted by exact collection scanning."""

from app.cv_ingestion import RawStoredChunk
from app.cv_retrieval import (
    AssistedCvRetriever,
    AssistedRetrievalConfig,
    RawCvRetrievalHit,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
)


class FakeRawRetriever:
    """Return a strong semantic duration hit but omit exact headcount evidence."""

    def retrieve(self, query):
        return RawCvRetrievalResult(
            query=query,
            requested_result_limit=query.result_limit or 50,
            collection_name="cv_chunks",
            collection_record_count=4,
            distance_metric="cosine",
            embedding_model="test-model",
            embedding_dimension=4,
            hits=(
                RawCvRetrievalHit(
                    rank=1,
                    chunk_id="chunk_duration",
                    distance=0.30,
                    text=(
                        "Senior Python backend engineer with 8 years of "
                        "experience and a track record of managing delivery."
                    ),
                    source=_source("candidate_001", 1),
                ),
                RawCvRetrievalHit(
                    rank=2,
                    chunk_id="chunk_duplicate",
                    distance=0.40,
                    text=(
                        "Senior Python backend engineer with 8 years of "
                        "experience and a track record of managing delivery."
                    ),
                    source=_source("candidate_001", 2),
                ),
            ),
        )


class FakeExactRepository:
    def get_all_chunks(self):
        return (
            RawStoredChunk(
                chunk_id="chunk_duration",
                text=(
                    "Senior Python backend engineer with 8 years of "
                    "experience and a track record of managing delivery."
                ),
                metadata=_metadata("candidate_001", 1),
            ),
            RawStoredChunk(
                chunk_id="chunk_exact",
                text=(
                    "Team leadership: managed 8 people. Led a team of exactly "
                    "8 engineers responsible for backend services."
                ),
                metadata=_metadata("candidate_006", 3),
            ),
            RawStoredChunk(
                chunk_id="chunk_comparative",
                text="Managed more than 8 engineers during a reorganisation.",
                metadata=_metadata("candidate_013", 4),
            ),
            RawStoredChunk(
                chunk_id="chunk_irrelevant",
                text="Designed accessible React interfaces.",
                metadata=_metadata("candidate_003", 5),
            ),
        )


def test_assisted_retriever_recovers_and_prioritizes_exact_headcount() -> None:
    """Clause-local exact evidence outranks high-similarity experience duration."""

    retriever = AssistedCvRetriever(
        AssistedRetrievalConfig(max_supplemental_hits=10),
        raw_retriever=FakeRawRetriever(),
        exact_repository=FakeExactRepository(),
    )

    result = retriever.retrieve(
        RawCvRetrievalQuery("Who managed exactly eight engineers?")
    )

    assert result.scanned_record_count == 4
    assert result.supplemental_hit_count == 1
    assert result.duplicates_removed == 1
    assert result.hits[0].chunk_id == "chunk_exact"
    assert result.hits[0].supplemental_exact_hit is True
    assert result.hits[0].raw_rank is None
    assert result.hits[0].score.contextual_numeric_match is True
    assert result.hits[0].score.numeric_score == 1.0
    duration = next(hit for hit in result.hits if hit.chunk_id == "chunk_duration")
    assert duration.score.numeric_score == 0.0
    assert "chunk_comparative" not in {hit.chunk_id for hit in result.hits}
    assert result.hits[0].score.combined_score > duration.score.combined_score


def test_assisted_retriever_can_disable_supplemental_hits() -> None:
    """The exact scan remains bounded and can be disabled through configuration."""

    retriever = AssistedCvRetriever(
        AssistedRetrievalConfig(max_supplemental_hits=0),
        raw_retriever=FakeRawRetriever(),
        exact_repository=FakeExactRepository(),
    )

    result = retriever.retrieve(RawCvRetrievalQuery("managed eight engineers"))

    assert result.supplemental_hit_count == 0
    assert {hit.chunk_id for hit in result.hits} == {"chunk_duration"}
    assert result.hits[0].score.numeric_score == 0.0


def _source(candidate_id: str, chunk_index: int) -> RawCvRetrievalSource:
    return RawCvRetrievalSource.from_chroma_metadata(
        _metadata(candidate_id, chunk_index)
    )


def _metadata(candidate_id: str, chunk_index: int) -> dict[str, object]:
    return {
        "document_id": f"document_{candidate_id}",
        "document_hash": (str(chunk_index + 1) * 64)[:64],
        "candidate_id": candidate_id,
        "candidate_name": f"Candidate {candidate_id[-3:]}",
        "professional_title": "Backend Engineer",
        "source_filename": f"{candidate_id}.pdf",
        "source_path": f"/app/data/cv_pdfs/{candidate_id}.pdf",
        "section_name": "experience",
        "page_numbers": "1",
        "chunk_index": chunk_index,
        "chunking_version": "cv-sections-v1",
    }
