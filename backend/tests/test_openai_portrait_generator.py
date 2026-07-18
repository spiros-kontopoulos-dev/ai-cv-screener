"""Tests for the direct OpenAI portrait provider wrapper."""

from base64 import b64encode
from types import SimpleNamespace

import pytest

from app.portrait_generation import (
    OpenAIPortraitGenerator,
    PortraitProviderError,
)


class _FakeImages:
    """Record one images.generate request and return configured data."""

    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeOpenAI:
    """Minimal injected client matching the wrapper's used surface."""

    def __init__(self, response) -> None:
        self.images = _FakeImages(response)


def _provider(client: _FakeOpenAI) -> OpenAIPortraitGenerator:
    return OpenAIPortraitGenerator(
        api_key="unused",
        model="gpt-image-1",
        size="1024x1024",
        quality="medium",
        output_compression=85,
        timeout_seconds=180,
        client=client,
    )


def test_openai_portrait_provider_decodes_base64_and_sends_controls() -> None:
    """The wrapper requests one opaque WebP and returns decoded bytes."""

    raw_bytes = b"fake-image-data"
    client = _FakeOpenAI(
        SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=b64encode(raw_bytes).decode("ascii")
                )
            ]
        )
    )
    provider = _provider(client)

    result = provider.generate(
        "portrait prompt",
        candidate_id="candidate_001",
    )

    assert result == raw_bytes
    call = client.images.calls[0]
    assert call["model"] == "gpt-image-1"
    assert call["size"] == "1024x1024"
    assert call["quality"] == "medium"
    assert call["output_format"] == "webp"
    assert "response_format" not in call
    assert call["user"] == "candidate_001"


def test_openai_portrait_provider_rejects_invalid_base64() -> None:
    """Malformed provider payloads are retryable rather than persisted."""

    client = _FakeOpenAI(
        SimpleNamespace(
            data=[SimpleNamespace(b64_json="%%%invalid%%%")]
        )
    )
    provider = _provider(client)

    with pytest.raises(PortraitProviderError) as captured:
        provider.generate(
            "portrait prompt",
            candidate_id="candidate_001",
        )

    assert captured.value.retryable is True
    assert "invalid base64" in str(captured.value)
