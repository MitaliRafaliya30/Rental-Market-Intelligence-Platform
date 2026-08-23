"""
rental_market_intelligence_pipeline
===================================

    S3 landing  ->  Bronze  ->  Silver  ->  Snapshots  ->  Gold  ->  tests
                        ^^^^^^^^^^^^ this DAG ^^^^^^^^^^^^

Written with the Airflow TaskFlow API (@dag / @task), so the whole pipeline is
eight Python functions called in order. Data moves between tasks as ordinary
return values and arguments; Airflow stores them in XCom behind the scenes.

Read the `pipeline()` function at the bottom and you have the entire
orchestration.

What each stage does
--------------------
  detect_new_snapshot   which S3 files are not in Bronze yet?
  load_bronze_*         COPY those files into Bronze (one task per dataset)
  validate_bronze       gate: is Bronze readable, complete and un-duplicated?
  dbt_deps              install dbt packages
  dbt_build             Silver -> snapshots -> Gold, plus all dbt tests
  validate_gold         gate: does the star schema reconcile with Silver?

Bronze ingestion
----------------
Files land in S3 under `landing/airbnb/<city>/<DD-MM-YYYY>/<dataset>.csv` and
reach Snowflake through the pre-existing external stage
BRONZE.S3_LANDING_STAGE1 (storage integration AWS_S3_SNF). Neither is created
or altered here - both are reused as-is.

Ingestion is incremental and idempotent: detect_new_snapshot diffs the stage
listing against the `_source_filename` values already in Bronze, and only
genuinely new files are COPYed. Running this DAG when S3 holds nothing new is
a no-op, so it is always safe to re-run.

The mechanics live in airflow/plugins/rental_bronze.py.

Transformation
--------------
One `dbt build` rather than a task per layer: dbt already derives the correct
order from its own manifest (seeds -> silver -> snapshots -> gold), running
each model's tests right after it. Splitting that across Airflow tasks would
mean maintaining a second copy of an ordering dbt computes for free.

Scheduling
----------
  schedule         "0 6 5 * *"  - 06:00 UTC on the 5th of each month
  catchup          False
  max_active_runs  1

Inside Airbnb publishes one snapshot per city per month and every
`_snapshot_date` we hold is the 1st of a month, so the cadence is monthly. We
run on the 5th rather than the 1st because the scrape is published during the
month and then still has to reach our S3 landing zone; the 5th buys a few days
of slack. Running early costs nothing - with no new files the run is a no-op.

catchup is False, and that is a correctness decision rather than a preference.
This pipeline is not partitioned by logical date: `_snapshot_date` is parsed
from the S3 object path, never from Airflow's execution date. A backfill run
dated 2025-10-05 would therefore not reprocess October - it would re-scan the
same live landing zone as every other run. Enabling catchup would queue one
run per month since start_date; none could corrupt anything (ingestion is
keyed on `_source_filename`), but each would pointlessly rebuild all of Gold.
Backfills here mean putting older files in S3, not replaying Airflow dates.

max_active_runs=1 keeps two runs from COPYing into Bronze or rebuilding Gold
at the same time.

Idempotency / retry safety
--------------------------
Retries are safe end to end:
  - ingestion skips files already recorded in `_source_filename`
  - silver_listings / silver_calendar : incremental, delete+insert on an
    explicit unique_key, filtered by a `_snapshot_date > max(...)` watermark
  - silver_reviews                    : append, filtered by review_id already
                                        present
  - snap_listing / snap_host          : same watermark, so a re-run creates no
                                        spurious SCD2 versions
  - gold models                       : materialized as tables, fully rebuilt

Credentials
-----------
Two consumers, one source of truth, zero secrets in code:

  * dbt            - reads SNOWFLAKE_* environment variables (injected by
                     docker-compose from the gitignored repo-root .env) via the
                     existing profiles.yml env_var() calls.
  * Airflow tasks  - use the `snowflake_default` Airflow connection, created by
                     the airflow-init service from those same environment
                     variables and stored Fernet-encrypted in the metadata DB.

Nothing is hardcoded here or in rental_bronze.py, and dbt never echoes the
password.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task

import rental_bronze
from rental_alerts import report_failure

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# dbt locations
# --------------------------------------------------------------------------
# dbt lives in its own virtualenv (see docker/Dockerfile) and is NOT on PATH.
DBT_BIN = os.environ.get("DBT_BIN", "/opt/dbt_venv/bin/dbt")

# SRC is the real repo, mounted read-only - the source of truth.
# WORK is a writable copy that dbt actually executes from.
#
# Why the copy: `dbt deps` rmtree()s and recreates <project>/dbt_packages,
# which requires write permission on the project ROOT, not just on that
# subdirectory - so no nested-mount trick makes it work against a :ro
# project. dbt 1.11.12 also ignores DBT_PACKAGES_INSTALL_PATH. Copying is
# the standard resolution: dbt gets a normal writable project, while the
# repo stays byte-for-byte untouchable by Airflow.
DBT_SRC = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/dbt")
DBT_WORK = os.environ.get("DBT_WORK_DIR", "/opt/airflow/dbt_work")

# Every dbt invocation gets the same location flags. --no-use-colors keeps ANSI
# escapes out of the Airflow task log, which otherwise makes it hard to read.
DBT_FLAGS = f"--profiles-dir {DBT_WORK} --project-dir {DBT_WORK} --no-use-colors"

# Refresh the working copy from the read-only source on every run, so a run
# can never pick up stale project files from a previous one. target/ and
# logs/ live on their own volumes, so they are not affected.
SYNC_PROJECT = (
    f"echo 'Syncing dbt project: {DBT_SRC} -> {DBT_WORK}'; "
    f"find {DBT_WORK} -mindepth 1 -maxdepth 1 -exec rm -rf {{}} +; "
    f"cp -r {DBT_SRC}/. {DBT_WORK}/; "
)


# Failure alerting lives in airflow/plugins/rental_alerts.py. report_failure is
# wired into default_args below, so every task - @task and @task.bash alike -
# inherits it. Airflow calls on_failure_callback only once a task reaches the
# terminal FAILED state, so exactly one email is sent after retries run out.


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
    "on_failure_callback": report_failure,
}


# ==========================================================================
# Tasks
# ==========================================================================
@task(execution_timeout=timedelta(minutes=10))
def detect_new_snapshot() -> dict[str, list[dict]]:
    """Work out which S3 files are not in Bronze yet.

    Returns a {dataset: [file, ...]} mapping. Returning nothing is a valid
    outcome, not a failure - it just means Bronze is already current.
    """
    return rental_bronze.detect_new_snapshot()


@task(execution_timeout=timedelta(minutes=30))
def load_bronze_listings(pending_files: dict[str, list[dict]]) -> int:
    """Load newly detected listings files into BRONZE_LISTINGS. Returns rows loaded."""
    return rental_bronze.load_dataset("listings", pending_files)


@task(execution_timeout=timedelta(minutes=30))
def load_bronze_reviews(pending_files: dict[str, list[dict]]) -> int:
    """Load newly detected reviews files into BRONZE_REVIEWS. Returns rows loaded."""
    return rental_bronze.load_dataset("reviews", pending_files)


@task(execution_timeout=timedelta(minutes=45))
def load_bronze_calendar(pending_files: dict[str, list[dict]]) -> int:
    """Load newly detected calendar files into BRONZE_CALENDAR. Returns rows loaded."""
    return rental_bronze.load_dataset("calendar", pending_files)


@task(execution_timeout=timedelta(minutes=15))
def validate_bronze(
    pending_files: dict[str, list[dict]],
    listings_rows: int,
    reviews_rows: int,
    calendar_rows: int,
) -> dict[str, int]:
    """Gate before dbt: refuse to transform a Bronze layer we do not trust.

    Checks that all three tables are readable and non-empty, that every file
    this run intended to load actually landed, and that no source file was
    ingested more than once.

    The three row-count arguments are what make this task wait for the loads -
    that is the whole dependency mechanism, no `>>` needed.
    """
    log.info(
        "Rows loaded this run - listings=%s reviews=%s calendar=%s",
        f"{listings_rows:,}", f"{reviews_rows:,}", f"{calendar_rows:,}",
    )
    return rental_bronze.validate_bronze(pending_files)


@task.bash(execution_timeout=timedelta(minutes=10), cwd=DBT_WORK)
def dbt_deps() -> str:
    """Refresh the working copy, then install the packages pinned in package-lock.yml.

    dbt_utils supplies macros the Gold models depend on: generate_surrogate_key,
    date_spine and unique_combination_of_columns.
    """
    return (
        "set -euo pipefail; "
        + SYNC_PROJECT
        + "echo 'Resolving dbt packages...'; "
        + f"{DBT_BIN} deps {DBT_FLAGS}"
    )


@task.bash(execution_timeout=timedelta(minutes=60), cwd=DBT_WORK)
def dbt_build() -> str:
    """Run the whole warehouse: seeds, Silver, snapshots, Gold and every dbt test.

    dbt derives the order from its own manifest:
        seed city_config
          -> silver_listings / silver_calendar / silver_reviews (+ tests)
          -> snap_listing / snap_host
          -> dim_* / fact_* / agg_* (+ tests)

    Exit codes: 0 = success (warn-severity tests may still have fired),
    1 = a model failed or a severity=error test failed, 2 = fatal. Anything
    non-zero fails the task, which is what we want.
    """
    return (
        "set -euo pipefail; "
        "echo 'Building Silver -> snapshots -> Gold, with tests, in dbt DAG order...'; "
        f"{DBT_BIN} build {DBT_FLAGS}"
    )


@task(execution_timeout=timedelta(minutes=15))
def validate_gold(bronze_summary: dict[str, int]) -> dict[str, int]:
    """Independent check that Gold is coherent with Silver, plus the run summary.

    dbt's own tests already ran inside `dbt build`; this adds the end-to-end
    assertions: row-count reconciliation, no orphan surrogate keys, and the
    SCD2 one-current-version-per-listing invariant.

    It also emits the PIPELINE SUMMARY block - Bronze counts, dbt
    PASS/WARN/ERROR/SKIP and Gold counts together - so one glance at the last
    task tells you how the whole run went.
    """
    return rental_bronze.validate_gold(bronze_summary)


# ==========================================================================
# The pipeline
# ==========================================================================
@dag(
    dag_id="rental_market_intelligence_pipeline",
    description="Monthly: S3 -> Bronze -> dbt (Silver/Gold) -> validation. Incremental and idempotent.",
    default_args=default_args,
    start_date=pendulum.datetime(2025, 8, 1, tz="UTC"),
    # ---------------- SCHEDULE ----------------
    # Inside Airbnb publishes one snapshot per city per month, and every
    # _snapshot_date we hold is the 1st of a month. We deliberately do NOT run
    # at 00:00 on the 1st: the scrape is published during the month and then
    # has to reach our S3 landing zone. Running on the 5th at 06:00 UTC gives
    # that pipeline a few days of slack.
    #
    # Being early is harmless anyway - if the file has not landed,
    # detect_new_snapshot finds nothing and the whole run is a cheap no-op.
    schedule="0 6 5 * *",

    # ---------------- CATCHUP ----------------
    # MUST stay False. This pipeline is NOT partitioned by logical date:
    # `_snapshot_date` is parsed from the S3 object path, never from Airflow's
    # execution date. A backfill run for, say, 2025-10-05 would therefore not
    # reprocess October - it would just re-scan the same live landing zone.
    #
    # With catchup=True, unpausing would immediately queue one run per month
    # since start_date. They could not corrupt anything (ingestion is keyed on
    # _source_filename, so nothing reloads), but each one would pointlessly
    # rebuild the full Gold layer. So: no catchup, and backfills are done by
    # dropping files into S3, not by manipulating Airflow dates.
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=90),
    tags=["rental-market-intelligence", "dbt", "snowflake", "production"],
    doc_md=__doc__,
)
def rental_market_intelligence_pipeline():
    """The whole orchestration, top to bottom."""

    # 1. What is new in S3?
    pending_files = detect_new_snapshot()

    # 2. Load it. Passing `pending_files` into each loader is what makes them
    #    depend on detection - Airflow reads the arguments and wires the graph.
    listings_result = load_bronze_listings(pending_files)
    reviews_result = load_bronze_reviews(pending_files)
    calendar_result = load_bronze_calendar(pending_files)

    # Keep the three loads SEQUENTIAL. They have no data dependency on each
    # other, so Airflow would happily run them at once - but calendar alone is
    # ~13M rows per snapshot, and three concurrent COPY INTO statements make a
    # single Snowflake warehouse contend with itself. Delete this one line to
    # get parallel loads.
    listings_result >> reviews_result >> calendar_result

    # 3. Gate before transforming. Depends on all three loads, because it takes
    #    all three return values as arguments.
    bronze_summary = validate_bronze(
        pending_files,
        listings_result,
        reviews_result,
        calendar_result,
    )

    # 4. Transform, then verify. These take no arguments from each other, so
    #    the order is stated explicitly.
    deps = dbt_deps()
    build = dbt_build()

    # validate_gold consumes the Bronze summary, so it already depends on
    # validate_bronze. The explicit chain below is what forces dbt to run
    # BETWEEN them - without it, Airflow would see no reason to wait for dbt.
    gold_summary = validate_gold(bronze_summary)

    bronze_summary >> deps >> build >> gold_summary


rental_market_intelligence_pipeline()
