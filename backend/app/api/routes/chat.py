"""Grounded candidate chat endpoint over the completed WP6/WP7 pipeline."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.cv_answer_generation import (
    GroundedAnswerConfigurationError,
    GroundedAnswerGenerationFailed,
    GroundedCvAnswerGenerator,
)
from app.cv_retrieval import FinalCvRetrievalQuery

from ..dependencies import get_grounded_answer_generator
from ..errors import ApiServiceUnavailableError, ApiUpstreamError
from ..presenters import present_chat_response
from ..schemas import ApiErrorResponse, ChatRequest, ChatResponse


router = APIRouter(prefix="/chat", tags=["chat"])
GroundedGeneratorDependency = Annotated[
    GroundedCvAnswerGenerator,
    Depends(get_grounded_answer_generator),
]


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a grounded candidate question",
    description=(
        "Runs semantic recall, relation-aware evidence recovery, candidate "
        "ranking, support classification, bounded context, grounded wording, "
        "and application-validated candidate-owned citations. Unsupported "
        "questions return HTTP 200 with outcome=unsupported."
    ),
    responses={
        422: {
            "model": ApiErrorResponse,
            "description": "Blank, overlong, or otherwise invalid request.",
        },
        502: {
            "model": ApiErrorResponse,
            "description": "Configured hosted provider failed.",
        },
        503: {
            "model": ApiErrorResponse,
            "description": (
                "Retrieval index or provider configuration unavailable."
            ),
        },
    },
)
def ask_candidates(
    request: ChatRequest,
    generator: GroundedGeneratorDependency,
) -> ChatResponse:
    try:
        result = generator.generate(
            FinalCvRetrievalQuery(
                request.question,
                candidate_limit=request.candidate_limit,
            )
        )
    except GroundedAnswerConfigurationError as error:
        raise ApiServiceUnavailableError(
            "provider_not_configured",
            "The selected hosted provider is not configured. Run setup.ps1 "
            "or select deterministic mode.",
        ) from error
    except GroundedAnswerGenerationFailed as error:
        if error.attempts > 0:
            raise ApiUpstreamError(
                "answer_provider_failed",
                "The configured answer provider could not complete the request.",
            ) from error
        raise ApiServiceUnavailableError(
            "retrieval_unavailable",
            "The indexed CV retrieval pipeline could not complete the request.",
        ) from error

    return present_chat_response(result)
