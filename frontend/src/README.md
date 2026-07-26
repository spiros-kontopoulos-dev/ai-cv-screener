# Frontend hooks

## Summary explanation

This folder contains reusable browser behavior that is not tied to one visual
component. Keeping this behavior in a hook makes the component easier to read
and lets the behavior be tested or reused independently.

## Files

| File | Purpose |
|---|---|
| [`useFocusTrap.ts`](useFocusTrap.ts) | Keeps keyboard focus inside an open overlay, supports Tab and Shift+Tab cycling, handles Escape, and restores focus after close. |

The hook is currently used by `components/SourcePanel.tsx` to make the evidence
drawer keyboard accessible.
