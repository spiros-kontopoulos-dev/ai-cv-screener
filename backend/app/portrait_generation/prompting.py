"""Deterministic prompts for realistic, fictional professional headshots."""

from app.schemas import CandidateProfile, SeniorityLevel


_BACKGROUNDS = (
    "a softly blurred neutral grey studio background",
    "a softly blurred warm beige office background",
    "a softly blurred cool blue-grey studio background",
    "a softly blurred modern office background with no visible branding",
    "a softly blurred pale stone background",
    "a softly blurred muted green-grey studio background",
)

_WARDROBES = (
    "a tailored dark blazer over a plain light shirt",
    "a smart navy jacket over a plain neutral top",
    "a modern business-casual shirt with no pattern or logo",
    "a charcoal blazer over a simple crew-neck top",
    "a professional light blouse or shirt with a dark jacket",
    "a refined business-casual outfit in muted colours",
)

_LIGHTING = (
    "soft window-style key lighting with natural shadows",
    "balanced studio lighting with gentle facial contrast",
    "soft diffused daylight with realistic skin texture",
    "clean editorial lighting with subtle depth and no glamour effect",
)

_EXPRESSIONS = (
    "a calm, approachable expression with a slight natural smile",
    "a confident, friendly expression with relaxed eyes",
    "a composed professional expression with a subtle smile",
    "a warm, credible expression suitable for a CV profile",
)

_POSES = (
    "facing the camera directly with shoulders slightly angled",
    "a slight three-quarter turn while maintaining eye contact",
    "facing the camera with a relaxed upright posture",
    "a subtle three-quarter pose with the face clearly visible",
)


def build_portrait_prompt(profile: CandidateProfile) -> str:
    """Create one controlled portrait prompt from validated profile facts.

    The prompt uses candidate identity only to keep the rendered artifact
    coherent. It never asks the model to copy a real person, public figure, or
    reference photograph. Stable candidate-ID variation keeps the collection
    visually diverse without maintaining another 30-entry data file.
    """

    variation_index = _candidate_number(profile.candidate_id) - 1
    age_description = _age_description(profile)

    return (
        "Create one photorealistic professional CV headshot of a completely "
        "fictional adult. The fictional candidate is named "
        f"{profile.full_name} and works as a {profile.professional_title} "
        f"based in {profile.contact.city}, {profile.contact.country}. "
        f"Portray an adult professional in the {age_description}. "
        f"Use {_WARDROBES[variation_index % len(_WARDROBES)]}, "
        f"{_BACKGROUNDS[variation_index % len(_BACKGROUNDS)]}, "
        f"{_LIGHTING[variation_index % len(_LIGHTING)]}, and "
        f"{_EXPRESSIONS[variation_index % len(_EXPRESSIONS)]}. The subject is "
        f"{_POSES[variation_index % len(_POSES)]}. Frame the image as a "
        "head-and-shoulders portrait with the full head visible, comfortable "
        "space above the hair, and the eyes near the upper third. Use realistic "
        "skin texture, natural facial asymmetry, and restrained professional "
        "retouching. The appearance should feel plausible within a diverse "
        "European workforce without stereotyping nationality. Produce one "
        "person only. Do not depict or imitate any real person, celebrity, or "
        "public figure. No text, letters, logos, badges, watermarks, company "
        "marks, dramatic props, hands near the face, full-body framing, or "
        "illustration style. Square composition, photographic realism, clean "
        "professional CV aesthetic."
    )


def _candidate_number(candidate_id: str) -> int:
    """Return the numeric portion of a validated candidate identifier."""

    return int(candidate_id.rsplit("_", maxsplit=1)[1])


def _age_description(profile: CandidateProfile) -> str:
    """Return a broad adult age range consistent with career seniority."""

    if profile.seniority == SeniorityLevel.JUNIOR:
        return "mid-to-late twenties age range"

    if profile.seniority == SeniorityLevel.MID:
        return "late twenties to late thirties age range"

    if profile.years_of_experience >= 10:
        return "late thirties to late forties age range"

    return "mid-thirties to early-forties age range"
