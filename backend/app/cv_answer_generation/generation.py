"""Grounded answer orchestration and deterministic output validation."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.cv_retrieval import (
    CvFinalRetrievalError,
    FinalCvRetrievalQuery,
    FinalCvRetrievalResult,
    FinalCvRetriever,
    build_final_cv_retriever,
)

from .client import GroundedAnswerProviderError, OpenAIGroundedAnswerProvider
from .models import GroundedAnswerDraft, GroundedCandidateAnswer


class GroundedAnswerProvider(Protocol):
    """Small provider contract used by orchestration and deterministic tests."""

    def generate(
        self,
        retrieval_result: FinalCvRetrievalResult,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> GroundedAnswerDraft:
        """Generate one structured answer from the final retrieval package."""

        ...


@dataclass(frozen=True, slots=True)
class GroundedAnswerGenerationConfig:
    """Bounded correction and output-size policy for answer generation."""

    max_retries: int = 1
    max_answer_characters: int = 5000
    max_candidate_assessment_characters: int = 1800

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("Grounded answer retry count cannot be negative.")
        if self.max_answer_characters < 100:
            raise ValueError(
                "Grounded answer character limit must be at least 100."
            )
        if self.max_candidate_assessment_characters < 100:
            raise ValueError(
                "Candidate assessment character limit must be at least 100."
            )


@dataclass(frozen=True, slots=True)
class GroundedAnswerGenerationResult:
    """Accepted answer draft plus its immutable retrieval evidence."""

    retrieval_result: FinalCvRetrievalResult
    draft: GroundedAnswerDraft
    attempts: int
    provider_called: bool
    model_name: str

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("Grounded answer attempts cannot be negative.")
        if self.provider_called != (self.attempts > 0):
            raise ValueError("Provider call state must match the attempt count.")
        if not self.model_name.strip():
            raise ValueError("Grounded answer model name is required.")


class GroundedAnswerGenerationFailed(RuntimeError):
    """Raised after a non-retryable error or exhausted correction budget."""

    def __init__(self, *, attempts: int, reasons: Sequence[str]) -> None:
        self.attempts = attempts
        self.reasons = tuple(reasons)
        super().__init__(
            f"Grounded answer generation failed after {attempts} attempt(s): "
            + "; ".join(self.reasons)
        )


class GroundedCvAnswerGenerator:
    """Retrieve evidence, invoke the LLM, and validate the structured draft."""

    def __init__(
        self,
        config: GroundedAnswerGenerationConfig,
        *,
        retriever: FinalCvRetriever,
        provider: GroundedAnswerProvider | None,
        model_name: str,
    ) -> None:
        self._config = config
        self._retriever = retriever
        self._provider = provider
        self._model_name = model_name

    def generate(
        self,
        query: FinalCvRetrievalQuery,
    ) -> GroundedAnswerGenerationResult:
        """Return a deterministic unsupported answer or a validated LLM draft."""

        try:
            retrieval_result = self._retriever.retrieve(query)
        except CvFinalRetrievalError as error:
            raise GroundedAnswerGenerationFailed(
                attempts=0,
                reasons=[str(error)],
            ) from error

        if retrieval_result.outcome == "unsupported":
            return GroundedAnswerGenerationResult(
                retrieval_result=retrieval_result,
                draft=_build_unsupported_draft(retrieval_result),
                attempts=0,
                provider_called=False,
                model_name=self._model_name,
            )

        if self._provider is None:
            raise GroundedAnswerGenerationFailed(
                attempts=0,
                reasons=[
                    "OPENAI_API_KEY is required when supported or partial "
                    "candidate evidence must be explained."
                ],
            )

        correction_feedback: tuple[str, ...] = ()
        total_attempts = self._config.max_retries + 1

        for attempt_number in range(1, total_attempts + 1):
            try:
                draft = self._provider.generate(
                    retrieval_result,
                    correction_feedback=correction_feedback,
                )
            except GroundedAnswerProviderError as error:
                if not error.retryable or attempt_number == total_attempts:
                    raise GroundedAnswerGenerationFailed(
                        attempts=attempt_number,
                        reasons=[str(error)],
                    ) from error
                correction_feedback = ()
                continue

            validation_problems = validate_grounded_answer_draft(
                draft,
                retrieval_result,
                config=self._config,
            )
            if not validation_problems:
                return GroundedAnswerGenerationResult(
                    retrieval_result=retrieval_result,
                    draft=draft,
                    attempts=attempt_number,
                    provider_called=True,
                    model_name=self._model_name,
                )

            if attempt_number == total_attempts:
                raise GroundedAnswerGenerationFailed(
                    attempts=attempt_number,
                    reasons=validation_problems,
                )
            correction_feedback = tuple(validation_problems)

        raise RuntimeError("Grounded answer generation ended without a result.")


def validate_grounded_answer_draft(
    draft: GroundedAnswerDraft,
    retrieval_result: FinalCvRetrievalResult,
    *,
    config: GroundedAnswerGenerationConfig,
) -> list[str]:
    """Validate model output against the exact final retrieval contract."""

    problems: list[str] = []

    if draft.outcome != retrieval_result.outcome:
        problems.append(
            "Draft outcome must equal the retrieval outcome "
            f"{retrieval_result.outcome!r}."
        )

    if len(draft.answer) > config.max_answer_characters:
        problems.append(
            "Overall answer exceeds the configured character limit of "
            f"{config.max_answer_characters}."
        )

    expected_ids = [
        candidate.candidate_id for candidate in retrieval_result.candidates
    ]
    actual_ids = [candidate.candidate_id for candidate in draft.candidates]
    if actual_ids != expected_ids:
        problems.append(
            "Draft candidates must exactly match retrieval order: "
            + ", ".join(expected_ids)
            + "."
        )

    if len(actual_ids) != len(set(actual_ids)):
        problems.append("Draft candidate IDs must be unique.")

    expected_by_id = {
        candidate.candidate_id: candidate
        for candidate in retrieval_result.candidates
    }
    for candidate_draft in draft.candidates:
        expected = expected_by_id.get(candidate_draft.candidate_id)
        if expected is None:
            continue
        _validate_candidate_draft(
            candidate_draft,
            expected,
            config=config,
            problems=problems,
        )

    if retrieval_result.outcome == "partial" and not draft.limitations:
        problems.append(
            "Partial answers must include at least one explicit limitation."
        )
    if retrieval_result.outcome == "supported" and not draft.candidates:
        problems.append("Supported answers must include retrieved candidates.")
    if retrieval_result.outcome == "unsupported":
        if draft.candidates:
            problems.append("Unsupported answers cannot include candidates.")
        if not draft.limitations:
            problems.append(
                "Unsupported answers must explain that evidence was not found."
            )

    return problems


def build_grounded_cv_answer_generator(
    settings: Settings,
) -> GroundedCvAnswerGenerator:
    """Build the final retriever and optional direct OpenAI answer provider."""

    api_key = _read_optional_openai_api_key(settings)
    provider: GroundedAnswerProvider | None = None
    if api_key is not None:
        provider = OpenAIGroundedAnswerProvider(
            api_key=api_key,
            model=settings.cv_grounded_answer_model,
            timeout_seconds=settings.cv_grounded_answer_timeout_seconds,
            max_completion_tokens=(
                settings.cv_grounded_answer_max_completion_tokens
            ),
        )

    return GroundedCvAnswerGenerator(
        GroundedAnswerGenerationConfig(
            max_retries=settings.cv_grounded_answer_max_retries,
            max_answer_characters=(
                settings.cv_grounded_answer_max_answer_characters
            ),
            max_candidate_assessment_characters=(
                settings.cv_grounded_answer_max_candidate_assessment_characters
            ),
        ),
        retriever=build_final_cv_retriever(settings),
        provider=provider,
        model_name=settings.cv_grounded_answer_model,
    )


def _validate_candidate_draft(
    candidate_draft: GroundedCandidateAnswer,
    expected,
    *,
    config: GroundedAnswerGenerationConfig,
    problems: list[str],
) -> None:
    """Check one candidate identity and requirement list without cross-mixing."""

    expected_name = expected.candidate_name or "Unknown candidate"
    expected_title = expected.professional_title or "Unknown title"
    expected_requirements = list(expected.matched_condition_labels)

    if candidate_draft.candidate_name != expected_name:
        problems.append(
            f"{expected.candidate_id} name must remain {expected_name!r}."
        )
    if candidate_draft.professional_title != expected_title:
        problems.append(
            f"{expected.candidate_id} title must remain {expected_title!r}."
        )
    if candidate_draft.matched_requirements != expected_requirements:
        problems.append(
            f"{expected.candidate_id} matched requirements must remain: "
            + ", ".join(expected_requirements)
            + "."
        )
    if (
        len(candidate_draft.assessment)
        > config.max_candidate_assessment_characters
    ):
        problems.append(
            f"{expected.candidate_id} assessment exceeds the configured "
            f"character limit of "
            f"{config.max_candidate_assessment_characters}."
        )


def _build_unsupported_draft(
    retrieval_result: FinalCvRetrievalResult,
) -> GroundedAnswerDraft:
    """Return an honest no-evidence answer without making an LLM call."""

    return GroundedAnswerDraft(
        outcome="unsupported",
        answer=(
            "I could not identify any candidate with sufficiently supported "
            "evidence for this question in the indexed CV collection."
        ),
        candidates=[],
        limitations=[retrieval_result.support_message],
    )


def _read_optional_openai_api_key(settings: Settings) -> str | None:
    """Return a non-empty API key while allowing unsupported local queries."""

    if settings.openai_api_key is None:
        return None
    value = settings.openai_api_key.get_secret_value().strip()
    return value or None
