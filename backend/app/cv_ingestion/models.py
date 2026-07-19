"""Immutable contracts for PDF extraction and future RAG ingestion.

These models deliberately describe documents independently from the synthetic
candidate generator. A PDF may come from the committed demo dataset, a file
copied into an administrator folder, or a future upload endpoint. Every later
chunk and vector can inherit the same stable source metadata.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CvSourceMetadata:
    """Stable technical and human-readable identity for one PDF CV."""

    document_id: str
    document_hash: str
    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    source_filename: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class ExtractedCvPage:
    """Normalized text and source metadata for one one-based PDF page."""

    source: CvSourceMetadata
    page_number: int
    total_pages: int
    text: str

    @property
    def text_character_count(self) -> int:
        """Return the number of non-whitespace extracted characters."""

        return len("".join(self.text.split()))


@dataclass(frozen=True, slots=True)
class ExtractedCvDocument:
    """A complete PDF represented as ordered, candidate-safe pages."""

    source: CvSourceMetadata
    pages: tuple[ExtractedCvPage, ...]

    @property
    def page_count(self) -> int:
        """Return the number of extracted pages."""

        return len(self.pages)

    @property
    def text(self) -> str:
        """Join page text without losing page order."""

        return "\n\n".join(page.text for page in self.pages)

    @property
    def text_character_count(self) -> int:
        """Return the total number of non-whitespace characters."""

        return sum(page.text_character_count for page in self.pages)


@dataclass(frozen=True, slots=True)
class CvChunk:
    """One stable, candidate-safe unit prepared for later embedding.

    ``text`` contains only content extracted from the source PDF. Candidate and
    source identity remain structured metadata, so later retrieval can group
    evidence without injecting generator JSON into the knowledge content.
    """

    chunk_id: str
    source: CvSourceMetadata
    section_name: str
    page_numbers: tuple[int, ...]
    chunk_index: int
    chunking_version: str
    text: str

    @property
    def text_character_count(self) -> int:
        """Return the number of non-whitespace characters in this chunk."""

        return len("".join(self.text.split()))

    @property
    def page_number_start(self) -> int:
        """Return the first source page represented by this chunk."""

        return self.page_numbers[0]

    @property
    def page_number_end(self) -> int:
        """Return the last source page represented by this chunk."""

        return self.page_numbers[-1]

    @property
    def page_label(self) -> str:
        """Return a concise one-page or page-range display label."""

        if self.page_number_start == self.page_number_end:
            return str(self.page_number_start)
        return f"{self.page_number_start}-{self.page_number_end}"


@dataclass(frozen=True, slots=True)
class CvRenamePlan:
    """One safe, reviewable filesystem rename operation."""

    source_path: Path
    target_path: Path
    document_id: str
    candidate_name: str
    professional_title: str

    @property
    def changes_filename(self) -> bool:
        """Return whether applying this plan would change the path."""

        return self.source_path != self.target_path
