"""Public contracts for grounded CV answer generation."""

from .client import GroundedAnswerProviderError, OpenAIGroundedAnswerProvider
from .gemini_client import GeminiGroundedAnswerProvider
from .generation import (
    GroundedAnswerGenerationConfig,
    GroundedAnswerGenerationFailed,
    GroundedAnswerGenerationResult,
    GroundedAnswerProvider,
    GroundedCvAnswerGenerator,
    build_grounded_cv_answer_generator,
    validate_grounded_answer_draft,
)
from .models import (
    GroundedAnswerDraft,
    GroundedAnswerOutcome,
    GroundedAnswerProviderName,
    GroundedAnswerResponse,
    GroundedAnswerSource,
    GroundedCandidateAnswer,
)
from .prompt import GROUNDED_ANSWER_INSTRUCTIONS, build_grounded_answer_prompt
from .provider_selection import (
    GroundedAnswerConfigurationError,
    ResolvedGroundedAnswerProvider,
    resolve_grounded_answer_provider,
)
from .sources import (
    build_grounded_answer_sources,
    build_source_id,
    default_candidate_citation_ids,
    validate_grounded_answer_citations,
)

__all__ = [
    "GROUNDED_ANSWER_INSTRUCTIONS",
    "GeminiGroundedAnswerProvider",
    "GroundedAnswerConfigurationError",
    "GroundedAnswerDraft",
    "GroundedAnswerGenerationConfig",
    "GroundedAnswerGenerationFailed",
    "GroundedAnswerGenerationResult",
    "GroundedAnswerOutcome",
    "GroundedAnswerProvider",
    "GroundedAnswerProviderError",
    "GroundedAnswerProviderName",
    "GroundedAnswerResponse",
    "GroundedAnswerSource",
    "GroundedCandidateAnswer",
    "GroundedCvAnswerGenerator",
    "OpenAIGroundedAnswerProvider",
    "ResolvedGroundedAnswerProvider",
    "build_grounded_answer_prompt",
    "build_grounded_answer_sources",
    "build_grounded_cv_answer_generator",
    "build_source_id",
    "default_candidate_citation_ids",
    "resolve_grounded_answer_provider",
    "validate_grounded_answer_citations",
    "validate_grounded_answer_draft",
]
