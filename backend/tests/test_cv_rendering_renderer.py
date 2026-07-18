"""Integration tests for Jinja, WeasyPrint, and PyMuPDF CV rendering."""

from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from app.cv_rendering import (
    CvRenderingError,
    build_cv_render_jobs,
    render_cv_html,
    render_cv_job,
    render_cv_jobs,
)
from app.portrait_generation import normalize_portrait_image
from app.schemas import CandidateProfile


def _build_job(
    tmp_path: Path,
    valid_candidate_payload: dict,
):
    """Create one isolated render job without a real portrait asset."""

    profile = CandidateProfile.model_validate(valid_candidate_payload)
    return build_cv_render_jobs(
        [profile],
        images_directory=tmp_path / "images",
        pdf_directory=tmp_path / "pdfs",
        html_preview_directory=tmp_path / "html",
    )[0]


def test_html_template_renders_all_required_profile_sections(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """The standalone HTML preserves facts required by future retrieval."""

    job = _build_job(tmp_path, valid_candidate_payload)

    rendered_html = render_cv_html(job)

    assert "Alex Morgan" in rendered_html
    assert "Senior Python Backend Engineer" in rendered_html
    assert "alex.morgan@example.com" in rendered_html
    assert "Professional Experience" in rendered_html
    assert "Team leadership: managed 4 people" in rendered_html
    assert "Python" in rendered_html
    assert "Greek" in rendered_html
    assert "Certifications" not in rendered_html
    assert "Selected Projects" not in rendered_html
    assert "portrait-placeholder" in rendered_html


def test_render_job_writes_searchable_pdf_and_optional_html(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Rendered output opens, contains text, and records placeholder usage."""

    job = _build_job(tmp_path, valid_candidate_payload)

    result = render_cv_job(job, keep_html=True)

    assert result.candidate_id == "candidate_001"
    assert result.pdf_path.is_file()
    assert result.html_preview_path == job.html_preview_path
    assert result.html_preview_path.is_file()
    assert result.page_count >= 1
    assert result.extracted_text_characters > 200
    assert result.used_placeholder_portrait is True

    with pymupdf.open(result.pdf_path) as document:
        extracted_text = "\n".join(
            page.get_text("text", sort=True)
            for page in document
        )

    assert "Alex Morgan" in extracted_text
    assert "FastAPI" in extracted_text
    assert "managed 4 people" in extracted_text

def test_final_batch_can_require_real_portraits(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Final dataset rendering fails before writing placeholder-based PDFs."""

    job = _build_job(tmp_path, valid_candidate_payload)

    with pytest.raises(CvRenderingError, match="candidate_001"):
        render_cv_jobs(
            [job],
            keep_html=False,
            require_portraits=True,
        )

    assert not job.pdf_path.exists()

def test_final_batch_renders_with_verified_real_portrait(
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """A normalized portrait satisfies the final-dataset rendering guard."""

    job = _build_job(tmp_path, valid_candidate_payload)
    source = Image.effect_noise((700, 700), 50).convert("RGB")
    buffer = BytesIO()
    source.save(buffer, format="PNG")
    normalize_portrait_image(
        buffer.getvalue(),
        output_path=job.portrait_path,
        normalized_size=512,
        webp_quality=88,
    )

    result = render_cv_jobs(
        [job],
        keep_html=False,
        require_portraits=True,
    )[0]

    assert result.pdf_path.is_file()
    assert result.used_placeholder_portrait is False

