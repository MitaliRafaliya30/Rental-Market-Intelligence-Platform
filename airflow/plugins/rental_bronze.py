"""
rental_bronze
=============

Bronze ingestion helpers for the Rental Market Intelligence pipeline.

Responsibilities
----------------
1. detect_new_snapshot  - list the S3 external stage, work out which files are
                          not yet in Bronze
2. load_dataset         - COPY INTO Bronze for exactly those files
3. validate_bronze      - assert Bronze is readable, non-empty, complete and
                          free of double-ingested files
4. validate_gold        - assert the star schema reconciles after dbt

Everything talks to Snowflake through the Airflow Snowflake provider's
SnowflakeHook, which reads the `snowflake_default` connection. No credential
is referenced in this module or in the DAG.

Design notes worth knowing
--------------------------
* IDEMPOTENCY is keyed on BRONZE.<table>._source_filename. A file is loaded
  iff its name is not already present there. This is deliberately stronger
  than relying on Snowflake's COPY load metadata, which only remembers loads
  for 64 days - after that, a naive re-run would silently duplicate.

* The stage path convention is:
      landing/airbnb/<city_key>/<DD-MM-YYYY>/<dataset>.csv
  The date component is DAY-first. Confirmed against existing data: folder
  `01-08-2025` corresponds to rows with _snapshot_date = 2025-08-01.

* METADATA$FILENAME on this stage yields a path INCLUDING the `landing/`
  prefix (e.g. landing/airbnb/new_york/01-08-2025/listings.csv), which is
  exactly the format already stored in _source_filename. We preserve that, so
  old and new rows remain directly comparable.

* The shared BRONZE.CSV_FORMAT sets PARSE_HEADER=TRUE, which Snowflake does
  not permit together with positional ($1, $2, ...) COPY transformations. A
  transformation is required in order to append the four metadata columns, so
  the COPY supplies an INLINE file format mirroring CSV_FORMAT but with
  SKIP_HEADER=1. MULTI_LINE=TRUE is essential: listings.csv contains embedded
  newlines inside quoted free-text fields.

* Business column ORDER in each Bronze table matches its CSV header exactly
  (verified for all three: 79/79, 6/6, 7/7), so positional mapping is safe.
  Arity is read from information_schema at run time rather than hardcoded.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

log = logging.getLogger(__name__)

SNOWFLAKE_CONN_ID = "snowflake_default"

DATABASE = "RENTAL_MARKET_INTELLIGENCE"
BRONZE_SCHEMA = "BRONZE"
STAGE = DATABASE + "." + BRONZE_SCHEMA + ".S3_LANDING_STAGE1"
STAGE_PREFIX = "airbnb"

# dataset -> target Bronze table
DATASETS: dict[str, str] = {
    "listings": "BRONZE_LISTINGS",
    "reviews": "BRONZE_REVIEWS",
    "calendar": "BRONZE_CALENDAR",
}

METADATA_COLUMNS = ("_SOURCE_FILENAME", "_LOADED_AT", "_SNAPSHOT_DATE", "CITY_KEY")

# Mirrors BRONZE.CSV_FORMAT, except SKIP_HEADER=1 replaces PARSE_HEADER=TRUE so
# that positional transformations are permitted. Declared inline so the shared
# file format object is never altered.
INLINE_CSV_FORMAT = r"""(
        TYPE = CSV
        FIELD_DELIMITER = ','
        RECORD_DELIMITER = '\n'
        SKIP_HEADER = 1
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        NULL_IF = ('', 'NULL', 'null', '\\N')
        EMPTY_FIELD_AS_NULL = TRUE
        TRIM_SPACE = FALSE
        ESCAPE = 'NONE'
        ESCAPE_UNENCLOSED_FIELD = '\\'
        ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
        MULTI_LINE = TRUE
        COMPRESSION = AUTO
        ENCODING = 'UTF8'
        SKIP_BYTE_ORDER_MARK = TRUE
        DATE_FORMAT = AUTO
        TIME_FORMAT = AUTO
        TIMESTAMP_FORMAT = AUTO
    )"""

# landing/airbnb/<city>/<DD-MM-YYYY>/<dataset>.csv
_PATH_RE = re.compile(
    r"(?:^|/)" + STAGE_PREFIX + r"/(?P<city>[^/]+)/(?P<date>\d{2}-\d{2}-\d{4})/(?P<dataset>[^/]+)\.csv$",
    re.IGNORECASE,
)


def _hook() -> SnowflakeHook:
    return SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)


def _q(sql: str, params: Any = None) -> list[tuple]:
    """Run a query and return all rows."""
    return _hook().get_records(sql, parameters=params) or []


def _path_is_safe(value: str) -> bool:
    """Guard for values interpolated into SQL (stage paths, city keys)."""
    return bool(re.fullmatch(r"[A-Za-z0-9_\-./]+", value or ""))


# ---------------------------------------------------------------------------
# 1. detection
# ---------------------------------------------------------------------------
def detect_new_snapshot() -> dict[str, list[dict]]:
    """List the stage, subtract what Bronze already has, return what is pending."""
    hook = _hook()

    # Stage URL, so the absolute s3:// paths LIST returns can be converted into
    # both a stage-relative path and the METADATA$FILENAME form.
    desc = hook.get_records("DESC STAGE " + STAGE) or []
    stage_url = ""
    for row in desc:
        if len(row) > 3 and str(row[1]).upper() == "URL":
            stage_url = str(row[3])
            break
    stage_url = stage_url.strip('[]"')
    if stage_url and not stage_url.endswith("/"):
        stage_url += "/"
    # e.g. s3://bucket/landing/  ->  bucket root is s3://bucket/
    bucket_root = "/".join(stage_url.split("/")[:3]) + "/"
    log.info("Stage %s -> %s", STAGE, stage_url)

    listed = hook.get_records("LIST @" + STAGE + "/" + STAGE_PREFIX + "/") or []
    log.info("Stage listing returned %d object(s)", len(listed))

    # what Bronze already holds
    loaded: dict[str, set[str]] = {}
    for dataset, table in DATASETS.items():
        rows = _q("SELECT DISTINCT _source_filename FROM {}.{}.{}".format(DATABASE, BRONZE_SCHEMA, table))
        loaded[dataset] = {r[0] for r in rows if r[0]}
        log.info("%s already contains %d distinct source file(s)", table, len(loaded[dataset]))

    pending: dict[str, list[dict]] = {d: [] for d in DATASETS}
    skipped = 0

    for row in listed:
        abs_path = str(row[0])  # s3://bucket/landing/airbnb/...
        match = _PATH_RE.search(abs_path)
        if not match:
            log.warning("Ignoring object with unexpected path shape: %s", abs_path)
            continue

        dataset = match.group("dataset").lower()
        if dataset not in DATASETS:
            log.warning("Ignoring unknown dataset '%s' in %s", dataset, abs_path)
            continue

        city_key = match.group("city").lower()
        try:
            snapshot_date = datetime.strptime(match.group("date"), "%d-%m-%Y").date()
        except ValueError:
            log.warning("Ignoring unparseable date folder in %s", abs_path)
            continue

        # METADATA$FILENAME form (includes the 'landing/' prefix)
        if abs_path.startswith(bucket_root):
            source_filename = abs_path[len(bucket_root):]
        else:
            source_filename = abs_path
        # stage-relative form used in the COPY FROM clause
        if stage_url and abs_path.startswith(stage_url):
            stage_path = abs_path[len(stage_url):]
        else:
            stage_path = source_filename

        if source_filename in loaded[dataset]:
            skipped += 1
            log.info("SKIP  already loaded: %s", source_filename)
            continue

        if not (_path_is_safe(stage_path) and _path_is_safe(city_key)):
            raise ValueError("Refusing unsafe stage path or city key: " + abs_path)

        pending[dataset].append(
            {
                "stage_path": stage_path,
                "source_filename": source_filename,
                "city_key": city_key,
                "snapshot_date": snapshot_date.isoformat(),
            }
        )
        log.info("NEW   %s | city=%s | snapshot=%s", source_filename, city_key, snapshot_date)

    total_new = sum(len(v) for v in pending.values())

    # ---- landing-zone inventory, grouped by (city, snapshot) -----------
    inventory: dict[tuple[str, str], list[str]] = {}
    for dataset, items in pending.items():
        for item in items:
            inventory.setdefault((item["city_key"], item["snapshot_date"]), []).append(dataset)

    log.info("=" * 62)
    log.info("LANDING ZONE SCAN")
    log.info("=" * 62)
    log.info("  objects seen in stage        : %d", len(listed))
    log.info("  files already in Bronze      : %d  (skipped)", skipped)
    log.info("  files NEW and to be loaded   : %d", total_new)
    if inventory:
        log.info("  NEW SNAPSHOT(S) DETECTED:")
        for (city, snap), datasets in sorted(inventory.items()):
            log.info("      city=%-12s snapshot=%s  datasets=%s",
                     city, snap, ",".join(sorted(datasets)))
    log.info("=" * 62)

    log.info(
        "Detection complete: %d new file(s) to load, %d already-loaded file(s) skipped.",
        total_new,
        skipped,
    )
    if total_new == 0:
        log.info("Bronze is already current with the landing zone - load tasks will no-op.")

    return pending


# ---------------------------------------------------------------------------
# 2. load
# ---------------------------------------------------------------------------
def _business_column_count(table: str) -> int:
    rows = _q(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %(schema)s AND table_name = %(table)s
          AND UPPER(column_name) NOT IN
              ('_SOURCE_FILENAME', '_LOADED_AT', '_SNAPSHOT_DATE', 'CITY_KEY')
        """,
        {"schema": BRONZE_SCHEMA, "table": table},
    )
    return int(rows[0][0])


