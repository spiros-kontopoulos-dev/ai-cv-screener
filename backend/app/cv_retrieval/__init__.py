"""Public contracts for candidate-aware CV retrieval development."""

from app.cv_retrieval.assisted_retrieval import (
    AssistedCvRetriever,
    AssistedRetrievalConfig,
    CvAssistedRetrievalError,
    build_assisted_cv_retriever,
)
from app.cv_retrieval.candidate_ranking import (
    CandidateConditionMatch,
    CandidateCvRetrievalResult,
    CandidateEvidenceSelection,
    CandidateQueryCondition,
    RankedCvCandidate,
    build_candidate_conditions,
    rank_candidates,
)
from app.cv_retrieval.candidate_retrieval import (
    CandidateAwareCvRetriever,
    CandidateCvRetrievalQuery,
    CandidateRetrievalConfig,
    CvCandidateRetrievalError,
    build_candidate_aware_cv_retriever,
)
from app.cv_retrieval.evidence_analysis import (
    AssistedCvRetrievalResult,
    CvEvidenceScore,
    CvQueryEvidenceFeatures,
    NumericQueryConstraint,
    ScoredCvEvidenceHit,
    TextRelationConstraint,
    analyze_recruiter_question,
    normalize_search_text,
    score_evidence_text,
    semantic_relevance_from_distance,
)
from app.cv_retrieval.models import (
    CvRawRetrievalContractError,
    RawCvRetrievalConfig,
    RawCvRetrievalHit,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
)
from app.cv_retrieval.raw_retrieval import (
    CvRawRetrievalError,
    RawCvRetriever,
    build_raw_cv_retriever,
)

__all__ = [
    "AssistedCvRetrievalResult",
    "AssistedCvRetriever",
    "AssistedRetrievalConfig",
    "CandidateAwareCvRetriever",
    "CandidateConditionMatch",
    "CandidateCvRetrievalQuery",
    "CandidateCvRetrievalResult",
    "CandidateEvidenceSelection",
    "CandidateQueryCondition",
    "CandidateRetrievalConfig",
    "CvAssistedRetrievalError",
    "CvCandidateRetrievalError",
    "CvEvidenceScore",
    "CvQueryEvidenceFeatures",
    "CvRawRetrievalContractError",
    "CvRawRetrievalError",
    "NumericQueryConstraint",
    "RankedCvCandidate",
    "RawCvRetrievalConfig",
    "RawCvRetrievalHit",
    "RawCvRetrievalQuery",
    "RawCvRetrievalResult",
    "RawCvRetrievalSource",
    "RawCvRetriever",
    "ScoredCvEvidenceHit",
    "TextRelationConstraint",
    "analyze_recruiter_question",
    "build_assisted_cv_retriever",
    "build_candidate_aware_cv_retriever",
    "build_candidate_conditions",
    "build_raw_cv_retriever",
    "normalize_search_text",
    "rank_candidates",
    "score_evidence_text",
    "semantic_relevance_from_distance",
]
