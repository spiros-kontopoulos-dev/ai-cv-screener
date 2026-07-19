"""Deterministic prompts for grounded CV answer generation."""

from collections.abc import Sequence
import json

from app.cv_retrieval import FinalCvRetrievalResult

from .sources import build_grounded_answer_sources


GROUNDED_ANSWER_INSTRUCTIONS = """
You are the answer-generation layer of a CV screening system.

The application has already retrieved, verified, ranked, filtered, and budgeted
all evidence. Use only the supplied RETRIEVAL CONTEXT and SOURCE REGISTRY. Do not
Do not use outside knowledge, assumptions, or facts remembered from training.

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
- Cite only source_id values from the SOURCE REGISTRY.
- Each candidate assessment must cite source IDs belonging to that candidate.
- Candidate citations must collectively support every matched requirement.
- The overall answer must cite at least one source for every returned candidate.
- For a partial result, clearly state that no candidate has complete coverage
  and describe only the supported subset of requirements.
- For an unsupported result, return no candidates, no citations, and say that
  the indexed CVs do not contain sufficiently supported evidence.
- Keep the overall answer concise and recruiter-friendly.
- Do not produce Markdown tables or invent citation formatting. Return source
  IDs in the schema fields; the application formats readable sources later.
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
    source_registry = [
        source.model_dump(exclude={"evidence_excerpt"})
        for source in build_grounded_answer_sources(retrieval_result)
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
        "SOURCE REGISTRY (immutable citation IDs):",
        json.dumps(source_registry, indent=2, ensure_ascii=False),
        "RETRIEVAL CONTEXT:",
        retrieval_result.context_text,
        (
            "Generate the final recruiter-facing explanation. Candidate and "
            "source registries are the authoritative identity, ordering, and "
            "citation contracts."
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
