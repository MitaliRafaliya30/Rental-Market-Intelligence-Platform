{#
    Pulls the bathroom count out of bathrooms_text.

    Phase 3 issues: L9, L22 (severity: medium)

    Why we do this: the numeric 'bathrooms' column is 40.81% null,
    but 'bathrooms_text' is only 0.35% null. Parsing the text
    recovers 14,730 listings - 40.5% of the dataset - that a
    naive pipeline silently loses.

    Verified vocabulary (34 distinct values, all covered):
      "1 bath"            -> 1
      "2.5 baths"         -> 2.5
      "1 shared bath"     -> 1
      "0 shared baths"    -> 0     (real - source says zero in words)
      "Half-bath"         -> 0.5
      "Private half-bath" -> 0.5
      "Shared half-bath"  -> 0.5
      "" (empty)          -> NULL

    Half-bath check comes first because those values have no digits.
#}

{% macro parse_bathrooms(column_name) %}
    CASE
        WHEN {{ column_name }} IS NULL
             OR TRIM({{ column_name }}) = ''
            THEN NULL
        WHEN LOWER({{ column_name }}) LIKE '%half-bath%'
            THEN 0.5
        ELSE
            TRY_TO_NUMBER(
                REGEXP_SUBSTR(TRIM(CAST({{ column_name }} AS VARCHAR)), '^[0-9\.]+')
            )
    END
{% endmacro %}