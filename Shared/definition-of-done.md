# Legacy Definition of Done - Reference Only

*Superseded by the minimal Core, routed verification modules and Objective Integrity checks. Retained for migration and evaluation.*

- **Self-verify end-to-end at the real surface.** "Done" means you ran the change where a user actually reaches it and observed correct behavior — invoked the command and read its output, issued the request and inspected the response, exercised the public interface, rendered the UI — not merely that tests or type-checks are green. Capture reproducible evidence (output, logs, a screenshot); your memory is not evidence. Emit an explicit verdict — pass, fail, or blocked — and when genuinely in doubt, treat it as a failure.

- **Hunt bugs with a fresh, adversarial pass.** Review the diff on its own terms, as if you did not write it — the author is a poor judge of their own work. Actively try to break it and disprove your assumptions. Scope the hunt to defects that affect correctness or the stated requirements; do not manufacture gaps that drive needless abstraction or defensive code for impossible states.

- **Cover the edge cases, not just the happy path.** Exercise empty, missing, and malformed input; boundary and conflicting arguments; error and failure paths; idempotency and re-run/state-persistence behavior; and adjacent functionality the change could disturb. Plausible-looking code that quietly mishandles the edges is the most common way a change ships broken.

- **Update the docs the change touches.** Bring the standing project-rules/instructions file, changelog, interface docs, and inline comments in line with what you changed. When a correction would otherwise recur, fold the lesson into the durable rules as part of finishing — do not leave documentation describing the old behavior.

- **Leave no debug cruft.** Strip temporary logging and print statements, commented-out experiments, throwaway scripts, and dead scaffolding. Keep the diff scoped and reviewable. Never weaken, skip, or delete a test to make the build pass — that hides broken functionality rather than fixing it.

- **Gate "done" on recorded evidence, never on self-assertion.** Tie completion to a check that runs and produces a pass/fail signal, and record that result alongside the work. "It looks done" is not a completion signal; a green, evidenced check is.
