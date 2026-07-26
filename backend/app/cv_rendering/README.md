# CV rendering

## Summary explanation

This section turns validated candidate profiles into professional, searchable
PDF CVs. It prepares deterministic render jobs, formats profile values for human
readers, renders Jinja HTML and CSS through WeasyPrint, and then validates the
resulting PDF text with PyMuPDF.

```text
CandidateProfile + optional portrait
-> render plan
-> Jinja HTML and CSS
-> WeasyPrint PDF
-> searchable-text and fact validation
```

## Files

| File | Purpose |
|---|---|
| [`models.py`](models.py) | Immutable render-job, profile-metric, and render-result data objects. |
| [`formatting.py`](formatting.py) | Formats dates, experience, seniority, skills, languages, and labels. |
| [`planning.py`](planning.py) | Measures profiles, chooses output paths, and selects render jobs without writing files. |
| [`rendering.py`](rendering.py) | Loads Jinja templates, embeds portraits, writes HTML/PDF output, and verifies the PDF can be read. |
| [`validation.py`](validation.py) | Extracts final PDF text and proves that expected profile facts and search scenarios are present. |
| [`templates/candidate_cv.html.j2`](templates/candidate_cv.html.j2) | Main CV structure. |
| [`assets/candidate_cv.css`](assets/candidate_cv.css) | Print layout and visual styling used by WeasyPrint. |

## Important boundary

The renderer receives already validated `CandidateProfile` objects. It does not
repair candidate facts. Its job is presentation, file creation, and proof that
the final PDFs remain machine-readable.

## Main commands

```powershell
docker compose exec backend python -m app.scripts.render_candidate_cvs --help
docker compose exec backend python -m app.scripts.validate_candidate_cvs --help
```

## Related tests

- `tests/test_cv_rendering_formatting.py`
- `tests/test_cv_rendering_planning.py`
- `tests/test_cv_rendering_renderer.py`
- `tests/test_cv_pdf_validation.py`
