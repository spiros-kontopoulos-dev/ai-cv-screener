"""Public contracts for grounded CV answer generation."""

from .client import GroundedAnswerProviderError, OpenAIGroundedAnswerProvider
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
    GroundedCandidateAnswer,
)
from .prompt import GROUNDED_ANSWER_INSTRUCTIONS, build_grounded_answer_prompt

__all__ = [
    "GROUNDED_ANSWER_INSTRUCTIONS",
    "GroundedAnswerDraft",
    "GroundedAnswerGenerationConfig",
    "GroundedAnswerGenerationFailed",
    "GroundedAnswerGenerationResult",
    "GroundedAnswerOutcome",
    "GroundedAnswerProvider",
    "GroundedAnswerProviderError",
    "GroundedCandidateAnswer",
    "GroundedCvAnswerGenerator",
    "OpenAIGroundedAnswerProvider",
    "build_grounded_answer_prompt",
    "build_grounded_cv_answer_generator",
    "validate_grounded_answer_draft",
]
