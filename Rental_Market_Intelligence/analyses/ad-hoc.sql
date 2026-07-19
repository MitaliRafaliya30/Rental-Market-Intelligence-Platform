{# SELECT
    TRY_TO_NUMBER(REPLACE(REPLACE("price",'$',''),',',''),10,2) AS price
FROM RENTAL_MARKET_INTELLIGENCE.BRONZE.BRONZE_LISTINGS; #}

{# SELECT
    "host_is_superhost" AS raw_value,
    COUNT(*)            AS row_count
FROM BRONZE.BRONZE_LISTINGS
GROUP BY 1; #}

{# SELECT DISTINCT "host_response_rate"
FROM BRONZE.BRONZE_LISTINGS
WHERE "host_response_rate" IS NOT NULL
ORDER BY 1
LIMIT 30; #}

{# SELECT
    "bathrooms_text",
    COUNT(*) AS row_count,
    CASE
        WHEN "bathrooms_text" IS NULL OR TRIM("bathrooms_text") = '' THEN NULL
        WHEN LOWER("bathrooms_text") LIKE '%half-bath%' THEN 0.5
        ELSE TRY_TO_NUMBER(REGEXP_SUBSTR(TRIM("bathrooms_text"), '^[0-9.]+'), 4, 1)
    END AS parsed_bathrooms
FROM BRONZE.BRONZE_LISTINGS
GROUP BY 1
ORDER BY row_count DESC; #}

{# SELECT
    CASE
        WHEN "bathrooms_text" IS NULL OR TRIM("bathrooms_text") = '' THEN NULL
        WHEN LOWER("bathrooms_text") LIKE '%shared%'  THEN 'shared'
        WHEN LOWER("bathrooms_text") LIKE '%private%' THEN 'private'
        ELSE 'unspecified'
    END      AS bathroom_type,
    COUNT(*) AS row_count
FROM BRONZE.BRONZE_LISTINGS
GROUP BY 1
ORDER BY row_count DESC; #}

{# SELECT
    _snapshot_date, count(*)
FROM RENTAL_MARKET_INTELLIGENCE.silver.silver_listings
GROUP BY _snapshot_date
ORDER BY 1;

SELECT COUNT(*) FROM RENTAL_MARKET_INTELLIGENCE.silver.silver_listings; #}


select max(try_to_number("maximum_nights")) from RENTAL_MARKET_INTELLIGENCE.BRONZE.bronze_calendar;