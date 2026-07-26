# Grounded answer generation pipeline

## Summary explanation

This section takes the final retrieval result and produces the answer shown to a
recruiter. It does not perform a new search and it does not allow a provider to
choose its own evidence.

The retrieval pipeline decides which candidates and sources are allowed. This
section chooses the answer mode, writes or requests structured wording, validates
that wording and exposes only referenced sources.

## Position in the complete application

### State before this section

- `FinalCvRetrievalResult` already exists;
- candidates are ranked and classified as complete or partial;
- source chunks have stable IDs and candidate ownership;
- context has already been bounded;
- the configured provider may be OpenAI, Gemini, automatic or deterministic.

### State after this section

- answer outcome agrees with retrieval outcome;
- candidate order and identities agree with retrieval;
- matched requirements agree with the candidate result;
- citations exist, belong to the correct candidate and cover the claims;
- only cited sources are exposed to the API;
- provider, model, attempts and warnings are recorded.

```text
FinalCvRetrievalResult
-> provider selection
-> unsupported / deterministic / hosted branch
-> GroundedAnswerDraft
-> deterministic validation
-> GroundedAnswerGenerationResult
-> GroundedAnswerResponse
```

## Entry point and coordinator

The central service is:

```text
GroundedCvAnswerGenerator.generate(FinalCvRetrievalQuery(...))
```

It is normally built by:

```text
build_grounded_cv_answer_generator(settings)
```

The FastAPI chat dependency caches this complete object and reuses it across
requests.

## Exact runtime order

### Service construction

```text
1. build_grounded_cv_answer_generator(settings)
2. build_final_cv_retriever(settings)
3. resolve_grounded_answer_provider(settings)
4. Build GroundedAnswerGenerationConfig from retry and length limits.
5. Return GroundedCvAnswerGenerator(retriever, provider, model labels).
```

Provider resolution follows this order:

```text
explicit gemini -> require Google/Gemini key
explicit openai -> require OpenAI key
explicit deterministic -> no provider object
auto -> Gemini key -> OpenAI key -> deterministic fallback
```

### One recruiter question

```text
1. GroundedCvAnswerGenerator.generate(query)
2. FinalCvRetriever.retrieve(query)
3. If retrieval is unsupported:
   a. build deterministic unsupported draft;
   b. do not call a hosted provider.
4. Else if provider is deterministic:
   a. build deterministic candidate draft;
   b. validate the draft locally.
5. Else hosted mode:
   a. provider.generate(retrieval_result, correction_feedback);
   b. parse structured GroundedAnswerDraft;
   c. validate_grounded_answer_draft();
   d. return when valid;
   e. otherwise send validation problems into the bounded retry loop.
6. GroundedAnswerGenerationResult.response builds final source objects.
7. Only source IDs referenced by the accepted draft are included.
```

## File map in execution order

| Runtime phase | File | Responsibility |
|---:|---|---|
| 1 | [`provider_selection.py`](provider_selection.py) | Resolves auto/OpenAI/Gemini/deterministic mode and validates required keys. |
| 2 | [`prompt.py`](prompt.py) | Builds the hosted-provider prompt from the approved retrieval package and correction feedback. |
| 3 | [`client.py`](client.py) | Calls OpenAI structured output and parses `GroundedAnswerDraft`. |
| 3 | [`gemini_client.py`](gemini_client.py) | Calls Gemini structured output and parses the same draft contract. |
| 4 | [`generation.py`](generation.py) | Runs retrieval, branch selection, hosted retries, deterministic drafts and final validation. |
| 5 | [`sources.py`](sources.py) | Creates stable source IDs and validates candidate-owned citations. |
| Shared | [`models.py`](models.py) | Defines draft, candidate answer, source and public response models. |

## Important functions and classes

### `resolve_grounded_answer_provider(settings)`

Returns `ResolvedGroundedAnswerProvider` containing:

- provider object or `None` for deterministic mode;
- stable provider label;
- model label.

