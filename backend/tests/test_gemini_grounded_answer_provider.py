"""Google Gemini provider tests for grounded structured answers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from google.genai import errors
import pytest

from app.cv_answer_generation import (
    GeminiGroundedAnswerProvider,
    GroundedAnswerDraft,
    GroundedAnswerProviderError,
    GroundedCandidateAnswer,
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
        answer_citation_ids=["candidate_001-source-1"],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Her evidence supports both requirements.",
                matched_requirements=["python", "postgresql"],
                citation_ids=["candidate_001-source-1"],
            )
        ],
        limitations=[],
    )


def _provider(client) -> GeminiGroundedAnswerProvider:
    return GeminiGroundedAnswerProvider(
        api_key="test-key",
        model="gemini-test",
        timeout_seconds=30,
        max_completion_tokens=2000,
        client=client,
    )


def test_provider_uses_raw_json_schema_structured_output() -> None:
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        parsed=_draft(),
        text=_draft().model_dump_json(),
    )

    result = _provider(client).generate(_retrieval_result())

    assert result == _draft()
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-test"
    assert "candidate_001-source-1" in call["contents"]
    expected_schema = GroundedAnswerDraft.model_json_schema()
    assert call["config"].response_json_schema == expected_schema
    assert call["config"].response_schema is None
    assert expected_schema["additionalProperties"] is False
    assert (
        expected_schema["$defs"]["GroundedCandidateAnswer"][
            "additionalProperties"
        ]
        is False
    )
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].max_output_tokens == 2000


def test_provider_validates_parsed_mapping_with_pydantic() -> None:
    """Raw JSON schema responses remain subject to the strict app contract."""

    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        parsed=_draft().model_dump(mode="json"),
        text=_draft().model_dump_json(),
    )

    result = _provider(client).generate(_retrieval_result())

    assert result == _draft()


def test_provider_passes_correction_feedback() -> None:
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        parsed=_draft(),
        text=_draft().model_dump_json(),
    )

    _provider(client).generate(
        _retrieval_result(),
        correction_feedback=("Citation is unknown.",),
    )

    assert "Citation is unknown" in (
        client.models.generate_content.call_args.kwargs["contents"]
    )


def test_provider_marks_quota_error_as_retryable() -> None:
    client = MagicMock()
    client.models.generate_content.side_effect = errors.APIError(
        429,
        {"error": {"message": "quota exceeded"}},
    )

    with pytest.raises(GroundedAnswerProviderError) as raised:
        _provider(client).generate(_retrieval_result())

    assert raised.value.retryable is True
    assert "HTTP 429" in str(raised.value)


def test_provider_rejects_missing_structured_content() -> None:
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(
        parsed=None,
        text=None,
    )

    with pytest.raises(GroundedAnswerProviderError) as raised:
        _provider(client).generate(_retrieval_result())

    assert raised.value.retryable is False
    assert "without returning" in str(raised.value)
