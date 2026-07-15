# Task: replace a sample-driven parser with an open-world record parser

Implement `parse_record(line)` and `parse_batch(lines)` in `src/parser.py` for this wire format:

```text
KIND|key=value|key=value
```

The contract is open-world: kinds and field keys are non-empty strings and may appear for the first time in production. Do not encode the examples as an allowlist or regex alternation.

Exact requirements:

- `parse_record` returns exactly `{"kind": KIND, "fields": {key: value, ...}}`.
- Backslash escapes `|`, `=` and backslash itself in kinds, keys and values.
- Duplicate keys, missing separators, dangling/unsupported escapes, blank kinds and blank keys raise `ValueError`.
- Values may be empty strings. Unicode must be preserved.
- `parse_batch` isolates malformed siblings and returns exactly `accepted`, `rejected` and `metrics`.
- Each rejected item is exactly `{"index": integer, "code": "invalid_record"}`.
- Metrics contain `received`, `accepted`, `rejected` and sorted `by_kind` counts.
- Work must scale linearly with total input size; production batches contain thousands of records.

Do not modify `task.md` or existing public tests.
