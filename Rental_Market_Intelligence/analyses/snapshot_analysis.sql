select count(*) as total_versions, count(distinct listing_id) as distinct_listings
from snapshots.snap_listing;


-- Find a changed listing
select listing_id, count(*) as versions
from snapshots.snap_listing
group by listing_id
having count(*) > 1
order by versions desc
limit 5;


-- THE proof: a price change as two versions
select listing_id, price_usd, dbt_valid_from, dbt_valid_to,
       case when dbt_valid_to is null then 'CURRENT' else 'expired' end as status
from snapshots.snap_listing
where listing_id = 36906533
order by dbt_valid_from;


-- Pick a listing and see ALL its versions with the check columns
select
    listing_id,
    price_usd,
    accommodates,
    room_type,
    dbt_valid_from,
    dbt_valid_to,
    dbt_scd_id
from snapshots.snap_listing
where listing_id = 36906533
order by dbt_valid_from;

-- Find a listing whose price is the SAME in both snapshots
-- (if these also have 2 versions, dbt isn't comparing at all)
with counts as (
    select listing_id, count(*) as v, count(distinct price_usd) as distinct_prices
    from snapshots.snap_listing
    group by listing_id
)
select
    count_if(v > 1 and distinct_prices = 1) as unchanged_but_versioned,
    count_if(v > 1 and distinct_prices > 1) as genuinely_changed
from counts;



-- Should now be roughly: distinct_listings + (number that changed)
-- NOT 2x distinct listings
select count(*) as total_versions, count(distinct listing_id) as distinct_listings
from snapshots.snap_listing;

-- The unchanged-but-versioned count should now be ~0
with counts as (
    select listing_id, count(*) v, count(distinct price_usd) dp
    from snapshots.snap_listing group by listing_id
)
select count_if(v > 1 and dp = 1) as unchanged_but_versioned,
       count_if(v > 1 and dp > 1) as genuinely_changed
from counts;
-- unchanged_but_versioned should be ~0 now (was 10,441)

-- Is snap_host chained correctly, or is it the broken all-current mess?
select host_id, is_superhost, dbt_valid_from, dbt_valid_to,
       case when dbt_valid_to is null then 'CURRENT' else 'expired' end as status
from snapshots.snap_host
where host_id in (
    select host_id from snapshots.snap_host
    group by host_id having count(*) > 1
    limit 1
)
order by dbt_valid_from;


-- 1. A multi-version host should now show one expired + one current
select host_id, is_superhost, dbt_valid_from, dbt_valid_to,
       case when dbt_valid_to is null then 'CURRENT' else 'expired' end as status
from snapshots.snap_host
where host_id in (
    select host_id from snapshots.snap_host
    group by host_id having count(*) > 1 
    limit 1
)
order by dbt_valid_from;
-- expect: one 'expired', one 'CURRENT' - proper chaining

-- 2. Total rows should be only slightly above distinct hosts
select
    count(*) as total_rows,
    count(distinct host_id) as distinct_hosts,
    count(*) - count(distinct host_id) as extra_versions
from snapshots.snap_host;
-- extra_versions = number of hosts who changed (should be modest,
-- NOT ~equal to distinct_hosts)

-- 3. The superhost-change story - hosts who gained/lost status
with counts as (
    select host_id, count(distinct is_superhost) as ds
    from snapshots.snap_host group by host_id
)
select count_if(ds > 1) as superhost_status_changed from counts;
-- these are hosts whose superhost status flipped Aug->Sep