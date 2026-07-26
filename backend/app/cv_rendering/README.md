# CV rendering and PDF validation pipeline

## Summary explanation

This section converts trusted candidate profiles into the PDF documents that
become the retrieval corpus. Jinja builds HTML, CSS defines the print layout,
WeasyPrint writes the PDF, and PyMuPDF proves that the result is readable and
contains selectable text.

## Position in the complete application

### State before this section

- `candidate_profiles.json` contains validated profiles;
- the portrait plan is valid;
- planned portrait files may be present;
- the Jinja template and CSS are committed.

### State after this section

- `data/cv_pdfs/*.pdf` contains one searchable CV per candidate;
- optional HTML previews may exist for layout inspection;
- PDF validation can compare rendered text with profile facts and planned search scenarios;
- ingestion can treat the PDFs as the source of truth.

```text
CandidateProfile + portrait state
-> CvRenderJob
-> Jinja HTML
-> CSS print layout
-> WeasyPrint PDF
-> PyMuPDF readability check
-> collection-level fact validation
```

## Entry point and coordinators

The normal command starts in:

```text
app.scripts.render_candidate_cvs.run_cli()
```

The central rendering functions are:

```text
render_cv_jobs()
-> render_cv_job()
-> render_cv_html()
-> _verify_rendered_pdf()
```

## Exact runtime order

### Planning and rendering

```text
1. run_cli() parses candidate selection and artifact options.
2. load_candidate_profiles() loads trusted CandidateProfile objects.
3. load_portrait_coverage_plan() loads the committed photo plan.
4. validate_portrait_coverage_against_profiles() checks profile/plan IDs.
5. build_cv_render_jobs() calculates paths, portrait state and profile metrics.
6. select_cv_render_jobs() selects one, N or all jobs.
7. find_profile_boundaries() identifies short and dense profiles for diagnostics.
8. --dry-run prints the planned artifacts and stops.
9. render_cv_jobs() optionally enforces that every planned portrait exists.
10. For each job, render_cv_job() calls render_cv_html().
11. render_cv_html() loads CSS and the Jinja template.
12. The template receives the profile, grouped skills, formatting filters and portrait data URI.
13. WeasyPrint writes the A4 PDF.
14. _verify_rendered_pdf() opens it with PyMuPDF and checks pages, text and candidate name.
15. Return CvRenderResult for every candidate.
```

### Collection validation after rendering

```text
validate_candidate_cvs command
-> load profiles and plan scenarios
-> extract_cv_pdf() for every PDF
-> build_profile_fact_expectations()
-> validate_profile_against_pdf_text()
-> validate_cv_pdf_collection()
-> validate planned search-scenario evidence
```

## File map in execution order

| Runtime position | File | Responsibility |
|---:|---|---|
| 1 | [`planning.py`](planning.py) | Converts profiles and portrait coverage into deterministic `CvRenderJob` objects. |
| 2 | [`formatting.py`](formatting.py) | Formats dates, experience, enums, initials and skill groups for the template. |
| 3 | [`templates/candidate_cv.html.j2`](templates/candidate_cv.html.j2) | Defines semantic CV structure and inserts profile fields. |
| 4 | [`assets/candidate_cv.css`](assets/candidate_cv.css) | Defines visual layout, typography, portrait placement and print behavior. |
| 5 | [`rendering.py`](rendering.py) | Produces HTML/PDF artifacts and verifies the new PDF immediately. |
| 6 | [`validation.py`](validation.py) | Re-extracts PDFs and compares them with profile facts and collection scenarios. |
| Shared | [`models.py`](models.py) | Carries profile metrics, render jobs and render results. |

## Important functions and classes

### `measure_candidate_profile(profile)`

Counts profile content and creates `CvProfileMetrics`. These metrics help locate
the shortest and densest examples before final bulk rendering.

### `build_cv_render_jobs(...)`

Creates stable output paths and portrait flags for every candidate. It does not
render yet. The job records:

- candidate profile;
- portrait path and whether the plan requires it;
- PDF path;
- optional HTML preview path;
- profile metrics.

### `render_cv_jobs(jobs, keep_html, enforce_portrait_plan)`

Sorts jobs by candidate ID, optionally fails fast on missing planned portraits,
and calls `render_cv_job()` for each selected candidate.

### `render_cv_job(job, keep_html)`

The main one-document coordinator:

```text
render_cv_html()
-> optionally save HTML
-> WeasyPrint.write_pdf()
-> _verify_rendered_pdf()
-> CvRenderResult
```

### `render_cv_html(job)`

Builds the Jinja environment with `StrictUndefined`. A missing template variable
therefore fails clearly instead of producing a silently incomplete CV.

It supplies formatting filters such as:

- `work_range`;
- `education_range`;
- `years_experience`;
- `skill_years`;
- `language_proficiency`;
- `seniority`.

### `_build_portrait_data_uri(job)`

Embeds WebP bytes directly into HTML. The same HTML preview therefore works in a
host browser and inside the container; it does not depend on a Docker-only file
URL.

### `_verify_rendered_pdf(job)`

Opens the new file with PyMuPDF and requires:

- at least one page;
- non-empty extractable text;
- the candidate's full name in that text.

### `validate_cv_pdf_collection(...)`

Performs deeper final checks. It detects missing or extra PDFs, validates profile
facts, confirms candidate identity and checks that planned recruiter scenarios
are actually supported by rendered document text.

## Important boundary

Rendering never repairs business facts. It receives already validated profiles
and is responsible for:

- presentation;
- deterministic file naming;
- machine-readable PDF output;
- proof that expected profile facts survived rendering.

## Connection to the next section

```text
validated PDF CV collection
-> cv_ingestion.select_cv_pdf_paths()
-> extraction and chunking
-> embedding and ChromaDB
```

After this handoff, recruiter search reads the PDF content, not the profile JSON
or HTML preview.

## Commands

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.render_candidate_cvs --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.validate_candidate_cvs --help
```

## Related tests

- `test_cv_rendering_formatting.py`
- `test_cv_rendering_planning.py`
- `test_cv_rendering_renderer.py`
- `test_cv_pdf_validation.py`
- `test_render_candidate_cvs_cli.py`
- `test_validate_candidate_cvs_cli.py`
