"""Inspect adaptive CV chunking before embeddings and ChromaDB persistence.

Examples:

    python -m app.scripts.inspect_cv_chunks --all
    python -m app.scripts.inspect_cv_chunks --file data/cv_pdfs/example.pdf
    python -m app.scripts.inspect_cv_chunks --directory data/cv_pdfs
"""

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
import sys

from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvChunk,
    CvChunkingConfig,
    CvChunkingError,
    CvDocumentExtractionError,
    CvDocumentSelectionError,
    ExtractedCvDocument,
    chunk_cv_documents,
    load_cv_document,
    load_cv_documents,
    select_cv_pdf_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line contract for extraction and chunk inspection."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract and chunk one or more CV PDFs without generating "
            "embeddings or writing vector records."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="Select one PDF. Repeat --file to inspect several PDFs.",
    )
    input_group.add_argument(
        "--directory",
        type=Path,
        help="Chunk every PDF directly inside this directory.",
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Chunk every PDF in the configured default CV directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include nested PDFs for --directory or --all.",
    )
    parser.add_argument(
        "--candidate-id",
        help="Override candidate identity when exactly one PDF is selected.",
    )
    parser.add_argument(
        "--candidate-name",
        help="Override the detected candidate name for one selected PDF.",
    )
    parser.add_argument(
        "--professional-title",
        help="Override the detected professional title for one selected PDF.",
    )
    parser.add_argument(
        "--chunking-version",
        help="Override the configured chunking strategy version.",
    )
    parser.add_argument(
        "--max-characters",
        type=int,
        help="Override the maximum visible characters per chunk.",
    )
    parser.add_argument(
        "--min-characters",
        type=int,
        help="Override the target minimum visible characters per chunk.",
    )
    parser.add_argument(
        "--overlap-characters",
        type=int,
        help="Override trailing context carried into adjacent section chunks.",
    )
    parser.add_argument(
        "--preview-characters",
        type=int,
        default=220,
        help="Maximum normalized text characters shown per chunk (default: 220).",
    )

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Select PDFs, extract them, chunk them, and print stable summaries."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    if arguments.preview_characters < 0:
        print("ERROR: --preview-characters cannot be negative.", file=sys.stderr)
        return 2

    try:
        selected_paths = select_cv_pdf_paths(
            files=tuple(arguments.files or ()),
            directory=arguments.directory,
            default_directory=active_settings.cv_ingestion_default_directory,
            select_all=arguments.select_all,
            recursive=arguments.recursive,
        )
        has_metadata_overrides = any(
            (
                arguments.candidate_id,
                arguments.candidate_name,
                arguments.professional_title,
            )
        )
        if has_metadata_overrides and len(selected_paths) != 1:
            raise CvDocumentSelectionError(
                "Candidate metadata overrides require exactly one selected PDF."
            )

        documents = _load_selected_documents(
            selected_paths,
            candidate_id=arguments.candidate_id,
            candidate_name=arguments.candidate_name,
            professional_title=arguments.professional_title,
        )
        config = CvChunkingConfig(
            version=(
                arguments.chunking_version
                or active_settings.cv_chunking_version
            ),
            max_characters=(
                arguments.max_characters
                if arguments.max_characters is not None
                else active_settings.cv_chunk_max_characters
            ),
            min_characters=(
                arguments.min_characters
                if arguments.min_characters is not None
                else active_settings.cv_chunk_min_characters
            ),
            overlap_characters=(
                arguments.overlap_characters
                if arguments.overlap_characters is not None
                else active_settings.cv_chunk_overlap_characters
            ),
        )
        chunks = chunk_cv_documents(documents, config=config)
    except (
        CvDocumentSelectionError,
        CvDocumentExtractionError,
        CvChunkingError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    _print_chunking_summary(
        documents,
        chunks,
        config=config,
        preview_characters=arguments.preview_characters,
    )
    return 0


def _load_selected_documents(
    selected_paths: Sequence[Path],
    *,
    candidate_id: str | None,
    candidate_name: str | None,
    professional_title: str | None,
) -> tuple[ExtractedCvDocument, ...]:
    """Load one override-aware PDF or a normal deterministic batch."""

    if len(selected_paths) == 1:
        return (
            load_cv_document(
                selected_paths[0],
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                professional_title=professional_title,
            ),
        )
    return load_cv_documents(selected_paths)


def _print_chunking_summary(
    documents: Sequence[ExtractedCvDocument],
    chunks: Sequence[CvChunk],
    *,
    config: CvChunkingConfig,
    preview_characters: int,
) -> None:
    """Print collection, section, document, and stable chunk details."""

    total_pages = sum(document.page_count for document in documents)
    below_target_count = sum(
        len(chunk.text) < config.min_characters
        for chunk in chunks
    )
    section_counts = Counter(chunk.section_name for chunk in chunks)

    print("CV CHUNKING COMPLETE")
    print(f"  Documents: {len(documents)}")
    print(f"  Pages: {total_pages}")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Chunking version: {config.version}")
    print(f"  Maximum characters: {config.max_characters}")
    print(f"  Target minimum characters: {config.min_characters}")
    print(f"  Overlap characters: {config.overlap_characters}")
    print(f"  Chunks below target minimum: {below_target_count}")

    print("\nSECTION COUNTS")
    for section_name, count in sorted(section_counts.items()):
        print(f"  {section_name}: {count}")

    print("\nCHUNKED DOCUMENTS")
    for document in documents:
        document_chunks = [
            chunk
            for chunk in chunks
            if chunk.source.document_id == document.source.document_id
        ]
        source = document.source
        print(
            f"  {source.candidate_id} | "
            f"name={source.candidate_name or 'unknown'} | "
            f"title={source.professional_title or 'unknown'} | "
            f"pages={document.page_count} | "
            f"chunks={len(document_chunks)} | "
            f"file={source.source_filename}"
        )
        for chunk in document_chunks:
            print(
                f"    index={chunk.chunk_index} | "
                f"id={chunk.chunk_id} | "
                f"section={chunk.section_name} | "
                f"pages={chunk.page_label} | "
                f"chars={len(chunk.text)}"
            )
            if preview_characters:
                preview = " ".join(chunk.text.split())[:preview_characters]
                print(f"      preview={preview}")


def main() -> None:
    """Execute the chunk inspection command."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
