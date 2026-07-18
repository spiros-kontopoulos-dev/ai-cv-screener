"""Controlled synthetic candidate generation domain.

The package grows by responsibility: typed plan models and loading first,
then prompt construction, OpenAI integration, validation, and persistence.
"""

from .models import CandidateDatasetPlan, CandidateGenerationSlot
from .plan import (
    CandidatePlanError,
    CandidateSelectionError,
    load_candidate_dataset_plan,
    select_candidate_slots,
)

__all__ = [
    "CandidateDatasetPlan",
    "CandidateGenerationSlot",
    "CandidatePlanError",
    "CandidateSelectionError",
    "load_candidate_dataset_plan",
    "select_candidate_slots",
]
