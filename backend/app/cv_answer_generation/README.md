# Grounded answer generation

## Summary explanation

This section receives the final candidate retrieval result and turns it into the
answer shown to the recruiter. Retrieval decides which candidates and evidence
are valid. The provider is allowed to word that approved evidence, but it cannot
introduce new candidates or citations.

```text
FinalCvRetrievalResult
-> bounded evidence prompt
-> OpenAI, Gemini, or deterministic draft
-> candidate and citation validation
-> GroundedAnswerResponse
```

## Files

| File | Purpose |
|---|---|
| [`models.py`](models.py) | Provider-independent models for candidate answers, drafts, sources, and final responses. |
| [`provider_selection.py`](provider_selection.py) | Resolves `auto`, `openai`, `gemini`, or `deterministic` mode from settings and available keys. |
| [`prompt.py`](prompt.py) | Builds strict instructions using only final retrieval evidence. |
| [`client.py`](client.py) | OpenAI structured-output provider. |
| [`gemini_client.py`](gemini_client.py) | Gemini JSON-mode provider. |
| [`generation.py`](generation.py) | Coordinates retrieval, provider wording, deterministic fallback, and final validation. |
| [`sources.py`](sources.py) | Creates stable source IDs and proves that each citation belongs to the cited candidate. |

## Grounding rules

- Candidate selection comes from retrieval, not from the language model.
- The provider receives bounded evidence rather than the complete CV collection.
- Every returned candidate must exist in the retrieval result.
- Every citation must resolve to evidence owned by that same candidate.
- Unsupported questions return a clear unsupported response rather than a
  plausible-looking guess.
- Deterministic mode can answer without any hosted provider key.

## Main inspection command

```powershell
docker compose exec backend python -m app.scripts.inspect_grounded_cv_answer --help
```

## Related tests

- `tests/test_cv_grounded_answer_generation.py`
- `tests/test_cv_grounded_answer_prompt.py`
- `tests/test_cv_grounded_answer_provider_selection.py`
- `tests/test_cv_grounded_answer_sources.py`
- `tests/test_openai_grounded_answer_provider.py`
- `tests/test_gemini_grounded_answer_provider.py`
