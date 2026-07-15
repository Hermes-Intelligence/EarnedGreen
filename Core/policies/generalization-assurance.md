# Generalization Assurance

Apply to parsers, discovery, extraction, classification, mapping, regexes, providers, integrations and any behavior inferred from examples.

## Required decision

Classify the value universe:

- **Closed-world:** the complete set is defined by an authoritative protocol, schema or domain invariant. Record that source and test completeness or upstream drift.
- **Open-world:** new values can appear. Do not encode observed values as the universe. Provide an unknown path, data/schema-driven extension and useful telemetry.

## Required challenges

- Test values absent from initial discovery and development fixtures.
- Test empty, malformed, reordered, duplicated, mixed-case and Unicode inputs where applicable.
- For regexes, test long inputs, multiline behavior, escaping, false positives and catastrophic backtracking risk.
- Prefer property, generative or metamorphic assertions when examples cannot span the input class.
- Keep evaluation fixtures independent of implementation fixtures.

## Suspicious patterns

- Large literal lists created from discovery output.
- Long regex alternations mirroring observed examples.
- Repeated `if value == ...` branches without a domain invariant.
- No behavior for unknown values.
- Tests containing exactly the same universe as production code.

Hardcoding a real constant is allowed. It must be named, isolated, traceable to an authoritative source and tested for the intended invariant.
