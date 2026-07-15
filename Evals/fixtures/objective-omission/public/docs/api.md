# API requirements

- **POL-001:** Return a new dictionary; never mutate the request or nested targets.
- **POL-002:** `name` is required, trimmed, and must remain valid Unicode.
- **POL-003:** `targets` is a required non-empty list of objects containing non-empty `type` and `value` strings.
- **POL-004:** Target types are open-world. Trim outer whitespace on the target `type` and `value` before normalization/dedup, then normalize type to case-folded lowercase; never use a discovered allowlist.
- **POL-005:** De-duplicate targets by case-insensitive `(type, value)` after trimming outer whitespace on `type` and `value`, while preserving first-seen order and the trimmed display spelling of `value`.
