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




-- 1. Row count: Silver must equal Bronze (no filtering)
select
    (select count(*) from silver.silver_calendar) as silver_rows,
    (select count(*) from bronze.bronze_calendar) as bronze_rows;
-- must be equal

-- 2. Boolean converted cleanly - no nulls introduced
select is_available, count(*)
from silver.silver_calendar
group by 1;
-- expect only TRUE and FALSE (no NULL, since bronze had only t/f)

-- 3. Three-part grain: must return ZERO rows
select listing_id, calendar_date, _snapshot_date, count(*)
from silver.silver_calendar
group by 1, 2, 3
having count(*) > 1
limit 10;




-- 1. One row per review (grain check) - must return ZERO rows
select review_id, count(*)
from silver.silver_reviews
group by review_id
having count(*) > 1
limit 10;

-- 2. Dedup worked: silver count = distinct review_ids in bronze
select
    (select count(*) from silver.silver_reviews)              as silver_rows,
    (select count(distinct id) from bronze.bronze_reviews)  as bronze_distinct_ids;
-- these should be EQUAL

-- 3. How many duplicates did we remove?
select
    (select count(*) from bronze.bronze_reviews)              as bronze_total_rows,
    (select count(*) from silver.silver_reviews)              as silver_rows,
    (select count(*) from bronze.bronze_reviews)
      - (select count(*) from silver.silver_reviews)          as duplicates_removed;

-- 4. is_automated flag distribution
select is_automated, count(*)
from silver.silver_reviews
group by 1;



select city_key, count(*) from silver.silver_listings group by 1;


SELECT
    MIN(calendar_date) AS min_date,
    MAX(calendar_date) AS max_date
FROM RENTAL_MARKET_INTELLIGENCE.silver.silver_calendar;



SELECT
    MIN(review_date) AS min_date,
    MAX(review_date) AS max_date
FROM RENTAL_MARKET_INTELLIGENCE.silver.silver_reviews;


