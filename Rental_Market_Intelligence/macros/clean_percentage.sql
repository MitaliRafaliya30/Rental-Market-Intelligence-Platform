{#
    Turns a percentage string into a number on a 0-100 scale.

    Phase 3 issue: L2 (severity: medium)
    Used by: host_response_rate, host_acceptance_rate

    "100%" -> 100.00
    "0%"   -> 0.00
    NULL   -> NULL

    Scale decision: we keep 0-100, not 0-1.
    Reason: it matches what the source meant, and the _pct
    suffix on the column name makes the scale obvious.
#}

{% macro clean_percentage(column_name) %}
    TRY_TO_NUMBER(
        REPLACE(CAST({{ column_name }} AS VARCHAR), '%', '')
    )
{% endmacro %}