"""Data objects passed between the PDF ingestion stages.

These models describe a CV independently from the way it was created. A PDF
can come from the included demo data, an administrator folder, or a future
upload endpoint.

The main transformation is:

``CvSourceMetadata`` -> ``ExtractedCvDocument`` -> ``CvChunk``

Every object keeps the same document hash, candidate ID, filename, and page
information. This lets later search results point back to the exact PDF source.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CvSourceMetadata:
    """Identity and display information shared by every page and chunk of one PDF.

``document_hash`` is calculated from the PDF bytes and is the technical
identity. The filename is only a human-readable label and may change without
creating a new document.
"""

    document_id: str
    document_hash: str
    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    source_filename: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class ExtractedCvPage:
    """Extracted text for one PDF page, using page numbers that start at 1."""

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
    """One complete CV PDF represented as ordered extracted pages.

All pages belong to the same source document and candidate. Keeping this
boundary prevents text from different CVs from being mixed during chunking.
"""

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
    """One bounded piece of PDF text prepared for embedding and search.

    The text comes only from the PDF. Candidate identity, pages, section, and
    filename remain separate metadata so search can group evidence by person
    and create accurate citations.
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
    """A planned PDF rename that can be reviewed before the file is changed."""

    source_path: Path
    target_path: Path
    document_id: str
    candidate_name: str
    professional_title: str

    @property
    def changes_filename(self) -> bool:
        """Return whether applying this plan would change the path."""

        return self.source_path != self.target_path
