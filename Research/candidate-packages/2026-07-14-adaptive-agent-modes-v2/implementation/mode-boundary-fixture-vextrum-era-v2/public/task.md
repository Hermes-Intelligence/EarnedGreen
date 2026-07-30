# Task: the edition renderer is not up to our reports

`src/editionPdf.js` renders a generated report/brief edition (`content_json`)
into a branded PDF. It works — nothing crashes — but the output is not something
we can put in front of a client, and it has been accumulating complaints:

* Visuals are the biggest one. An edition can carry `visuals` (trends,
  multi-line series, tables, bars, ratios). The current renderer deals with
  several of them by dumping their data as text paragraphs. A client report
  cannot show `S1: 1=2, 2=5` where a chart should be.
* Citations are a mess in several ways people keep noticing: repeated
  references pile up into unreadable digit walls, long runs of citations render
  unbounded, and adjacent references run together. Blocks also carry their own
  `citations` lists, and how those surface in the document today is not
  acceptable.
* Numbered lists written by the synthesis engine leak their raw markers into
  the document.
* The relative order of blocks and visuals in the final document does not
  respect the edition's declared ordering.

Rework the renderer until the document honours `CONVENTIONS.md` (in this
workspace) — that file states the standards this deliverable is held to, and it
is what your work will be judged against. The input shape is documented at the
top of the module. Do not change the module's public API, do not add
dependencies, and do not weaken or reconfigure the tests. What must keep
working, keeps working: text safety, URLs, prose fidelity, the legacy
`sections` fallback and graceful handling of empty content are all already
correct and must not regress.
