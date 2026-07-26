"""Public interface for CV planning, rendering, and PDF validation.

The rendering flow is:

1. Map validated profiles to stable image, HTML, and PDF paths.
2. Format machine-friendly values for display.
3. Render one standalone HTML document with Jinja.
4. Convert HTML and CSS to an A4 PDF with WeasyPrint.
5. Reopen the PDF with PyMuPDF and verify its text.
6. Validate the complete PDF collection against the expected visible facts.
"""

from app.cv_rendering.formatting import (
    CvFormattingError,
    candidate_initials,
    format_education_year_range,
    format_language_proficiency,
    format_seniority,
    format_skill_years,
    format_work_date_range,
    format_year_month,
    format_years_of_experience,
    group_skills,
    humanize_identifier,
)
from app.cv_rendering.models import (
    CvProfileMetrics,
    CvRenderJob,
    CvRenderResult,
)
from app.cv_rendering.planning import (
    NORMALIZED_PORTRAIT_EXTENSION,
    CvRenderingPlanError,
    build_cv_render_jobs,
    find_profile_boundaries,
    measure_candidate_profile,
    select_cv_render_jobs,
)
from app.cv_rendering.rendering import (
    DEFAULT_CV_STYLESHEET_PATH,
    DEFAULT_CV_TEMPLATE_PATH,
    CvRenderingError,
    render_cv_html,
    render_cv_job,
    render_cv_jobs,
)
from app.cv_rendering.validation import (
    CandidateCvValidation,
    CvFactExpectation,
    CvPdfCollectionValidationReport,
    CvPdfValidationError,
    ExtractedCvDocument,
    build_profile_fact_expectations,
    extract_cv_pdf,
    validate_cv_pdf_collection,
    validate_profile_against_pdf_text,
)

__all__ = [
    "CandidateCvValidation",
    "CvFactExpectation",
    "CvPdfCollectionValidationReport",
    "CvPdfValidationError",
    "ExtractedCvDocument",
    "build_profile_fact_expectations",
    "extract_cv_pdf",
    "validate_cv_pdf_collection",
    "validate_profile_against_pdf_text",
    "DEFAULT_CV_STYLESHEET_PATH",
    "DEFAULT_CV_TEMPLATE_PATH",
    "NORMALIZED_PORTRAIT_EXTENSION",
    "CvFormattingError",
    "CvProfileMetrics",
    "CvRenderJob",
    "CvRenderResult",
    "CvRenderingError",
    "CvRenderingPlanError",
    "build_cv_render_jobs",
    "candidate_initials",
    "find_profile_boundaries",
    "format_education_year_range",
    "format_language_proficiency",
    "format_seniority",
    "format_skill_years",
    "format_work_date_range",
    "format_year_month",
    "format_years_of_experience",
    "group_skills",
    "humanize_identifier",
    "measure_candidate_profile",
    "render_cv_html",
    "render_cv_job",
    "render_cv_jobs",
    "select_cv_render_jobs",
]
