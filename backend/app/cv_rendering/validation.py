"""Validate the final PDF CV collection against its rendering contract.

The structured candidate profiles remain preparation data.  This module opens
only the generated PDF artifacts with PyMuPDF, extracts their text, and checks
that every profile field intended for the CV survived the complete rendering
boundary.  Curated search scenarios are then validated against that extracted
PDF text rather than against the original JSON.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re

import pymupdf

from app.candidate_generation.models import CandidateDatasetPlan, SearchScenario
from app.schemas import CandidateProfile

from .formatting import (
    format_education_year_range,
    format_language_proficiency,
    format_seniority,
    format_skill_years,
    format_work_date_range,
    format_years_of_experience,
    humanize_identifier,
)


# Unsupported scenarios intentionally expect no source evidence.  The same
# explicit phrase boundary used by the profile validator is repeated here so
# the final check proves that unsupported information did not enter the PDFs.
_UNSUPPORTED_SCENARIO_PHRASES: dict[str, tuple[str, ...]] = {
    "unsupported_security_clearance": ("security clearance",),
}


class CvPdfValidationError(RuntimeError):
    """Raised when one PDF cannot be opened or text cannot be extracted."""


@dataclass(frozen=True, slots=True)
class CvFactExpectation:
    """One human-readable profile fact expected in a rendered PDF."""

    label: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ExtractedCvDocument:
    """Text and metadata extracted from one candidate PDF."""

    candidate_id: str
    path: Path
    page_count: int
    text: str

    @property
    def text_character_count(self) -> int:
        """Return the number of non-whitespace extracted characters."""

        return len("".join(self.text.split()))


@dataclass(frozen=True, slots=True)
class CandidateCvValidation:
    """Validation result for one expected candidate PDF."""

    candidate_id: str
    path: Path
    page_count: int
    extracted_text_characters: int
    expected_fact_count: int
    validated_fact_count: int
    missing_facts: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return True when structural and fact checks passed."""

        return not self.missing_facts


