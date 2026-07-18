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

# Field adds numeric boundaries to configuration values.
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

        app_name                         <- APP_NAME
        app_env                          <- APP_ENV
        openai_api_key                   <- OPENAI_API_KEY
        candidate_dataset_plan_path      <- CANDIDATE_DATASET_PLAN_PATH
        candidate_generation_max_retries <- CANDIDATE_GENERATION_MAX_RETRIES

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

    # The key is optional at this stage so that basic endpoints such as
    # /health and the candidate-plan dry run work before OpenAI is connected.
    #
    # SecretStr prevents the real value from appearing accidentally when
    # the Settings object is printed or included in logs.
    openai_api_key: SecretStr | None = None

    # WP3 candidate-generation configuration.
    #
    # The plan path identifies the deterministic JSON specification that
    # controls all 30 candidate slots. Path parsing is handled by Pydantic,
    # so developers may provide either a relative or absolute environment
    # value without adding conversion logic elsewhere.
    candidate_dataset_plan_path: Path = DEFAULT_CANDIDATE_DATASET_PLAN_PATH

    # A bounded retry count prevents one malformed LLM response from creating
    # an endless or unexpectedly expensive generation loop. Patch 01 only
    # displays this value; the OpenAI integration will use it next.
    candidate_generation_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )

    # model_config configures how BaseSettings handles incoming values.
    #
    # case_sensitive=False:
    # APP_NAME, app_name, and similar casing variations can be recognized.
    #
    # extra="ignore":
    # If the environment contains variables that are not defined above,
    # Pydantic ignores them instead of raising a validation error.
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Create and return the application's shared Settings object.

    The @lru_cache decorator remembers the first returned Settings instance.
    Future calls return that same object, avoiding repeated parsing and
    validation of the environment variables.
    """

    return Settings()
