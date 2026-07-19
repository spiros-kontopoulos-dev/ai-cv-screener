"""Typed contracts for broad, source-traceable CV retrieval.

Work Package 5 exposed storage-level Chroma matches containing a free-form
metadata dictionary. Work Package 6 converts those records into immutable
application contracts before candidate grouping, exact-condition scoring, or
LLM context construction is allowed to use them.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


class CvRawRetrievalContractError(ValueError):
    """Raised when a query or persisted raw result violates its contract."""


@dataclass(frozen=True, slots=True)
class RawCvRetrievalConfig:
    """Limits governing broad first-stage semantic retrieval.

    The default deliberately retrieves substantially more chunks than a final
    answer will consume. Later WP6 patches will deduplicate, group, score, and
    budget this broad candidate pool.
    """

    default_result_limit: int = 50
    max_result_limit: int = 200
    max_question_characters: int = 2000

    def __post_init__(self) -> None:
        """Reject contradictory limits before embedding or Chroma access."""

        if self.default_result_limit < 1:
            raise CvRawRetrievalContractError(
                "Default raw retrieval limit must be positive."
            )
        if self.max_result_limit < 1:
            raise CvRawRetrievalContractError(
                "Maximum raw retrieval limit must be positive."
            )
        if self.default_result_limit > self.max_result_limit:
            raise CvRawRetrievalContractError(
                "Default raw retrieval limit cannot exceed the maximum limit."
            )
        if self.max_question_characters < 1:
            raise CvRawRetrievalContractError(
                "Maximum retrieval-question length must be positive."
            )

    def resolve_result_limit(self, requested_limit: int | None) -> int:
        """Resolve an optional caller limit within the configured safety cap."""

        result_limit = (
            self.default_result_limit
            if requested_limit is None
            else requested_limit
        )
        if result_limit < 1:
            raise CvRawRetrievalContractError(
                "Raw retrieval result limit must be positive."
            )
        if result_limit > self.max_result_limit:
            raise CvRawRetrievalContractError(
                "Raw retrieval result limit cannot exceed "
                f"{self.max_result_limit}."
            )
        return result_limit


@dataclass(frozen=True, slots=True)
class RawCvRetrievalQuery:
    """One normalized recruiter question and optional broad-result override."""

    text: str
    result_limit: int | None = None

    def __post_init__(self) -> None:
        """Normalize surrounding whitespace and reject unusable requests."""

        normalized_text = " ".join(self.text.split())
        if not normalized_text:
            raise CvRawRetrievalContractError(
                "Retrieval question cannot be empty."
            )
        if self.result_limit is not None and self.result_limit < 1:
            raise CvRawRetrievalContractError(
                "Raw retrieval result limit must be positive."
            )
        object.__setattr__(self, "text", normalized_text)


@dataclass(frozen=True, slots=True)
class RawCvRetrievalSource:
    """Complete candidate, document, page, section, and chunk provenance."""

    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    document_id: str
    document_hash: str
    source_filename: str
    source_path: str
    section_name: str
    page_numbers: tuple[int, ...]
    chunk_index: int
    chunking_version: str

    def __post_init__(self) -> None:
        """Validate provenance even when constructed outside the Chroma parser."""

        required_values = {
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "document_hash": self.document_hash,
            "source_filename": self.source_filename,
            "source_path": self.source_path,
            "section_name": self.section_name,
            "chunking_version": self.chunking_version,
        }
        for field_name, value in required_values.items():
            if not value.strip():
                raise CvRawRetrievalContractError(
                    f"Raw retrieval source field '{field_name}' cannot be empty."
                )
        if not self.page_numbers or any(page < 1 for page in self.page_numbers):
            raise CvRawRetrievalContractError(
                "Raw retrieval page numbers must be positive."
            )
        if list(self.page_numbers) != sorted(set(self.page_numbers)):
            raise CvRawRetrievalContractError(
                "Raw retrieval page numbers must be unique and ordered."
            )
        if self.chunk_index < 0:
            raise CvRawRetrievalContractError(
                "Raw retrieval chunk index cannot be negative."
            )

    @property
    def page_number_start(self) -> int:
        """Return the first PDF page represented by the evidence chunk."""

        return self.page_numbers[0]

    @property
    def page_number_end(self) -> int:
        """Return the final PDF page represented by the evidence chunk."""

        return self.page_numbers[-1]

    @property
    def page_label(self) -> str:
        """Return a concise one-page or page-range display label."""

        if self.page_number_start == self.page_number_end:
            return str(self.page_number_start)
        return f"{self.page_number_start}-{self.page_number_end}"

    @classmethod
    def from_chroma_metadata(
        cls,
        metadata: Mapping[str, Any],
    ) -> RawCvRetrievalSource:
        """Parse and validate one persisted Chroma metadata dictionary."""

        page_numbers = _parse_page_numbers(metadata)
        return cls(
            candidate_id=_required_text(metadata, "candidate_id"),
            candidate_name=_optional_text(metadata, "candidate_name"),
            professional_title=_optional_text(metadata, "professional_title"),
            document_id=_required_text(metadata, "document_id"),
            document_hash=_required_text(metadata, "document_hash"),
            source_filename=_required_text(metadata, "source_filename"),
            source_path=_required_text(metadata, "source_path"),
            section_name=_required_text(metadata, "section_name"),
            page_numbers=page_numbers,
            chunk_index=_required_non_negative_integer(metadata, "chunk_index"),
            chunking_version=_required_text(metadata, "chunking_version"),
        )


@dataclass(frozen=True, slots=True)
class RawCvRetrievalHit:
    """One ungrouped semantic chunk returned in Chroma nearest order."""

    rank: int
    chunk_id: str
    distance: float
    text: str
    source: RawCvRetrievalSource

    def __post_init__(self) -> None:
        """Protect later ranking code from malformed raw evidence."""

        if self.rank < 1:
            raise CvRawRetrievalContractError(
                "Raw retrieval rank must be positive."
            )
        if not self.chunk_id.strip():
            raise CvRawRetrievalContractError(
                "Raw retrieval chunk ID cannot be empty."
            )
        if not math.isfinite(self.distance):
            raise CvRawRetrievalContractError(
                "Raw retrieval distance must be finite."
            )
        if not self.text.strip():
            raise CvRawRetrievalContractError(
                f"Raw retrieval chunk {self.chunk_id} contains no evidence text."
            )


@dataclass(frozen=True, slots=True)
class RawCvRetrievalResult:
    """Broad first-stage retrieval output before candidate-aware processing."""

    query: RawCvRetrievalQuery
    requested_result_limit: int
    collection_name: str
    collection_record_count: int
    distance_metric: str
    embedding_model: str
    embedding_dimension: int
    hits: tuple[RawCvRetrievalHit, ...]

    def __post_init__(self) -> None:
        """Validate collection diagnostics and raw hit ordering."""

        if self.requested_result_limit < 1:
            raise CvRawRetrievalContractError(
                "Requested raw retrieval limit must be positive."
            )
        if not self.collection_name.strip():
            raise CvRawRetrievalContractError(
                "Raw retrieval collection name cannot be empty."
            )
        if self.collection_record_count < 1:
            raise CvRawRetrievalContractError(
                "Raw retrieval collection must contain records."
            )
        if not self.distance_metric.strip():
            raise CvRawRetrievalContractError(
                "Raw retrieval distance metric cannot be empty."
            )
        if not self.embedding_model.strip():
            raise CvRawRetrievalContractError(
                "Raw retrieval embedding model cannot be empty."
            )
        if self.embedding_dimension < 1:
            raise CvRawRetrievalContractError(
                "Raw retrieval embedding dimension must be positive."
            )
        expected_ranks = list(range(1, len(self.hits) + 1))
        actual_ranks = [hit.rank for hit in self.hits]
        if actual_ranks != expected_ranks:
            raise CvRawRetrievalContractError(
                "Raw retrieval hits must use consecutive one-based ranks."
            )
        if len(self.hits) > self.requested_result_limit:
            raise CvRawRetrievalContractError(
                "Raw retrieval returned more hits than requested."
            )

    @property
    def returned_result_count(self) -> int:
        """Return the number of raw chunks supplied by Chroma."""

        return len(self.hits)

    @property
    def distinct_candidate_count(self) -> int:
        """Count candidates represented without changing raw result order."""

        return len({hit.source.candidate_id for hit in self.hits})


def _required_text(metadata: Mapping[str, Any], key: str) -> str:
    """Read one required scalar metadata value as stripped text."""

    value = str(metadata.get(key, "")).strip()
    if not value:
        raise CvRawRetrievalContractError(
            f"Raw retrieval metadata is missing required field '{key}'."
        )
    return value


def _optional_text(metadata: Mapping[str, Any], key: str) -> str | None:
    """Read one optional scalar metadata value without returning empty text."""

    value = str(metadata.get(key, "")).strip()
    return value or None


def _required_non_negative_integer(
    metadata: Mapping[str, Any],
    key: str,
) -> int:
    """Read a required non-negative integer from Chroma scalar metadata."""

    value = metadata.get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise CvRawRetrievalContractError(
            f"Raw retrieval metadata field '{key}' must be an integer."
        ) from error
    if parsed < 0:
        raise CvRawRetrievalContractError(
            f"Raw retrieval metadata field '{key}' cannot be negative."
        )
    return parsed


def _parse_page_numbers(metadata: Mapping[str, Any]) -> tuple[int, ...]:
    """Parse ordered one-based source pages from persisted scalar metadata."""

    raw_page_numbers = str(metadata.get("page_numbers", "")).strip()
    values: list[int] = []
    if raw_page_numbers:
        try:
            values = [
                int(value.strip())
                for value in raw_page_numbers.split(",")
                if value.strip()
            ]
        except ValueError as error:
            raise CvRawRetrievalContractError(
                "Raw retrieval page_numbers metadata is invalid."
            ) from error
    else:
        start = metadata.get("page_number_start")
        end = metadata.get("page_number_end", start)
        try:
            start_number = int(start)
            end_number = int(end)
        except (TypeError, ValueError) as error:
            raise CvRawRetrievalContractError(
                "Raw retrieval metadata does not contain valid page numbers."
            ) from error
        if end_number < start_number:
            raise CvRawRetrievalContractError(
                "Raw retrieval page range is reversed."
            )
        values = list(range(start_number, end_number + 1))

    if not values or any(value < 1 for value in values):
        raise CvRawRetrievalContractError(
            "Raw retrieval page numbers must be positive."
        )
    if values != sorted(set(values)):
        raise CvRawRetrievalContractError(
            "Raw retrieval page numbers must be unique and ordered."
        )
    return tuple(values)
