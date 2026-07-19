"""Direct OpenAI structured-output client for grounded CV answers."""

from collections.abc import Sequence

import openai
from openai import OpenAI
from pydantic import ValidationError

from app.cv_retrieval import FinalCvRetrievalResult

from .models import GroundedAnswerDraft
from .prompt import GROUNDED_ANSWER_INSTRUCTIONS, build_grounded_answer_prompt


class GroundedAnswerProviderError(RuntimeError):
    """Provider failure annotated for the bounded generation retry loop."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class OpenAIGroundedAnswerProvider:
    """Generate one structured recruiter answer through the Responses API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._max_completion_tokens = max_completion_tokens
        self._client = client or OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate(
        self,
        retrieval_result: FinalCvRetrievalResult,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> GroundedAnswerDraft:
        """Return one schema-valid draft for the supplied evidence package."""

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=GROUNDED_ANSWER_INSTRUCTIONS,
                input=build_grounded_answer_prompt(
                    retrieval_result,
                    correction_feedback=correction_feedback,
                ),
                text_format=GroundedAnswerDraft,
                max_output_tokens=self._max_completion_tokens,
                store=False,
            )
        except ValidationError as error:
            raise GroundedAnswerProviderError(
                "The structured response did not pass GroundedAnswerDraft "
                "validation.",
                retryable=True,
            ) from error
        except openai.APIConnectionError as error:
            raise GroundedAnswerProviderError(
                "The OpenAI API could not be reached or timed out.",
                retryable=True,
            ) from error
        except openai.APIStatusError as error:
            retryable = (
                error.status_code in {408, 409, 429}
                or error.status_code >= 500
            )
            request_suffix = (
                f" Request ID: {error.request_id}."
                if error.request_id
                else ""
            )
            raise GroundedAnswerProviderError(
                f"OpenAI returned HTTP {error.status_code}."
                f"{request_suffix}",
                retryable=retryable,
            ) from error
        except openai.APIError as error:
            raise GroundedAnswerProviderError(
                "OpenAI rejected the grounded-answer request.",
                retryable=False,
            ) from error

        if response.output_parsed is not None:
            return response.output_parsed

        if response.status == "incomplete":
            reason = (
                response.incomplete_details.reason
                if response.incomplete_details is not None
                else "unknown"
            )
            raise GroundedAnswerProviderError(
                f"OpenAI returned an incomplete structured response: {reason}.",
                retryable=reason == "max_output_tokens",
            )

        raise GroundedAnswerProviderError(
            "The model completed without returning a structured grounded "
            "answer.",
            retryable=False,
        )
