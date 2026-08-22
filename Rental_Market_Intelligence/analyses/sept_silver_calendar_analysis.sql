select
    (select sum(total_nights) from gold.agg_availability_monthly) as agg_total,
    (select count(*) from gold.fact_daily_availability)            as fact_total
-- must be EQUAL

-- Occupancy comparison Aug vs Sep - now possible!
select
    _snapshot_date,
    round(avg(occupancy_rate) * 100, 1) as avg_occupancy_pct
from gold.agg_availability_monthly
group by 1
order by 1

-- Both snapshots present, matching bronze exactly
select _snapshot_date, count(*)
from silver.silver_calendar
group by 1 order by 1;
-- expect: 2025-08-01 | 13,287,103   and   2025-09-01 | 13,204,990

-- Three-part grain still clean at 26.5M rows
select listing_id, calendar_date, _snapshot_date, count(*)
from silver.silver_calendar
group by 1,2,3
having count(*) > 1
limit 5;
-- must return ZERO

select
    (select sum(total_nights) from gold.agg_availability_monthly) as agg_total,
    (select count(*) from gold.fact_daily_availability)            as fact_total;
-- must be EQUAL