"""Preview or apply readable filenames for selected CV PDFs.

The command is separate from ingestion. Extracting or indexing a PDF must not
silently rename a user's file. Without ``--apply``, it only prints the planned
changes.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from app.scripts.cli_help import build_cli_parser
from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvDocumentExtractionError,
    CvDocumentNamingError,
    CvDocumentSelectionError,
    apply_cv_document_renames,
    load_cv_documents,
    plan_cv_document_renames,
    select_cv_pdf_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Define PDF selection and the explicit ``--apply`` option."""

    parser = build_cli_parser(
        description=(
            "Create name-role-cv.pdf filenames from PDF-extracted metadata. "
            "The default is a dry-run preview."
        ),
        sections=(
            (
                'Valid command combinations',
                (
                    '--file PATH may be repeated, or use one --directory PATH, or use --all.',
                    '--file, --directory, and --all are mutually exclusive.',
                    '--recursive may be used with --directory or --all.',
                    'Without --apply the command is always a preview.',
                    '--apply may be added to any valid selection to perform the displayed renames.',
                ),
            ),
            (
                'What the command changes',
                (
                    'Preview mode writes nothing.',
                    '--apply renames selected PDF files on disk. It does not rebuild Chroma automatically.',
                ),
            ),
            (
                'Examples',
                (
                    'python -m app.scripts.rename_cv_documents --all',
                    'python -m app.scripts.rename_cv_documents --directory data/cv_pdfs --recursive',
                    'python -m app.scripts.rename_cv_documents --file data/cv_pdfs/example.pdf --apply',
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
        help="Select one PDF. Repeat --file to select several PDFs.",
    )
    input_group.add_argument(
        "--directory",
        type=Path,
        help="Select PDFs directly inside this directory.",
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Select PDFs in the configured default CV directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include PDFs in nested directories.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the displayed renames. Without this flag nothing changes.",
    )

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
) -> int:
    """Extract display metadata, show rename plans, and apply them when requested."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    try:
        selected_paths = select_cv_pdf_paths(
            files=tuple(arguments.files or ()),
            directory=arguments.directory,
            default_directory=active_settings.cv_ingestion_default_directory,
            select_all=arguments.select_all,
            recursive=arguments.recursive,
        )
        documents = load_cv_documents(selected_paths)
        plans = plan_cv_document_renames(documents)
        applied_plans = (
            apply_cv_document_renames(plans)
            if arguments.apply
            else ()
        )
    except (
        CvDocumentSelectionError,
        CvDocumentExtractionError,
        CvDocumentNamingError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print("CV FILENAME MIGRATION")
    print(f"  Selected PDFs: {len(plans)}")
    print(f"  Mode: {'APPLY' if arguments.apply else 'DRY RUN'}")
    print(f"  Renames required: {sum(plan.changes_filename for plan in plans)}")

    print("\nPLANNED RENAMES")
    for plan in plans:
        status = "rename" if plan.changes_filename else "unchanged"
        print(
            f"  {status} | {plan.source_path.name} -> {plan.target_path.name}"
        )

    if arguments.apply:
        print(f"\n  Applied renames: {len(applied_plans)}")
        print("  Result: COMPLETE")
    else:
        print("\n  Result: REVIEW ONLY — no files changed")

    return 0


def main() -> None:
    """Execute the optional filename migration command."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
