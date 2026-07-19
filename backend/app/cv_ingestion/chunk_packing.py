"""Pack section fragments into bounded, overlapping text chunks."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re

from app.cv_ingestion.sectioning import SectionFragment


_BULLET_PREFIX_PATTERN = re.compile(r"^[•▪◦‣*-]\s+")
_UNIT_LABEL_PATTERN = re.compile(
    r"^(technologies|technology|team leadership|tools|stack)\s*:",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class TextUnit:
    """A paragraph, bullet, label, or bounded text window used for packing."""

    page_numbers: tuple[int, ...]
    text: str
    has_leading_overlap: bool = False


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Internal chunk content before stable identifiers are assigned."""

    section_name: str
    page_numbers: tuple[int, ...]
    text: str


def fragment_to_units(
    fragment: SectionFragment,
    *,
    max_characters: int,
    overlap_characters: int,
) -> tuple[TextUnit, ...]:
    """Convert one section fragment into paragraph and bullet-aware units."""

    raw_units: list[str] = []
    buffered_lines: list[str] = []

    def flush_buffer() -> None:
        if not buffered_lines:
            return
        unit_text = " ".join(buffered_lines).strip()
        buffered_lines.clear()
        if unit_text:
            raw_units.append(unit_text)

    for line in fragment.text.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            flush_buffer()
            continue

        if (
            _BULLET_PREFIX_PATTERN.match(stripped_line)
            or _UNIT_LABEL_PATTERN.match(stripped_line)
        ):
            flush_buffer()
            buffered_lines.append(stripped_line)
            continue

        buffered_lines.append(stripped_line)

    flush_buffer()

    units: list[TextUnit] = []
    for raw_unit in raw_units:
        units.extend(
            _split_long_unit(
                TextUnit(
                    page_numbers=(fragment.page_number,),
                    text=raw_unit,
                ),
                max_characters=max_characters,
                overlap_characters=overlap_characters,
            )
        )

    return tuple(units)


def pack_section_units(
    section_name: str,
    units: Sequence[TextUnit],
    *,
    max_characters: int,
    min_characters: int,
    overlap_characters: int,
) -> tuple[ChunkDraft, ...]:
    """Pack section units into bounded chunks with controlled local overlap."""

    if not units:
        return ()

    drafts: list[ChunkDraft] = []
    current_units: list[TextUnit] = []

    def finalize_current() -> None:
        if not current_units:
            return
        drafts.append(
            ChunkDraft(
                section_name=section_name,
                page_numbers=_merge_page_numbers(current_units),
                text=_join_unit_text(current_units),
            )
        )

    for unit in units:
        prospective_units = [*current_units, unit]
        if (
            not current_units
            or len(_join_unit_text(prospective_units)) <= max_characters
        ):
            current_units.append(unit)
            continue

        finalize_current()
        overlap_unit = None
        if not unit.has_leading_overlap:
            overlap_unit = _build_overlap_unit(
                current_units,
                overlap_characters=overlap_characters,
                available_characters=max_characters - len(unit.text) - 1,
            )
        current_units = [unit]
        if overlap_unit is not None:
            current_units.insert(0, overlap_unit)

    finalize_current()
    return _merge_small_final_draft(
        tuple(drafts),
        min_characters=min_characters,
        max_characters=max_characters,
    )


def build_chunk_id(
    *,
    document_hash: str,
    chunking_version: str,
    chunk_index: int,
    section_name: str,
    page_numbers: Sequence[int],
    text: str,
) -> str:
    """Return a stable ID independent from filename and filesystem location."""

    identity_payload = "\x1f".join(
        (
            document_hash,
            chunking_version,
            str(chunk_index),
            section_name,
            ",".join(str(page_number) for page_number in page_numbers),
            sha256(text.encode("utf-8")).hexdigest(),
        )
    )
    return f"chunk_{sha256(identity_payload.encode('utf-8')).hexdigest()[:24]}"


def _split_long_unit(
    unit: TextUnit,
    *,
    max_characters: int,
    overlap_characters: int,
) -> tuple[TextUnit, ...]:
    """Split one oversized unit into bounded word windows with overlap."""

    if len(unit.text) <= max_characters:
        return (unit,)

    windows = _split_text_windows(
        unit.text,
        max_characters=max_characters,
        overlap_characters=overlap_characters,
    )
    return tuple(
        TextUnit(
            page_numbers=unit.page_numbers,
            text=window,
            has_leading_overlap=window_index > 0,
        )
        for window_index, window in enumerate(windows)
    )


