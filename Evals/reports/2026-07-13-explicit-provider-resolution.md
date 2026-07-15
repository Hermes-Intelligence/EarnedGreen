# Explicit Provider Resolution and Minimum-Cost Next Step

- Generated: 2026-07-13T15:11:00+02:00
- Expires: 2026-07-20T15:10:46.4282540+02:00
- Verdict: **PASS**
- Stable rules changed: **No**
- Additional provider calls: **0**

## Resolved selectors

| Provider | Explicit model | Effort | Evidence |
|---|---|---|---|
| Codex | `gpt-5.6-sol` | medium | Official default Power model; present at priority 1 in today's CLI 0.144.3 cache |
| Claude | `claude-opus-4-8` | medium | Reported by the clean smoke; supported by installed CLI 2.1.207 and documented as a fixed full model ID |

The Codex resolution is authoritative for **future explicit runs**. It does not rewrite history or claim that the earlier anonymous `provider-default` calls definitely used Sol. Claude's model is directly supported by retained provider-event evidence.

Official sources:

- [OpenAI Codex models](https://developers.openai.com/codex/models)
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config)
- [Claude model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)

## Why these models

The next harness calibration should preserve the frontier capability regime used by the smoke. `gpt-5.6-terra`, `gpt-5.6-luna`, Claude Sonnet and Fable remain useful future routing lanes, but switching capability tiers now would confound model quality with harness quality.

## Minimum-cost calibration

Run only two explicitly approved calls:

| Fixture | Provider | Model | Arms | Maximum calls |
|---|---|---|---|---:|
| `database-migration-rollback` | Codex | `gpt-5.6-sol`, medium | vanilla and full | 2 |

This fixture is selected because its full arm deterministically routes `database-migration`, `change-impact` and `security-boundaries`. It exercises reversibility, idempotence, schema preservation and data integrity, making another universal 100/100 less likely than the entity parser.

The probe is screening-only and excluded from publishable confirmatory scores:

- Both arms score 100: stop; declare another ceiling and redesign a harder fixture. Spend zero Claude calls.
- Scores differ: inspect the exact checks, then request separate approval for a balanced four-cell confirmation.
- Equal scores below 100: stop and inspect the shared failure mode or grader alignment.
- Infrastructure failure: invalidate; any replacement requires separate human approval.

## Router finding

The `prompt-injection-repo` fixture exposed a separate routing miss: trusted/untrusted instruction-boundary language did not select `security-boundaries`. This must become a candidate regression and pass evaluation before any Stable promotion. It is not silently fixed as part of this benchmark step.

Structured JSON beside this document is the source of truth. No benchmark call has been authorized by this report.
