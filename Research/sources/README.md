# Durable Source Registry

`registry.json` contains reviewed seed sources. `claude-v1-migration.json` is the complete, mechanically recovered inventory of links found by Claude's first run. Migrated entries remain `pending-review` until a research candidate checks availability, provenance, relevance, date and the exact claims they support.

Research loads and de-duplicates both files by normalized URL. Discovery history is evidence of where a source came from, not evidence that its claims are true.

## Evidence tiers

1. Official docs, changelogs and authoritative product repositories.
2. Primary papers, benchmarks, standards and original empirical studies.
3. Production postmortems and engineering reports with inspectable methods.
4. YouTube, conference talks and podcasts with dates/transcripts.
5. Practitioner blogs and social profiles used as discovery signals.

Tier 4–5 material may create a hypothesis or point to a primary source. It cannot alone define a version-sensitive config key, security guarantee or mandatory stable policy.

## Lifecycle

- Preserve a normalized URL, stable source ID, type, tier, topics, status, `last_checked` and `next_check`.
- A run rechecks due active sources first, then performs bounded discovery for genuinely new sources.
- New URLs are proposed in `source-registry.patch.json`; research does not edit the stable registry directly.
- Keep stale, superseded and retired sources for history. Do not delete them to make the registry look current.
- Record redirects and replacements explicitly.
