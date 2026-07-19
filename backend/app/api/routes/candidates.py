"""Candidate catalogue and trusted PDF delivery endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.services import (
    CandidateCatalogError,
    CandidateCatalogService,
    CandidateNotFoundError,
    CandidatePdfUnavailableError,
)

from ..dependencies import get_candidate_catalog_service
from ..errors import ApiNotFoundError, ApiServiceUnavailableError
from ..schemas import (
    ApiErrorResponse,
    CandidateListItem,
    CandidateListResponse,
)


router = APIRouter(prefix="/candidates", tags=["candidates"])
CandidateCatalogDependency = Annotated[
    CandidateCatalogService,
    Depends(get_candidate_catalog_service),
]


@router.get(
    "",
    response_model=CandidateListResponse,
    summary="List indexed candidates",
    description=(
        "Returns sidebar identity assembled from persisted PDF-index metadata. "
        "The endpoint does not use candidate profile JSON as answer evidence."
    ),
    responses={
        503: {
            "model": ApiErrorResponse,
            "description": "Candidate index unavailable.",
        }
    },
)
def list_candidates(
    catalog: CandidateCatalogDependency,
) -> CandidateListResponse:
    try:
        indexed = catalog.list_candidates()
    except CandidateCatalogError as error:
        raise ApiServiceUnavailableError(
            "candidate_index_unavailable",
            "The indexed candidate catalogue is currently unavailable.",
        ) from error

    candidates = [
        CandidateListItem(
            candidate_id=item.candidate_id,
            name=item.name,
            professional_title=item.professional_title,
            source_filename=item.source_filename,
            cv_available=item.cv_available,
            photo_available=item.photo_available,
        )
        for item in indexed
    ]
    return CandidateListResponse(count=len(candidates), candidates=candidates)


@router.get(
    "/{candidate_id}/cv",
    response_class=FileResponse,
    summary="Open a candidate CV",
    description=(
        "Resolves the PDF from trusted indexed metadata and configured CV "
        "directories. User-supplied filesystem paths are never accepted."
    ),
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {
            "model": ApiErrorResponse,
            "description": "Unknown candidate or unavailable PDF.",
        },
        503: {
            "model": ApiErrorResponse,
            "description": "Candidate index unavailable.",
        },
    },
)
def open_candidate_cv(
    candidate_id: str,
    catalog: CandidateCatalogDependency,
) -> FileResponse:
    try:
        candidate = catalog.get_candidate(candidate_id)
        path = catalog.resolve_candidate_pdf(candidate_id)
    except CandidateNotFoundError as error:
        raise ApiNotFoundError(
            "candidate_not_found",
            "The requested candidate does not exist.",
        ) from error
    except CandidatePdfUnavailableError as error:
        raise ApiNotFoundError(
            "candidate_cv_not_found",
            "The requested candidate CV is not available.",
        ) from error
    except CandidateCatalogError as error:
        raise ApiServiceUnavailableError(
            "candidate_index_unavailable",
            "The indexed candidate catalogue is currently unavailable.",
        ) from error

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=candidate.source_filename,
        content_disposition_type="inline",
    )
