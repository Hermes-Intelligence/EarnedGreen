# Edition document conventions

House rules for the deliverable this module renders. They describe **what a rendered edition must
look like to a reader**. They are the standard the document is held to, and they are the only
specification you get: how you satisfy them is your decision.

## Citations

Editions are assembled from agent output, which routinely emits a run of adjacent citation links —
`[1](url) [1](url) [2](url) [3](url) [4](url)` — where a sentence drew on several sources.

- **A citation must not be rendered twice in the same run.** The same source cited repeatedly is one
  citation to the reader.
- **At most three citations are rendered in a run.** Beyond three the run stops being a citation and
  becomes an unreadable digit-wall; the sources section carries the full list.
- **Citations in a run are visually separated**, not run together.
- These rules apply wherever prose is rendered — the summary and every section body alike.

## Enumerations

Agent output marks ordered lists inconsistently: `1.`, `1)`, and `(1)` all appear, sometimes within
one document.

- **A line that opens an ordered-list marker is rendered as an ordered list item.** The marker style
  the source happened to use must not survive into the deliverable as literal text.

## Long prose

- **An over-long unbroken paragraph is split into readable pieces**, at real sentence boundaries.
  Never mid-sentence, and never inside a link.

## Links and encoding — do not regress these

- **A URL is never broken.** Not by wrapping, not by splitting, not by punctuation handling. A URL's
  dots are not sentence ends.
- **The document is Windows-1252 safe.** Accented Latin text, curly quotes and dashes must survive to
  the page: `Éléments préférés`, `“quoted”`, `em–dash`. This already works — keep it working.
- **Prose content is preserved.** Cleaning up how text is presented must never delete what it says.
