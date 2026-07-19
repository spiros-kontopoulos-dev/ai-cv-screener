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
from typing import Literal

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
DEFAULT_CANDIDATE_PORTRAIT_PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "dataset"
    / "candidate_portrait_plan.json"
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
    candidate_portrait_plan_path: Path = DEFAULT_CANDIDATE_PORTRAIT_PLAN_PATH

    # The generated profile collection is preparation data for WP4 PDF
    # rendering. A relative path resolves from /app inside the backend
    # container, where Compose mounts the repository's shared data directory.
    candidate_profiles_output_path: Path = Path(
        "data/candidate_profiles/candidate_profiles.json"
    )

    # WP4 keeps visual assets in shared repository directories mounted at
    # /app/data by Compose.  Candidate IDs provide the stable mapping between
    # one validated profile, normalized portrait, HTML preview, and PDF file.
    candidate_images_directory: Path = Path("data/candidate_images")
    cv_pdfs_output_directory: Path = Path("data/cv_pdfs")

    # WP5 accepts arbitrary PDF paths, but --all needs one explicit default
    # directory. Keeping this separate from the WP4 output setting makes the
    # ingestion service reusable for future upload or administrator folders.
    cv_ingestion_default_directory: Path = Path("data/cv_pdfs")

    # WP5 section-aware chunking remains configurable without coupling the
    # algorithm to the committed synthetic CV layout. The version is stored
    # with every future vector record so an incompatible strategy change can
    # trigger an explicit rebuild rather than silently mixing chunk formats.
    cv_chunking_version: str = Field(
        default="cv-sections-v1",
        min_length=1,
        max_length=100,
    )
    cv_chunk_max_characters: int = Field(
        default=1200,
        ge=200,
        le=5000,
    )
    cv_chunk_min_characters: int = Field(
        default=80,
        ge=1,
        le=2000,
    )
    cv_chunk_overlap_characters: int = Field(
        default=120,
        ge=0,
        le=1000,
    )

    # WP5 uses one local Sentence Transformer for both document chunks and
    # later user questions. The selected MiniLM model is compact enough for a
    # CPU-only evaluator while producing 384-dimensional semantic vectors.
    cv_embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        min_length=1,
        max_length=200,
    )
    cv_embedding_expected_dimension: int = Field(
        default=384,
        ge=1,
        le=8192,
    )
    cv_embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=512,
    )
    cv_embedding_normalize: bool = True
    cv_embedding_device: str = Field(
        default="cpu",
        min_length=1,
        max_length=50,
    )
    cv_embedding_cache_directory: Path = Path("storage/models")

    # Chroma stores vectors supplied by our own embedding provider. Collection
    # metadata records every compatibility boundary so a changed model, vector
    # dimension, chunking strategy, or index version cannot be mixed silently.
    cv_vector_store_directory: Path = Path("storage/chroma")
    cv_vector_collection_name: str = Field(
        default="cv_chunks",
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    cv_vector_index_version: str = Field(
        default="cv-index-v1",
        min_length=1,
        max_length=100,
    )
    cv_vector_distance_metric: Literal["cosine", "l2", "ip"] = "cosine"
    cv_vector_upsert_batch_size: int = Field(
        default=100,
        ge=1,
        le=5000,
    )

    # WP6 begins with broad semantic recall and bounded exact-text assistance.
    # Candidate grouping, balancing, and final context budgeting remain later
    # retrieval stages.
    cv_raw_retrieval_default_limit: int = Field(
        default=50,
        ge=1,
        le=200,
    )
    cv_raw_retrieval_max_limit: int = Field(
        default=200,
        ge=1,
        le=500,
    )
    cv_retrieval_max_question_characters: int = Field(
        default=2000,
        ge=1,
        le=10000,
    )
    cv_assisted_retrieval_max_supplemental_hits: int = Field(
        default=50,
        ge=0,
        le=500,
    )

    # HTML previews are developer-only inspection artifacts.  They make CSS
    # iteration faster but are not the source indexed by the future RAG system.
    cv_html_preview_directory: Path = Path("data/cv_html")

    # WP4 portrait generation remains a developer-only dataset preparation
    # workflow. The model and quality controls are configurable so a reviewer
    # can trade cost against visual quality without editing application code.
    portrait_generation_model: str = Field(
        default="gpt-image-1",
        min_length=1,
        max_length=100,
    )
    portrait_generation_size: Literal[
        "1024x1024",
        "1024x1536",
        "1536x1024",
    ] = "1024x1024"
    portrait_generation_quality: Literal[
        "low",
        "medium",
        "high",
        "auto",
    ] = "medium"
    portrait_generation_output_compression: int = Field(
        default=85,
        ge=0,
        le=100,
    )
    portrait_generation_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )
    portrait_generation_timeout_seconds: float = Field(
        default=180.0,
        ge=10.0,
        le=600.0,
    )

    # Every accepted provider image is decoded, centre-cropped, resized, and
    # re-encoded locally. This gives the renderer one predictable WebP asset
    # shape regardless of provider metadata or future model changes.
    portrait_normalized_size: int = Field(
        default=512,
        ge=256,
        le=1024,
    )
    portrait_webp_quality: int = Field(
        default=88,
        ge=60,
        le=100,
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
