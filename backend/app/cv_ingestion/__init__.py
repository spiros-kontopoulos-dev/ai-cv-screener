"""Public contracts for generic CV PDF loading and source identity."""

from app.cv_ingestion.extraction import (
    CvDocumentExtractionError,
    calculate_pdf_sha256,
    detect_candidate_header,
    detect_candidate_id,
    load_cv_document,
    load_cv_documents,
    normalize_extracted_page_text,
)
from app.cv_ingestion.models import (
    CvRenamePlan,
    CvSourceMetadata,
    ExtractedCvDocument,
    ExtractedCvPage,
)
from app.cv_ingestion.naming import (
    CvDocumentNamingError,
    apply_cv_document_renames,
    build_readable_cv_filename,
    plan_cv_document_renames,
)
from app.cv_ingestion.selection import (
    CvDocumentSelectionError,
    select_cv_pdf_paths,
)

__all__ = [
    "CvDocumentExtractionError",
    "CvDocumentNamingError",
    "CvDocumentSelectionError",
    "CvRenamePlan",
    "CvSourceMetadata",
    "ExtractedCvDocument",
    "ExtractedCvPage",
    "apply_cv_document_renames",
    "build_readable_cv_filename",
    "calculate_pdf_sha256",
    "detect_candidate_header",
    "detect_candidate_id",
    "load_cv_document",
    "load_cv_documents",
    "normalize_extracted_page_text",
    "plan_cv_document_renames",
    "select_cv_pdf_paths",
]
