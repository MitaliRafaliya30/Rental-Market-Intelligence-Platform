-- 1. Grain: one row per listing per snapshot
select count(*) as fact_rows,
       count(distinct listing_id || '-' || _snapshot_date) as distinct_grain
from gold.fact_listing_snapshot;
-- these must be EQUAL

-- 2. Row count matches silver_listings
select
    (select count(*) from gold.fact_listing_snapshot) as fact_rows,
    (select count(*) from silver.silver_listings)      as silver_rows;
-- must be equal

-- 3. THE CRITICAL JOIN CHECK: does every fact resolve to a dimension?
--    This proves the SCD2 fact join works.
select count(*) as orphaned_facts
from gold.fact_listing_snapshot f
left join gold.dim_listing d on f.listing_sk = d.listing_sk
where d.listing_sk is null;
-- must be ZERO - every fact must find its listing version

-- 4. Same check for host
select count(*) as orphaned_host_fks
from gold.fact_listing_snapshot f
left join gold.dim_host d on f.host_sk = d.host_sk
where d.host_sk is null;
-- must be ZERO

-- 5. Same for location
select count(*) as orphaned_location_fks
from gold.fact_listing_snapshot f
left join gold.dim_location d on f.location_sk = d.location_sk
where d.location_sk is null;
-- must be ZERO

-- 6. THE PAYOFF: verify version alignment on our known listing
--    Does the fact join to the RIGHT price version?
select
    f.listing_id,
    f._snapshot_date,
    d.price_usd,
    d.effective_from,
    d.is_current,
    f.estimated_occupancy_rate
from gold.fact_listing_snapshot f
join gold.dim_listing d on f.listing_sk = d.listing_sk
where f.listing_id = 36906533
order by f._snapshot_date;
-- expect:
--   Aug row -> price 68, effective_from 2025-08-01
--   Sep row -> price 82, effective_from 2025-09-01
-- ← the fact correctly points to each snapshot's version!