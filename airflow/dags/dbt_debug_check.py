"""
dbt_debug_check
===============

Phase 1A smoke test. Its ONLY purpose is to prove that the containerised
Airflow environment can reach Snowflake through the existing, unmodified
dbt project.

It runs exactly one command:

    dbt debug --profiles-dir /opt/airflow/dbt

What a green run proves:
  - the dbt project is mounted and parseable inside the container
  - profiles.yml resolves all six SNOWFLAKE_* env vars injected by compose
  - the account authenticates, and the role / database / warehouse are usable

This DAG deliberately does NOT run `dbt build`, `dbt run`, `dbt seed` or
`dbt snapshot`. It writes nothing to Snowflake - `dbt debug` only issues a
connectivity check. Scheduling is disabled; trigger it manually.
"""

from __future__ import annotations

import os
import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Absolute path: dbt lives in its own virtualenv, not on PATH.
DBT_BIN = os.environ.get("DBT_BIN", "/opt/dbt_venv/bin/dbt")
DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/dbt")

with DAG(
    dag_id="dbt_debug_check",
    description="Phase 1A smoke test: dbt debug against Snowflake",
    start_date=pendulum.datetime(2025, 8, 1, tz="UTC"),
    schedule=None,          # manual trigger only
    catchup=False,
    max_active_runs=1,
    tags=["phase-1a", "smoke-test", "dbt"],
    doc_md=__doc__,
) as dag:

    dbt_debug = BashOperator(
        task_id="dbt_debug",
        # cwd is the read-only project; target/ and logs/ are redirected
        # to named volumes via DBT_TARGET_PATH / DBT_LOG_PATH.
        cwd=DBT_PROJECT_DIR,
        bash_command=(
            f"{DBT_BIN} debug "
            f"--profiles-dir {DBT_PROJECT_DIR} "
            f"--project-dir {DBT_PROJECT_DIR}"
        ),
        # env is not passed explicitly, so the task inherits the container
        # environment - including the SNOWFLAKE_* vars from compose env_file.
        # Nothing is echoed: dbt never prints the password.
    )
