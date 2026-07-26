"""Build the instructions for one fictional candidate profile.

The dataset plan says which facts are fixed. This module turns one slot into a
focused prompt and keeps provider wording separate from generation logic.
Correction feedback can be added after a failed attempt without changing the
underlying slot.
"""

from collections.abc import Sequence

from .experience import extract_locked_experience_years
from .models import CandidateGenerationSlot


# These instructions apply to every candidate. The candidate-specific details
# are added by ``build_candidate_prompt`` below.
CANDIDATE_GENERATION_INSTRUCTIONS = """
You generate one realistic technology-sector CV profile as structured data.

Follow these rules:
- Treat every candidate-slot requirement as immutable.
- Generate a completely fictional identity and career history. Do not use real
  employers, schools, certification issuers, personal emails, or real people.
- Preserve the provided candidate ID, full name, professional title,
  profession, seniority, city, country, languages, and all required facts.
- Use an email address under example.com and a plausible fictional phone number.
- Keep the profile concise enough for a polished one-to-two-page CV.
- Use two to four work-experience entries with two to four concise highlights
  per role. Order work experience newest first.
- Use one current role at most. Do not create dates later than July 2026.
- Include every required skill in the skills list and support it with visible
  evidence in the summary, work highlights, work technologies, or projects.
- When a required certification, education entry, project, or leadership team
  size is provided, preserve it exactly and make it visible in the CV content.
- When no certification is required, return an empty certifications list.
- When no project is required, return an empty projects list.
- When no leadership team size is required, keep managed_team_size null in
  every role.
- Real technology and platform names such as Python, AWS, or Azure are
  allowed. Only people, employers, schools, certification issuers, and
  histories must be invented.
- Do not write words such as fake, fictional, synthetic, generated, or test in
  the candidate-facing profile content.
- Do not return Markdown or explanatory text. Return only data that conforms to
  the supplied CandidateProfile schema.
""".strip()


def build_candidate_prompt(
    slot: CandidateGenerationSlot,
    *,
    correction_feedback: Sequence[str] = (),
) -> str:
    """Build the user prompt for one slot and optional correction feedback.
    
    Only the selected candidate's requirements are included. Sending the complete
    30-candidate plan would waste tokens and increase the risk of mixing facts
    between candidates.
    """

    slot_json = slot.model_dump_json(indent=2)
    experience_instruction = _build_experience_instruction(slot)

    prompt_sections = [
        "Generate the candidate described by this controlled dataset slot:",
        slot_json,
        (
            "The known_facts entries describe evidence that must be represented "
            "naturally in visible CV fields. Preserve their meaning, but do not "
            "repeat wording such as 'fictional' in the candidate-facing text."
        ),
        experience_instruction,
    ]

    if correction_feedback:
        formatted_feedback = "\n".join(
            f"- {problem}" for problem in correction_feedback
        )
        prompt_sections.extend(
            [
                "A previous attempt failed these deterministic checks:",
                formatted_feedback,
                (
                    "Return a complete corrected CandidateProfile. Keep every "
                    "already-correct slot requirement unchanged. Python owns "
                    "experience arithmetic, so repair the requested dates or "
                    "wording rather than trying to estimate interval totals."
                ),
            ]
        )

    return "\n\n".join(prompt_sections)


def _build_experience_instruction(slot: CandidateGenerationSlot) -> str:
    """Explain whether experience is plan-locked or calculated later by Python."""

    locked_years = extract_locked_experience_years(slot)

    if locked_years is not None:
        return (
            f"This slot locks total experience at {locked_years:g} years. Set "
            "years_of_experience to that exact value and create a plausible "
            "ordered work history. Python will normalize the employment dates "
            "deterministically if their calendar duration is materially "
            "different. Exact experience wording in the summary must use the "
            "same locked value."
        )

    return (
        "This slot does not lock an exact experience total. Treat the "
        "years_of_experience field as provisional because Python will derive "
        "the final value from the employment dates. Do not state a numeric "
        "total such as '6 years of experience' in the summary; describe the "
        "candidate as experienced or mid-level instead."
    )
