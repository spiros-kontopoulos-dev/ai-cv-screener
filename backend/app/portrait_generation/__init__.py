"""Public interface for fictional candidate portrait generation."""

from .client import OpenAIPortraitGenerator, PortraitProviderError
from .coverage import (
    PortraitCoveragePlan,
    PortraitCoveragePlanError,
    load_portrait_coverage_plan,
    validate_portrait_coverage_against_profiles,
)
from .generation import (
    PortraitGenerationFailed,
    PortraitImageProvider,
    generate_portrait_with_retries,
)
from .images import (
    PortraitImageError,
    inspect_portrait_image,
    normalize_portrait_image,
)
from .models import (
    PortraitCollectionValidation,
    PortraitGenerationJob,
    PortraitGenerationResult,
    PortraitImageMetadata,
)
from .planning import (
    NORMALIZED_PORTRAIT_EXTENSION,
    PortraitGenerationPlanError,
    build_portrait_generation_jobs,
    select_portrait_generation_jobs,
)
from .prompting import build_portrait_prompt
from .validation import validate_portrait_collection

__all__ = [
    "NORMALIZED_PORTRAIT_EXTENSION",
    "OpenAIPortraitGenerator",
    "PortraitCoveragePlan",
    "PortraitCoveragePlanError",
    "PortraitCollectionValidation",
    "PortraitGenerationFailed",
    "PortraitGenerationJob",
    "PortraitGenerationPlanError",
    "PortraitGenerationResult",
    "PortraitImageError",
    "PortraitImageMetadata",
    "PortraitImageProvider",
    "PortraitProviderError",
    "build_portrait_generation_jobs",
    "build_portrait_prompt",
    "generate_portrait_with_retries",
    "inspect_portrait_image",
    "load_portrait_coverage_plan",
    "normalize_portrait_image",
    "select_portrait_generation_jobs",
    "validate_portrait_collection",
    "validate_portrait_coverage_against_profiles",
]
