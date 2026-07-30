# Harness-authoring rules (C7)

A rule, not a mechanism: nothing here can be enforced by code, because the whole
point is that the harness is the thing outside the code's reach. Written down
because the same two mistakes cost real time in one afternoon.

## 1. A stand-in must be faithful in the ways the real thing is boring

A fake that returns **live references**, or that lets **framework-injected
defaults arrive unresolved**, invents failures that do not exist.

Both happened in a single test file:

- The in-memory database returned the live row object from its own store. A route
  read its "before" state, issued an update, then rendered a trail line from that
  same object — which the update had already mutated. Result: `Moved exploring →
  exploring`. psycopg2 returns fresh dicts; the fake did not. **Copy on the way
  out.**
- Route functions were called directly, so FastAPI never resolved
  `include_deleted: bool = Query(False)`. The parameter arrived as a truthy
  `Query` object and the "deleted" filter silently did nothing. **Pass
  framework-injected parameters explicitly** when you bypass the framework.

## 2. When a fake produces a false failure, check what it is pointing at

The aliasing bug above was a harness bug. It was also pointing at genuine
fragility in the route: reading `current["stage"]` *after* the UPDATE works only
because the driver happens to return copies. That is now a local captured before
the write, with a comment saying why.

Dismissing a false failure without asking what made it possible throws away the
most useful thing the harness produced that day.

## 3. A predicate that has not been RED on something broken is worth zero

Not a style preference — measured, twice in one hour, on the same defect:

1. A layout predicate written to catch visibly clipped card text was **green on
   the build that had the defect.** It compared card geometry to column geometry;
   the card fitted, and a row *inside* it was overflowing. Wrong element.
2. The corrected predicate went red, the defect was fixed — and then the same
   predicate went green again on a build where the label was still being cut,
   because it exempted anything whose computed `text-overflow` was `ellipsis`.
   `text-overflow` **has no effect on a flex container**: the property was set,
   the ellipsis never rendered, and the check was asking about a property that
   did nothing.

Both versions would have shipped as "covered". The rule that catches this is the
one that catches everything else in this package: **show the red first.**

## 4. Do not exempt a case by asking whether a property is SET

Ask whether it is **in effect**. Property-is-set is what the agent can see
cheaply; property-is-in-effect is what the user experiences. The gap between them
is where a check quietly stops checking.
