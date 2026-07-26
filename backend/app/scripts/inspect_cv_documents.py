"""Show what the PDF extraction stage reads from selected CV files.

The command calculates document hashes, extracts pages, and prints detected
candidate details and text counts. It does not create chunks, embeddings, or
ChromaDB records.

Examples:

    python -m app.scripts.inspect_cv_documents --all
    python -m app.scripts.inspect_cv_documents --file data/cv_pdfs/example.pdf
    python -m app.scripts.inspect_cv_documents --directory data/cv_pdfs
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from app.scripts.cli_help import build_cli_parser
from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvDocumentExtractionError,
    CvDocumentSelectionError,
    ExtractedCvDocument,
    load_cv_document,
    load_cv_documents,
    select_cv_pdf_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Define file, directory, recursion, and display options for the command."""

    parser = build_cli_parser(
        description=(
            "Extract text and source metadata from one or more CV PDFs "
            "without writing chunks, embeddings, or vector records."
        ),
        sections=(
            (
                'Valid command combinations',
                (
                    '--file PATH may be repeated, or use one --directory PATH, or use --all.',
                    '--file, --directory, and --all are mutually exclusive.',
                    '--recursive may be used with --directory or --all.',
                    '--candidate-id ID, --candidate-name NAME, and --professional-title TITLE may be combined, but require exactly one selected PDF.',
                    '--preview-characters N may be added to any selection and changes only terminal output.',
                ),
            ),
            (
                'What the command changes',
                (
                    'It reads and extracts PDFs in memory. It writes nothing.',
                ),
            ),
            (
                'Examples',
                (
                    'python -m app.scripts.inspect_cv_documents --file data/cv_pdfs/example.pdf',
                    'python -m app.scripts.inspect_cv_documents --directory data/cv_pdfs',
                    'python -m app.scripts.inspect_cv_documents --all --recursive --preview-characters 400',
                    'python -m app.scripts.inspect_cv_documents --file data/imports/cv.pdf --candidate-id candidate_031 --candidate-name "Alex Morgan" --professional-title "Python Engineer"',
                ),
            ),
        ),
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
        help="Inspect every PDF directly inside this directory.",
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Inspect every PDF in the configured default CV directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include PDFs from nested directories for --directory or --all.",
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
        "--preview-characters",
        type=int,
        default=240,
        help="Maximum normalized text characters shown per page (default: 240).",
    )

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Run PDF selection and extraction, then print a readable summary."""

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

        if len(selected_paths) == 1:
            documents = (
                load_cv_document(
                    selected_paths[0],
                    candidate_id=arguments.candidate_id,
                    candidate_name=arguments.candidate_name,
                    professional_title=arguments.professional_title,
                ),
            )
        else:
            documents = load_cv_documents(selected_paths)
    except (CvDocumentSelectionError, CvDocumentExtractionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    _print_extraction_summary(
        documents,
        preview_characters=arguments.preview_characters,
    )
    return 0


def _print_extraction_summary(
    documents: Sequence[ExtractedCvDocument],
    *,
    preview_characters: int,
) -> None:
    """Print concise collection, document, and page extraction details."""

    total_pages = sum(document.page_count for document in documents)
    total_characters = sum(
        document.text_character_count for document in documents
    )

    print("CV PDF EXTRACTION COMPLETE")
    print(f"  Documents: {len(documents)}")
    print(f"  Pages: {total_pages}")
    print(f"  Extracted text characters: {total_characters}")

    print("\nEXTRACTED DOCUMENTS")
    for document in documents:
        source = document.source
        print(
            f"  {source.candidate_id} | "
            f"name={source.candidate_name or 'unknown'} | "
            f"title={source.professional_title or 'unknown'} | "
            f"pages={document.page_count} | "
            f"chars={document.text_character_count} | "
            f"file={source.source_filename} | "
            f"hash={source.document_hash[:12]}"
        )
        for page in document.pages:
            print(
                f"    page={page.page_number}/{page.total_pages} | "
                f"chars={page.text_character_count}"
            )
            if preview_characters:
                preview = " ".join(page.text.split())[:preview_characters]
                print(f"      preview={preview}")


def main() -> None:
    """Execute the extraction inspection command."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
