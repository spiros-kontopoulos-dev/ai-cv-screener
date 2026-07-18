"""Direct OpenAI image-generation client for fictional CV portraits."""

from base64 import b64decode
from binascii import Error as Base64DecodeError

import openai
from openai import OpenAI


class PortraitProviderError(RuntimeError):
    """A provider failure with explicit retry guidance."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class OpenAIPortraitGenerator:
    """Generate one base64-backed portrait through the OpenAI Images API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        size: str,
        quality: str,
        output_compression: int,
        timeout_seconds: float,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._size = size
        self._quality = quality
        self._output_compression = output_compression
        self._client = client or OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    def generate(self, prompt: str, *, candidate_id: str) -> bytes:
        """Return decoded image bytes for one fictional candidate portrait."""

        try:
            response = self._client.images.generate(
                model=self._model,
                prompt=prompt,
                n=1,
                size=self._size,
                quality=self._quality,
                background="opaque",
                output_format="webp",
                output_compression=self._output_compression,
                user=candidate_id,
            )
        except openai.APIConnectionError as error:
            raise PortraitProviderError(
                "The OpenAI image API could not be reached or timed out.",
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
            provider_message = str(error).strip()
            message_suffix = (
                f" Provider message: {provider_message}"
                if provider_message
                else ""
            )
            raise PortraitProviderError(
                f"OpenAI returned HTTP {error.status_code}."
                f"{message_suffix}{request_suffix}",
                retryable=retryable,
            ) from error
        except openai.APIError as error:
            raise PortraitProviderError(
                "OpenAI rejected the portrait-generation request.",
                retryable=False,
            ) from error

        response_data = response.data or []
        if len(response_data) != 1 or not response_data[0].b64_json:
            raise PortraitProviderError(
                "OpenAI returned no usable portrait image data.",
                retryable=True,
            )

        try:
            image_bytes = b64decode(
                response_data[0].b64_json,
                validate=True,
            )
        except (Base64DecodeError, ValueError) as error:
            raise PortraitProviderError(
                "OpenAI returned invalid base64 portrait data.",
                retryable=True,
            ) from error

        if not image_bytes:
            raise PortraitProviderError(
                "OpenAI returned an empty portrait image.",
                retryable=True,
            )

        return image_bytes
