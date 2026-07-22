-- 1. dim_listing: version count matches the snapshot
select
    (select count(*) from gold.dim_listing)     as dim_versions,
    (select count(*) from snapshots.snap_listing) as snap_versions;
-- should be equal

-- 2. THE key proof: honest effective dates on a changed listing
select
    listing_id,
    price_usd,
    effective_from,
    effective_to,
    is_current
from gold.dim_listing
where listing_id = 36906533
order by effective_from;
-- expect:
--   68 | 2025-08-01 | 2025-09-01 | false
--   82 | 2025-09-01 | 9999-12-31 | true
-- ← honest dates now, NOT wall-clock time!

-- 3. Exactly one current version per listing
select listing_id, count(*) as current_versions
from gold.dim_listing
where is_current = true
group by listing_id
having count(*) > 1
limit 10;
-- must return ZERO (a listing can't have 2 current versions)

-- 4. Surrogate keys are unique per version
select listing_sk, count(*)
from gold.dim_listing
group by listing_sk
having count(*) > 1;
-- must return ZERO

-- 5. Same checks for dim_host
-- 5. dim_host: a host whose attributes changed across snapshots
select
    host_id,
    is_superhost,
    host_response_rate_pct,
    effective_from,
    effective_to,
    is_current
from gold.dim_host
where host_id in (
    select host_id from gold.dim_host
    where is_current = false limit 1
)
order by effective_from;

select listing_id, count(*)
from gold.dim_listing
where is_current = true
group by listing_id
having count(*) > 1
limit 10;