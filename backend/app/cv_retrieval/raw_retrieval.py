"""Run broad semantic search over the persistent CV index.

The question is embedded with the same local model used for CV chunks. ChromaDB
then returns the nearest text chunks in distance order.

This stage is designed for recall: it tries to bring related evidence into the
search pool. It does not yet decide whether an exact number is correct, combine
several chunks for one person, or decide whether a candidate fully matches.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.core.config import Settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvEmbeddingError,
    CvVectorStoreConfig,
    CvVectorStoreError,
    RawVectorMatch,
    VectorCollectionInfo,
    get_embedding_provider,
)
from app.cv_retrieval.models import (
    CvRawRetrievalContractError,
    RawCvRetrievalConfig,
    RawCvRetrievalHit,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
)


class CvRawRetrievalError(RuntimeError):
    """Raised when semantic search cannot return safe, usable evidence."""


class QueryEmbeddingProvider(Protocol):
    """Small interface for turning recruiter questions into embedding vectors."""

    def embed_texts(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        """Create vectors for one or more question strings."""


class RawVectorRepository(Protocol):
    """Read-only interface used to inspect and query the Chroma collection."""

    def get_collection_info(self) -> VectorCollectionInfo:
        """Open the collection and verify its compatibility metadata."""

    def query_nearest(
        self,
        query_embedding: Sequence[float],
        *,
        n_results: int,
    ) -> tuple[RawVectorMatch, ...]:
        """Return raw Chroma matches in nearest-neighbour order."""


class RawCvRetriever:
    """Embed one question and retrieve a broad pool of source-traceable chunks."""

    def __init__(
        self,
        config: RawCvRetrievalConfig,
        *,
        embedding_provider: QueryEmbeddingProvider,
        vector_repository: RawVectorRepository,
    ) -> None:
        self._config = config
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository

    @property
    def config(self) -> RawCvRetrievalConfig:
        """Return immutable broad-retrieval settings."""

        return self._config

    def retrieve(self, query: RawCvRetrievalQuery) -> RawCvRetrievalResult:
        """Search the vector index for chunks related to the question.

        The method checks question length, collection compatibility, embedding output,
        and stored metadata. The result remains chunk-level and follows Chroma distance
        order.
        """

        if len(query.text) > self._config.max_question_characters:
            raise CvRawRetrievalError(
                "Retrieval question exceeds the configured maximum of "
                f"{self._config.max_question_characters} characters."
            )

        try:
            result_limit = self._config.resolve_result_limit(query.result_limit)
            collection_info = self._vector_repository.get_collection_info()
        except CvRawRetrievalContractError as error:
            raise CvRawRetrievalError(str(error)) from error
        except CvVectorStoreError as error:
            raise CvRawRetrievalError(
                f"CV vector collection is unavailable or incompatible: {error}"
            ) from error

        if collection_info.record_count == 0:
            raise CvRawRetrievalError(
                "The CV vector collection is empty. Run ingestion first."
            )

        try:
            query_vectors = self._embedding_provider.embed_texts((query.text,))
            query_vector = query_vectors[0]
            matches = self._vector_repository.query_nearest(
                query_vector,
                n_results=result_limit,
            )
            hits = tuple(
                _build_typed_hit(rank, match)
                for rank, match in enumerate(matches, start=1)
            )
        except CvEmbeddingError as error:
            raise CvRawRetrievalError(
                f"Unable to embed retrieval question: {error}"
            ) from error
        except CvVectorStoreError as error:
            raise CvRawRetrievalError(
                f"Unable to query the CV vector collection: {error}"
            ) from error
        except (CvRawRetrievalContractError, IndexError) as error:
            raise CvRawRetrievalError(
                f"Persisted CV retrieval evidence is invalid: {error}"
            ) from error

        collection_metadata = collection_info.metadata
        return RawCvRetrievalResult(
            query=query,
            requested_result_limit=result_limit,
            collection_name=collection_info.collection_name,
            collection_record_count=collection_info.record_count,
            distance_metric=collection_info.distance_metric,
            embedding_model=_metadata_text(
                collection_metadata,
                "embedding_model",
            ),
            embedding_dimension=_metadata_integer(
                collection_metadata,
                "embedding_dimension",
            ),
            hits=hits,
        )


def build_raw_cv_retriever(
    settings: Settings,
    *,
    vector_repository: RawVectorRepository | None = None,
) -> RawCvRetriever:
    """Build semantic search from application settings.

    The builder reuses the cached embedding model and creates a compatible Chroma
    repository with the same model, dimension, chunking, and distance settings used
    when the index was built.
    """

    embedding_provider = get_embedding_provider(
        settings.cv_embedding_model_name,
        settings.cv_embedding_expected_dimension,
        settings.cv_embedding_batch_size,
        settings.cv_embedding_normalize,
        settings.cv_embedding_device,
        settings.cv_embedding_cache_directory,
    )
    active_repository = vector_repository or CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=settings.cv_vector_store_directory,
            collection_name=settings.cv_vector_collection_name,
            index_version=settings.cv_vector_index_version,
            embedding_model=settings.cv_embedding_model_name,
            embedding_dimension=settings.cv_embedding_expected_dimension,
            chunking_version=settings.cv_chunking_version,
            distance_metric=settings.cv_vector_distance_metric,
            upsert_batch_size=settings.cv_vector_upsert_batch_size,
        )
    )
    return RawCvRetriever(
        RawCvRetrievalConfig(
            default_result_limit=settings.cv_raw_retrieval_default_limit,
            max_result_limit=settings.cv_raw_retrieval_max_limit,
            max_question_characters=(
                settings.cv_retrieval_max_question_characters
            ),
        ),
        embedding_provider=embedding_provider,
        vector_repository=active_repository,
    )


def _build_typed_hit(rank: int, match: RawVectorMatch) -> RawCvRetrievalHit:
    """Convert one Chroma match into the checked raw-hit model."""

    return RawCvRetrievalHit(
        rank=rank,
        chunk_id=match.chunk_id,
        distance=match.distance,
        text=match.text,
        source=RawCvRetrievalSource.from_chroma_metadata(match.metadata),
    )


def _metadata_text(metadata: dict[str, object], key: str) -> str:
    """Read required text collection metadata for result diagnostics."""

    value = str(metadata.get(key, "")).strip()
    if not value:
        raise CvRawRetrievalError(
            f"CV vector collection metadata is missing valid '{key}'."
        )
    return value


def _metadata_integer(metadata: dict[str, object], key: str) -> int:
    """Read required numeric collection metadata for result diagnostics."""

    try:
        value = int(metadata[key])
    except (KeyError, TypeError, ValueError) as error:
        raise CvRawRetrievalError(
            f"CV vector collection metadata is missing valid '{key}'."
        ) from error
    if value < 1:
        raise CvRawRetrievalError(
            f"CV vector collection metadata '{key}' must be positive."
        )
    return value
