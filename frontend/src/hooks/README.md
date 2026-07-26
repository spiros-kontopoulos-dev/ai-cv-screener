# React interaction hooks

## Summary explanation

This folder contains reusable browser interaction behavior that is independent
from API data and visual markup. At present it contains the keyboard-focus hook
used by modal-style panels.

## Position in the component flow

```text
SourcePanel opens
-> useFocusTrap(containerRef, active=true, onEscape)
-> focus enters panel
-> Tab stays inside panel
-> Escape calls close callback
-> panel closes
-> previous focus is restored
```

## Files

| File | Runtime role |
|---|---|
| [`useFocusTrap.ts`](useFocusTrap.ts) | Contains keyboard focus inside an active panel and restores focus on cleanup. |

## Exact runtime order of `useFocusTrap()`

```text
1. React runs the effect after render.
2. If inactive or the ref is missing, do nothing.
3. Save document.activeElement.
4. Find current focusable elements inside the container.
5. Focus the first focusable element, or the container itself.
6. Add one document keydown listener.
7. Escape prevents default and calls onEscape().
8. Tab on the last element wraps to the first.
9. Shift+Tab on the first wraps to the last.
10. Cleanup removes the listener and restores previous focus.
```

The focusable-element list is recalculated on every Tab press, so buttons or
links that appear while the panel is open are included.

## Important boundary

The hook owns keyboard behavior only. The calling component still owns:

- whether the panel is open;
- the close callback;
- ARIA labels and semantic markup;
- the container ref;
- source data and visual styling.
