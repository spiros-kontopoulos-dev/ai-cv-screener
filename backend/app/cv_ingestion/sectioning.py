"""Detect common CV sections without depending on one document template.

PyMuPDF text order may merge two visual columns onto one line. The detector
therefore accepts exact headings and carefully constrained uppercase headings
embedded after ordinary content. Unknown layouts remain valid and fall back to
a generic document section.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import re

from app.cv_ingestion.models import ExtractedCvDocument


SECTION_IDENTITY = "identity"
SECTION_PROFESSIONAL_SUMMARY = "professional_summary"
SECTION_EXPERIENCE = "experience"
SECTION_SKILLS = "skills"
SECTION_LANGUAGES = "languages"
SECTION_SKILLS_AND_LANGUAGES = "skills_and_languages"
SECTION_EDUCATION = "education"
SECTION_CERTIFICATIONS = "certifications"
SECTION_PROJECTS = "projects"
SECTION_DOCUMENT = "document"

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    SECTION_PROFESSIONAL_SUMMARY: (
        "professional profile",
        "professional summary",
        "career profile",
        "personal profile",
        "profile",
        "summary",
    ),
    SECTION_EXPERIENCE: (
        "professional experience",
        "work experience",
        "employment history",
        "career history",
        "experience",
    ),
    SECTION_SKILLS: (
        "technical skills",
        "core skills",
        "key skills",
        "competencies",
        "skills",
    ),
    SECTION_LANGUAGES: (
        "language skills",
        "spoken languages",
        "languages",
    ),
    SECTION_EDUCATION: (
        "academic background",
        "academic history",
        "education and training",
        "education",
    ),
    SECTION_CERTIFICATIONS: (
        "professional certifications",
        "certificates and certifications",
        "certifications",
        "certificates",
    ),
    SECTION_PROJECTS: (
        "selected projects",
        "personal projects",
        "portfolio projects",
        "projects",
        "portfolio",
    ),
}
_ALIAS_TO_SECTION = {
    alias: section_name
    for section_name, aliases in _SECTION_ALIASES.items()
    for alias in aliases
}
_HEADING_PATTERN = re.compile(
    r"(?<!\w)("
    + "|".join(
        re.escape(alias)
        for alias in sorted(_ALIAS_TO_SECTION, key=len, reverse=True)
    )
    + r")(?!\w)",
    flags=re.IGNORECASE,
)
_CV_TITLE_WORDS = frozenset({"cv", "curriculumvitae", "resume", "résumé"})
_COMBINED_SKILLS_LANGUAGE_HEADINGS = frozenset(
    {
        "skills languages",
        "languages skills",
        "technical skills languages",
    }
)


@dataclass(frozen=True, slots=True)
class SectionFragment:
    """Contiguous PDF text assigned to one section on one page."""

    section_name: str
    page_number: int
    text: str


def split_document_into_sections(
    document: ExtractedCvDocument,
) -> tuple[SectionFragment, ...]:
    """Assign page text to recognized sections or a generic fallback."""

    fragments: list[SectionFragment] = []
    current_section = SECTION_IDENTITY
    found_heading = False

    for page in document.pages:
        buffered_lines: list[str] = []

        def flush_buffer() -> None:
            cleaned_text = _clean_fragment_lines(buffered_lines)
            buffered_lines.clear()
            if cleaned_text:
                fragments.append(
                    SectionFragment(
                        section_name=current_section,
                        page_number=page.page_number,
                        text=cleaned_text,
                    )
                )

        for line in page.text.splitlines():
            if _is_decorative_cv_title(line):
                continue

            for part_kind, part_value in _split_line_on_headings(line):
                if part_kind == "heading":
                    flush_buffer()
                    current_section = part_value
                    found_heading = True
                else:
                    buffered_lines.append(part_value)

        flush_buffer()

    if not found_heading:
        return tuple(
            SectionFragment(
                section_name=SECTION_DOCUMENT,
                page_number=fragment.page_number,
                text=fragment.text,
            )
            for fragment in fragments
        )

    return tuple(fragments)


def group_contiguous_sections(
    fragments: Sequence[SectionFragment],
) -> tuple[tuple[str, tuple[SectionFragment, ...]], ...]:
    """Group adjacent page fragments that belong to the same section."""

    grouped_sections: list[tuple[str, tuple[SectionFragment, ...]]] = []
    current_name: str | None = None
    current_fragments: list[SectionFragment] = []

    for fragment in fragments:
        if current_name is None or fragment.section_name == current_name:
            current_name = fragment.section_name
            current_fragments.append(fragment)
            continue

        grouped_sections.append((current_name, tuple(current_fragments)))
        current_name = fragment.section_name
        current_fragments = [fragment]

    if current_name is not None:
        grouped_sections.append((current_name, tuple(current_fragments)))

    return tuple(grouped_sections)


def _split_line_on_headings(line: str) -> tuple[tuple[str, str], ...]:
    """Split one line around exact or uppercase embedded CV headings."""

    stripped_line = line.strip()
    if not stripped_line:
        return (("text", ""),)

    folded_line = " ".join(stripped_line.casefold().split())
    if folded_line in _COMBINED_SKILLS_LANGUAGE_HEADINGS:
        return (("heading", SECTION_SKILLS_AND_LANGUAGES),)

    accepted_matches: list[re.Match[str]] = []
    for match in _HEADING_PATTERN.finditer(stripped_line):
        alias = " ".join(match.group(0).casefold().split())
        if folded_line == alias or _is_embedded_heading(stripped_line, match):
            accepted_matches.append(match)

    if not accepted_matches:
        return (("text", stripped_line),)

    parts: list[tuple[str, str]] = []
    cursor = 0
    for match in accepted_matches:
        text_before_heading = stripped_line[cursor : match.start()].strip()
        if text_before_heading:
            parts.append(("text", text_before_heading))

        alias = " ".join(match.group(0).casefold().split())
        parts.append(("heading", _ALIAS_TO_SECTION[alias]))
        cursor = match.end()

    text_after_heading = stripped_line[cursor:].strip()
    if text_after_heading:
        parts.append(("text", text_after_heading))

    return tuple(parts)


def _is_embedded_heading(line: str, match: re.Match[str]) -> bool:
    """Accept embedded headings only when layout evidence is strong."""

    matched_text = match.group(0)
    letters = [character for character in matched_text if character.isalpha()]
    if not letters or not all(character.isupper() for character in letters):
        return False

    prefix = line[: match.start()].strip()
    if not prefix:
        return False

    # Two-column extraction may append a right-column heading to left-column
    # content, e.g. ``Apache Airflow 5y EDUCATION``. Requiring lower-case text
    # or digits before the match avoids treating category labels such as
    # ``PROGRAMMING LANGUAGES`` as a new top-level section.
    return any(character.islower() or character.isdigit() for character in prefix)


def _is_decorative_cv_title(line: str) -> bool:
    """Return whether a line is only a generic CV or résumé title."""

    compact = re.sub(r"[^\wÀ-ÿ]+", "", line, flags=re.UNICODE).casefold()
    return compact in _CV_TITLE_WORDS


def _clean_fragment_lines(lines: Sequence[str]) -> str:
    """Normalize repeated blanks without joining meaningful PDF lines."""

    cleaned_lines: list[str] = []
    previous_was_blank = False
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            if cleaned_lines and not previous_was_blank:
                cleaned_lines.append("")
            previous_was_blank = True
            continue

        cleaned_lines.append(stripped_line)
        previous_was_blank = False

    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)
