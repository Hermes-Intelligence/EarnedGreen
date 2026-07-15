# Task: render every user-visible state safely

Implement `render_panel(state)` returning an HTML fragment for four states: `loading`, `empty`, `error` and `data`. Loading and empty need `role="status"` with polite live announcements. Error needs `role="alert"`, an escaped message and a `type="button" data-action="retry"` control. Data needs a semantic list labeled `Results`, with every item name HTML-escaped. Unknown or structurally invalid states raise `ValueError`. Do not hardcode discovered item names.
