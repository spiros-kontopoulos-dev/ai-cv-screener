"""Non-secret application, provider, and index readiness endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.cv_answer_generation import (
    GroundedAnswerConfigurationError,
    resolve_grounded_answer_provider,
)
from app.services import CandidateCatalogError, CandidateCatalogService

from ..dependencies import get_api_settings, get_candidate_catalog_service
from ..schemas import (
    HealthIndexStatus,
    HealthProviderStatus,
    HealthResponse,
)


router = APIRouter(tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_api_settings)]
CatalogDependency = Annotated[
    CandidateCatalogService,
    Depends(get_candidate_catalog_service),
]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API readiness",
    description=(
        "Reports only non-secret provider selection and index coverage. API "
        "keys and provider error details are never returned."
    ),
)
def health_check(
    settings: SettingsDependency,
    catalog: CatalogDependency,
) -> HealthResponse:
    provider = _provider_status(settings)

    try:
        coverage = catalog.get_index_coverage()
        index = HealthIndexStatus(
            available=(
                coverage.record_count > 0
                and coverage.candidate_count > 0
                and coverage.incomplete_document_count == 0
            ),
            record_count=coverage.record_count,
            document_count=coverage.document_count,
            candidate_count=coverage.candidate_count,
            complete_document_count=coverage.complete_document_count,
            incomplete_document_count=coverage.incomplete_document_count,
        )
    except CandidateCatalogError:
        index = HealthIndexStatus(
            available=False,
            record_count=0,
            document_count=0,
            candidate_count=0,
            complete_document_count=0,
            incomplete_document_count=0,
        )

    return HealthResponse(
        status="ok" if provider.ready and index.available else "degraded",
        service=settings.app_name,
        environment=settings.app_env,
        provider=provider,
        index=index,
    )


def _provider_status(settings: Settings) -> HealthProviderStatus:
    """Resolve provider diagnostics without exposing any secret value."""

    try:
        resolved = resolve_grounded_answer_provider(settings)
        return HealthProviderStatus(
            requested_mode=settings.cv_grounded_answer_provider,
            active_provider=resolved.provider_name,
            model=resolved.model_name,
            ready=True,
        )
    except GroundedAnswerConfigurationError:
        requested = settings.cv_grounded_answer_provider
        if requested == "openai":
            provider = "openai"
            model = settings.cv_grounded_answer_model
        elif requested == "gemini":
            provider = "gemini"
            model = settings.cv_grounded_answer_gemini_model
        else:
            provider = "deterministic"
            model = "deterministic-template-v1"
        return HealthProviderStatus(
            requested_mode=requested,
            active_provider=provider,
            model=model,
            ready=False,
        )
