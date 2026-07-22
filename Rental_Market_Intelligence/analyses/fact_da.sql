-- 1. Grain: one row per listing per night per snapshot
select count(*) as fact_rows,
       count(distinct listing_id || '-' || calendar_date || '-' || _snapshot_date) as distinct_grain
from gold.fact_daily_availability;
-- must be EQUAL (if fact_rows > grain, the range join double-matched)

-- 2. Row count matches silver_calendar (no rows lost/gained)
select
    (select count(*) from gold.fact_daily_availability) as fact_rows,
    (select count(*) from silver.silver_calendar)        as silver_rows;
-- must be equal (~26M)

-- 3. THE orphan check: every fact resolves to a listing version
select count(*) as orphaned
from gold.fact_daily_availability f
left join gold.dim_listing d on f.listing_sk = d.listing_sk
where d.listing_sk is null;
-- must be ZERO (proves the SCD2 join worked at scale)

-- 4. Both date keys resolve to dim_date
select count(*) as orphaned_dates
from gold.fact_daily_availability f
left join gold.dim_date d1 on f.date_sk = d1.date_sk
left join gold.dim_date d2 on f.snapshot_date_sk = d2.date_sk
where d1.date_sk is null or d2.date_sk is null;
-- must be ZERO (both the night and the capture date exist in dim_date)

-- 5. A real business number: overall availability rate
select
    is_available,
    count(*) as nights,
    round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
from gold.fact_daily_availability
group by is_available;
-- ~44% available / ~56% unavailable (matches your silver_calendar finding)