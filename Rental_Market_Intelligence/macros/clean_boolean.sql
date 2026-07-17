{#
    Turns the source's t/f text into a real boolean.

    Phase 3 issue: L3 (severity: medium)
    Used by: host_is_superhost, host_identity_verified,
             instant_bookable, calendar.available

    't'  -> TRUE
    'f'  -> FALSE
    NULL -> NULL   (unknown stays unknown - we do not guess FALSE)
    'x'  -> NULL   (anything unexpected becomes null, not a crash)

    LOWER and TRIM protect against ' T ' if the source ever changes.
#}

{% macro clean_boolean(column_name) %}
    CASE
        WHEN LOWER(TRIM({{ column_name }})) = 't' THEN TRUE
        WHEN LOWER(TRIM({{ column_name }})) = 'f' THEN FALSE
        ELSE NULL
    END
{% endmacro %}