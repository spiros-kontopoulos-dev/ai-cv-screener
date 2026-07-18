"""Render validated candidate profiles into standalone HTML and PDF files.

Jinja owns variable substitution, CSS owns document presentation, WeasyPrint
owns paged layout, and PyMuPDF performs a small post-render integrity check.  No
step reads from the dataset plan or bypasses the validated ``CandidateProfile``.
"""

from collections.abc import Sequence
from pathlib import Path

import pymupdf
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateError,
    select_autoescape,
)
from weasyprint import HTML

from app.cv_rendering.formatting import (
    candidate_initials,
    format_education_year_range,
    format_language_proficiency,
    format_seniority,
    format_skill_years,
    format_work_date_range,
    format_years_of_experience,
    group_skills,
    humanize_identifier,
)
from app.cv_rendering.models import CvRenderJob, CvRenderResult


_PACKAGE_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_CV_TEMPLATE_PATH = (
    _PACKAGE_DIRECTORY / "templates" / "candidate_cv.html.j2"
)
DEFAULT_CV_STYLESHEET_PATH = (
    _PACKAGE_DIRECTORY / "assets" / "candidate_cv.css"
)


class CvRenderingError(RuntimeError):
    """Raised when HTML or PDF rendering cannot produce a usable CV."""


def render_cv_jobs(
    jobs: Sequence[CvRenderJob],
    *,
    keep_html: bool,
    require_portraits: bool = False,
    template_path: Path = DEFAULT_CV_TEMPLATE_PATH,
    stylesheet_path: Path = DEFAULT_CV_STYLESHEET_PATH,
) -> list[CvRenderResult]:
    """Render selected jobs in deterministic order and return their results.

    ``require_portraits`` protects final dataset generation from silently
    falling back to the development initials placeholder. Sample layout work
    may still omit portraits by leaving the option disabled.
    """

    if require_portraits:
        missing_portraits = [
            job.candidate_id
            for job in jobs
            if not job.portrait_exists
        ]
        if missing_portraits:
            raise CvRenderingError(
                "Real portraits are required but missing for: "
                f"{', '.join(sorted(missing_portraits))}."
            )

    return [
        render_cv_job(
            job,
            keep_html=keep_html,
            template_path=template_path,
            stylesheet_path=stylesheet_path,
        )
        for job in sorted(jobs, key=lambda item: item.candidate_id)
    ]


def render_cv_job(
    job: CvRenderJob,
    *,
    keep_html: bool,
    template_path: Path = DEFAULT_CV_TEMPLATE_PATH,
    stylesheet_path: Path = DEFAULT_CV_STYLESHEET_PATH,
) -> CvRenderResult:
    """Render one job to PDF and verify that its identity remains extractable."""

    rendered_html = render_cv_html(
        job,
        template_path=template_path,
        stylesheet_path=stylesheet_path,
    )

    try:
        job.pdf_path.parent.mkdir(parents=True, exist_ok=True)

        saved_html_path: Path | None = None
        if keep_html:
            job.html_preview_path.parent.mkdir(parents=True, exist_ok=True)
            job.html_preview_path.write_text(rendered_html, encoding="utf-8")
            saved_html_path = job.html_preview_path

        HTML(
            string=rendered_html,
            base_url=str(template_path.parent),
        ).write_pdf(job.pdf_path)
    except OSError as error:
        raise CvRenderingError(
            f"CV artifacts could not be written for {job.candidate_id}."
        ) from error
    except Exception as error:  # WeasyPrint exposes several backend errors.
        raise CvRenderingError(
            f"PDF rendering failed for {job.candidate_id}: {error}"
        ) from error

    page_count, extracted_text_characters = _verify_rendered_pdf(job)

    return CvRenderResult(
        candidate_id=job.candidate_id,
        pdf_path=job.pdf_path,
        html_preview_path=saved_html_path,
        page_count=page_count,
        extracted_text_characters=extracted_text_characters,
        used_placeholder_portrait=not job.portrait_exists,
    )


def render_cv_html(
    job: CvRenderJob,
    *,
    template_path: Path = DEFAULT_CV_TEMPLATE_PATH,
    stylesheet_path: Path = DEFAULT_CV_STYLESHEET_PATH,
) -> str:
    """Return one standalone HTML document ready for browser or PDF output."""

    if not template_path.is_file():
        raise CvRenderingError(f"CV template does not exist: {template_path}")
    if not stylesheet_path.is_file():
        raise CvRenderingError(
            f"CV stylesheet does not exist: {stylesheet_path}"
        )

    try:
        stylesheet = stylesheet_path.read_text(encoding="utf-8")
        environment = _build_jinja_environment(template_path.parent)
        template = environment.get_template(template_path.name)

        return template.render(
            candidate=job.profile,
            candidate_initials=candidate_initials(job.profile.full_name),
            portrait_uri=(
                job.portrait_path.resolve().as_uri()
                if job.portrait_exists
                else None
            ),
            skill_groups=group_skills(job.profile.skills),
            stylesheet=stylesheet,
        )
    except OSError as error:
        raise CvRenderingError(
            f"CV template assets could not be read for {job.candidate_id}."
        ) from error
    except TemplateError as error:
        raise CvRenderingError(
            f"CV template failed for {job.candidate_id}: {error}"
        ) from error


def _build_jinja_environment(template_directory: Path) -> Environment:
    """Create a strict, HTML-safe Jinja environment for the CV template."""

    environment = Environment(
        loader=FileSystemLoader(template_directory),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    environment.filters.update(
        {
            "education_range": format_education_year_range,
            "humanize": humanize_identifier,
            "language_proficiency": format_language_proficiency,
            "seniority": format_seniority,
            "skill_years": format_skill_years,
            "work_range": format_work_date_range,
            "years_experience": format_years_of_experience,
        }
    )

    return environment


def _verify_rendered_pdf(job: CvRenderJob) -> tuple[int, int]:
    """Verify that the new PDF opens and preserves the candidate's name."""

    try:
        with pymupdf.open(job.pdf_path) as document:
            page_count = document.page_count
            extracted_text = "\n".join(
                page.get_text("text", sort=True)
                for page in document
            )
    except (OSError, RuntimeError, ValueError) as error:
        raise CvRenderingError(
            f"Rendered PDF could not be inspected: {job.pdf_path}"
        ) from error

    if page_count < 1:
        raise CvRenderingError(
            f"Rendered PDF contains no pages: {job.pdf_path}"
        )

    normalized_text = " ".join(extracted_text.split())
    if not normalized_text:
        raise CvRenderingError(
            f"Rendered PDF contains no extractable text: {job.pdf_path}"
        )

    if job.profile.full_name not in normalized_text:
        raise CvRenderingError(
            "Rendered PDF does not preserve the candidate name: "
            f"{job.profile.full_name}."
        )

    return page_count, len(normalized_text)