def load_dataset(dataset: str, pending_files: dict[str, list[dict]]) -> int:
    """COPY every pending file for one dataset into its Bronze table.

    `pending_files` is the value returned by detect_new_snapshot() and is
    passed in as an ordinary argument - TaskFlow moves it through XCom for us,
    so there is no xcom_pull here.
    """
    pending = (pending_files or {}).get(dataset, [])
    table = DATASETS[dataset]
    fqn = "{}.{}.{}".format(DATABASE, BRONZE_SCHEMA, table)

    if not pending:
        log.info("No new %s file(s) to load - %s is already current. No-op.", dataset, table)
        return 0

    n_business = _business_column_count(table)
    if n_business <= 0:
        raise ValueError("Could not determine business column count for " + fqn)
    log.info("%s has %d business columns (+%d metadata)", fqn, n_business, len(METADATA_COLUMNS))

    # $1..$N positional, then the four metadata columns in table order.
    positional = ", ".join("t.${}".format(i) for i in range(1, n_business + 1))

    hook = _hook()
    total_rows = 0

    for item in pending:
        # One literal timestamp per COPY, so each file maps to exactly one
        # _loaded_at batch. validate_bronze relies on that to detect double loads.
        loaded_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

        sql = """
            COPY INTO {fqn}
            FROM (
                SELECT
                    {positional},
                    METADATA$FILENAME,
                    '{loaded_at}'::TIMESTAMP_NTZ,
                    '{snapshot_date}'::DATE,
                    '{city_key}'
                FROM @{stage}/{stage_path} t
            )
            FILE_FORMAT = {file_format}
            ON_ERROR = 'ABORT_STATEMENT'
            PURGE = FALSE
        """.format(
            fqn=fqn,
            positional=positional,
            loaded_at=loaded_at,
            snapshot_date=item["snapshot_date"],
            city_key=item["city_key"],
            stage=STAGE,
            stage_path=item["stage_path"],
            file_format=INLINE_CSV_FORMAT,
        )

        log.info(
            "COPY INTO %s  <-  %s (city=%s, snapshot=%s)",
            fqn,
            item["stage_path"],
            item["city_key"],
            item["snapshot_date"],
        )
        result = hook.get_records(sql) or []
        for r in result:
            log.info("COPY result: %s", r)
            # rows_loaded is the 4th column of Snowflake's COPY result set
            try:
                total_rows += int(r[3])
            except (IndexError, TypeError, ValueError):
                pass

    log.info("Loaded %s row(s) into %s across %d file(s).", format(total_rows, ","), fqn, len(pending))
    return total_rows


