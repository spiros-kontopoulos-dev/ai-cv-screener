"""Tests for explicit and automatic grounded-answer provider selection."""

import pytest

from app.core.config import Settings
from app.cv_answer_generation import (
    GeminiGroundedAnswerProvider,
    GroundedAnswerConfigurationError,
    OpenAIGroundedAnswerProvider,
    resolve_grounded_answer_provider,
)


def test_auto_mode_uses_deterministic_fallback_without_keys() -> None:
    resolved = resolve_grounded_answer_provider(
        Settings(
            cv_grounded_answer_provider="auto",
            openai_api_key=None,
            gemini_api_key=None,
            google_api_key=None,
        )
    )

    assert resolved.provider is None
    assert resolved.provider_name == "deterministic"
    assert resolved.model_name == "deterministic-template-v1"


def test_auto_mode_prefers_gemini_over_openai() -> None:
    resolved = resolve_grounded_answer_provider(
        Settings(
            gemini_api_key="gemini-test-key",
            openai_api_key="openai-test-key",
        )
    )

    assert isinstance(resolved.provider, GeminiGroundedAnswerProvider)
    assert resolved.provider_name == "gemini"


def test_explicit_openai_provider_requires_key() -> None:
    with pytest.raises(GroundedAnswerConfigurationError) as raised:
        resolve_grounded_answer_provider(
            Settings(
                cv_grounded_answer_provider="openai",
                openai_api_key=None,
                gemini_api_key=None,
                google_api_key=None,
            )
        )

    assert "OPENAI_API_KEY" in str(raised.value)


def test_explicit_openai_provider_uses_configured_model() -> None:
    resolved = resolve_grounded_answer_provider(
        Settings(
            cv_grounded_answer_provider="openai",
            openai_api_key="openai-test-key",
            cv_grounded_answer_model="gpt-test",
        )
    )

    assert isinstance(resolved.provider, OpenAIGroundedAnswerProvider)
    assert resolved.provider_name == "openai"
    assert resolved.model_name == "gpt-test"


def test_google_api_key_takes_precedence_for_gemini() -> None:
    resolved = resolve_grounded_answer_provider(
        Settings(
            cv_grounded_answer_provider="gemini",
            gemini_api_key="gemini-key",
            google_api_key="google-key",
        )
    )

    assert isinstance(resolved.provider, GeminiGroundedAnswerProvider)
    assert resolved.model_name == "gemini-3.1-flash-lite"
