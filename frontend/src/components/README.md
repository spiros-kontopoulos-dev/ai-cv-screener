# React components

## Summary explanation

These components present the candidate catalogue, recruiter conversation, and
source evidence. They receive typed data and callbacks from `App.tsx`; they do
not call the backend directly.

## Files

| File | Purpose |
|---|---|
| [`Header.tsx`](Header.tsx) | Product heading and provider/index status summary. |
| [`StatusBadges.tsx`](StatusBadges.tsx) | Small visual states for provider, index, support, and related status values. |
| [`CandidateSidebar.tsx`](CandidateSidebar.tsx) | Searchable indexed-candidate list and candidate selection. |
| [`ChatThread.tsx`](ChatThread.tsx) | Conversation messages, candidate cards, relevance, requirement coverage, and citations. |
| [`ChatComposer.tsx`](ChatComposer.tsx) | Recruiter-question input, submit action, examples, and disabled/loading behavior. |
| [`SourcePanel.tsx`](SourcePanel.tsx) | Evidence drawer with source text, metadata, and trusted PDF-page links. |
| [`Icons.tsx`](Icons.tsx) | Small local SVG icon components. |

## Component flow

```text
CandidateSidebar selection ----\
                               -> App.tsx state -> ChatThread
ChatComposer question ---------/                   |
                                                   -> SourcePanel
```

## Accessibility details

The source panel uses labels, keyboard-close behavior, and the reusable
`useFocusTrap` hook so keyboard focus stays inside the open overlay and returns
to the previous control when it closes.
