"""
rental_alerts
=============

Failure alerting for the Rental Market Intelligence pipeline.

Kept out of the DAG file because alerting is infrastructure, not pipeline
logic - and because keeping it importable lets it be exercised independently
of the production DAG.

Gmail SMTP settings live in the `smtp_default` Airflow connection, created by
the airflow-init service from docker/.env. The APP PASSWORD is never read by
this module: only SmtpHook touches it, and Airflow's secrets masker keeps it
out of task logs. Sender and recipient come from the environment, so no
address is hardcoded anywhere in source.

If alerting is not configured the callback degrades to log-only. The pipeline
never depends on email being available.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


# Gmail SMTP settings live in the `smtp_default` Airflow connection, created by
# airflow-init from docker/.env. The APP PASSWORD is never read by this module -
# only SmtpHook touches it, and Airflow's secrets masker keeps it out of logs.
# Sender/recipient come from the environment, so no address is hardcoded here.
SMTP_CONN_ID = "smtp_default"
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "").strip()
AIRFLOW_BASE_URL = os.environ.get("AIRFLOW__API__BASE_URL", "http://localhost:8080").rstrip("/")


def _failure_details(context) -> dict[str, str]:
    """Pull everything worth putting in an alert out of the task context."""
    ti = context.get("task_instance")
    dag_obj = context.get("dag")
    dag_id = getattr(dag_obj, "dag_id", "?")
    task_id = getattr(ti, "task_id", "?")
    run_id = context.get("run_id") or getattr(ti, "run_id", "?")

    try_number = getattr(ti, "try_number", None)
    max_tries = getattr(ti, "max_tries", None)
    attempts_allowed = (max_tries + 1) if isinstance(max_tries, int) else None

    log_url = getattr(ti, "log_url", None)
    if not log_url:
        # Airflow 3 UI route, used when the runtime TI does not expose log_url.
        log_url = f"{AIRFLOW_BASE_URL}/dags/{dag_id}/runs/{run_id}/tasks/{task_id}"

    exc = context.get("exception")
    if exc is None:
        exception_text = "(not supplied by Airflow - see task log)"
    else:
        exception_text = f"{type(exc).__name__}: {exc}"
    if len(exception_text) > 2000:
        exception_text = exception_text[:2000] + " ... [truncated]"

    return {
        "dag_id": dag_id,
        "task_id": task_id,
        "run_id": str(run_id),
        "logical_date": str(context.get("logical_date") or context.get("execution_date") or "-"),
        "attempt": (
            f"{try_number} of {attempts_allowed}"
            if try_number is not None and attempts_allowed is not None
            else str(try_number)
        ),
        "exception": exception_text,
        "log_url": log_url,
        "ui_url": f"{AIRFLOW_BASE_URL}/dags/{dag_id}",
    }


def report_failure(context) -> None:
    """Log a failure summary and email it.

    Airflow invokes on_failure_callback ONLY when a task reaches the terminal
    FAILED state. While retries remain the task goes to UP_FOR_RETRY and fires
    on_retry_callback instead (which we deliberately leave unset). So this runs
    exactly once per task, after the last retry is exhausted - no duplicate
    alerts, and no manual attempt-counting needed.

    Applies to @task and @task.bash alike: both are operators underneath, and
    both inherit this through default_args.

    This function never raises. An exception here would fire while Airflow is
    already handling a failure, and could mask the real error.
    """
    d = _failure_details(context)

    log.error(
        "PIPELINE FAILURE | dag=%s task=%s run=%s attempt=%s | check the task "
        "output above: for dbt, a non-zero exit is either a model error or a "
        "severity=error test failure.",
        d["dag_id"], d["task_id"], d["run_id"], d["attempt"],
    )

    if not ALERT_EMAIL_TO:
        log.warning(
            "ALERT_EMAIL_TO is not set - skipping failure email. "
            "Set GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD / ALERT_EMAIL_FROM / "
            "ALERT_EMAIL_TO in docker/.env to enable alerting."
        )
        return

    subject = f"[Airflow FAILURE] {d['dag_id']} :: {d['task_id']}"
    body = (
        "An Airflow task has failed after exhausting all retries.\n"
        "\n"
        f"DAG:             {d['dag_id']}\n"
        f"Task:            {d['task_id']}\n"
        f"Run ID:          {d['run_id']}\n"
        f"Execution date:  {d['logical_date']}\n"
        f"Attempt:         {d['attempt']}\n"
        "Final failure:   YES - all retries exhausted, task is FAILED\n"
        "\n"
        "Exception\n"
        "---------\n"
        f"{d['exception']}\n"
        "\n"
        "Where to look\n"
        "-------------\n"
        f"Log URL:         {d['log_url']}\n"
        f"Airflow UI URL:  {d['ui_url']}\n"
        "\n"
        "Notes\n"
        "-----\n"
        "* Downstream tasks are skipped, so the warehouse is left in its\n"
        "  last-good state. Bronze ingestion is keyed on _source_filename and\n"
        "  dbt models are incremental or full-rebuild, so re-running the DAG\n"
        "  after a fix is safe and will not duplicate data.\n"
    )

    try:
        from airflow.providers.smtp.hooks.smtp import SmtpHook

        with SmtpHook(smtp_conn_id=SMTP_CONN_ID) as smtp:
            smtp.send_email_smtp(to=ALERT_EMAIL_TO, subject=subject, html_content=body)
        log.info("Failure alert email sent for %s.%s", d["dag_id"], d["task_id"])
    except Exception as exc:  # noqa: BLE001
        # Never re-raise from a failure callback.
        log.warning(
            "Could not send failure alert email (%s: %s). The task failure itself "
            "is unaffected; see the PIPELINE FAILURE line above.",
            type(exc).__name__, exc,
        )
