# Database schema available to the pipeline

Two servers. Connection strings come from the environment.

## Workspace database — `DATABASE_URL`

Schema `vextrum_v0`:

| table | columns (the ones the pipeline uses) |
|---|---|
| `uds_selection_criteria` | `id`, `workspace_id`, `source_types`, `topic_tags`, `keyword_patterns`, `min_authority_level`, `geo_filter`, `is_active` |
| `materialization_watermark` | `workspace_id` (PK), `last_as_of`, `updated_at` |
| `event_records` | `id`, `workspace_id`, `uds_event_id`, `selection_criteria_id`, `title`, `event_timestamp`, `summary`, `description`, `event_natural_id`, `data_source_type`, `data_source_name`, `authority_level`, `topic_tags`, `materialized_at` — unique on `(workspace_id, uds_event_id)` |
| `execution_runs` | `id`, `workspace_id`, `config_id`, `config_version`, `status`, `event_records_planned`, `event_records_processed`, `started_at`, `completed_at` |
| `records_data_operations_steps` | `id`, `event_record_id`, `component_id`, `execution_run_id`, `component_type`, `component_version`, `config_version`, `workspace_config_hash`, `status`, `result_code`, `output_data`, `completed_at` |
| `data_operations_configurations` | `id`, `workspace_id`, `version`, `is_active`, `created_at` |
| `data_operations_components` | `id`, `config_id`, `component_type`, `component_version`, `parameters` |
| `data_operations_edges` | `config_id`, `from_component_id`, `to_component_id` |
| `client_config_*`, `client_ontology_*`, `operating_specs` | `id`, `version`, `workspace_id` (read by `config_hash.py`) |

## UDS database — `UDS_DATABASE_URL`

Schema `uds` (read-only for the pipeline; reads are metered):

| table | columns |
|---|---|
| `events` | `id`, `data_source_id`, `title`, `event_timestamp`, `summary`, `description`, `event_natural_id`, `topic_tags`, `as_of_hermes_intelligence` (monotone ingestion time) |
| `data_sources` | `id`, `source_type`, `source_name`, `authority_level` |

Statements use the psycopg2 `%s` parameter style. Column aliases in your SQL
are yours to choose; the tables and columns above are what exists.
