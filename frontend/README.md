# React component architecture

## Summary explanation

These components render the state owned by `App.tsx`. They are mostly
presentation components: they receive typed props and callbacks, display data
and report user actions back to `App`.

## Render tree

```text
App
├── Header
├── CandidateSidebar
│   └── CandidateCard / CandidateAvatar
├── chat-main
│   ├── connection or empty state
│   ├── ChatThread
│   │   ├── EmptyState
│   │   ├── UserMessage
│   │   ├── AssistantMessage
│   │   │   ├── OutcomeBadge / ProviderBadge
│   │   │   ├── CandidateAssessment
│   │   │   └── CitationChip
│   │   ├── ErrorMessage
│   │   └── TypingMessage
│   └── ChatComposer
└── SourcePanel
    └── source excerpt + PDF link
```

## State and callback direction

```text
App state
-> component props
-> rendered interface
-> user event
-> callback to App
-> App updates state
-> rerender
```

Components do not independently write conversation state or query the backend.

## File map in render order

| File | Main responsibility | Important inputs/actions |
|---|---|---|
| [`Header.tsx`](Header.tsx) | Shows application identity, candidate count, mobile menu and clear-conversation action. | candidate count, loading state, open sidebar, clear chat |
| [`CandidateSidebar.tsx`](CandidateSidebar.tsx) | Lists indexed candidates and highlights candidates in the latest response. | catalogue, matched-candidate map, loading/error/retry state |
| [`ChatThread.tsx`](ChatThread.tsx) | Renders all turns, outcomes, assessments, citations, retries and suggestions. | turns, submitting state, select-source and retry callbacks |
| [`ChatComposer.tsx`](ChatComposer.tsx) | Controlled recruiter-question input with length and submitting state. | value, error, max length, change and submit callbacks |
| [`SourcePanel.tsx`](SourcePanel.tsx) | Displays one selected evidence source and opens the trusted PDF page. | selected `ChatSource`, close action |
| [`StatusBadges.tsx`](StatusBadges.tsx) | Converts outcome/provider values into compact labels. | outcome, provider, provider-called state |
| [`Icons.tsx`](Icons.tsx) | Provides local SVG icon components used by the interface. | size/class props where applicable |

## Component execution details

### `CandidateSidebar`

```text
App candidates + latest matchedCandidates map
-> loading/error/empty branch
-> CandidateCard for each indexed candidate
-> card checks candidate_id in matchedCandidates
-> show match rank/score when available
-> open candidate PDF when available
```

The sidebar always starts from the indexed catalogue. It does not replace the
catalogue with only matched candidates.

Important helper components:

- `CandidateAvatar` shows a static portrait when available and falls back to initials;
- `CandidateCard` combines catalogue identity with optional latest-response match data.

### `ChatThread`

For every `ChatTurn`:

```text
UserMessage(question)
-> response exists: AssistantMessage(response)
-> error exists: ErrorMessage + retry action
-> active final turn: TypingMessage
```

`AssistantMessage` renders:

- answer text;
- supported/partial/unsupported badge;
- provider/model diagnostics;
- candidate assessments and matched requirements;
- citation chips linked to `ChatSource` objects;
- warnings that the backend intentionally exposed.

`CitationChip` looks up the source ID in `response.sources` and calls
`onSelectSource(source)`. Unknown IDs are not fabricated into a panel.

### `ChatComposer`

A controlled form. Text lives in `App`, so clear, submit and validation behavior
remain coordinated with the conversation state.

It prevents accidental duplicate submission while `isSubmitting` is true and
shows the current length against the maximum.

### `SourcePanel`

```text
selected source is null
-> panel closed

selected source exists
-> render candidate/file/page/section/support details
-> render exact evidence excerpt
-> build PDF href from source.cv_url + page fragment
-> trap focus and support Escape
```

The PDF URL comes from the backend presenter, not from a local path assembled by
the component.

### `StatusBadges`

Presentation-only mapping. The backend owns the meaning of supported, partial,
unsupported, provider and provider-called values.

## Important presentation helpers outside this folder

`utils.ts` supplies:

- initials and stable avatar color;
- score/percentage formatting;
- readable section names;
- outcome and provider labels.

These helpers must not change retrieval meaning. They format values that the API
has already decided.

## Accessibility and interaction rules

- buttons use real button elements;
- loading and error regions use appropriate status/alert roles;
- source evidence behaves like a modal panel;
- focus is contained while the panel is open;
- Escape closes the panel;
- focus returns to the element that was active before opening;
- PDF links open the trusted API URL rather than hidden filesystem paths.

## Related tests

`App.test.tsx` exercises the components through the real `App` state flow,
including candidate loading, supported/partial/unsupported results, citations,
PDF page links, errors and retries.
