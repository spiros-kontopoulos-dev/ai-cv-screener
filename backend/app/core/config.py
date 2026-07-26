"""Load all backend settings from environment variables.

The application uses one shared ``Settings`` object. Other modules ask for it
through ``get_settings()`` instead of reading environment variables directly.
This keeps paths, model names, limits, and API keys in one place.

The settings are grouped in the same order as the main application flow:

1. General application and provider keys.
2. Candidate and portrait data preparation.
3. PDF rendering and document ingestion.
4. Chunking, embeddings, and ChromaDB storage.
5. Candidate search and context limits.
6. Grounded answer generation.

Most values have safe defaults and can be changed in ``.env`` without editing
Python code. Secret values use ``SecretStr`` so they are hidden when printed.
"""

# ``get_settings`` is cached at the bottom of this file, so one Settings
# object is reused for the lifetime of the Python process.
from functools import lru_cache
from pathlib import Path
from typing import Literal

# ``Field`` validates limits such as minimum and maximum values.
# ``SecretStr`` keeps API keys hidden in logs and normal string output.
from pydantic import Field, SecretStr

# ``BaseSettings`` maps fields to environment variables automatically.
# ``SettingsConfigDict`` controls the loading rules.
from pydantic_settings import BaseSettings, SettingsConfigDict


# These committed JSON files live inside the backend package. Absolute default
# paths make them work no matter which directory started the Python process.
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
DEFAULT_CV_QUERY_ROBUSTNESS_MATRIX_PATH = (
    Path(__file__).resolve().parents[1]
    / "dataset"
    / "cv_query_robustness_matrix.json"
)


