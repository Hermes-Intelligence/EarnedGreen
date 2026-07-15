# Model Capability Router

Stable policy selects a capability profile, never a volatile model ID. Provider catalogs are refreshable data caches with an expiry date and official provenance. A recommendation is scoped to one session, task or subagent; it must not silently persist a user's default model.

## Decision order

1. Respect an explicit user model or effort choice.
2. Enforce the task's risk floor and required capabilities.
3. Select a stable capability profile.
4. Resolve it against the provider's current, allowed and available catalog.
5. Record provider, requested selector, resolved model, effort, fallback and catalog timestamp in the workstream/eval evidence.
6. If the catalog is expired or availability is unknown, recommend refresh or a provider-native current alias; do not invent an ID.

Automatic switching remains recommendation-only until repository A/B evals show better outcome quality after accounting for cost and latency.

## Refresh and promotion

Weekly research may propose a refreshed provider catalog inside a candidate package. Stable mappings change only after official-source verification, routing tests and outcome evals. Current official sources include [OpenAI models](https://developers.openai.com/api/docs/models), [Anthropic model overview](https://platform.claude.com/docs/en/about-claude/models/overview) and [Claude Code model configuration](https://code.claude.com/docs/en/model-config).
