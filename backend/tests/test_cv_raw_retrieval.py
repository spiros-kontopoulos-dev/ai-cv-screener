"""Focused tests for broad, typed, source-traceable CV retrieval."""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.cv_ingestion import (
    CvEmbeddingError,
    CvVectorStoreError,
    RawVectorMatch,
    VectorCollectionInfo,
)
from app.cv_retrieval import (
    CvRawRetrievalContractError,
    CvRawRetrievalError,
    RawCvRetrievalConfig,
    RawCvRetrievalQuery,
    RawCvRetrievalSource,
    RawCvRetriever,
    build_raw_cv_retriever,
)


class FakeProvider:
    """Record query text and return one deterministic four-value vector."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, ...]] = []

    def embed_texts(self, texts):
        self.calls.append(tuple(texts))
        if self.error:
            raise self.error
        return ((1.0, 0.0, 0.0, 0.0),)


class FakeRepository:
    """Expose collection compatibility information and deterministic matches."""

    def __init__(
        self,
        *,
        matches: tuple[RawVectorMatch, ...] | None = None,
        record_count: int = 184,
        info_error: Exception | None = None,
        query_error: Exception | None = None,
    ) -> None:
        self.matches = matches if matches is not None else (_raw_match(),)
        self.record_count = record_count
        self.info_error = info_error
        self.query_error = query_error
        self.query_calls: list[tuple[tuple[float, ...], int]] = []

    def get_collection_info(self):
        if self.info_error:
            raise self.info_error
        return VectorCollectionInfo(
            collection_name="cv_chunks",
            record_count=self.record_count,
            metadata={
                "embedding_model": "test-model",
                "embedding_dimension": 4,
            },
            distance_metric="cosine",
        )

    def query_nearest(self, vector, *, n_results):
        self.query_calls.append((tuple(vector), n_results))
        if self.query_error:
            raise self.query_error
        return self.matches[:n_results]


def test_query_and_config_normalize_and_validate_inputs() -> None:
    """Raw retrieval contracts reject empty or unsafe caller settings."""

    query = RawCvRetrievalQuery(
        text="  Who   knows Python?  ",
        result_limit=12,
    )
    config = RawCvRetrievalConfig(
        default_result_limit=50,
        max_result_limit=100,
    )

    assert query.text == "Who knows Python?"
    assert config.resolve_result_limit(None) == 50
    assert config.resolve_result_limit(12) == 12

    with pytest.raises(CvRawRetrievalContractError, match="cannot be empty"):
        RawCvRetrievalQuery(text="  ")
    with pytest.raises(CvRawRetrievalContractError, match="cannot exceed"):
        config.resolve_result_limit(101)
    with pytest.raises(CvRawRetrievalContractError, match="Default"):
        RawCvRetrievalConfig(default_result_limit=20, max_result_limit=10)


def test_source_contract_parses_complete_chroma_metadata() -> None:
    """Free-form Chroma metadata becomes one strict provenance object."""

    source = RawCvRetrievalSource.from_chroma_metadata(_metadata())

    assert source.candidate_id == "candidate_001"
    assert source.candidate_name == "Jane Example"
    assert source.professional_title == "Backend Engineer"
    assert source.document_hash == "a" * 64
    assert source.page_numbers == (1, 2)
    assert source.page_label == "1-2"
    assert source.chunk_index == 3


def test_source_contract_rejects_missing_identity_and_invalid_pages() -> None:
    """Incomplete provenance never reaches later candidate-aware stages."""

    missing_candidate = _metadata()
    missing_candidate.pop("candidate_id")
    invalid_pages = _metadata()
    invalid_pages["page_numbers"] = "2,1"

    with pytest.raises(CvRawRetrievalContractError, match="candidate_id"):
        RawCvRetrievalSource.from_chroma_metadata(missing_candidate)
    with pytest.raises(CvRawRetrievalContractError, match="unique and ordered"):
        RawCvRetrievalSource.from_chroma_metadata(invalid_pages)


def test_retriever_uses_broad_default_and_returns_typed_hits() -> None:
    """Question embedding and Chroma access preserve complete source identity."""

    provider = FakeProvider()
    repository = FakeRepository(
        matches=(
            _raw_match(chunk_id="chunk_a", distance=0.12),
            _raw_match(chunk_id="chunk_b", distance=0.18),
        )
    )
    retriever = RawCvRetriever(
        RawCvRetrievalConfig(default_result_limit=50, max_result_limit=100),
        embedding_provider=provider,
        vector_repository=repository,
    )

    result = retriever.retrieve(RawCvRetrievalQuery("Who knows Python?"))

    assert provider.calls == [("Who knows Python?",)]
    assert repository.query_calls == [((1.0, 0.0, 0.0, 0.0), 50)]
    assert result.requested_result_limit == 50
    assert result.returned_result_count == 2
    assert result.distinct_candidate_count == 1
    assert result.embedding_model == "test-model"
    assert result.embedding_dimension == 4
    assert result.hits[0].rank == 1
    assert result.hits[0].chunk_id == "chunk_a"
    assert result.hits[0].source.source_filename == "jane-example-cv.pdf"
    assert result.hits[0].source.section_name == "experience"


def test_retriever_rejects_empty_collection_before_loading_model() -> None:
    """A missing index fails clearly without unnecessary embedding work."""

    provider = FakeProvider()
    retriever = RawCvRetriever(
        RawCvRetrievalConfig(),
        embedding_provider=provider,
        vector_repository=FakeRepository(record_count=0),
    )

    with pytest.raises(CvRawRetrievalError, match="empty"):
        retriever.retrieve(RawCvRetrievalQuery("Python"))

    assert provider.calls == []


def test_retriever_enforces_question_and_result_limits() -> None:
    """Unsafe requests fail before provider or Chroma query execution."""

    provider = FakeProvider()
    repository = FakeRepository()
    retriever = RawCvRetriever(
        RawCvRetrievalConfig(
            default_result_limit=5,
            max_result_limit=10,
            max_question_characters=8,
        ),
        embedding_provider=provider,
        vector_repository=repository,
    )

    with pytest.raises(CvRawRetrievalError, match="maximum"):
        retriever.retrieve(RawCvRetrievalQuery("A question that is too long"))
    with pytest.raises(CvRawRetrievalError, match="cannot exceed"):
        retriever.retrieve(RawCvRetrievalQuery("Python", result_limit=11))

    assert provider.calls == []
    assert repository.query_calls == []


def test_retriever_translates_provider_store_and_metadata_failures() -> None:
    """External failures become one stable retrieval-layer error boundary."""

    embedding_failure = RawCvRetriever(
        RawCvRetrievalConfig(),
        embedding_provider=FakeProvider(error=CvEmbeddingError("model failed")),
        vector_repository=FakeRepository(),
    )
    store_failure = RawCvRetriever(
        RawCvRetrievalConfig(),
        embedding_provider=FakeProvider(),
        vector_repository=FakeRepository(
            query_error=CvVectorStoreError("query failed")
        ),
    )
    bad_metadata = _metadata()
    bad_metadata.pop("document_hash")
    metadata_failure = RawCvRetriever(
        RawCvRetrievalConfig(),
        embedding_provider=FakeProvider(),
        vector_repository=FakeRepository(
            matches=(
                RawVectorMatch(
                    chunk_id="chunk_bad",
                    distance=0.1,
                    text="Evidence",
                    metadata=bad_metadata,
                ),
            )
        ),
    )

    with pytest.raises(CvRawRetrievalError, match="embed"):
        embedding_failure.retrieve(RawCvRetrievalQuery("Python"))
    with pytest.raises(CvRawRetrievalError, match="query"):
        store_failure.retrieve(RawCvRetrievalQuery("Python"))
    with pytest.raises(CvRawRetrievalError, match="document_hash"):
        metadata_failure.retrieve(RawCvRetrievalQuery("Python"))


def test_factory_reuses_wp5_cached_provider_and_collection_settings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The production factory does not introduce a second embedding model path."""

    from app.cv_retrieval import raw_retrieval as module

    provider = FakeProvider()
    repository = FakeRepository()
    provider_calls = []
    repository_configs = []

    def fake_get_embedding_provider(*arguments):
        provider_calls.append(arguments)
        return provider

    def fake_repository(config):
        repository_configs.append(config)
        return repository

    monkeypatch.setattr(module, "get_embedding_provider", fake_get_embedding_provider)
    monkeypatch.setattr(module, "CvChromaRepository", fake_repository)
    settings = Settings(
        cv_embedding_model_name="test-model",
        cv_embedding_expected_dimension=4,
        cv_embedding_batch_size=8,
        cv_embedding_cache_directory=tmp_path / "models",
        cv_vector_store_directory=tmp_path / "chroma",
        cv_raw_retrieval_default_limit=25,
        cv_raw_retrieval_max_limit=80,
    )

    retriever = build_raw_cv_retriever(settings)
    result = retriever.retrieve(RawCvRetrievalQuery("Python"))

    assert provider_calls == [
        (
            "test-model",
            4,
            8,
            True,
            "cpu",
            tmp_path / "models",
        )
    ]
    assert repository_configs[0].persist_directory == tmp_path / "chroma"
    assert repository_configs[0].embedding_model == "test-model"
    assert retriever.config.default_result_limit == 25
    assert result.requested_result_limit == 25


def _raw_match(
    *,
    chunk_id: str = "chunk_1",
    distance: float = 0.12,
) -> RawVectorMatch:
    return RawVectorMatch(
        chunk_id=chunk_id,
        distance=distance,
        text="Built Python and FastAPI services.",
        metadata=_metadata(),
    )


def _metadata() -> dict[str, object]:
    return {
        "document_id": "document_abc123",
        "document_hash": "a" * 64,
        "candidate_id": "candidate_001",
        "candidate_name": "Jane Example",
        "professional_title": "Backend Engineer",
        "source_filename": "jane-example-cv.pdf",
        "source_path": "/app/data/cv_pdfs/jane-example-cv.pdf",
        "section_name": "experience",
        "page_number_start": 1,
        "page_number_end": 2,
        "page_numbers": "1,2",
        "chunk_index": 3,
        "chunking_version": "cv-sections-v1",
    }
