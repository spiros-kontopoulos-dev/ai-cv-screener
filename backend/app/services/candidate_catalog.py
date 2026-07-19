"""Read-only candidate catalogue assembled from persisted index metadata.

The service deliberately uses Chroma metadata rather than candidate profile JSON.
That keeps the API aligned with the PDF/index truth boundary established in WP5:
sidebar identity may be displayed, but answer evidence still comes only from
retrieved PDF chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from app.core.config import Settings
from app.cv_ingestion import (
    CvChromaRepository,
    CvVectorStoreConfig,
    CvVectorStoreError,
    RawStoredChunk,
    VectorIndexCoverage,
)
from app.schemas.candidate import CANDIDATE_ID_PATTERN


_CANDIDATE_ID_RE = re.compile(CANDIDATE_ID_PATTERN)


class CandidateCatalogError(RuntimeError):
    """Raised when indexed candidate metadata is unavailable or inconsistent."""


class CandidateNotFoundError(CandidateCatalogError):
    """Raised when a requested candidate ID is not present in the index."""


class CandidatePdfUnavailableError(CandidateCatalogError):
    """Raised when indexed metadata cannot resolve to a trusted local PDF."""


@dataclass(frozen=True, slots=True)
class IndexedCandidate:
    """Stable read-only identity for one candidate represented in Chroma."""

    candidate_id: str
    name: str
    professional_title: str
    document_id: str
    document_hash: str
    source_filename: str
    source_path: Path
    cv_available: bool
    photo_available: bool


class CandidateCatalogService:
    """Expose candidate and index metadata without reading generation JSON."""

    def __init__(
        self,
        settings: Settings,
        *,
        repository: CvChromaRepository,
    ) -> None:
        self._settings = settings
        self._repository = repository

    def list_candidates(self) -> tuple[IndexedCandidate, ...]:
        """Return one deterministic catalogue row per indexed candidate."""

        try:
            chunks = self._repository.get_all_chunks()
        except CvVectorStoreError as error:
            raise CandidateCatalogError(
                "The candidate index could not be read."
            ) from error

        grouped: dict[str, list[RawStoredChunk]] = {}
        for chunk in chunks:
            candidate_id = _required_metadata_text(
                chunk.metadata,
                "candidate_id",
            )
            if _CANDIDATE_ID_RE.fullmatch(candidate_id) is None:
                raise CandidateCatalogError(
                    "Indexed candidate metadata contains an invalid candidate ID."
                )
            grouped.setdefault(candidate_id, []).append(chunk)

        candidates = [
            self._build_candidate(candidate_id, candidate_chunks)
            for candidate_id, candidate_chunks in grouped.items()
        ]
        return tuple(sorted(candidates, key=lambda item: item.candidate_id))

    def get_index_coverage(self) -> VectorIndexCoverage:
        """Return collection coverage while translating storage failures."""

        try:
            return self._repository.get_index_coverage()
        except CvVectorStoreError as error:
            raise CandidateCatalogError(
                "The candidate index could not be inspected."
            ) from error

    def get_candidate(self, candidate_id: str) -> IndexedCandidate:
        """Return one candidate or raise a stable not-found error."""

        normalized = candidate_id.strip()
        if _CANDIDATE_ID_RE.fullmatch(normalized) is None:
            raise CandidateNotFoundError("Unknown candidate ID.")

        for candidate in self.list_candidates():
            if candidate.candidate_id == normalized:
                return candidate
        raise CandidateNotFoundError("Unknown candidate ID.")

    def resolve_candidate_pdf(self, candidate_id: str) -> Path:
        """Resolve one indexed PDF only within configured trusted directories."""

        candidate = self.get_candidate(candidate_id)
        filename = candidate.source_filename
        if (
            Path(filename).name != filename
            or Path(filename).suffix.casefold() != ".pdf"
        ):
            raise CandidatePdfUnavailableError(
                "The indexed candidate PDF metadata is invalid."
            )

        allowed_roots = tuple(
            dict.fromkeys(
                path.resolve()
                for path in (
                    self._settings.cv_ingestion_default_directory,
                    self._settings.cv_pdfs_output_directory,
                )
            )
        )
        candidate_paths = (
            candidate.source_path,
            *(root / filename for root in allowed_roots),
        )

        for path in candidate_paths:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if not any(resolved.is_relative_to(root) for root in allowed_roots):
                continue
            if resolved.is_file() and resolved.suffix.casefold() == ".pdf":
                return resolved

        raise CandidatePdfUnavailableError(
            "The candidate CV is not available on this server."
        )

    def _build_candidate(
        self,
        candidate_id: str,
        chunks: list[RawStoredChunk],
    ) -> IndexedCandidate:
        """Validate consistent document identity across all candidate chunks."""

        metadata = chunks[0].metadata
        values = {
            "name": _required_metadata_text(metadata, "candidate_name"),
            "professional_title": _required_metadata_text(
                metadata,
                "professional_title",
            ),
            "document_id": _required_metadata_text(metadata, "document_id"),
            "document_hash": _required_metadata_text(metadata, "document_hash"),
            "source_filename": _required_metadata_text(
                metadata,
                "source_filename",
            ),
            "source_path": _required_metadata_text(metadata, "source_path"),
        }

        for chunk in chunks[1:]:
            checks = {
                "candidate_name": values["name"],
                "professional_title": values["professional_title"],
                "document_id": values["document_id"],
                "document_hash": values["document_hash"],
                "source_filename": values["source_filename"],
                "source_path": values["source_path"],
            }
            for key, expected in checks.items():
                if _required_metadata_text(chunk.metadata, key) != expected:
                    raise CandidateCatalogError(
                        f"Indexed metadata for {candidate_id} is inconsistent."
                    )

        source_filename = values["source_filename"]
        if Path(source_filename).name != source_filename:
            raise CandidateCatalogError(
                f"Indexed filename for {candidate_id} is not a safe basename."
            )

        source_path = Path(values["source_path"])
        cv_available = self._candidate_pdf_exists(source_path, source_filename)
        photo_path = self._settings.candidate_images_directory / f"{candidate_id}.webp"

        return IndexedCandidate(
            candidate_id=candidate_id,
            name=values["name"],
            professional_title=values["professional_title"],
            document_id=values["document_id"],
            document_hash=values["document_hash"],
            source_filename=source_filename,
            source_path=source_path,
            cv_available=cv_available,
            photo_available=photo_path.is_file(),
        )

    def _candidate_pdf_exists(self, source_path: Path, filename: str) -> bool:
        """Check the indexed path and safe configured filename fallbacks."""

        roots = (
            self._settings.cv_ingestion_default_directory.resolve(),
            self._settings.cv_pdfs_output_directory.resolve(),
        )
        paths = (source_path, *(root / filename for root in roots))
        for path in paths:
            try:
                resolved = path.resolve()
            except OSError:
                continue
            inside_trusted_root = any(
                resolved.is_relative_to(root) for root in roots
            )
            if inside_trusted_root and resolved.is_file():
                return True
        return False


def build_candidate_catalog_service(settings: Settings) -> CandidateCatalogService:
    """Build the catalogue over the same compatible Chroma collection as WP5-7."""

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
    return CandidateCatalogService(settings, repository=repository)


def _required_metadata_text(metadata: dict[str, Any], key: str) -> str:
    """Read one required scalar string from trusted index metadata."""

    value = str(metadata.get(key, "")).strip()
    if not value:
        raise CandidateCatalogError(
            f"Indexed candidate metadata is missing '{key}'."
        )
    return value
