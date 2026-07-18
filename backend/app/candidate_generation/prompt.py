"""Prompt construction for one controlled fictional candidate profile.

The dataset plan decides *what* each candidate must contain. This module turns
one deterministic plan slot into the focused instructions sent to the LLM.
Keeping prompt construction separate makes it easy to inspect, test, and tune
without mixing provider calls or validation logic into the prompt text.
"""

from collections.abc import Sequence

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
- Make the employment dates consistent with years_of_experience. The visible
  non-overlapping work history should cover approximately the declared total.
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
    """Build the user prompt for one candidate-generation attempt.

    ``correction_feedback`` is empty on the first attempt. After a structurally
    valid response fails deterministic slot checks, the retry loop passes the
    exact validation problems back to the model so it can repair only the
    conflicting details.
    """

    slot_json = slot.model_dump_json(indent=2)

    prompt_sections = [
        "Generate the candidate described by this controlled dataset slot:",
        slot_json,
        (
            "The known_facts entries describe evidence that must be represented "
            "naturally in visible CV fields. Preserve their meaning, but do not "
            "repeat wording such as 'fictional' in the candidate-facing text."
        ),
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
                    "already-correct slot requirement unchanged."
                ),
            ]
        )

    return "\n\n".join(prompt_sections)
