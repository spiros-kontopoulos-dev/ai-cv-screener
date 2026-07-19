"""Fingerprint and extract arbitrary PDF CV documents with PyMuPDF.

The extractor is reusable by the current administrator CLI and a future upload
endpoint. It reads only the supplied PDF bytes: no candidate-profile JSON and
no assumptions about how the document was generated.
"""

from collections.abc import Callable, Sequence
from hashlib import sha256
from pathlib import Path
import re

import pymupdf

from app.cv_ingestion.models import (
    CvSourceMetadata,
    ExtractedCvDocument,
    ExtractedCvPage,
)
from app.cv_ingestion.selection import validate_cv_pdf_path


_DOCUMENT_ID_PREFIX_LENGTH = 16
_GENERATED_CANDIDATE_ID_PATTERN = re.compile(
    r"\bcandidate_\d{3}\b",
    flags=re.IGNORECASE,
)
_PAGE_FOOTER_PATTERN = re.compile(
    r"^page\s+\d+\s+of\s+\d+$",
    flags=re.IGNORECASE,
)
_STANDALONE_BULLETS = frozenset({"•", "·", "▪", "◦"})
_CV_TITLE_WORDS = frozenset(
    {
        "cv",
        "curriculumvitae",
        "resume",
        "résumé",
    }
)
_SECTION_HEADINGS = frozenset(
    {
        "professional profile",
        "professional summary",
        "profile",
        "summary",
        "professional experience",
        "work experience",
        "employment history",
        "skills",
        "languages",
        "education",
        "certifications",
        "projects",
        "selected projects",
    }
)


class CvDocumentExtractionError(RuntimeError):
    """Raised when a selected PDF cannot become a valid extracted document."""


def calculate_pdf_sha256(path: Path) -> str:
    """Return a SHA-256 fingerprint of the exact PDF file bytes."""

    validated_path = validate_cv_pdf_path(path)
    digest = sha256()
    try:
        with validated_path.open("rb") as source_file:
            for block in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise CvDocumentExtractionError(
            f"CV PDF could not be read for fingerprinting: {validated_path}"
        ) from error

    return digest.hexdigest()


def normalize_extracted_page_text(raw_text: str) -> str:
    """Clean extraction noise while preserving headings and line boundaries."""

    normalized_lines: list[str] = []
    previous_line_was_blank = False

    normalized_newlines = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in normalized_newlines.split("\n"):
        line = " ".join(raw_line.replace("\u00a0", " ").split()).strip()

        if _PAGE_FOOTER_PATTERN.fullmatch(line) or line in _STANDALONE_BULLETS:
            continue

        if not line:
            if normalized_lines and not previous_line_was_blank:
                normalized_lines.append("")
            previous_line_was_blank = True
            continue

        normalized_lines.append(line)
        previous_line_was_blank = False

    while normalized_lines and not normalized_lines[-1]:
        normalized_lines.pop()

    return "\n".join(normalized_lines)


def load_cv_document(
    path: Path,
    *,
    candidate_id: str | None = None,
    candidate_name: str | None = None,
    professional_title: str | None = None,
) -> ExtractedCvDocument:
    """Extract one PDF into a deterministic document and page contract."""

    validated_path = validate_cv_pdf_path(path)
    document_hash = calculate_pdf_sha256(validated_path)
    document_id = f"document_{document_hash[:_DOCUMENT_ID_PREFIX_LENGTH]}"

    try:
        with pymupdf.open(validated_path) as pdf_document:
            if pdf_document.page_count < 1:
                raise CvDocumentExtractionError(
                    f"CV PDF contains no pages: {validated_path}"
                )

            normalized_page_texts = tuple(
                normalize_extracted_page_text(
                    page.get_text("text", sort=True)
                )
                for page in pdf_document
            )
    except CvDocumentExtractionError:
        raise
    except (pymupdf.FileDataError, RuntimeError, OSError, ValueError) as error:
        raise CvDocumentExtractionError(
            f"CV PDF could not be opened or extracted: {validated_path}"
        ) from error

    if not any("".join(page_text.split()) for page_text in normalized_page_texts):
        raise CvDocumentExtractionError(
            f"CV PDF contains no extractable text: {validated_path}"
        )

    first_page_text = normalized_page_texts[0]
    detected_candidate_name, detected_professional_title = (
        detect_candidate_header(first_page_text)
    )
    resolved_candidate_id = candidate_id or detect_candidate_id(
        validated_path,
        first_page_text,
        document_hash=document_hash,
    )
    resolved_candidate_name = _clean_optional_metadata(
        candidate_name or detected_candidate_name
    )
    resolved_professional_title = _clean_optional_metadata(
        professional_title or detected_professional_title
    )

    source = CvSourceMetadata(
        document_id=document_id,
        document_hash=document_hash,
        candidate_id=resolved_candidate_id,
        candidate_name=resolved_candidate_name,
        professional_title=resolved_professional_title,
        source_filename=validated_path.name,
        source_path=validated_path.resolve(),
    )
    total_pages = len(normalized_page_texts)
    pages = tuple(
        ExtractedCvPage(
            source=source,
            page_number=page_index,
            total_pages=total_pages,
            text=page_text,
        )
        for page_index, page_text in enumerate(
            normalized_page_texts,
            start=1,
        )
    )

    return ExtractedCvDocument(source=source, pages=pages)


