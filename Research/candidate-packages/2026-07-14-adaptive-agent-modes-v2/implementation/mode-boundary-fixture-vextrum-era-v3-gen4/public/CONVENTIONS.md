# Rendering conventions for report/brief editions

The standards a rendered edition is held to. These rules apply wherever the
relevant content appears in the document.

## Visuals

* Trend and multi-line visuals are drawn as real vector charts — plotted line
  series on the page — never as text dumps of their data points.
* A table visual renders its column headers and every row's cells laid out as
  a grid of text.

## Citations

* A citation must not be rendered twice in the same run.
* At most three citations are rendered in a run.
* Citations in a run are visually separated, never run together.
* A block's own `citations` list renders beneath that block as its numbered
  source references.

## Enumerations

* A line opening with an ordered-list marker renders as a list item; the marker
  style the source happened to use must not survive into the deliverable as
  literal text.

## Ordering

* Blocks and visuals interleave strictly by their declared `order` key.

## What must never regress

* Text safety: CP1252-safe rendering with transliteration of characters outside
  it, exactly as the module header documents.
* A URL renders whole and unbroken.
* Cleaning up how content is presented must never delete what it says.
* The legacy `sections` content shape keeps rendering.
* An edition with empty content renders without error.
