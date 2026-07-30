"""Thin daily run shells and the production run order.

Shells stay thin by design (the Airflow-style pattern): fetch cadence and
retries live with ops; ORDER lives in registry.RUN_ORDER.
"""
