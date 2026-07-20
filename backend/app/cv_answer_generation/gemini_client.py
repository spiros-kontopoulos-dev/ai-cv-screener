"""Google Gemini JSON-mode client for grounded CV answers."""

from collections.abc import Sequence

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.cv_retrieval import FinalCvRetrievalResult

from .client import GroundedAnswerProviderError
from .models import GroundedAnswerDraft
from .prompt import (
    GEMINI_GROUNDED_ANSWER_JSON_CONTRACT,
    GROUNDED_ANSWER_INSTRUCTIONS,
    build_grounded_answer_prompt,
)


class GeminiGroundedAnswerProvider:
    """Generate one validated recruiter answer through Gemini JSON mode."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int,
        client: genai.Client | None = None,
    ) -> None:
        self._model = model
        self._max_completion_tokens = max_completion_tokens
        self._client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                # The SDK expects milliseconds for this request timeout.
                timeout=int(timeout_seconds * 1000),
                # Application-level validation owns the bounded retry loop.
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(
        self,
        retrieval_result: FinalCvRetrievalResult,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> GroundedAnswerDraft:
        """Return one Pydantic-valid draft for the supplied evidence package."""

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=build_grounded_answer_prompt(
                    retrieval_result,
                    correction_feedback=correction_feedback,
                ),
                config=types.GenerateContentConfig(
                    system_instruction=(
                        GROUNDED_ANSWER_INSTRUCTIONS
                        + "\n\n"
                        + GEMINI_GROUNDED_ANSWER_JSON_CONTRACT
                    ),
                    # Gemini JSON mode guarantees JSON syntax without sending
                    # the nested Pydantic schema through either of the API
                    # schema transports. Both schema paths were rejected by
                    # the live Gemini endpoint for this contract. The compact
                    # prompt contract guides generation, while the original
                    # GroundedAnswerDraft remains the strict validation
                    # boundary immediately after the response.
                    response_mime_type="application/json",
                    max_output_tokens=self._max_completion_tokens,
                    temperature=0.1,
                ),
            )
        except errors.APIError as error:
            retryable = error.code in {408, 409, 429} or error.code >= 500
            raise GroundedAnswerProviderError(
                f"Gemini returned HTTP {error.code}: {error.message}",
                retryable=retryable,
            ) from error
        except (OSError, TimeoutError) as error:
            raise GroundedAnswerProviderError(
                "The Gemini API could not be reached or timed out.",
                retryable=True,
            ) from error

        try:
            if isinstance(response.parsed, GroundedAnswerDraft):
                return response.parsed
            if response.parsed is not None:
                return GroundedAnswerDraft.model_validate(response.parsed)
            if response.text:
                return GroundedAnswerDraft.model_validate_json(response.text)
        except ValidationError as error:
            raise GroundedAnswerProviderError(
                "The Gemini JSON response did not pass "
                "GroundedAnswerDraft validation.",
                retryable=True,
            ) from error

        raise GroundedAnswerProviderError(
            "Gemini completed without returning a grounded JSON answer.",
            retryable=False,
        )
