"""Tests for the direct OpenAI structured-output boundary."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIConnectionError

from app.candidate_generation import (
    CandidateProviderError,
    OpenAICandidateGenerator,
    load_candidate_dataset_plan,
)
from app.schemas import CandidateProfile


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


def _candidate_001_slot():
    return load_candidate_dataset_plan(PLAN_PATH).candidates[0]


def _generator(client: MagicMock) -> OpenAICandidateGenerator:
    return OpenAICandidateGenerator(
        api_key="test-key",
        model="test-model",
        timeout_seconds=30,
        max_completion_tokens=4000,
        client=client,
    )


def test_openai_generator_returns_the_parsed_candidate_profile(
    valid_candidate_001_payload: dict,
) -> None:
    """The provider boundary should return the SDK-parsed Pydantic model."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=profile,
        status="completed",
        incomplete_details=None,
    )

    generated = _generator(client).generate(_candidate_001_slot())

    assert generated == profile
    call = client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["text_format"] is CandidateProfile
    assert call["max_output_tokens"] == 4000
    assert call["store"] is False
    assert "technology-sector CV" in call["instructions"]
    assert "candidate_001" in call["input"]


def test_openai_generator_marks_connection_failures_as_retryable() -> None:
    """Transient transport failures should use the bounded retry loop."""

    client = MagicMock()
    client.responses.parse.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )

    with pytest.raises(CandidateProviderError) as raised:
        _generator(client).generate(_candidate_001_slot())

    assert raised.value.retryable is True
    assert "could not be reached" in str(raised.value)


def test_openai_generator_retries_an_output_token_limit() -> None:
    """An incomplete response may be retried when the output limit caused it."""

    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None,
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    with pytest.raises(CandidateProviderError) as raised:
        _generator(client).generate(_candidate_001_slot())

    assert raised.value.retryable is True
    assert "max_output_tokens" in str(raised.value)


def test_openai_generator_rejects_a_completed_unparsed_response() -> None:
    """A completed response without parsed data is not a valid profile."""

    client = MagicMock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=None,
        status="completed",
        incomplete_details=None,
    )

    with pytest.raises(CandidateProviderError) as raised:
        _generator(client).generate(_candidate_001_slot())

    assert raised.value.retryable is False
    assert "without returning" in str(raised.value)