class Settings(BaseSettings):
    """Validated settings shared by the whole backend.

    Pydantic maps a field such as ``app_name`` to ``APP_NAME`` and converts the
    text value into the correct Python type. A field's default is used when the
    environment variable is missing.
    """

    # Basic application and browser connection settings.
    app_name: str = "AI CV Screener API"
    app_env: str = "development"
    log_level: str = "INFO"

    # The only browser origin allowed to call the local API.
    frontend_origin: str = "http://localhost:5173"

    # Provider keys are optional because deterministic answer mode, health
    # checks, and dry-run scripts can work without a hosted provider.
    openai_api_key: SecretStr | None = None
    # The Google SDK accepts both names. If both are set, GOOGLE_API_KEY wins.
    gemini_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Committed plans used to generate candidates, portraits, and query tests.
    candidate_dataset_plan_path: Path = DEFAULT_CANDIDATE_DATASET_PLAN_PATH
    candidate_portrait_plan_path: Path = DEFAULT_CANDIDATE_PORTRAIT_PLAN_PATH
    cv_query_robustness_matrix_path: Path = (
        DEFAULT_CV_QUERY_ROBUSTNESS_MATRIX_PATH
    )

    # Generated profile JSON is used to render CVs. It is not used as answer
    # evidence. Inside Docker, relative paths start from ``/app``.
    candidate_profiles_output_path: Path = Path(
        "data/candidate_profiles/candidate_profiles.json"
    )

    # Candidate IDs connect each profile to its portrait and rendered PDF.
    candidate_images_directory: Path = Path("data/candidate_images")
    cv_pdfs_output_directory: Path = Path("data/cv_pdfs")

    # ``--all`` scans this directory. Other ingestion commands can still point
    # to a different file or directory.
    cv_ingestion_default_directory: Path = Path("data/cv_pdfs")

    # Chunk size and overlap settings. The version is stored with every vector.
    # If the chunking rules change, the index must be rebuilt instead of mixing
    # old and new chunk formats.
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

    # One local Sentence Transformer embeds both CV chunks and user questions.
    # The default model is small enough to run on CPU and returns 384 numbers
    # for each piece of text.
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

    # ChromaDB stores the vectors created by this application. Collection
    # metadata records the model, vector size, chunking version, and index
    # version so incompatible data is rejected instead of mixed silently.
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

    # Search first retrieves a broad set of related chunks. Later steps add
    # exact evidence, group the chunks by candidate, and remove weak matches.
    # These limits control how much work each search stage may do.
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
    cv_candidate_retrieval_default_limit: int = Field(
        default=10,
        ge=1,
        le=30,
    )
    cv_candidate_retrieval_max_limit: int = Field(
        default=30,
        ge=1,
        le=100,
    )
    cv_candidate_retrieval_evidence_limit: int = Field(
        default=4,
        ge=1,
        le=8,
    )
    cv_candidate_retrieval_max_evidence_limit: int = Field(
        default=8,
        ge=1,
        le=20,
    )

    # Final result and context limits. The search keeps a larger candidate pool
    # at first, then applies score and coverage checks before building the small
    # evidence context sent to the answer generator.
    cv_final_retrieval_default_candidate_limit: int = Field(
        default=5,
        ge=1,
        le=10,
    )
    cv_final_retrieval_max_candidate_limit: int = Field(
        default=10,
        ge=1,
        le=30,
    )
    cv_final_retrieval_candidate_pool_limit: int = Field(
        default=15,
        ge=1,
        le=30,
    )
    cv_final_retrieval_candidate_evidence_pool_limit: int = Field(
        default=4,
        ge=1,
        le=8,
    )
    cv_final_retrieval_evidence_per_candidate_limit: int = Field(
        default=3,
        ge=1,
        le=8,
    )
    cv_final_retrieval_max_evidence_chunks: int = Field(
        default=12,
        ge=1,
        le=50,
    )
    cv_final_retrieval_max_context_characters: int = Field(
        default=7000,
        ge=500,
        le=50000,
    )
    cv_final_retrieval_max_evidence_characters: int = Field(
        default=900,
        ge=100,
        le=5000,
    )
    cv_final_retrieval_complete_min_score: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
    )
    cv_final_retrieval_partial_min_score: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
    )
    cv_final_retrieval_partial_min_coverage: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
    )

    # Answer generation receives only the evidence approved by candidate search.
    # ``auto`` uses Gemini when configured, then OpenAI, then the no-key
    # deterministic answer writer.
    cv_grounded_answer_provider: Literal[
        "auto",
        "openai",
        "gemini",
        "deterministic",
    ] = "auto"
    cv_grounded_answer_model: str = Field(
        default="gpt-5.4-mini",
        min_length=1,
        max_length=100,
    )
    cv_grounded_answer_gemini_model: str = Field(
        default="gemini-3.1-flash-lite",
        min_length=1,
        max_length=100,
    )
    cv_grounded_answer_max_retries: int = Field(
        default=1,
        ge=0,
        le=3,
    )
    cv_grounded_answer_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
    )
    cv_grounded_answer_max_completion_tokens: int = Field(
        default=3000,
        ge=500,
        le=8000,
    )
    cv_grounded_answer_max_answer_characters: int = Field(
        default=5000,
        ge=100,
        le=12000,
    )
    cv_grounded_answer_max_candidate_assessment_characters: int = Field(
        default=1800,
        ge=100,
        le=4000,
    )

    # HTML previews help developers inspect the CV layout. The searchable source
    # remains the rendered PDF, not the preview HTML.
    cv_html_preview_directory: Path = Path("data/cv_html")

    # Portrait generation is a developer tool, not a public API feature. These
    # settings control provider cost, image size, and retry behaviour.
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

    # Every generated image is cropped, resized, and saved again as WebP so the
    # renderer always receives the same format and dimensions.
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

    # Candidate-generation model settings.
    candidate_generation_model: str = Field(
        default="gpt-5.4-mini",
        min_length=1,
        max_length=100,
    )

    # Stop one invalid response from causing an endless paid retry loop.
    candidate_generation_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )

    # Fail slow provider calls clearly. The application, not the SDK, decides
    # whether another attempt should be made.
    candidate_generation_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
    )

    # Candidate profiles need more output space than chat answers, but the limit
    # still controls cost and prevents very long generated CV content.
    candidate_generation_max_completion_tokens: int = Field(
        default=6000,
        ge=1000,
        le=12000,
    )

    # Environment variable names are case-insensitive. Unknown values are ignored
    # so one shared .env file can also contain frontend settings.
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the one cached Settings object used by the application."""

    return Settings()
