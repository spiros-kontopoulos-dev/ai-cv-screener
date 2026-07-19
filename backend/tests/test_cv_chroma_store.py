"""Tests for persistent, compatibility-safe ChromaDB CV storage."""

from pathlib import Path

import pytest

from app.cv_ingestion import (
    CvChromaRepository,
    CvChunk,
    CvSourceMetadata,
    CvVectorStoreConfig,
    CvVectorStoreError,
    EmbeddedCvChunk,
)


def test_repository_upserts_documents_vectors_and_complete_metadata(tmp_path: Path) -> None:
    """Explicit embeddings and source metadata are persisted together."""

    repository = _repository(tmp_path)
    items = (_embedded("chunk_1", 0), _embedded("chunk_2", 1))

    summary = repository.upsert_embeddings(items)
    stored = repository.collection.get(
        ids=["chunk_1", "chunk_2"],
        include=["documents", "metadatas", "embeddings"],
    )

    assert summary.records_submitted == 2
    assert summary.collection_count == 2
    assert summary.batches_written == 1
    assert stored["documents"] == ["Evidence 0", "Evidence 1"]
    assert stored["metadatas"][0]["candidate_id"] == "candidate_001"
    assert stored["metadatas"][0]["page_numbers"] == "1"
    assert stored["metadatas"][0]["embedding_model"] == "test-model"
    assert stored["metadatas"][0]["document_chunk_count"] == 2
    assert len(stored["embeddings"][0]) == 4


def test_repeated_upsert_is_idempotent_and_survives_new_client(tmp_path: Path) -> None:
    """Stable chunk IDs update records rather than duplicating them."""

    first_repository = _repository(tmp_path)
    item = _embedded("chunk_1", 0)

    first_repository.upsert_embeddings((item,))
    second_summary = first_repository.upsert_embeddings((item,))
    reopened_repository = _repository(tmp_path)

    assert second_summary.collection_count == 1
    assert reopened_repository.get_collection_info().record_count == 1
    assert reopened_repository.get_collection_info().distance_metric == "cosine"


def test_repository_batches_upserts(tmp_path: Path) -> None:
    """Large vector sets are written in bounded storage batches."""

    repository = _repository(tmp_path, upsert_batch_size=2)
    items = tuple(_embedded(f"chunk_{index + 1}", index) for index in range(5))

    summary = repository.upsert_embeddings(items)

    assert summary.batches_written == 3
    assert summary.collection_count == 5


def test_existing_collection_rejects_incompatible_model_metadata(tmp_path: Path) -> None:
    """A changed model requires an explicit rebuild rather than silent mixing."""

    _repository(tmp_path).get_collection_info()
    incompatible = CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=tmp_path,
            collection_name="cv_chunks",
            index_version="cv-index-v1",
            embedding_model="different-model",
            embedding_dimension=4,
            chunking_version="cv-sections-v1",
        )
    )

    with pytest.raises(CvVectorStoreError, match="incompatible"):
        incompatible.get_collection_info()


def test_repository_rejects_vector_and_chunk_contract_mismatches(tmp_path: Path) -> None:
    """Every record must match the configured model and chunking version."""

    repository = _repository(tmp_path)
    wrong_model = EmbeddedCvChunk(
        chunk=_embedded("chunk_1", 0).chunk,
        embedding=(0.1, 0.2, 0.3, 0.4),
        embedding_model="wrong",
        embedding_dimension=4,
        normalized=True,
    )

    with pytest.raises(CvVectorStoreError, match="model mismatch"):
        repository.upsert_embeddings((wrong_model,))


def test_reset_collection_removes_persistent_records(tmp_path: Path) -> None:
    """The repository exposes reset mechanics without making reset the default."""

    repository = _repository(tmp_path)
    repository.upsert_embeddings((_embedded("chunk_1", 0),))

    repository.reset_collection()

    assert repository.get_collection_info().record_count == 0


def test_document_completeness_and_raw_query_are_exposed(tmp_path: Path) -> None:
    """The repository detects partial documents and returns traceable raw matches."""

    repository = _repository(tmp_path)
    repository.upsert_embeddings(
        (_embedded("chunk_1", 0), _embedded("chunk_2", 1))
    )

    complete = repository.get_document_summaries()[0]
    matches = repository.query_nearest((0.5, 0.5, 0.5, 0.5), n_results=1)
    repository.collection.delete(ids=["chunk_2"])
    incomplete = repository.get_document_summaries()[0]

    assert complete.complete is True
    assert complete.expected_chunk_count == 2
    assert matches[0].chunk_id in {"chunk_1", "chunk_2"}
    assert matches[0].metadata["candidate_id"] == "candidate_001"
    assert incomplete.complete is False
    assert incomplete.stored_chunk_count == 1
    assert incomplete.expected_chunk_count == 2


def _repository(
    path: Path,
    *,
    upsert_batch_size: int = 100,
) -> CvChromaRepository:
    return CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=path,
            collection_name="cv_chunks",
            index_version="cv-index-v1",
            embedding_model="test-model",
            embedding_dimension=4,
            chunking_version="cv-sections-v1",
            distance_metric="cosine",
            upsert_batch_size=upsert_batch_size,
        )
    )


def _embedded(chunk_id: str, index: int) -> EmbeddedCvChunk:
    source = CvSourceMetadata(
        document_id="document_abc",
        document_hash="a" * 64,
        candidate_id="candidate_001",
        candidate_name="Jane Example",
        professional_title="Backend Engineer",
        source_filename="jane.pdf",
        source_path=Path("/tmp/jane.pdf"),
    )
    chunk = CvChunk(
        chunk_id=chunk_id,
        source=source,
        section_name="experience",
        page_numbers=(1,),
        chunk_index=index,
        chunking_version="cv-sections-v1",
        text=f"Evidence {index}",
    )
    return EmbeddedCvChunk(
        chunk=chunk,
        embedding=(0.5, 0.5, 0.5, 0.5),
        embedding_model="test-model",
        embedding_dimension=4,
        normalized=True,
    )
