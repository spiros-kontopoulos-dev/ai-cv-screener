"""Deterministic prompts for clean, fictional professional headshots."""

from app.schemas import CandidateProfile, SeniorityLevel

from .coverage import PortraitAppearance


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

_DEFAULT_APPEARANCE = PortraitAppearance(
    candidate_id="candidate_001",
    presentation="androgynous-presenting",
    visual_description=(
        "short dark-brown hair, an oval face, and no visible eyewear"
    ),
)


def build_portrait_prompt(
    profile: CandidateProfile,
    *,
    appearance: PortraitAppearance | None = None,
) -> str:
    """Create one controlled prompt for a clean fictional portrait.

    Candidate names, job titles, and locations are intentionally excluded from
    the provider prompt. Those values do not determine a person's appearance,
    and image models may incorrectly turn identity text into captions,
    nameplates, or profile-card layouts. Instead, the committed portrait plan
    provides an explicit fictional presentation and visual descriptor for each
    selected candidate.
    """

    variation_index = _candidate_number(profile.candidate_id) - 1
    age_description = _age_description(profile)
    active_appearance = appearance or _DEFAULT_APPEARANCE.model_copy(
        update={"candidate_id": profile.candidate_id}
    )

    return (
        "Generate only one clean, borderless, square photographic portrait. "
        "The photograph must fill the entire canvas from edge to edge. Output "
        "only the portrait photograph itself, with no surrounding document or "
        "graphic layout. Create one photorealistic head-and-shoulders portrait "
        "of a completely fictional adult professional in the "
        f"{age_description}. The subject must be clearly "
        f"{active_appearance.presentation}. Give the fictional subject "
        f"{active_appearance.visual_description}. Use "
        f"{_WARDROBES[variation_index % len(_WARDROBES)]}, "
        f"{_BACKGROUNDS[variation_index % len(_BACKGROUNDS)]}, "
        f"{_LIGHTING[variation_index % len(_LIGHTING)]}, and "
        f"{_EXPRESSIONS[variation_index % len(_EXPRESSIONS)]}. The subject is "
        f"{_POSES[variation_index % len(_POSES)]}. Frame the image as a "
        "professional head-and-shoulders photograph with the full head visible, "
        "comfortable space above the hair, and the eyes near the upper third. "
        "Use realistic skin texture, natural facial asymmetry, restrained "
        "professional retouching, and a plausible diverse European workforce "
        "appearance without stereotyping nationality. The face must be newly "
        "generated and visually distinct from generic repeated stock-photo "
        "faces. Produce exactly one person. Do not depict or imitate any real "
        "person, celebrity, or public figure. Do not create a CV, resume, "
        "profile card, ID card, business card, poster, social-media profile, "
        "composite, badge, nameplate, lower third, caption strip, banner, footer, "
        "border, frame, or white text panel. Do not include any text, letters, "
        "words, captions, names, job titles, numbers, symbols, logos, watermarks, "
        "signatures, labels, or typography anywhere in the image, background, "
        "clothing, or accessories. No dramatic props, hands near the face, "
        "full-body framing, illustration, painting, or cartoon style. Return "
        "only the uninterrupted photograph, with photographic content extending "
        "to every edge of the square canvas."
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
