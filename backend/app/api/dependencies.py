"""Create shared backend services for FastAPI route functions.

FastAPI calls these small functions when a route declares ``Depends(...)``.
The expensive services are cached, so they are built once and reused for later
requests instead of being recreated every time.

Routes depend on interfaces such as ``CandidateCatalogService`` and
``GroundedCvAnswerGenerator`` rather than building those objects themselves.
This keeps HTTP code small and makes the routes easier to test.
"""

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.cv_answer_generation import (
    GroundedAnswerConfigurationError,
    GroundedCvAnswerGenerator,
    build_grounded_cv_answer_generator,
)
from app.services import CandidateCatalogService, build_candidate_catalog_service

from .errors import ApiServiceUnavailableError


def get_api_settings() -> Settings:
    """Give a route access to the shared validated settings."""

    return get_settings()


@lru_cache
def get_candidate_catalog_service() -> CandidateCatalogService:
    """Build and reuse the read-only service that lists candidates and CVs."""

    return build_candidate_catalog_service(get_settings())


@lru_cache
def get_grounded_answer_generator() -> GroundedCvAnswerGenerator:
    """Build and reuse the complete search-and-answer service.

    The builder connects candidate retrieval, provider selection, answer
    generation, and citation checks. A missing key for an explicitly selected
    hosted provider is converted into a safe API error before a route runs.
    """

    try:
        return build_grounded_cv_answer_generator(get_settings())
    except GroundedAnswerConfigurationError as error:
        raise ApiServiceUnavailableError(
            "provider_not_configured",
            "The selected hosted provider is not configured. Run setup.ps1 "
            "or select deterministic mode.",
        ) from error
