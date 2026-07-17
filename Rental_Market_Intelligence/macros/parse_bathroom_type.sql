{#
    Pulls the sharing status out of bathrooms_text.

    Three states, because the source genuinely has three:
      "1 shared bath"     -> 'shared'
      "1 private bath"    -> 'private'
      "1 bath"            -> 'unspecified'   (source did not say)
      "" (empty)          -> NULL

    Why not a boolean 'is_shared_bathroom':
    about 22,500 listings say only "1 bath". The source never said
    whether it is shared or private. A boolean would force those
    rows into TRUE or FALSE, and both would be inventions.
    'unspecified' records exactly what the source said - nothing more.

    Gold decides what to do with 'unspecified'. That is a judgment,
    and judgments belong in Gold.
#}

{% macro parse_bathroom_type(column_name) %}
    CASE
        WHEN {{ column_name }} IS NULL
             OR TRIM({{ column_name }}) = ''
            THEN NULL
        WHEN LOWER({{ column_name }}) LIKE '%shared%'
            THEN 'shared'
        WHEN LOWER({{ column_name }}) LIKE '%private%'
            THEN 'private'
        ELSE 'unspecified'
    END
{% endmacro %}