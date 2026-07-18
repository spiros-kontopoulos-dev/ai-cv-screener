"""Controlled synthetic candidate generation domain.

The package is divided by responsibility: plan models and loading, prompt
construction, provider integration, deterministic compliance and uniqueness
checks, bounded generation, and safe profile persistence.
"""

from .client import CandidateProviderError, OpenAICandidateGenerator
from .compliance import validate_profile_against_slot
from .dataset_validation import (
    CandidateDatasetValidationReport,
    validate_candidate_dataset,
)
from .experience import (
    CandidateExperienceNormalizationError,
    calculate_employment_years,
    calculate_non_overlapping_employment_months,
    extract_locked_experience_years,
    normalize_profile_experience,
)
from .generation import (
    CandidateGenerationFailed,
    CandidateGenerationResult,
    CandidateProfileProvider,
    generate_candidate_with_retries,
)
from .models import CandidateDatasetPlan, CandidateGenerationSlot
from .persistence import (
    CandidateProfilesFileError,
    load_candidate_profiles,
    save_candidate_profiles,
)
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
from .uniqueness import (
    CandidateUniquenessError,
    find_profile_uniqueness_problems,
    validate_profile_uniqueness,
)

__all__ = [
    "CANDIDATE_GENERATION_INSTRUCTIONS",
    "CandidateExperienceNormalizationError",
    "CandidateDatasetPlan",
    "CandidateDatasetValidationReport",
    "CandidateGenerationFailed",
    "CandidateGenerationResult",
    "CandidateGenerationSlot",
    "CandidatePlanError",
    "CandidateProfileProvider",
    "CandidateProfilesFileError",
    "CandidateProviderError",
    "CandidateSelectionError",
    "CandidateUniquenessError",
    "OpenAICandidateGenerator",
    "build_candidate_prompt",
    "calculate_employment_years",
    "calculate_non_overlapping_employment_months",
    "extract_locked_experience_years",
    "find_profile_uniqueness_problems",
    "generate_candidate_with_retries",
    "load_candidate_dataset_plan",
    "load_candidate_profiles",
    "normalize_profile_experience",
    "save_candidate_profiles",
    "select_candidate_slots",
    "validate_candidate_dataset",
    "validate_profile_against_slot",
    "validate_profile_uniqueness",
]
