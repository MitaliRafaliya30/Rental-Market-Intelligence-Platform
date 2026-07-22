-- Total rows ingested per file per snapshot
select
    'listings' as source_file,
    _snapshot_date,
    count(*) as rows_ingested
from bronze.bronze_listings
group by 1, 2

union all

select
    'calendar',
    _snapshot_date,
    count(*)
from bronze.bronze_calendar
group by 1, 2

union all

select
    'reviews',
    _snapshot_date,
    count(*)
from bronze.bronze_reviews
group by 1, 2

order by _snapshot_date, source_file


-- ------------------------------------ Totals per snapshot
with all_bronze as (
    select 'listings' as f, _snapshot_date as d, count(*) as c
    from bronze.bronze_listings group by 1,2
    union all
    select 'calendar', _snapshot_date, count(*)
    from bronze.bronze_calendar group by 1,2
    union all
    select 'reviews', _snapshot_date, count(*)
    from bronze.bronze_reviews group by 1,2
)
select
    d as snapshot_date,
    sum(case when f = 'listings' then c end) as listings,
    sum(case when f = 'calendar'  then c end) as calendar,
    sum(case when f = 'reviews'   then c end) as reviews,
    sum(c)                                    as total_rows
from all_bronze
group by d
order by d

-- ----------------------- TOTAL ROWS INGESTED ------------------------------

select
    (select count(*) from bronze.bronze_listings)
  + (select count(*) from bronze.bronze_calendar)
  + (select count(*) from bronze.bronze_reviews) as total_rows_ingested


  -- -----------------------------
  -- What actually landed in Silver (after cleaning and dedup)
select 'silver_listings' as tbl, count(*) as rowss from silver.silver_listings
union all select 'silver_calendar', count(*) from silver.silver_calendar
union all select 'silver_reviews',  count(*) from silver.silver_reviews

-- What's in Gold
select 'fact_daily_availability' as tbl, count(*) as rowss from gold.fact_daily_availability
union all select 'fact_listing_snapshot', count(*) from gold.fact_listing_snapshot
union all select 'fact_review',            count(*) from gold.fact_review
union all select 'dim_listing',            count(*) from gold.dim_listing
union all select 'agg_availability_monthly', count(*) from gold.agg_availability_monthly;