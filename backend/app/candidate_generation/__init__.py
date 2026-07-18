"""Controlled synthetic candidate generation domain.

The package is divided by responsibility: plan models and loading, prompt
construction, provider integration, deterministic compliance checks, and the
bounded generation orchestrator.
"""

from .client import CandidateProviderError, OpenAICandidateGenerator
from .compliance import validate_profile_against_slot
from .generation import (
    CandidateGenerationFailed,
    CandidateGenerationResult,
    CandidateProfileProvider,
    generate_candidate_with_retries,
)
from .models import CandidateDatasetPlan, CandidateGenerationSlot
from .plan import (
    CandidatePlanError,
    CandidateSelectionError,
    load_candidate_dataset_plan,
    select_candidate_slots,
)
from .prompt import (
    CANDIDATE_GENERATION_INSTRUCTIONS,
    build_candidate_prompt,
)

__all__ = [
    "CANDIDATE_GENERATION_INSTRUCTIONS",
    "CandidateDatasetPlan",
    "CandidateGenerationFailed",
    "CandidateGenerationResult",
    "CandidateGenerationSlot",
    "CandidatePlanError",
    "CandidateProfileProvider",
    "CandidateProviderError",
    "CandidateSelectionError",
    "OpenAICandidateGenerator",
    "build_candidate_prompt",
    "generate_candidate_with_retries",
    "load_candidate_dataset_plan",
    "select_candidate_slots",
    "validate_profile_against_slot",
]
