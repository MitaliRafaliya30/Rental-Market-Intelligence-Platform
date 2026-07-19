{#
    Turns a price string into a number.

    Source stores price as text with a dollar sign and commas: "$1,250.00"
    Phase 3 issue: L1 (severity: high)

    "$260.00"   -> 260.00
    "$1,250.00" -> 1250.00
    NULL        -> NULL
    "abc"       -> NULL  (TRY_ returns null instead of failing the run)

    Precision is fixed at DECIMAL(10,2) here on purpose.
    SCD2 compares this value across snapshots. If precision varied,
    260.00 vs 260.0 would look like a change when nothing changed.
#}

{% macro clean_price(col_name) %}
    TRY_TO_NUMBER(
        REPLACE(REPLACE(CAST({{ col_name }} AS VARCHAR), '$', ''), ',', '')
    )
{% endmacro %}