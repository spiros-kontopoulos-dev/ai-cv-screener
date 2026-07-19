"""Semantic retrieval assisted by bounded exact lexical and numeric scanning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvVectorStoreConfig,
    CvVectorStoreError,
    RawStoredChunk,
)
from app.cv_retrieval.evidence_analysis import (
    AssistedCvRetrievalResult,
    CvEvidenceScore,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
    normalize_search_text,
    score_evidence_text,
    score_raw_hit,
)
from app.cv_retrieval.models import (
    CvRawRetrievalContractError,
    RawCvRetrievalHit,
    RawCvRetrievalQuery,
    RawCvRetrievalSource,
)
from app.cv_retrieval.raw_retrieval import (
    CvRawRetrievalError,
    RawCvRetriever,
    build_raw_cv_retriever,
)


class CvAssistedRetrievalError(RuntimeError):
    """Raised when exact-condition-assisted retrieval cannot be completed."""


class ExactEvidenceRepository(Protocol):
    """Read-only storage boundary for bounded exact-condition scanning."""

    def get_all_chunks(self) -> tuple[RawStoredChunk, ...]:
        """Return persisted text and provenance without embeddings."""


@dataclass(frozen=True, slots=True)
class AssistedRetrievalConfig:
    """Bound the number of exact text hits added beyond semantic retrieval."""

    max_supplemental_hits: int = 50

    def __post_init__(self) -> None:
        if self.max_supplemental_hits < 0:
            raise ValueError("Maximum supplemental hit count cannot be negative.")


ScoredCandidate = tuple[
    RawCvRetrievalHit | None,
    RawStoredChunk | None,
    CvEvidenceScore,
]


class AssistedCvRetriever:
    """Merge semantic recall with exact text evidence, then rerank chunks."""

    def __init__(
        self,
        config: AssistedRetrievalConfig,
        *,
        raw_retriever: RawCvRetriever,
        exact_repository: ExactEvidenceRepository,
    ) -> None:
        self._config = config
        self._raw_retriever = raw_retriever
        self._exact_repository = exact_repository

    def retrieve(self, query: RawCvRetrievalQuery) -> AssistedCvRetrievalResult:
        """Return unique scored chunks without grouping different CV sections."""

        try:
            raw_result = self._raw_retriever.retrieve(query)
            features = analyze_recruiter_question(raw_result.query.text)
            stored_chunks = self._exact_repository.get_all_chunks()
        except (CvRawRetrievalError, CvVectorStoreError, ValueError) as error:
            raise CvAssistedRetrievalError(str(error)) from error

        try:
            semantic_by_id = {hit.chunk_id: hit for hit in raw_result.hits}
            scored_candidates: list[ScoredCandidate] = []

            for hit in raw_result.hits:
                scored_candidates.append(
                    (
                        hit,
                        None,
                        score_raw_hit(
                            hit,
                            features,
                            distance_metric=raw_result.distance_metric,
                        ),
                    )
                )

            supplemental: list[tuple[RawStoredChunk, CvEvidenceScore]] = []
            for record in stored_chunks:
                if record.chunk_id in semantic_by_id:
                    continue
                score = score_evidence_text(record.text, features)
                if features.has_numeric_constraints:
                    # For numeric questions, the collection scan exists to
                    # recover a relation-valid number that semantic top-k may
                    # miss. Pure lexical overlap is not enough to add a new
                    # chunk because it would recreate broad noisy retrieval.
                    if score.numeric_score <= 0.0:
                        continue
                elif score.lexical_score <= 0.0:
                    continue
                supplemental.append((record, score))

            supplemental.sort(
                key=lambda item: (
                    item[1].contextual_numeric_match,
                    item[1].numeric_score,
                    item[1].lexical_score,
                    item[1].combined_score,
                    item[0].chunk_id,
                ),
                reverse=True,
            )
            for record, score in supplemental[
                : self._config.max_supplemental_hits
            ]:
                scored_candidates.append((None, record, score))

            unique_candidates, duplicates_removed = _deduplicate_candidates(
                scored_candidates
            )
            ordered = sorted(
                unique_candidates,
                key=lambda item: (
                    item[2].combined_score,
                    item[2].contextual_numeric_match,
                    item[2].numeric_score,
                    item[2].lexical_score,
                    item[2].semantic_score,
                    -(item[0].rank if item[0] is not None else 10_000),
                ),
                reverse=True,
            )

            hits = tuple(
                _build_scored_hit(rank, semantic_hit, stored_record, score)
                for rank, (semantic_hit, stored_record, score) in enumerate(
                    ordered,
                    start=1,
                )
            )
            return AssistedCvRetrievalResult(
                raw_result=raw_result,
                query_features=features,
                scanned_record_count=len(stored_chunks),
                duplicates_removed=duplicates_removed,
                supplemental_hit_count=sum(
                    hit.supplemental_exact_hit for hit in hits
                ),
                hits=hits,
            )
        except (CvRawRetrievalContractError, ValueError) as error:
            raise CvAssistedRetrievalError(
                f"Persisted exact CV evidence is invalid: {error}"
            ) from error


def build_assisted_cv_retriever(settings: Settings) -> AssistedCvRetriever:
    """Build one shared repository plus the cached semantic retrieval provider."""

    repository = CvChromaRepository(
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
    raw_retriever = build_raw_cv_retriever(
        settings,
        vector_repository=repository,
    )
    return AssistedCvRetriever(
        AssistedRetrievalConfig(
            max_supplemental_hits=(
                settings.cv_assisted_retrieval_max_supplemental_hits
            )
        ),
        raw_retriever=raw_retriever,
        exact_repository=repository,
    )


def _deduplicate_candidates(
    candidates: list[ScoredCandidate],
) -> tuple[list[ScoredCandidate], int]:
    """Remove repeated IDs and candidate-local duplicate text, keeping best score."""

    ordered = sorted(
        candidates,
        key=lambda item: item[2].combined_score,
        reverse=True,
    )
    seen_ids: set[str] = set()
    seen_text: set[tuple[str, str]] = set()
    unique: list[ScoredCandidate] = []
    duplicates = 0
    for semantic_hit, stored_record, score in ordered:
        chunk_id = (
            semantic_hit.chunk_id
            if semantic_hit is not None
            else stored_record.chunk_id
        )
        source = (
            semantic_hit.source
            if semantic_hit is not None
            else RawCvRetrievalSource.from_chroma_metadata(
                stored_record.metadata
            )
        )
        text = (
            semantic_hit.text
            if semantic_hit is not None
            else stored_record.text
        )
        text_key = (source.candidate_id, normalize_search_text(text))
        if chunk_id in seen_ids or text_key in seen_text:
            duplicates += 1
            continue
        seen_ids.add(chunk_id)
        seen_text.add(text_key)
        unique.append((semantic_hit, stored_record, score))
    return unique, duplicates


def _build_scored_hit(
    rank: int,
    semantic_hit: RawCvRetrievalHit | None,
    stored_record: RawStoredChunk | None,
    score: CvEvidenceScore,
) -> ScoredCvEvidenceHit:
    """Create one public scored hit from semantic or exact-scan evidence."""

    if semantic_hit is not None:
        return ScoredCvEvidenceHit(
            rank=rank,
            raw_rank=semantic_hit.rank,
            chunk_id=semantic_hit.chunk_id,
            distance=semantic_hit.distance,
            text=semantic_hit.text,
            source=semantic_hit.source,
            score=score,
            supplemental_exact_hit=False,
        )
    if stored_record is None:
        raise ValueError("Scored evidence is missing both source record types.")
    return ScoredCvEvidenceHit(
        rank=rank,
        raw_rank=None,
        chunk_id=stored_record.chunk_id,
        distance=None,
        text=stored_record.text,
        source=RawCvRetrievalSource.from_chroma_metadata(
            stored_record.metadata
        ),
        score=score,
        supplemental_exact_hit=True,
    )