An explicitly selected hosted provider without its required key raises
`GroundedAnswerConfigurationError`. `auto` is allowed to fall back.

### `build_grounded_answer_prompt(retrieval_result, correction_feedback)`

Builds instructions around the exact final context. The provider is told to:

- preserve outcome and candidate order;
- describe only returned candidates;
- keep partial results clearly partial;
- use only supplied source IDs;
- keep citations attached to the candidate that owns them;
- correct any problems reported from the previous attempt.

### `OpenAIGroundedAnswerProvider.generate(...)`

Calls OpenAI with structured output and returns `GroundedAnswerDraft`.
Provider-specific failures become `GroundedAnswerProviderError` with retryability
information.

### `GeminiGroundedAnswerProvider.generate(...)`

Uses the official Gemini client but returns the same draft model. The rest of
the application does not need provider-specific result handling.

### `GroundedCvAnswerGenerator.generate(query)`

The main coordinator. It always runs retrieval first. Hosted provider calls are
skipped for unsupported questions because no model is needed to say that the
index lacks support.

### `_build_deterministic_draft(retrieval_result)`

Creates no-key wording from the same ranked candidates and source contracts.
This keeps local evaluation useful without changing retrieval behavior.

### `_build_unsupported_draft(retrieval_result)`

Builds an honest unsupported answer with no candidate claims and no citations.

### `validate_grounded_answer_draft(...)`

Checks that provider wording cannot break the retrieval contract. It validates:

- draft outcome equals retrieval outcome;
- answer and assessments stay within length limits;
- unsupported drafts expose no candidates;
- candidate IDs, order, names and titles match;
- matched requirements are not invented or removed;
- answer citations reference known source IDs;
- overall citations include every returned candidate;
- each candidate cites only its own sources;
- candidate citations cover the matched requirements being claimed.

### `build_grounded_answer_sources(retrieval_result)`

Converts final evidence into stable source objects. Source IDs are generated by
`build_source_id(candidate_id, evidence_order)`.

### `validate_grounded_answer_citations(...)`

Performs candidate-ownership and coverage checks used by the draft validator.
This prevents a plausible but invalid answer from citing another candidate's
chunk.

### `GroundedAnswerGenerationResult.response`

Builds the final answer-domain response. It includes only sources actually
referenced in the accepted draft, adds deterministic-mode warnings where useful
and preserves provider diagnostics.

## Why retrieval and wording are separate

Retrieval makes factual decisions:

- which requirements were parsed;
- which evidence supports them;
- which candidates pass thresholds;
- whether the result is supported, partial or unsupported.

Answer generation makes presentation decisions:

- how to summarise the result;
- how to explain each candidate;
- where to place validated citations.

A hosted model cannot promote a weak candidate, add a missing candidate or cite
unapproved evidence.

## Failure and retry behavior

| Failure | Behavior |
|---|---|
| Retrieval unavailable | Fail with zero provider attempts. |
| Unsupported retrieval | Return deterministic unsupported response. |
| Explicit provider missing key | Configuration error before route execution. |
| Retryable hosted-provider error | Retry within configured limit. |
| Invalid hosted draft | Send the exact validation problems as correction feedback. |
| Final hosted draft still invalid | Raise `GroundedAnswerGenerationFailed`. |
| Deterministic draft invalid | Fail immediately because local contract construction is broken. |

## Connection to the API

```text
GroundedAnswerGenerationResult
-> api.presenters.present_chat_response()
-> join candidate answer details with retrieval scores and pages
-> ChatResponse JSON
-> React chat thread and source panel
```

## Main command

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_grounded_cv_answer --help
```

Use `--show-context` to inspect the exact evidence context available to the
selected provider.

## Related tests

- `test_cv_grounded_answer_provider_selection.py`
- `test_openai_grounded_answer_provider.py`
- `test_gemini_grounded_answer_provider.py`
- `test_cv_grounded_answer_prompt.py`
- `test_cv_grounded_answer_sources.py`
- `test_cv_grounded_answer_generation.py`
- `test_inspect_grounded_cv_answer_cli.py`