@dataclass(frozen=True, slots=True)
class CvPdfCollectionValidationReport:
    """Complete integrity report for the committed PDF collection."""

    expected_pdf_count: int
    actual_pdf_count: int
    validated_pdf_count: int
    expected_fact_count: int
    validated_fact_count: int
    total_scenario_count: int
    validated_scenario_count: int
    missing_pdf_names: tuple[str, ...]
    unexpected_pdf_names: tuple[str, ...]
    candidate_results: tuple[CandidateCvValidation, ...]
    issues: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return True only when every PDF and scenario check passed."""

        return not self.issues


def extract_cv_pdf(path: Path, *, candidate_id: str) -> ExtractedCvDocument:
    """Open one PDF and extract page-sorted text with PyMuPDF."""

    if not path.is_file():
        raise CvPdfValidationError(f"CV PDF does not exist: {path}")

    try:
        with pymupdf.open(path) as document:
            page_count = document.page_count
            text = "\n".join(
                page.get_text("text", sort=True)
                for page in document
            )
    except (pymupdf.FileDataError, RuntimeError, OSError, ValueError) as error:
        raise CvPdfValidationError(
            f"CV PDF could not be opened or read: {path}"
        ) from error

    return ExtractedCvDocument(
        candidate_id=candidate_id,
        path=path,
        page_count=page_count,
        text=text,
    )


def build_profile_fact_expectations(
    profile: CandidateProfile,
) -> tuple[CvFactExpectation, ...]:
    """Return every profile fact intentionally rendered as visible CV text."""

    facts: list[CvFactExpectation] = [
        CvFactExpectation("candidate ID", profile.candidate_id),
        CvFactExpectation("full name", profile.full_name),
        CvFactExpectation("professional title", profile.professional_title),
        CvFactExpectation(
            "profession",
            humanize_identifier(profile.profession.value),
        ),
        CvFactExpectation(
            "seniority",
            format_seniority(profile.seniority.value),
        ),
        CvFactExpectation(
            "total experience",
            f"{format_years_of_experience(profile.years_of_experience)} experience",
        ),
        CvFactExpectation("email", str(profile.contact.email)),
        CvFactExpectation("phone", profile.contact.phone),
        CvFactExpectation("city", profile.contact.city),
        CvFactExpectation("country", profile.contact.country),
        CvFactExpectation("professional summary", profile.summary),
    ]

    for role_index, role in enumerate(profile.work_experience, start=1):
        prefix = f"work experience {role_index}"
        facts.extend(
            [
                CvFactExpectation(f"{prefix} job title", role.job_title),
                CvFactExpectation(f"{prefix} company", role.company),
                CvFactExpectation(
                    f"{prefix} date range",
                    format_work_date_range(role.start_date, role.end_date),
                ),
            ]
        )
        if role.location:
            facts.append(
                CvFactExpectation(f"{prefix} location", role.location)
            )
        for highlight_index, highlight in enumerate(role.highlights, start=1):
            facts.append(
                CvFactExpectation(
                    f"{prefix} highlight {highlight_index}",
                    highlight,
                )
            )
        for technology in role.technologies:
            facts.append(
                CvFactExpectation(
                    f"{prefix} technology {technology}",
                    technology,
                )
            )
        if role.managed_team_size is not None:
            facts.append(
                CvFactExpectation(
                    f"{prefix} managed team size",
                    f"managed {role.managed_team_size} people",
                )
            )

    for skill in profile.skills:
        facts.append(CvFactExpectation(f"skill {skill.name}", skill.name))
        rendered_years = format_skill_years(skill.years_of_experience)
        if rendered_years is not None:
            facts.append(
                CvFactExpectation(
                    f"skill duration {skill.name}",
                    f"{skill.name} {rendered_years}",
                )
            )

    for language in profile.languages:
        proficiency = format_language_proficiency(language.proficiency.value)
        facts.append(
            CvFactExpectation(
                f"language {language.name}",
                f"{language.name} {proficiency}",
            )
        )

    for education_index, education in enumerate(profile.education, start=1):
        prefix = f"education {education_index}"
        facts.extend(
            [
                CvFactExpectation(
                    f"{prefix} qualification",
                    f"{education.degree} in {education.field_of_study}",
                ),
                CvFactExpectation(
                    f"{prefix} institution",
                    education.institution,
                ),
                CvFactExpectation(
                    f"{prefix} date range",
                    format_education_year_range(
                        education.start_year,
                        education.end_year,
                    ),
                ),
            ]
        )
        if education.location:
            facts.append(
                CvFactExpectation(f"{prefix} location", education.location)
            )

    for certification_index, certification in enumerate(
        profile.certifications,
        start=1,
    ):
        prefix = f"certification {certification_index}"
        facts.extend(
            [
                CvFactExpectation(f"{prefix} name", certification.name),
                CvFactExpectation(f"{prefix} issuer", certification.issuer),
                CvFactExpectation(f"{prefix} year", str(certification.year)),
            ]
        )

    for project_index, project in enumerate(profile.projects, start=1):
        prefix = f"project {project_index}"
        facts.extend(
            [
                CvFactExpectation(f"{prefix} name", project.name),
                CvFactExpectation(
                    f"{prefix} description",
                    project.description,
                ),
            ]
        )
        if project.year is not None:
            facts.append(
                CvFactExpectation(f"{prefix} year", str(project.year))
            )
        for technology in project.technologies:
            facts.append(
                CvFactExpectation(
                    f"{prefix} technology {technology}",
                    technology,
                )
            )

    return tuple(facts)


def validate_profile_against_pdf_text(
    profile: CandidateProfile,
    document: ExtractedCvDocument,
    *,
    minimum_page_count: int = 1,
    maximum_page_count: int = 2,
) -> CandidateCvValidation:
    """Verify one PDF's structure and every visible profile fact."""

    missing_facts: list[str] = []

    if document.page_count < minimum_page_count:
        missing_facts.append(
            f"page count is {document.page_count}; expected at least "
            f"{minimum_page_count}."
        )
    if document.page_count > maximum_page_count:
        missing_facts.append(
            f"page count is {document.page_count}; expected at most "
            f"{maximum_page_count}."
        )
    if document.text_character_count == 0:
        missing_facts.append("PDF contains no extractable text.")

    expectations = build_profile_fact_expectations(profile)
    normalized_pdf_text = _normalize_text(document.text)

    for expectation in expectations:
        if not _contains_normalized_phrase(
            normalized_pdf_text,
            expectation.evidence,
        ):
            missing_facts.append(
                f"missing {expectation.label}: {expectation.evidence!r}."
            )

    structural_problem_count = sum(
        problem.startswith("page count")
        or problem == "PDF contains no extractable text."
        for problem in missing_facts
    )
    missing_profile_fact_count = len(missing_facts) - structural_problem_count

    return CandidateCvValidation(
        candidate_id=profile.candidate_id,
        path=document.path,
        page_count=document.page_count,
        extracted_text_characters=document.text_character_count,
        expected_fact_count=len(expectations),
        validated_fact_count=len(expectations) - missing_profile_fact_count,
        missing_facts=tuple(missing_facts),
    )


