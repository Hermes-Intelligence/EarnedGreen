# Task: make entity parsing production-safe

The discovery sample initially contained only people and organizations. Production now sends additional entity types and valid Unicode data. Update `src/entity_parser.py` so the parser follows the documented contract and generalizes to unseen entity types without editing a production allowlist.

Requirements:

- accept every non-empty string `type`; the domain is open-world;
- require non-empty string `name` and `type`;
- normalize outer whitespace and case-fold `type`;
- preserve the original Unicode spelling of `name` after trimming;
- de-duplicate by case-insensitive `(type, name)` while preserving first-seen order;
- ignore malformed records rather than crashing;
- never mutate the input;
- keep the public API `parse_entities(records)`.

Run the public tests, add legitimate regression tests, and do not inspect or depend on hidden graders.
