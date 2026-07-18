"""Public contracts for planning and later rendering candidate CVs."""

from app.cv_rendering.models import CvProfileMetrics, CvRenderJob
from app.cv_rendering.planning import (
    NORMALIZED_PORTRAIT_EXTENSION,
    CvRenderingPlanError,
    build_cv_render_jobs,
    find_profile_boundaries,
    measure_candidate_profile,
    select_cv_render_jobs,
)

__all__ = [
    "NORMALIZED_PORTRAIT_EXTENSION",
    "CvProfileMetrics",
    "CvRenderJob",
    "CvRenderingPlanError",
    "build_cv_render_jobs",
    "find_profile_boundaries",
    "measure_candidate_profile",
    "select_cv_render_jobs",
]