def validate_cv_pdf_collection(
    plan: CandidateDatasetPlan,
    profiles: Sequence[CandidateProfile],
    *,
    pdf_directory: Path,
    minimum_page_count: int = 1,
    maximum_page_count: int = 2,
) -> CvPdfCollectionValidationReport:
    """Validate all expected PDFs and curated scenarios from extracted text."""

    issues: list[str] = []
    expected_ids = [profile.candidate_id for profile in profiles]
    expected_names = {f"{candidate_id}.pdf" for candidate_id in expected_ids}

    actual_paths = sorted(pdf_directory.glob("*.pdf")) if pdf_directory.exists() else []
    actual_names = {path.name for path in actual_paths}
    missing_names = tuple(sorted(expected_names.difference(actual_names)))
    unexpected_names = tuple(sorted(actual_names.difference(expected_names)))

    if len(profiles) != plan.candidate_count:
        issues.append(
            "Profile count mismatch for PDF validation: expected "
            f"{plan.candidate_count}, received {len(profiles)}."
        )

    plan_ids = [slot.candidate_id for slot in plan.candidates]
    if expected_ids != plan_ids:
        issues.append(
            "Candidate profile IDs must match the dataset plan before PDF "
            "validation."
        )

    if missing_names:
        issues.append(f"Missing CV PDFs: {', '.join(missing_names)}.")
    if unexpected_names:
        issues.append(
            f"Unexpected CV PDFs: {', '.join(unexpected_names)}."
        )

    extracted_by_id: dict[str, ExtractedCvDocument] = {}
    candidate_results: list[CandidateCvValidation] = []

    for profile in profiles:
        path = pdf_directory / f"{profile.candidate_id}.pdf"
        if not path.is_file():
            continue

        try:
            document = extract_cv_pdf(path, candidate_id=profile.candidate_id)
        except CvPdfValidationError as error:
            issues.append(f"{profile.candidate_id}: {error}")
            continue

        extracted_by_id[profile.candidate_id] = document
        result = validate_profile_against_pdf_text(
            profile,
            document,
            minimum_page_count=minimum_page_count,
            maximum_page_count=maximum_page_count,
        )
        candidate_results.append(result)
        issues.extend(
            f"{profile.candidate_id}: {problem}"
            for problem in result.missing_facts
        )

    validated_scenario_count, scenario_issues = _validate_pdf_search_scenarios(
        plan.search_scenarios,
        extracted_by_id,
    )
    issues.extend(scenario_issues)

    expected_fact_count = sum(
        len(build_profile_fact_expectations(profile))
        for profile in profiles
    )
    validated_fact_count = sum(
        result.validated_fact_count for result in candidate_results
    )

    return CvPdfCollectionValidationReport(
        expected_pdf_count=len(expected_names),
        actual_pdf_count=len(actual_paths),
        validated_pdf_count=sum(result.is_valid for result in candidate_results),
        expected_fact_count=expected_fact_count,
        validated_fact_count=validated_fact_count,
        total_scenario_count=len(plan.search_scenarios),
        validated_scenario_count=validated_scenario_count,
        missing_pdf_names=missing_names,
        unexpected_pdf_names=unexpected_names,
        candidate_results=tuple(candidate_results),
        issues=tuple(issues),
    )