# ---------------------------------------------------------------------------
# 3. Bronze validation
# ---------------------------------------------------------------------------
def validate_bronze(pending_files: dict[str, list[dict]]) -> dict[str, int]:
    """Fail loudly if Bronze is unreadable, empty, incomplete or double-loaded.

    `pending_files` tells us which files THIS run was supposed to load, so we
    can assert they actually landed. Passed in as a normal argument.
    """
    pending_all = pending_files or {}

    failures: list[str] = []
    summary: dict[str, int] = {}

    log.info("=" * 62)
    log.info("BRONZE VALIDATION")
    log.info("=" * 62)

    for dataset, table in DATASETS.items():
        fqn = "{}.{}.{}".format(DATABASE, BRONZE_SCHEMA, table)

        # (a) readable  (b) non-zero
        try:
            count = int(_q("SELECT COUNT(*) FROM " + fqn)[0][0])
        except Exception as exc:  # noqa: BLE001
            failures.append("{}: NOT READABLE ({}: {})".format(table, type(exc).__name__, exc))
            continue

        summary[table] = count
        log.info("%-18s rows=%s", table, format(count, ","))
        if count == 0:
            failures.append(table + ": row count is zero")

        # (c) every file this run was meant to load is actually present
        for item in pending_all.get(dataset, []):
            n = int(
                _q(
                    "SELECT COUNT(*) FROM " + fqn + " WHERE _source_filename = %(f)s",
                    {"f": item["source_filename"]},
                )[0][0]
            )
            if n == 0:
                failures.append(
                    "{}: expected snapshot {} ({}) was not loaded".format(
                        table, item["snapshot_date"], item["source_filename"]
                    )
                )
            else:
                log.info("  loaded this run: %s -> %s rows", item["source_filename"], format(n, ","))

        # (d) no file ingested twice. One COPY writes one _loaded_at literal, so
        #     more than one distinct value for a file means it was loaded twice.
        dupes = _q(
            """
            SELECT _source_filename, COUNT(DISTINCT _loaded_at) AS batches
            FROM {}
            GROUP BY 1
            HAVING COUNT(DISTINCT _loaded_at) > 1
            """.format(fqn)
        )
        for fname, batches in dupes:
            failures.append(
                "{}: DUPLICATE INGESTION - {} loaded in {} batches".format(table, fname, batches)
            )

        # informational: snapshot inventory
        for snap, n in _q("SELECT _snapshot_date, COUNT(*) FROM " + fqn + " GROUP BY 1 ORDER BY 1"):
            log.info("  snapshot %s -> %s rows", snap, format(n, ","))

    if failures:
        for f in failures:
            log.error("BRONZE VALIDATION FAILURE: %s", f)
        raise ValueError(
            "Bronze validation failed with {} problem(s): {}".format(len(failures), failures)
        )

    log.info("Bronze validation passed. %s", summary)
    return summary



