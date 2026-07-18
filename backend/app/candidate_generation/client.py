"""Direct OpenAI structured-output client for candidate generation."""

from collections.abc import Sequence

import openai
from openai import OpenAI
from pydantic import ValidationError

from app.schemas import CandidateProfile

from .models import CandidateGenerationSlot
from .prompt import CANDIDATE_GENERATION_INSTRUCTIONS, build_candidate_prompt


class CandidateProviderError(RuntimeError):
    """A provider failure with explicit retry guidance for the orchestrator."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class OpenAICandidateGenerator:
    """Generate one CandidateProfile through OpenAI Structured Outputs.

    The modern Responses API receives the shared instructions, one focused
    candidate prompt, and the Pydantic model used as the structured output
    contract. SDK retries are disabled because the application-level loop owns
    one clear retry budget for provider and slot-compliance failures together.
    """

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
        slot: CandidateGenerationSlot,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> CandidateProfile:
        """Return one schema-validated profile for a controlled slot."""

        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=CANDIDATE_GENERATION_INSTRUCTIONS,
                input=build_candidate_prompt(
                    slot,
                    correction_feedback=correction_feedback,
                ),
                text_format=CandidateProfile,
                max_output_tokens=self._max_completion_tokens,
                # Candidate-generation responses do not need server-side
                # retrieval after the local validation step completes.
                store=False,
            )
        except ValidationError as error:
            raise CandidateProviderError(
                "The structured response did not pass CandidateProfile "
                "validation.",
                retryable=True,
            ) from error
        except openai.APIConnectionError as error:
            raise CandidateProviderError(
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
            raise CandidateProviderError(
                f"OpenAI returned HTTP {error.status_code}."
                f"{request_suffix}",
                retryable=retryable,
            ) from error
        except openai.APIError as error:
            raise CandidateProviderError(
                "OpenAI rejected the candidate-generation request.",
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
            raise CandidateProviderError(
                f"OpenAI returned an incomplete structured response: {reason}.",
                retryable=reason == "max_output_tokens",
            )

        raise CandidateProviderError(
            "The model completed without returning a structured "
            "CandidateProfile.",
            retryable=False,
        )
