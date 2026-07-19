"""Configuration-driven selection of grounded-answer generation providers."""

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

from .client import OpenAIGroundedAnswerProvider
from .gemini_client import GeminiGroundedAnswerProvider
from .models import GroundedAnswerProviderName


class GroundedAnswerConfigurationError(RuntimeError):
    """Raised when an explicitly selected provider is missing its API key."""


@dataclass(frozen=True, slots=True)
class ResolvedGroundedAnswerProvider:
    """One selected provider plus stable diagnostic labels."""

    provider: Any | None
    provider_name: GroundedAnswerProviderName
    model_name: str


def resolve_grounded_answer_provider(
    settings: Settings,
) -> ResolvedGroundedAnswerProvider:
    """Resolve auto, OpenAI, Gemini, or deterministic answer generation."""

    requested = settings.cv_grounded_answer_provider
    gemini_key = _read_gemini_api_key(settings)
    openai_key = _read_secret(settings.openai_api_key)

    if requested == "auto":
        # Gemini is the preferred zero-cost hosted option for local evaluators.
        if gemini_key is not None:
            requested = "gemini"
        elif openai_key is not None:
            requested = "openai"
        else:
            requested = "deterministic"

    if requested == "gemini":
        if gemini_key is None:
            raise GroundedAnswerConfigurationError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is required when "
                "CV_GROUNDED_ANSWER_PROVIDER=gemini."
            )
        return ResolvedGroundedAnswerProvider(
            provider=GeminiGroundedAnswerProvider(
                api_key=gemini_key,
                model=settings.cv_grounded_answer_gemini_model,
                timeout_seconds=settings.cv_grounded_answer_timeout_seconds,
                max_completion_tokens=(
                    settings.cv_grounded_answer_max_completion_tokens
                ),
            ),
            provider_name="gemini",
            model_name=settings.cv_grounded_answer_gemini_model,
        )

    if requested == "openai":
        if openai_key is None:
            raise GroundedAnswerConfigurationError(
                "OPENAI_API_KEY is required when "
                "CV_GROUNDED_ANSWER_PROVIDER=openai."
            )
        return ResolvedGroundedAnswerProvider(
            provider=OpenAIGroundedAnswerProvider(
                api_key=openai_key,
                model=settings.cv_grounded_answer_model,
                timeout_seconds=settings.cv_grounded_answer_timeout_seconds,
                max_completion_tokens=(
                    settings.cv_grounded_answer_max_completion_tokens
                ),
            ),
            provider_name="openai",
            model_name=settings.cv_grounded_answer_model,
        )

    return ResolvedGroundedAnswerProvider(
        provider=None,
        provider_name="deterministic",
        model_name="deterministic-template-v1",
    )


def _read_gemini_api_key(settings: Settings) -> str | None:
    """Follow Google's precedence when both supported key names are present."""

    return _read_secret(settings.google_api_key) or _read_secret(
        settings.gemini_api_key
    )


def _read_secret(secret) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None