# ---------------------------------------------------------------------------
# dbt run summary
# ---------------------------------------------------------------------------
def summarise_dbt_run(target_path: str | None = None) -> dict[str, int]:
    """Read dbt's run_results.json and count node outcomes.

    dbt already prints `Done. PASS=.. WARN=.. ERROR=.. SKIP=..` in the
    dbt_build task log. This lifts the same numbers into the final task so the
    whole pipeline outcome is visible in one place, and returns them as data
    rather than as text buried in a bash log.

    Never raises: a missing or unreadable file just yields an empty summary.
    The authoritative pass/fail signal is dbt's own exit code, which already
    decided whether dbt_build succeeded.
    """
    path = target_path or os.environ.get("DBT_TARGET_PATH", "/opt/airflow/dbt_target")
    results_file = os.path.join(path, "run_results.json")

    buckets = {"PASS": 0, "WARN": 0, "ERROR": 0, "SKIP": 0, "TOTAL": 0}
    try:
        with open(results_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read dbt run_results.json at %s (%s)", results_file, exc)
        return buckets

    # dbt statuses: models -> success/error/skipped, tests -> pass/fail/warn/error/skipped
    mapping = {
        "success": "PASS", "pass": "PASS",
        "warn": "WARN",
        "error": "ERROR", "fail": "ERROR", "runtime error": "ERROR",
        "skipped": "SKIP",
    }
    for node in payload.get("results", []):
        bucket = mapping.get(str(node.get("status", "")).lower())
        if bucket:
            buckets[bucket] += 1
        buckets["TOTAL"] += 1

    return buckets


# ---------------------------------------------------------------------------
# 4. Gold validation
# ---------------------------------------------------------------------------
def validate_gold(bronze_summary: dict[str, int] | None = None) -> dict[str, int]:
    """Post-dbt reconciliation of the star schema, plus the run's final summary.

    These checks mirror the hand-written queries in the repo's analyses/
    directory, promoted into the pipeline so a bad build cannot pass silently.
    dbt's own tests already ran inside `dbt build`; this is the independent
    end-to-end assertion that Gold is coherent with Silver.

    `bronze_summary` is validate_bronze()'s return value, passed straight
    through by TaskFlow so the closing log block can show the whole pipeline -
    Bronze counts, dbt outcome and Gold counts - in one place.
    """
    checks: list[tuple[str, str, str]] = [
        # (name, sql, rule) - rule is 'nonzero' or 'zero'
        ("dim_listing populated",
         "SELECT COUNT(*) FROM {}.GOLD.DIM_LISTING".format(DATABASE), "nonzero"),
        ("fact_listing_snapshot populated",
         "SELECT COUNT(*) FROM {}.GOLD.FACT_LISTING_SNAPSHOT".format(DATABASE), "nonzero"),
        ("fact_daily_availability populated",
         "SELECT COUNT(*) FROM {}.GOLD.FACT_DAILY_AVAILABILITY".format(DATABASE), "nonzero"),
        ("fact_review populated",
         "SELECT COUNT(*) FROM {}.GOLD.FACT_REVIEW".format(DATABASE), "nonzero"),
        ("agg_availability_monthly populated",
         "SELECT COUNT(*) FROM {}.GOLD.AGG_AVAILABILITY_MONTHLY".format(DATABASE), "nonzero"),
        ("fact_daily_availability reconciles with silver_calendar",
         """SELECT ABS(
                (SELECT COUNT(*) FROM {db}.GOLD.FACT_DAILY_AVAILABILITY)
              - (SELECT COUNT(*) FROM {db}.SILVER.SILVER_CALENDAR))""".format(db=DATABASE),
         "zero"),
        ("no orphan listing_sk in fact_listing_snapshot",
         """SELECT COUNT(*) FROM {db}.GOLD.FACT_LISTING_SNAPSHOT f
            LEFT JOIN {db}.GOLD.DIM_LISTING d ON f.listing_sk = d.listing_sk
            WHERE d.listing_sk IS NULL""".format(db=DATABASE),
         "zero"),
        ("exactly one current version per listing",
         """SELECT COUNT(*) FROM (
                SELECT listing_id FROM {db}.GOLD.DIM_LISTING
                WHERE is_current = TRUE
                GROUP BY listing_id HAVING COUNT(*) > 1)""".format(db=DATABASE),
         "zero"),
    ]

    failures: list[str] = []
    results: dict[str, int] = {}

    for name, sql, rule in checks:
        value = int(_q(sql)[0][0])
        results[name] = value
        ok = (value > 0) if rule == "nonzero" else (value == 0)
        log.info("%-52s %-14s %s", name, format(value, ","), "OK" if ok else "FAIL")
        if not ok:
            failures.append(
                "{}: got {}, expected {}".format(name, value, "> 0" if rule == "nonzero" else "0")
            )

    if failures:
        for f in failures:
            log.error("GOLD VALIDATION FAILURE: %s", f)
        raise ValueError(
            "Gold validation failed with {} problem(s): {}".format(len(failures), failures)
        )

    log.info("Gold validation passed.")

    # ---- one consolidated end-of-pipeline summary ----------------------
    dbt_summary = summarise_dbt_run()
    log.info("=" * 62)
    log.info("PIPELINE SUMMARY")
    log.info("=" * 62)
    log.info("  BRONZE row counts:")
    for table, count in sorted((bronze_summary or {}).items()):
        log.info("      %-24s %14s", table, format(count, ","))
    log.info("  dbt result:")
    log.info(
        "      PASS=%d  WARN=%d  ERROR=%d  SKIP=%d  TOTAL=%d",
        dbt_summary["PASS"], dbt_summary["WARN"], dbt_summary["ERROR"],
        dbt_summary["SKIP"], dbt_summary["TOTAL"],
    )
    log.info("  GOLD validation: all %d checks passed", len(results))
    for name, value in results.items():
        log.info("      %-52s %12s", name, format(value, ","))
    log.info("=" * 62)

    return results
