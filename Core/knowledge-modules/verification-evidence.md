# Verification and Evidence

Select checks from the risk and changed surface; do not run ceremonial commands that prove nothing.

Record:

- command or observation,
- exit status or explicit verdict,
- what behavior it proves,
- what remains unverified,
- environment and relevant version.

Use compile/typecheck to catch undefined symbols and invalid imports, focused tests for local behavior, wider tests for regressions and runtime observation at the public surface. Tests written from the same examples as the implementation do not prove generalization. Existing failures and skipped checks must be reported, never hidden.

Verdicts are `PASS`, `FAIL`, `BLOCKED` or `NOT_APPLICABLE`. `PASS` requires evidence.