def _build_overlap_unit(
    previous_units: Sequence[TextUnit],
    *,
    overlap_characters: int,
    available_characters: int,
) -> TextUnit | None:
    """Return a bounded trailing context unit for the next chunk."""

    requested_characters = min(overlap_characters, available_characters)
    if requested_characters <= 0 or not previous_units:
        return None

    overlap_text = _tail_at_word_boundary(
        _join_unit_text(previous_units),
        requested_characters,
    )
    if not overlap_text:
        return None

    contributing_pages: list[int] = []
    remaining_characters = len(overlap_text)
    for unit in reversed(previous_units):
        contributing_pages.extend(unit.page_numbers)
        remaining_characters -= len(unit.text)
        if remaining_characters <= 0:
            break

    return TextUnit(
        page_numbers=tuple(sorted(set(contributing_pages))),
        text=overlap_text,
        has_leading_overlap=True,
    )


def _merge_small_final_draft(
    drafts: tuple[ChunkDraft, ...],
    *,
    min_characters: int,
    max_characters: int,
) -> tuple[ChunkDraft, ...]:
    """Merge a tiny final piece when doing so respects the hard maximum."""

    if len(drafts) < 2 or len(drafts[-1].text) >= min_characters:
        return drafts

    combined_text = f"{drafts[-2].text}\n{drafts[-1].text}".strip()
    if len(combined_text) > max_characters:
        return drafts

    merged_draft = ChunkDraft(
        section_name=drafts[-1].section_name,
        page_numbers=tuple(
            sorted(
                set(drafts[-2].page_numbers) | set(drafts[-1].page_numbers)
            )
        ),
        text=combined_text,
    )
    return (*drafts[:-2], merged_draft)


def _split_text_windows(
    text: str,
    *,
    max_characters: int,
    overlap_characters: int,
) -> tuple[str, ...]:
    """Split text on word boundaries while carrying trailing context."""

    raw_words = text.split()
    if not raw_words:
        return ()

    # Preserve unusually long URLs or tokens instead of truncating them.
    words = [
        word_slice
        for word in raw_words
        for word_slice in (
            tuple(
                word[index : index + max_characters]
                for index in range(0, len(word), max_characters)
            )
            if len(word) > max_characters
            else (word,)
        )
    ]

    windows: list[str] = []
    start_index = 0
    while start_index < len(words):
        end_index = start_index
        current_words: list[str] = []
        while end_index < len(words):
            candidate_words = [*current_words, words[end_index]]
            candidate_text = " ".join(candidate_words)
            if current_words and len(candidate_text) > max_characters:
                break
            current_words = candidate_words
            end_index += 1

        window = " ".join(current_words)
        windows.append(window)
        if end_index >= len(words):
            break

        next_start = end_index
        overlap_size = 0
        while next_start > start_index:
            candidate_word = words[next_start - 1]
            added_size = len(candidate_word) + (1 if overlap_size else 0)
            if overlap_size + added_size > overlap_characters:
                break
            overlap_size += added_size
            next_start -= 1

        if next_start == start_index:
            next_start = end_index
        start_index = next_start

    return tuple(windows)


def _tail_at_word_boundary(text: str, max_characters: int) -> str:
    """Return the largest trailing word sequence within a character limit."""

    selected_words: list[str] = []
    current_size = 0
    for word in reversed(text.split()):
        added_size = len(word) + (1 if selected_words else 0)
        if current_size + added_size > max_characters:
            break
        selected_words.append(word)
        current_size += added_size

    return " ".join(reversed(selected_words))


def _join_unit_text(units: Iterable[TextUnit]) -> str:
    """Join packed units with visible paragraph boundaries."""

    return "\n".join(unit.text.strip() for unit in units if unit.text.strip())


def _merge_page_numbers(units: Iterable[TextUnit]) -> tuple[int, ...]:
    """Return sorted unique pages represented by a unit collection."""

    return tuple(
        sorted(
            {
                page_number
                for unit in units
                for page_number in unit.page_numbers
            }
        )
    )
