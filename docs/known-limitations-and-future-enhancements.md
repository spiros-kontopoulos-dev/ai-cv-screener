# Known Limitation and Future Enhancement

## Natural-language query planning for unrestricted recruiter phrasing

## Summary

The AI CV Screener is an MVP natural-language retrieval application for a controlled collection of candidate CVs. Its current retrieval pipeline combines semantic vector recall with deterministic query analysis, relation-aware evidence verification, candidate-level ranking, support classification, and grounded answer generation.

The implementation performs reliably across its committed regression matrix and supported recruiter-query families. Exploratory testing has nevertheless shown an important boundary: two sentences with the same intended meaning can occasionally produce different retrieval outcomes when their grammatical structure falls outside the patterns currently recognized by the deterministic query-understanding layer.

This limitation concerns **interpreting unrestricted wording before retrieval**. It does not change the source-of-truth boundary, vector index, candidate ownership rules, evidence verification, or citation validation.

## Current request flow

```text
User question
    ↓
Deterministic query analysis
    ↓
Semantic recall from Chroma
    ↓
Relation-aware evidence verification
    ↓
Candidate-level ranking and support classification
    ↓
Grounded answer generation with validated citations
```

The hosted answer provider receives the question only after candidate evidence has been retrieved and validated. It writes the grounded response; it does not currently create the initial retrieval plan.

## Observed wording sensitivity

The following examples express closely related candidate-search intentions but can be interpreted differently by the current deterministic query-understanding layer:

```text
Which candidates know Python?
What candidates know Python?

Find someone who has worked for a company from the Netherlands.
Find someone who had worked for a company from the Netherlands.

Who is a junior Python API engineer?
I need the list of all junior Python API engineers.
```

This behavior can make a genuine no-match result difficult to distinguish from a query-understanding failure.

## Why a larger phrase dictionary is not the long-term solution

Adding aliases and grammatical variants is useful for well-defined domain concepts, but unrestricted natural language cannot be covered reliably by continuously expanding a static collection of words and sentence patterns.

A phrase-by-phrase approach would:

- require ongoing additions for verb tense, request framing, plurals, and paraphrases;
- remain vulnerable to unseen wording;
- make query behavior harder to reason about;
- blur the difference between conversational scaffolding and candidate requirements;
- risk converting unrelated wording into accidental CV constraints.

The long-term solution should therefore improve the responsibility boundary rather than keep growing a list of exceptions.

## Proposed production enhancement

A future version should use a **hybrid query-planning layer**:

```text
User question
    ↓
Deterministic query planner
    ├── high-confidence plan → continue directly
    └── uncertain or unrecognized plan
            ↓
       LLM query planner
            ↓
Strict application-side plan validation
    ↓
Existing candidate-aware retrieval pipeline
    ↓
Grounded answer generation
```

The LLM planner would not answer the recruiter question. It would translate the message into a constrained search plan such as:

```json
{
  "intent": "candidate_search",
  "in_scope": true,
  "result_scope": "all",
  "normalized_query": "junior Python API engineers",
  "constraints": {
    "seniority": ["junior"],
    "skills": ["Python"],
    "roles": ["API engineer"]
  },
  "confidence": 0.96,
  "clarification_question": null
}
```

For an unrelated question, it could return an out-of-scope intent rather than extracting incidental CV keywords.

## Important trigger rule

The LLM fallback should **not** run simply because retrieval returned zero candidates.

A zero-result retrieval can mean either:

1. the request was understood correctly and no indexed candidate satisfies it; or
2. the request was interpreted incorrectly.

The correct trigger is low query-plan confidence or failure to create a valid structured plan—not an empty candidate result by itself.

## Safety and grounding requirements

Any future LLM-generated query plan should pass a strict Pydantic contract before retrieval. The application should verify that:

- only supported intents and constraint types are accepted;
- unknown fields are rejected;
- important numbers, countries, skills, roles, and candidate names are grounded in the original message;
- the planner cannot silently invent additional requirements;
- low-confidence requests produce a clarification question;
- out-of-scope requests receive a domain-specific response;
- provider failures fall back safely;
- the original question and normalized plan remain observable for diagnostics.

The existing vector retrieval, candidate grouping, exact evidence checks, support thresholds, bounded context, and citation validation should remain unchanged.

## Future validation strategy

The enhancement should be evaluated by intent families rather than by isolated phrase fixes. A provider-free and provider-backed test matrix should include:

- skill and technology searches;
- role and seniority searches;
- employment-country relationships;
- education and certification requirements;
- numeric experience and team-size constraints;
- language proficiency;
- candidate comparisons;
- list-all and count requests;
- ambiguous wording;
- out-of-scope questions;
- genuine no-result searches.

Each family should contain many paraphrases and should assert equivalent structured plans and candidate policies where appropriate.

## MVP decision

This enhancement is intentionally deferred from the submitted MVP.

The current application already demonstrates the requested end-to-end RAG workflow, including PDF ingestion, local embeddings, persistent vector search, candidate-aware evidence verification, grounded answer generation, and source citations. Introducing a second model call, confidence routing, structured query-plan contracts, clarification behavior, provider parity, and a new evaluation matrix would be a meaningful architectural feature rather than a safe last-minute wording patch.

Documenting the boundary preserves a stable submission while providing a clear, technically justified path toward more robust conversational behavior.

## Related documentation

- [Technical highlight: grounded hybrid retrieval with relation-aware candidate evidence](technical-highlight.md)
