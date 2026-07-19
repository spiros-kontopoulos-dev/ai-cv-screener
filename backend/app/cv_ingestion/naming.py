"""Plan and apply optional human-readable CV filename migrations.

File names are presentation metadata, never document identity.  The exact PDF
bytes remain identified by their SHA-256 hash, so renaming or moving an
unchanged file will not create a second vector record in later WP5 patches.
"""

from collections.abc import Sequence
from pathlib import Path
import re
import unicodedata

from app.cv_ingestion.models import CvRenamePlan, ExtractedCvDocument


class CvDocumentNamingError(ValueError):
    """Raised when a safe readable filename cannot be produced or applied."""


def build_readable_cv_filename(document: ExtractedCvDocument) -> str:
    """Return ``name-role-cv.pdf`` for a document with detected metadata."""

    return build_readable_cv_filename_from_metadata(
        candidate_name=document.source.candidate_name,
        professional_title=document.source.professional_title,
        source_label=document.source.source_filename,
    )


def build_readable_cv_filename_from_metadata(
    *,
    candidate_name: str | None,
    professional_title: str | None,
    source_label: str = "candidate profile",
) -> str:
    """Return the canonical readable PDF filename from display metadata.

    Both PDF ingestion and deterministic PDF rendering use this helper so a
    rerender cannot silently recreate the legacy ``candidate_XXX.pdf`` names.
    ``source_label`` is used only to make validation errors actionable.
    """

    if not candidate_name or not professional_title:
        raise CvDocumentNamingError(
            "Readable CV naming requires both candidate name and "
            f"professional title: {source_label}."
        )

    stem = _slugify(f"{candidate_name}-{professional_title}-cv")
    if not stem:
        raise CvDocumentNamingError(
            f"Readable CV filename is empty for {source_label}."
        )

    return f"{stem}.pdf"


def plan_cv_document_renames(
    documents: Sequence[ExtractedCvDocument],
) -> tuple[CvRenamePlan, ...]:
    """Build collision-safe rename operations without touching the filesystem."""

    reserved_targets: set[Path] = set()
    plans: list[CvRenamePlan] = []

    for document in sorted(
        documents,
        key=lambda item: (
            item.source.source_filename.casefold(),
            item.source.source_path.as_posix().casefold(),
        ),
    ):
        candidate_name = document.source.candidate_name
        professional_title = document.source.professional_title
        if not candidate_name or not professional_title:
            raise CvDocumentNamingError(
                "Readable CV naming requires detected candidate metadata for "
                f"{document.source.source_filename}."
            )

        requested_target = (
            document.source.source_path.parent
            / build_readable_cv_filename(document)
        )
        target_path = _choose_available_target(
            requested_target,
            source_path=document.source.source_path,
            short_hash=document.source.document_hash[:8],
            reserved_targets=reserved_targets,
        )
        reserved_targets.add(target_path.resolve())
        plans.append(
            CvRenamePlan(
                source_path=document.source.source_path,
                target_path=target_path,
                document_id=document.source.document_id,
                candidate_name=candidate_name,
                professional_title=professional_title,
            )
        )

    return tuple(plans)


def apply_cv_document_renames(
    plans: Sequence[CvRenamePlan],
) -> tuple[CvRenamePlan, ...]:
    """Apply reviewed plans without overwriting existing different files."""

    applied_plans: list[CvRenamePlan] = []
    for plan in plans:
        if not plan.changes_filename:
            continue
        if not plan.source_path.is_file():
            raise CvDocumentNamingError(
                f"CV source file no longer exists: {plan.source_path}"
            )
        if plan.target_path.exists():
            raise CvDocumentNamingError(
                f"CV rename target already exists: {plan.target_path}"
            )

        try:
            plan.source_path.rename(plan.target_path)
        except OSError as error:
            raise CvDocumentNamingError(
                f"CV file could not be renamed: {plan.source_path}"
            ) from error
        applied_plans.append(plan)

    return tuple(applied_plans)


def _choose_available_target(
    requested_target: Path,
    *,
    source_path: Path,
    short_hash: str,
    reserved_targets: set[Path],
) -> Path:
    """Return the readable target or a deterministic hash-suffixed variant."""

    requested_resolved = requested_target.resolve()
    source_resolved = source_path.resolve()
    if requested_resolved == source_resolved:
        return requested_target

    if (
        requested_resolved not in reserved_targets
        and not requested_target.exists()
    ):
        return requested_target

    suffixed_target = requested_target.with_name(
        f"{requested_target.stem}-{short_hash}{requested_target.suffix}"
    )
    suffixed_resolved = suffixed_target.resolve()
    if (
        suffixed_resolved in reserved_targets
        or (suffixed_target.exists() and suffixed_resolved != source_resolved)
    ):
        raise CvDocumentNamingError(
            "Unable to create a unique readable CV filename for "
            f"{source_path}."
        )

    return suffixed_target


def _slugify(value: str) -> str:
    """Convert display metadata into a portable lowercase filename slug."""

    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-")
    return re.sub(r"-{2,}", "-", slug).casefold()