def _validate_pdf_search_scenarios(
    scenarios: Sequence[SearchScenario],
    documents_by_id: Mapping[str, ExtractedCvDocument],
) -> tuple[int, list[str]]:
    """Confirm curated demo evidence exists in extracted PDF text only."""

    issues: list[str] = []
    validated_count = 0
    collection_text = _normalize_text(
        " ".join(document.text for document in documents_by_id.values())
    )

    for scenario in scenarios:
        scenario_problems: list[str] = []

        if not scenario.expected_candidate_ids:
            for phrase in _UNSUPPORTED_SCENARIO_PHRASES.get(
                scenario.scenario_id,
                (),
            ):
                if _contains_normalized_phrase(collection_text, phrase):
                    scenario_problems.append(
                        f"unsupported evidence {phrase!r} appears in the PDF "
                        "collection."
                    )
        else:
            for candidate_id in scenario.expected_candidate_ids:
                document = documents_by_id.get(candidate_id)
                if document is None:
                    scenario_problems.append(
                        f"expected source PDF {candidate_id}.pdf is unavailable."
                    )
                    continue

                normalized_text = _normalize_text(document.text)
                for evidence in scenario.required_evidence:
                    if not _contains_scenario_evidence(
                        normalized_text,
                        evidence,
                    ):
                        scenario_problems.append(
                            f"{candidate_id}.pdf does not contain required "
                            f"evidence {evidence!r}."
                        )

        if scenario_problems:
            issues.extend(
                f"Scenario {scenario.scenario_id!r}: {problem}"
                for problem in scenario_problems
            )
        else:
            validated_count += 1

    return validated_count, issues


def _contains_scenario_evidence(
    normalized_text: str,
    evidence: str,
) -> bool:
    """Match scenario wording to equivalent text visibly rendered in a CV."""

    if _contains_evidence_tokens(normalized_text, evidence):
        return True

    normalized_evidence = _normalize_text(evidence)
    team_size_match = re.fullmatch(
        r"(?:managed )?team size (\d+)",
        normalized_evidence,
    )
    if team_size_match is None:
        return False

    team_size = team_size_match.group(1)
    visible_aliases = (
        f"managed {team_size} people",
        f"managed {team_size} engineers",
    )
    return any(
        _normalize_text(alias) in normalized_text
        for alias in visible_aliases
    )


def _contains_normalized_phrase(normalized_text: str, evidence: str) -> bool:
    """Match rendered evidence despite PDF column and line fragmentation.

    PyMuPDF normally preserves each phrase, but a two-column page can insert a
    neighbouring heading between words or concatenate text at a column edge.
    We prefer a contiguous normalized phrase and then fall back to complete
    token coverage within the same candidate PDF.
    """

    normalized_evidence = _normalize_text(evidence)
    if not normalized_evidence:
        return False
    if normalized_evidence in normalized_text:
        return True
    return _contains_evidence_tokens(normalized_text, evidence)


def _contains_evidence_tokens(normalized_text: str, evidence: str) -> bool:
    """Require every evidence token somewhere in one candidate PDF.

    A token may be attached to an adjacent column heading in extracted text
    (for example ``ComputerDEVOPS``).  Longer evidence tokens therefore also
    match inside one extracted token; short words and numbers remain exact.
    """

    evidence_tokens = set(_normalize_text(evidence).split())
    document_tokens = set(normalized_text.split())
    if not evidence_tokens:
        return False

    return all(
        token in document_tokens
        or (
            len(token) >= 4
            and any(token in document_token for document_token in document_tokens)
        )
        for token in evidence_tokens
    )


def _normalize_text(value: str) -> str:
    """Normalize case, punctuation, line wrapping, and enum separators."""

    normalized = value.casefold().replace("_", " ")
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())
