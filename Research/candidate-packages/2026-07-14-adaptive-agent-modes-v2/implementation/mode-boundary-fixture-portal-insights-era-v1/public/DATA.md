# Database surface available to the insights layer

PostgreSQL, reached exclusively through `hermes_intelligence.db`
(`read_single_record(sql, params)` / `read_multiple_records(sql, params)` →
dict rows; RealDictCursor semantics, `%s` paramstyle). The insights layer is
read-only.

| table | columns the layer uses |
|---|---|
| `vextrum.discovery_runs` | `id` (portal UUID), `pipeline_run_id` (nullable UUID — analytics tables key on its STRING form), `run_type`, `follow_up_of`, `result_summary` (JSONB or JSON string), `portfolio_analysis`, `tag_taxonomy`, `strategic_briefing`, `coverage_matrix` (JSONB) |
| `vextrum.sources` | `run_id` (str(pipeline_run_id)), `domain`, `title`, `reasoning`, `source_type`, `is_relevant`, `priority_label`, `strategic_questions_served` (int[]), `country`, `source_tier` (int), `intelligence_function`, `content_originality`, `bucket_label`, `topics` (text[]), `config_tags` (JSONB), `viability_score` (numeric), plus `id`, `created_at` |
| `vextrum.source_buckets` | `run_id`, `bucket_label`, `source_count`, `coverage_pct` (numeric), `question_coverage` (JSONB), `geographic_assessment`, `geographic_flags` (list), `quality_gate` (JSONB), `builder_method`, `llm_calls_used` (int) |
| `vextrum.question_source_matrix` | `run_id`, `question_number`, `domain`, `bucket_label`, `strength`, `reasoning` |
| `webpage.organizations` | `id`, `name`, `vextrum_access`, `is_internal` (auth gate) |

Notes: SQL numerics arrive as `Decimal`, timestamps as `datetime`, ids as
`UUID` — payload serialization is the layer's job. Authentication and access
control are infrastructure seams (`hermes_intelligence.auth`,
`hermes_intelligence.access_control`) — consume, don't modify.
