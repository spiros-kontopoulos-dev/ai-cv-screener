"""Turn an extracted CV document into stable, candidate-safe chunks.

This module coordinates two focused helpers:

- ``sectioning.py`` labels text as experience, skills, education, and other
  common CV sections;
- ``chunk_packing.py`` keeps each chunk within the configured size limits.

Every output chunk belongs to one document and one candidate. The chunker also
checks ordering, page numbers, sizes, and unique IDs before returning data to
the embedding stage.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.cv_ingestion.chunk_packing import (
    build_chunk_id,
    fragment_to_units,
    pack_section_units,
)
from app.cv_ingestion.models import CvChunk, ExtractedCvDocument
from app.cv_ingestion.sectioning import (
    SECTION_CERTIFICATIONS,
    SECTION_DOCUMENT,
    SECTION_EDUCATION,
    SECTION_EXPERIENCE,
    SECTION_IDENTITY,
    SECTION_LANGUAGES,
    SECTION_PROFESSIONAL_SUMMARY,
    SECTION_PROJECTS,
    SECTION_SKILLS,
    SECTION_SKILLS_AND_LANGUAGES,
    group_contiguous_sections,
    split_document_into_sections,
)


DEFAULT_CHUNKING_VERSION = "cv-sections-v1"
DEFAULT_MAX_CHARACTERS = 1200
DEFAULT_MIN_CHARACTERS = 80
DEFAULT_OVERLAP_CHARACTERS = 120


class CvChunkingError(ValueError):
    """Raised when extracted documents cannot produce safe, valid chunks."""


@dataclass(frozen=True, slots=True)
class CvChunkingConfig:
    """Version, size, and overlap settings that define the chunking contract."""

    version: str = DEFAULT_CHUNKING_VERSION
    max_characters: int = DEFAULT_MAX_CHARACTERS
    min_characters: int = DEFAULT_MIN_CHARACTERS
    overlap_characters: int = DEFAULT_OVERLAP_CHARACTERS

    def __post_init__(self) -> None:
        """Reject incompatible limits before any document is processed."""

        if not self.version.strip():
            raise CvChunkingError("Chunking version cannot be empty.")
        if self.max_characters < 200:
            raise CvChunkingError(
                "Maximum chunk size must be at least 200 characters."
            )
        if self.min_characters < 1:
            raise CvChunkingError(
                "Minimum chunk size must be at least 1 character."
            )
        if self.min_characters > self.max_characters:
            raise CvChunkingError(
                "Minimum chunk size cannot exceed maximum chunk size."
            )
        if self.overlap_characters < 0:
            raise CvChunkingError("Chunk overlap cannot be negative.")
        if self.overlap_characters >= self.max_characters:
            raise CvChunkingError(
                "Chunk overlap must be smaller than maximum chunk size."
            )


def chunk_cv_document(
    document: ExtractedCvDocument,
    *,
    config: CvChunkingConfig | None = None,
) -> tuple[CvChunk, ...]:
    """Split one extracted PDF into section-aware chunks with stable IDs."""

    active_config = config or CvChunkingConfig()
    fragments = split_document_into_sections(document)
    drafts = []

    for section_name, section_fragments in group_contiguous_sections(
        fragments
    ):
        units = tuple(
            unit
            for fragment in section_fragments
            for unit in fragment_to_units(
                fragment,
                max_characters=active_config.max_characters,
                overlap_characters=active_config.overlap_characters,
            )
        )
        drafts.extend(
            pack_section_units(
                section_name,
                units,
                max_characters=active_config.max_characters,
                min_characters=active_config.min_characters,
                overlap_characters=active_config.overlap_characters,
            )
        )

    if not drafts:
        raise CvChunkingError(
            f"CV document produced no usable chunks: "
            f"{document.source.source_filename}."
        )

    chunks = tuple(
        CvChunk(
            chunk_id=build_chunk_id(
                document_hash=document.source.document_hash,
                chunking_version=active_config.version,
                chunk_index=chunk_index,
                section_name=draft.section_name,
                page_numbers=draft.page_numbers,
                text=draft.text,
            ),
            source=document.source,
            section_name=draft.section_name,
            page_numbers=draft.page_numbers,
            chunk_index=chunk_index,
            chunking_version=active_config.version,
            text=draft.text,
        )
        for chunk_index, draft in enumerate(drafts)
    )

    _validate_chunks(document, chunks, active_config)
    return chunks


def chunk_cv_documents(
    documents: Sequence[ExtractedCvDocument],
    *,
    config: CvChunkingConfig | None = None,
) -> tuple[CvChunk, ...]:
    """Chunk several documents while keeping every candidate completely separate."""

    if not documents:
        raise CvChunkingError(
            "At least one extracted CV document is required for chunking."
        )

    active_config = config or CvChunkingConfig()
    ordered_documents = sorted(
        documents,
        key=lambda document: (
            document.source.source_filename.casefold(),
            document.source.source_path.as_posix().casefold(),
        ),
    )
    chunks = tuple(
        chunk
        for document in ordered_documents
        for chunk in chunk_cv_document(document, config=active_config)
    )

    chunk_ids = [chunk.chunk_id for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise CvChunkingError("Chunking produced duplicate stable chunk IDs.")

    return chunks


def _validate_chunks(
    document: ExtractedCvDocument,
    chunks: Sequence[CvChunk],
    config: CvChunkingConfig,
) -> None:
    """Check that every chunk keeps valid identity, pages, size, order, and ID."""

    expected_indices = list(range(len(chunks)))
    actual_indices = [chunk.chunk_index for chunk in chunks]
    if actual_indices != expected_indices:
        raise CvChunkingError("Chunk indices are not contiguous and deterministic.")

    valid_page_numbers = {page.page_number for page in document.pages}
    for chunk in chunks:
        if chunk.source is not document.source:
            raise CvChunkingError(
                "Chunk source metadata does not belong to its input document."
            )
        if not chunk.text.strip():
            raise CvChunkingError("Chunk text cannot be empty.")
        if len(chunk.text) > config.max_characters:
            raise CvChunkingError(
                f"Chunk exceeds {config.max_characters} characters: "
                f"{chunk.chunk_id}."
            )
        if not chunk.page_numbers:
            raise CvChunkingError("Chunk must preserve at least one page number.")
        if not set(chunk.page_numbers).issubset(valid_page_numbers):
            raise CvChunkingError(
                f"Chunk references a page outside its source PDF: "
                f"{chunk.chunk_id}."
            )
