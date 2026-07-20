"""Google Gemini structured-output client for grounded CV answers."""

from collections.abc import Sequence

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.cv_retrieval import FinalCvRetrievalResult

from .client import GroundedAnswerProviderError
from .models import GroundedAnswerDraft
from .prompt import GROUNDED_ANSWER_INSTRUCTIONS, build_grounded_answer_prompt


class GeminiGroundedAnswerProvider:
    """Generate one structured recruiter answer through the Gemini API."""

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
                    system_instruction=GROUNDED_ANSWER_INSTRUCTIONS,
                    response_mime_type="application/json",
                    # ``response_schema`` converts the Pydantic model through
                    # Gemini's legacy Schema message. That path rejects valid
                    # JSON Schema keywords emitted by ``extra="forbid"``,
                    # including ``additionalProperties``. Send the model's raw
                    # JSON Schema instead, then keep Pydantic as the strict
                    # application-side validation boundary below.
                    response_json_schema=(
                        GroundedAnswerDraft.model_json_schema()
                    ),
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
                "The Gemini structured response did not pass "
                "GroundedAnswerDraft validation.",
                retryable=True,
            ) from error

        raise GroundedAnswerProviderError(
            "Gemini completed without returning a structured grounded answer.",
            retryable=False,
        )