def load_cv_documents(
    paths: Sequence[Path],
) -> tuple[ExtractedCvDocument, ...]:
    """Extract a deterministic batch and reject ambiguous document identity."""

    if not paths:
        raise CvDocumentExtractionError(
            "At least one PDF path is required for extraction."
        )

    documents = tuple(
        load_cv_document(path)
        for path in sorted(
            paths,
            key=lambda item: (
                item.name.casefold(),
                item.as_posix().casefold(),
            ),
        )
    )

    _reject_duplicate_values(
        documents,
        value_name="document content hash",
        value_getter=lambda document: document.source.document_hash,
    )
    _reject_duplicate_values(
        documents,
        value_name="candidate ID",
        value_getter=lambda document: document.source.candidate_id.casefold(),
    )

    return documents


def detect_candidate_id(
    path: Path,
    first_page_text: str,
    *,
    document_hash: str,
) -> str:
    """Derive candidate identity without depending on a fixed filename format."""

    filename_match = _GENERATED_CANDIDATE_ID_PATTERN.search(path.stem)
    if filename_match is not None:
        return filename_match.group(0).casefold()

    text_match = _GENERATED_CANDIDATE_ID_PATTERN.search(first_page_text)
    if text_match is not None:
        return text_match.group(0).casefold()

    return f"candidate_{document_hash[:_DOCUMENT_ID_PREFIX_LENGTH]}"


def detect_candidate_header(first_page_text: str) -> tuple[str | None, str | None]:
    """Best-effort detection of the visible name and role near a CV header.

    Upload callers may override these values explicitly. The heuristic is
    intentionally conservative: failure to detect optional display metadata
    never makes an otherwise extractable PDF invalid.
    """

    lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
    content_lines = [line for line in lines[:20] if not _is_cv_title(line)]

    candidate_name: str | None = None
    name_index: int | None = None
    for index, line in enumerate(content_lines):
        if _looks_like_candidate_name(line):
            candidate_name = line
            name_index = index
            break

    if name_index is None:
        return None, None

    for line in content_lines[name_index + 1 :]:
        if _looks_like_professional_title(line):
            return candidate_name, line

    return candidate_name, None


def _reject_duplicate_values(
    documents: Sequence[ExtractedCvDocument],
    *,
    value_name: str,
    value_getter: Callable[[ExtractedCvDocument], str],
) -> None:
    """Reject duplicate technical or candidate identity inside one batch."""

    documents_by_value: dict[str, list[ExtractedCvDocument]] = {}
    for document in documents:
        documents_by_value.setdefault(
            value_getter(document),
            [],
        ).append(document)

    duplicate_groups = [
        group
        for group in documents_by_value.values()
        if len(group) > 1
    ]
    if not duplicate_groups:
        return

    duplicate_paths = "; ".join(
        ", ".join(document.source.source_filename for document in group)
        for group in duplicate_groups
    )
    raise CvDocumentExtractionError(
        f"Selected PDFs contain duplicate {value_name}: {duplicate_paths}."
    )


def _is_cv_title(line: str) -> bool:
    """Return whether a line is only a generic CV or résumé title."""

    compact = re.sub(r"[^\wÀ-ÿ]+", "", line, flags=re.UNICODE).casefold()
    return compact in _CV_TITLE_WORDS


def _looks_like_candidate_name(line: str) -> bool:
    """Return whether one header line plausibly contains a person's name."""

    if (
        "@" in line
        or any(character.isdigit() for character in line)
        or line.casefold() in _SECTION_HEADINGS
    ):
        return False

    words = line.split()
    if not 2 <= len(words) <= 6:
        return False

    return all(
        any(character.isalpha() for character in word)
        for word in words
    )


def _looks_like_professional_title(line: str) -> bool:
    """Return whether one line can serve as professional-title metadata."""

    folded_line = line.casefold()
    return not (
        "@" in line
        or any(character.isdigit() for character in line)
        or folded_line in _SECTION_HEADINGS
        or "candidate_" in folded_line
        or "·" in line
    )


def _clean_optional_metadata(value: str | None) -> str | None:
    """Trim optional caller or heuristic metadata consistently."""

    if value is None:
        return None

    cleaned_value = " ".join(value.split()).strip()
    return cleaned_value or None
