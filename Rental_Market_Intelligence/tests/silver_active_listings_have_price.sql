/*
    Active listings should have a price.

    Step 2 finding: 'previous scrape' listings are stale carry-forwards
    with 100% null price. 'city scrape' (active) listings had only
    1.27% null - 273 rows. This test asserts that the active-listing
    price coverage stays healthy.

    We allow a small tolerance (up to ~500 nulls) because the 273
    active nulls are real and immaterial. If active nulls spike far
    beyond that, something changed in the source and we want to know.

    The tolerance is PER SNAPSHOT, and the grouping below is what makes
    it so. silver_listings is incremental: it holds one row set per
    monthly scrape, so an ungrouped count(*) would sum every snapshot
    ever ingested and drift past any fixed ceiling purely because time
    passed. It did exactly that on the third snapshot - 273 + 215 + 379
    = 867 - while no individual scrape was anywhere near 500. Grouping
    by _snapshot_date keeps the threshold measuring what it was
    calibrated against: the quality of ONE scrape.

    A singular test passes when it returns ZERO rows.
    Here we return a row only for a snapshot whose bad count exceeds
    the threshold.
*/

{{ config(severity='error') }}

select
    _snapshot_date,
    count(*) as active_null_price_count
from {{ ref('silver_listings') }}
where is_active_listing = true
  and price_usd is null
group by _snapshot_date
having count(*) > 500
