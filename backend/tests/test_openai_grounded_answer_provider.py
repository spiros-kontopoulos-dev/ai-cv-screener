"""Direct OpenAI provider tests for grounded structured answers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
from openai import APIConnectionError
import pytest

from app.cv_answer_generation import (
    GroundedAnswerDraft,
    GroundedAnswerProviderError,
    GroundedCandidateAnswer,
    OpenAIGroundedAnswerProvider,
)
from cv_retrieval_test_helpers import CandidateSpec, build_candidate_result, finalize_for_test


def _retrieval_result():
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            )
        )
    )


def _draft() -> GroundedAnswerDraft:
    return GroundedAnswerDraft(
        outcome="supported",
        answer="Eleni is a complete source-backed match.",
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Her evidence supports both requested requirements.",
                matched_requirements=["python", "postgresql"],
            )
        ],
        limitations=[],
    )


def _provider(client) -> OpenAIGroundedAnswerProvider:
    return OpenAIGroundedAnswerProvider(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=30,
        max_completion_tokens=2000,
        client=client,
    )


def test_provider_uses_responses_structured_output() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=_draft(),
        status="completed",
        incomplete_details=None,
    )

    result = _provider(client).generate(_retrieval_result())

    assert result == _draft()
    call = client.responses.parse.call_args.kwargs
    assert call["model"] == "gpt-test"
    assert call["text_format"] is GroundedAnswerDraft
    assert call["max_output_tokens"] == 2000
    assert call["store"] is False
    assert "candidate_001" in call["input"]
    assert "answer-generation layer" in call["instructions"]


def test_provider_passes_correction_feedback_to_prompt() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=_draft(),
        status="completed",
        incomplete_details=None,
    )

    _provider(client).generate(
        _retrieval_result(),
        correction_feedback=("Candidate order is wrong.",),
    )

    assert "Candidate order is wrong" in (
        client.responses.parse.call_args.kwargs["input"]
    )


def test_provider_marks_connection_failures_as_retryable() -> None:
    client = MagicMock()
    client.responses.parse.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )

    with pytest.raises(GroundedAnswerProviderError) as raised:
        _provider(client).generate(_retrieval_result())

    assert raised.value.retryable is True
    assert "could not be reached" in str(raised.value)


def test_provider_retries_output_token_incompletion() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None,
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    with pytest.raises(GroundedAnswerProviderError) as raised:
        _provider(client).generate(_retrieval_result())

    assert raised.value.retryable is True
    assert "max_output_tokens" in str(raised.value)


def test_provider_rejects_completed_unparsed_response() -> None:
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None,
        status="completed",
        incomplete_details=None,
    )

    with pytest.raises(GroundedAnswerProviderError) as raised:
        _provider(client).generate(_retrieval_result())

    assert raised.value.retryable is False
    assert "without returning" in str(raised.value)
