"""Deterministic prompts for grounded CV answer generation."""

from collections.abc import Sequence
import json

from app.cv_retrieval import FinalCvRetrievalResult


GROUNDED_ANSWER_INSTRUCTIONS = """
You are the answer-generation layer of a CV screening system.

The application has already retrieved, verified, ranked, filtered, and budgeted
all evidence. Use only the supplied RETRIEVAL CONTEXT. Do not use outside knowledge,
assumptions, or facts remembered from training.

Required behavior:
- Preserve the retrieval outcome exactly: supported, partial, or unsupported.
- Include exactly the candidates listed in the candidate registry, in the same
  order. Never add, remove, merge, rename, or reorder candidates.
- Keep every candidate's facts separate. Never attribute one candidate's
  skills, history, language level, leadership, or education to another.
- Preserve candidate IDs, names, professional titles, and matched requirement
  labels exactly as supplied.
- Explain why each candidate matches using only the provided evidence.
- Do not infer missing years, seniority, proficiency, achievements, or skills.
- For a partial result, clearly state that no candidate has complete coverage
  and describe only the supported subset of requirements.
- For an unsupported result, return no candidates and say that the indexed CVs
  do not contain sufficiently supported evidence.
- Keep the overall answer concise and recruiter-friendly.
- Do not produce Markdown tables, source citations, filenames, page numbers, or
  chunk IDs in this patch. Citation formatting is handled by the next layer.
- Return only data conforming to the GroundedAnswerDraft schema.
""".strip()


def build_grounded_answer_prompt(
    retrieval_result: FinalCvRetrievalResult,
    *,
    correction_feedback: Sequence[str] = (),
) -> str:
    """Build one model prompt from the immutable final retrieval result."""

    candidate_registry = [
        {
            "candidate_id": candidate.candidate_id,
            "candidate_name": candidate.candidate_name or "Unknown candidate",
            "professional_title": (
                candidate.professional_title or "Unknown title"
            ),
            "support_level": candidate.support_level,
            "matched_requirements": list(
                candidate.matched_condition_labels
            ),
        }
        for candidate in retrieval_result.candidates
    ]

    sections = [
        "ORIGINAL RECRUITER QUESTION:",
        retrieval_result.query.text,
        "RETRIEVAL OUTCOME:",
        retrieval_result.outcome,
        "SUPPORT POLICY MESSAGE:",
        retrieval_result.support_message,
        "CANDIDATE REGISTRY (immutable):",
        json.dumps(candidate_registry, indent=2, ensure_ascii=False),
        "RETRIEVAL CONTEXT:",
        retrieval_result.context_text,
        (
            "Generate the final recruiter-facing explanation. The candidate "
            "registry is the authoritative identity and ordering contract."
        ),
    ]

    if correction_feedback:
        sections.extend(
            [
                "A previous structured draft failed these deterministic checks:",
                "\n".join(f"- {problem}" for problem in correction_feedback),
                (
                    "Return a complete corrected GroundedAnswerDraft. Change "
                    "only what is needed to satisfy these checks."
                ),
            ]
        )

    return "\n\n".join(sections)
