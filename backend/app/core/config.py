"""
Central application configuration.

This module defines the settings that the backend reads from environment
variables. Keeping configuration here prevents values such as API keys,
environment names, and file paths from being hard-coded throughout the
application.
"""

# lru_cache stores the result returned by get_settings().
# This means the Settings object is created only once per Python process
# instead of being recreated every time another module requests it.
from functools import lru_cache
from pathlib import Path

# Field adds numeric and text boundaries to configuration values.
# SecretStr is a Pydantic type designed for sensitive values. When printed,
# it hides the actual secret instead of displaying it directly.
from pydantic import Field, SecretStr

# BaseSettings automatically reads matching values from environment variables.
# SettingsConfigDict controls how that environment-variable loading behaves.
from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve the committed plan relative to the backend package, not the shell's
# current working directory. Developers may still override it through the
# CANDIDATE_DATASET_PLAN_PATH environment variable.
DEFAULT_CANDIDATE_DATASET_PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "dataset"
    / "candidate_dataset_plan.json"
)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    BaseSettings matches each Python field with an environment variable.
    For example:

        app_name <- APP_NAME
        openai_api_key <- OPENAI_API_KEY
        candidate_generation_model <- CANDIDATE_GENERATION_MODEL

    The default values are used when the corresponding environment variable
    has not been provided.
    """

    # General application configuration.
    app_name: str = "AI CV Screener API"
    app_env: str = "development"
    log_level: str = "INFO"

    # The browser origin that will later be allowed to call the backend.
    # This value will be used when we configure CORS.
    frontend_origin: str = "http://localhost:5173"

    # The key remains optional so health checks and dry-run plan inspection can
    # work before OpenAI is configured. Real generation validates it explicitly.
    openai_api_key: SecretStr | None = None

    # WP3 candidate-generation configuration.
    candidate_dataset_plan_path: Path = DEFAULT_CANDIDATE_DATASET_PLAN_PATH

    # The generated profile collection is preparation data for WP4 PDF
    # rendering. A relative path resolves from /app inside the backend
    # container, where Compose mounts the repository's shared data directory.
    candidate_profiles_output_path: Path = Path(
        "data/candidate_profiles/candidate_profiles.json"
    )

    # The model is configurable because model availability and cost choices may
    # change without requiring a code edit.
    candidate_generation_model: str = Field(
        default="gpt-5.4-mini",
        min_length=1,
        max_length=100,
    )

    # A bounded retry count prevents one malformed response from creating an
    # endless or unexpectedly expensive generation loop.
    candidate_generation_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )

    # Provider calls should fail clearly rather than relying on the SDK's much
    # longer default timeout. The application-level retry loop owns retries.
    candidate_generation_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
    )

    # A complete profile can be larger than a short chat response. The limit is
    # still bounded to control cost and avoid unexpectedly verbose CV content.
    candidate_generation_max_completion_tokens: int = Field(
        default=6000,
        ge=1000,
        le=12000,
    )

    # model_config configures how BaseSettings handles incoming values.
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Create and return the application's shared Settings object."""

    return Settings()
