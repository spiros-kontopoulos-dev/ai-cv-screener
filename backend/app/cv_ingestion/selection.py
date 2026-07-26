"""Choose which PDF files an ingestion or inspection command will process.

A caller must choose exactly one mode: explicit files, one directory, or the
configured default CV directory. The returned paths are validated and sorted
so repeated runs process documents in the same order.
"""

from collections.abc import Sequence
from pathlib import Path


class CvDocumentSelectionError(ValueError):
    """Raised when the requested file or directory selection is not valid."""


def select_cv_pdf_paths(
    *,
    files: Sequence[Path] = (),
    directory: Path | None = None,
    default_directory: Path | None = None,
    select_all: bool = False,
    recursive: bool = False,
) -> tuple[Path, ...]:
    """Return validated PDF paths for exactly one selection mode.

    ``files`` accepts one or more named PDFs. ``directory`` scans a chosen
    folder. ``select_all`` scans the configured CV folder. Requiring one mode
    avoids accidentally processing a larger collection than intended.
    """

    selection_mode_count = sum(
        (
            bool(files),
            directory is not None,
            select_all,
        )
    )
    if selection_mode_count != 1:
        raise CvDocumentSelectionError(
            "Choose exactly one PDF input mode: files, directory, or all."
        )

    if recursive and directory is None and not select_all:
        raise CvDocumentSelectionError(
            "Recursive scanning requires directory or all selection."
        )

    if files:
        selected_paths = [validate_cv_pdf_path(path) for path in files]
    else:
        scan_directory = default_directory if select_all else directory
        if scan_directory is None:
            raise CvDocumentSelectionError(
                "The configured default CV directory is required for all "
                "selection."
            )
        selected_paths = list(
            _scan_pdf_directory(scan_directory, recursive=recursive)
        )

    ordered_paths = sorted(
        selected_paths,
        key=lambda path: (path.name.casefold(), path.as_posix().casefold()),
    )
    canonical_paths = [path.resolve() for path in ordered_paths]
    if len(canonical_paths) != len(set(canonical_paths)):
        raise CvDocumentSelectionError(
            "The same PDF path was selected more than once."
        )

    if not ordered_paths:
        raise CvDocumentSelectionError(
            "No PDF files were found for the selected input."
        )

    return tuple(ordered_paths)


def validate_cv_pdf_path(path: Path) -> Path:
    """Check that one path exists, is a file, and has a PDF extension."""

    if path.suffix.casefold() != ".pdf":
        raise CvDocumentSelectionError(
            f"Selected CV file must use the .pdf extension: {path}"
        )
    if not path.exists():
        raise CvDocumentSelectionError(f"Selected CV PDF does not exist: {path}")
    if not path.is_file():
        raise CvDocumentSelectionError(
            f"Selected CV PDF is not a regular file: {path}"
        )

    return path


def _scan_pdf_directory(
    directory: Path,
    *,
    recursive: bool,
) -> tuple[Path, ...]:
    """Scan one directory and return its PDF files in stable order."""

    if not directory.exists():
        raise CvDocumentSelectionError(
            f"CV directory does not exist: {directory}"
        )
    if not directory.is_dir():
        raise CvDocumentSelectionError(
            f"CV directory is not a directory: {directory}"
        )

    iterator = directory.rglob("*") if recursive else directory.iterdir()
    return tuple(
        path
        for path in iterator
        if path.is_file() and path.suffix.casefold() == ".pdf"
    )
