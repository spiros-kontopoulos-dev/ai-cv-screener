"""Public interface for fictional candidate generation.

The package follows this order:

1. Load one controlled slot from the dataset plan.
2. Build a focused prompt for that slot.
3. Ask OpenAI for a structured ``CandidateProfile``.
4. Normalise dates and experience in Python.
5. Check the profile against the slot and existing candidates.
6. Save only accepted profiles.

The separate modules keep provider calls, business rules, and file writing easy
to test and explain.
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
