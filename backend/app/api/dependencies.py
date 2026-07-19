"""FastAPI dependency factories for the thin WP8 HTTP layer."""

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
    """Expose cached validated settings through FastAPI dependency injection."""

    return get_settings()


@lru_cache
def get_candidate_catalog_service() -> CandidateCatalogService:
    """Build the read-only candidate catalogue over the existing index."""

    return build_candidate_catalog_service(get_settings())


@lru_cache
def get_grounded_answer_generator() -> GroundedCvAnswerGenerator:
    """Build WP7 orchestration and map explicit key misconfiguration safely."""

    try:
        return build_grounded_cv_answer_generator(get_settings())
    except GroundedAnswerConfigurationError as error:
        raise ApiServiceUnavailableError(
            "provider_not_configured",
            "The selected hosted provider is not configured. Run setup.ps1 "
            "or select deterministic mode.",
        ) from error
