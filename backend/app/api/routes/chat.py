"""Accept recruiter questions and return grounded candidate answers.

``POST /api/chat`` passes the question to the shared answer generator. That
service runs the complete flow:

1. Search the indexed CV chunks.
2. Check exact words, numbers, and relationships where needed.
3. Group evidence by candidate and rank the candidates.
4. Decide whether the evidence is complete, partial, or unsupported.
5. Build a small source-backed context.
6. Write the answer with the selected provider or deterministic fallback.
7. Validate that every candidate claim uses citations owned by that candidate.

The route itself only validates HTTP input, calls the service, maps expected
failures to safe HTTP errors, and presents the final response for React.
"""

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
        "Searches indexed CV evidence, ranks whole candidates, writes a grounded "
        "answer, and returns validated citations. Unsupported questions return "
        "HTTP 200 with outcome=unsupported."
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
    """Run one grounded search request and return its browser-facing response."""

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
        # ``attempts > 0`` means retrieval succeeded but a hosted provider was
        # called and failed. Zero attempts means the local retrieval path could
        # not finish before any provider call.
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
