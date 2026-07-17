"""
Central application configuration.

This module defines the settings that the backend reads from environment
variables. Keeping configuration here prevents values such as API keys,
environment names, and frontend URLs from being hard-coded throughout
the application.
"""

# lru_cache stores the result returned by get_settings().
# This means the Settings object is created only once per Python process
# instead of being recreated every time another module requests it.
from functools import lru_cache

# SecretStr is a Pydantic type designed for sensitive values.
# When printed, it hides the actual secret instead of displaying it directly.
from pydantic import SecretStr

# BaseSettings automatically reads matching values from environment variables.
# SettingsConfigDict controls how that environment-variable loading behaves.
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    BaseSettings matches each Python field with an environment variable.
    For example:

        app_name          <- APP_NAME
        app_env           <- APP_ENV
        openai_api_key    <- OPENAI_API_KEY

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
    # /health can run even before an OpenAI key has been configured.
    #
    # SecretStr prevents the real value from appearing accidentally when
    # the Settings object is printed or included in logs.
    openai_api_key: SecretStr | None = None

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