# syntax=docker/dockerfile:1
#
# Rental Market Intelligence Platform - Airflow + dbt image
# ---------------------------------------------------------
# Phase 1A: foundation only. No Cosmos, no ingestion dependencies.
#
# Design note: dbt is installed into its OWN virtualenv (/opt/dbt_venv)
# rather than into Airflow's site-packages. Airflow and dbt-core both pin
# large, overlapping dependency trees (jinja2, pydantic, protobuf,
# packaging). Sharing one environment makes every future Airflow upgrade a
# dbt-compatibility problem. Isolating dbt means the two can be upgraded
# independently, and it is the same pattern Cosmos uses when we adopt it.
#
# dbt is therefore invoked by ABSOLUTE PATH ($DBT_BIN), never as a bare
# `dbt` on PATH.

ARG AIRFLOW_VERSION=3.1.2
ARG PYTHON_VERSION=3.12

FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

# Pinned to match the versions already proven against this warehouse
# (see uv.lock / pyproject.toml in the repo root).
ARG DBT_CORE_VERSION=1.11.12
ARG DBT_SNOWFLAKE_VERSION=1.11.6
ARG SNOWFLAKE_CONNECTOR_VERSION=4.7.1

USER root

# The dbt project is mounted READ-ONLY, so every path dbt wants to write to
# must live outside it. These MUST be created here, owned by airflow: a named
# volume mounted over a path that does not exist in the image is created
# root-owned, and the container runs as uid 50000.
#
#   dbt_work    - writable copy of the project that dbt actually runs from
#                 (`dbt deps` needs write access on the project root itself)
#   dbt_target  - DBT_TARGET_PATH
#   dbt_logs    - DBT_LOG_PATH
RUN mkdir -p /opt/dbt_venv \
             /opt/airflow/dbt_work \
             /opt/airflow/dbt_target \
             /opt/airflow/dbt_logs \
 && chown -R airflow:root /opt/dbt_venv \
                          /opt/airflow/dbt_work \
                          /opt/airflow/dbt_target \
                          /opt/airflow/dbt_logs

USER airflow

RUN python -m venv /opt/dbt_venv \
 && /opt/dbt_venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/dbt_venv/bin/pip install --no-cache-dir \
        "dbt-core==${DBT_CORE_VERSION}" \
        "dbt-snowflake==${DBT_SNOWFLAKE_VERSION}" \
        "snowflake-connector-python==${SNOWFLAKE_CONNECTOR_VERSION}" \
 && /opt/dbt_venv/bin/dbt --version

# NOTE: DBT_PACKAGES_INSTALL_PATH is deliberately absent - dbt 1.11.12 does
# not honour it. `dbt deps` always writes to <project>/dbt_packages, which is
# why the DAG runs dbt from DBT_WORK_DIR rather than the read-only mount.
ENV DBT_VENV_PATH=/opt/dbt_venv \
    DBT_BIN=/opt/dbt_venv/bin/dbt \
    DBT_PROJECT_DIR=/opt/airflow/dbt \
    DBT_PROFILES_DIR=/opt/airflow/dbt \
    DBT_WORK_DIR=/opt/airflow/dbt_work \
    DBT_TARGET_PATH=/opt/airflow/dbt_target \
    DBT_LOG_PATH=/opt/airflow/dbt_logs
